"""Submit stored Argo Workflow manifests to a user's namespace on Kubernetes."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import yaml
from kubernetes import client
from kubernetes.client.rest import ApiException

from clusters.exploration.client import (
    K8sAPIError,
    format_api_exception,
    format_connection_error,
    k8s_client_for_cluster,
)
from resources.models import ResourceProvision
from workflows.models import WorkflowScript


@dataclass
class SubmitResult:
    success: bool
    k8s_workflow_name: str = ""
    namespace_name: str = ""
    service_account_name: str = ""
    error_message: str = ""


def get_active_provision(user, cluster) -> ResourceProvision | None:
    return ResourceProvision.objects.filter(
        user=user,
        cluster=cluster,
        status=ResourceProvision.Status.ACTIVE,
    ).first()


def get_user_service_account_token(provision: ResourceProvision) -> tuple[str, str]:
    """Return the user's personal SA bearer token stored on their provision."""
    token = provision.service_account_token.strip()
    if token:
        return token, ""
    return (
        "",
        "No personal service account token is stored for this cluster. "
        "Re-request your resources under My resources so a token secret is created and "
        f'the bearer token is saved for service account "{provision.service_account_name}" '
        f'in namespace "{provision.namespace_name}".',
    )


def can_submit_workflow(workflow: WorkflowScript) -> tuple[bool, str, ResourceProvision | None]:
    provision = get_active_provision(workflow.user, workflow.cluster)
    if not provision:
        return False, "No active resource provision on this cluster.", None
    if not workflow.namespace_name.strip():
        return False, "Workflow namespace is not set.", provision
    if not provision.service_account_name.strip():
        return False, "Service account name is missing on your provision.", provision
    token, token_error = get_user_service_account_token(provision)
    if not token:
        return False, token_error, provision
    return True, "", provision


def _prepare_workflow_body(
    workflow: WorkflowScript,
    provision: ResourceProvision,
) -> dict:
    parsed = yaml.safe_load(workflow.manifest)
    if not isinstance(parsed, dict):
        raise ValueError("Workflow manifest must be a YAML mapping.")

    body = deepcopy(parsed)
    metadata = body.setdefault("metadata", {})
    metadata["namespace"] = provision.namespace_name

    spec = body.setdefault("spec", {})
    if not spec.get("serviceAccountName"):
        spec["serviceAccountName"] = provision.service_account_name

    return body


def submit_workflow_to_cluster(workflow: WorkflowScript) -> SubmitResult:
    can_submit, block_reason, provision = can_submit_workflow(workflow)
    if not can_submit or not provision:
        return SubmitResult(success=False, error_message=block_reason)

    namespace_name = provision.namespace_name
    token, token_error = get_user_service_account_token(provision)
    if not token:
        return SubmitResult(success=False, error_message=token_error)

    try:
        body = _prepare_workflow_body(workflow, provision)
    except ValueError as exc:
        return SubmitResult(success=False, error_message=str(exc))

    try:
        with k8s_client_for_cluster(workflow.cluster, token=token) as bundle:
            custom_api = client.CustomObjectsApi(bundle.api_client)
            response = custom_api.create_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace_name,
                plural="workflows",
                body=body,
            )
    except ApiException as exc:
        api_error = format_api_exception(exc)
        return SubmitResult(
            success=False,
            namespace_name=namespace_name,
            service_account_name=provision.service_account_name,
            error_message=str(api_error),
        )
    except K8sAPIError as exc:
        return SubmitResult(
            success=False,
            namespace_name=namespace_name,
            service_account_name=provision.service_account_name,
            error_message=str(exc),
        )
    except Exception as exc:
        from django.conf import settings

        timeout = float(getattr(settings, "K8S_API_TIMEOUT_SECONDS", 30))
        api_error = format_connection_error(
            exc,
            cluster_url=workflow.cluster.api_server_url,
            timeout=timeout,
        )
        return SubmitResult(
            success=False,
            namespace_name=namespace_name,
            service_account_name=provision.service_account_name,
            error_message=str(api_error),
        )

    metadata = response.get("metadata") or {}
    spec = response.get("spec") or {}
    return SubmitResult(
        success=True,
        k8s_workflow_name=metadata.get("name", ""),
        namespace_name=metadata.get("namespace", namespace_name),
        service_account_name=spec.get("serviceAccountName", provision.service_account_name),
    )
