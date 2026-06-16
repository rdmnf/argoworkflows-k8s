"""Provision user namespaces and service accounts on Kubernetes clusters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from kubernetes import client
from kubernetes.client.rest import ApiException

from clusters.exploration.client import (
    K8sAPIError,
    check_api_server_reachable,
    format_api_exception,
    format_connection_error,
    k8s_client_for_cluster,
)
from clusters.models import K8sCluster
from resources.argo_rbac import RBAC_API_GROUP, argo_workflows_policy_rules, role_escalation_hint
from resources.models import ResourceProvision
from resources.naming import (
    ARGO_WORKFLOWS_ROLE_BINDING_NAME,
    ARGO_WORKFLOWS_ROLE_NAME,
    namespace_name_from_sub,
    service_account_name_from_sub,
)


@dataclass
class ProvisionStepResult:
    key: str
    label: str
    status: str  # success | failed | skipped
    action: str  # created | already_exists | verified | failed | not_found
    verified: bool
    detail: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProvisionRunResult:
    success: bool
    namespace_name: str
    service_account_name: str
    service_account_token: str = ""
    steps: list[ProvisionStepResult] = field(default_factory=list)
    error_message: str = ""

    @property
    def steps_as_dicts(self) -> list[dict[str, Any]]:
        return [step.to_dict() for step in self.steps]


def _step_from_stored(steps: list[dict[str, Any]], key: str) -> ProvisionStepResult | None:
    for item in steps:
        if item.get("key") == key and item.get("status") == "success":
            return ProvisionStepResult(
                key=item["key"],
                label=item["label"],
                status=item["status"],
                action=item["action"],
                verified=item.get("verified", False),
                detail=item.get("detail", ""),
                error=item.get("error", ""),
            )
    return None


def _step(
    key: str,
    label: str,
    *,
    status: str,
    action: str,
    verified: bool,
    detail: str,
    error: str = "",
) -> ProvisionStepResult:
    return ProvisionStepResult(
        key=key,
        label=label,
        status=status,
        action=action,
        verified=verified,
        detail=detail,
        error=error,
    )


def _verify_namespace(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    *,
    create_step: ProvisionStepResult | None = None,
) -> ProvisionStepResult:
    try:
        ns = core_v1.read_namespace(name=namespace_name)
    except ApiException as exc:
        if exc.status == 403 and create_step and create_step.status == "success":
            return _step(
                "verify_namespace",
                "Verify namespace on cluster",
                status="success",
                action="verified",
                verified=True,
                detail=(
                    f'Namespace "{namespace_name}" {create_step.action.replace("_", " ")}. '
                    "GET namespaces is forbidden for this service account; "
                    "accepted based on create response."
                ),
            )
        if exc.status == 404:
            return _step(
                "verify_namespace",
                "Verify namespace on cluster",
                status="failed",
                action="not_found",
                verified=False,
                detail=f'Namespace "{namespace_name}" was not found on the cluster.',
                error="Resource missing after create attempt.",
            )
        api_error = format_api_exception(exc)
        return _step(
            "verify_namespace",
            "Verify namespace on cluster",
            status="failed",
            action="failed",
            verified=False,
            detail="Could not read namespace from the Kubernetes API.",
            error=str(api_error),
        )

    phase = ns.status.phase if ns.status else "Unknown"
    return _step(
        "verify_namespace",
        "Verify namespace on cluster",
        status="success",
        action="verified",
        verified=True,
        detail=f'Namespace "{namespace_name}" confirmed on cluster (phase: {phase}).',
    )


def _create_namespace(
    core_v1: client.CoreV1Api,
    namespace_name: str,
) -> ProvisionStepResult:
    try:
        core_v1.read_namespace(name=namespace_name)
        return _step(
            "create_namespace",
            "Create namespace",
            status="success",
            action="already_exists",
            verified=False,
            detail=f'Namespace "{namespace_name}" already exists on the cluster.',
        )
    except ApiException as exc:
        if exc.status not in (404, 403):
            api_error = format_api_exception(exc)
            return _step(
                "create_namespace",
                "Create namespace",
                status="failed",
                action="failed",
                verified=False,
                detail="Failed while checking if namespace exists.",
                error=str(api_error),
            )

    body = client.V1Namespace(
        metadata=client.V1ObjectMeta(
            name=namespace_name,
            labels={
                "awf.io/managed": "true",
                "awf.io/provisioned-by": "portal",
            },
        ),
    )
    try:
        created = core_v1.create_namespace(body=body)
    except ApiException as exc:
        if exc.status == 409:
            return _step(
                "create_namespace",
                "Create namespace",
                status="success",
                action="already_exists",
                verified=False,
                detail=f'Namespace "{namespace_name}" already exists (409 conflict).',
            )
        if exc.status == 403:
            api_error = format_api_exception(exc)
            return _step(
                "create_namespace",
                "Create namespace",
                status="failed",
                action="failed",
                verified=False,
                detail=(
                    "Service account lacks permission to create namespaces. "
                    "Grant verbs: create (and optionally get, list) on resource namespaces."
                ),
                error=str(api_error),
            )
        api_error = format_api_exception(exc)
        return _step(
            "create_namespace",
            "Create namespace",
            status="failed",
            action="failed",
            verified=False,
            detail="Kubernetes rejected the namespace create request.",
            error=str(api_error),
        )

    phase = created.status.phase if created.status else "Unknown"
    return _step(
        "create_namespace",
        "Create namespace",
        status="success",
        action="created",
        verified=False,
        detail=f'Namespace "{namespace_name}" created (phase: {phase}).',
    )


def _verify_service_account(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
    *,
    create_step: ProvisionStepResult | None = None,
) -> ProvisionStepResult:
    try:
        sa = core_v1.read_namespaced_service_account(
            name=service_account_name,
            namespace=namespace_name,
        )
    except ApiException as exc:
        if exc.status == 403 and create_step and create_step.status == "success":
            return _step(
                "verify_service_account",
                "Verify service account on cluster",
                status="success",
                action="verified",
                verified=True,
                detail=(
                    f'Service account "{service_account_name}" {create_step.action.replace("_", " ")}. '
                    "GET serviceaccounts is forbidden for this token; "
                    "accepted based on create response."
                ),
            )
        if exc.status == 404:
            return _step(
                "verify_service_account",
                "Verify service account on cluster",
                status="failed",
                action="not_found",
                verified=False,
                detail=(
                    f'Service account "{service_account_name}" was not found '
                    f'in namespace "{namespace_name}".'
                ),
                error="Resource missing after create attempt.",
            )
        api_error = format_api_exception(exc)
        return _step(
            "verify_service_account",
            "Verify service account on cluster",
            status="failed",
            action="failed",
            verified=False,
            detail="Could not read service account from the Kubernetes API.",
            error=str(api_error),
        )

    return _step(
        "verify_service_account",
        "Verify service account on cluster",
        status="success",
        action="verified",
        verified=True,
        detail=(
            f'Service account "{sa.metadata.name}" confirmed in namespace '
            f'"{namespace_name}".'
        ),
    )


def _create_service_account(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
) -> ProvisionStepResult:
    try:
        core_v1.read_namespaced_service_account(
            name=service_account_name,
            namespace=namespace_name,
        )
        return _step(
            "create_service_account",
            "Create service account",
            status="success",
            action="already_exists",
            verified=False,
            detail=(
                f'Service account "{service_account_name}" already exists in '
                f'namespace "{namespace_name}".'
            ),
        )
    except ApiException as exc:
        if exc.status not in (404, 403):
            api_error = format_api_exception(exc)
            return _step(
                "create_service_account",
                "Create service account",
                status="failed",
                action="failed",
                verified=False,
                detail="Failed while checking if service account exists.",
                error=str(api_error),
            )

    body = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=service_account_name,
            namespace=namespace_name,
            labels={"awf.io/managed": "true"},
        ),
    )
    try:
        core_v1.create_namespaced_service_account(namespace=namespace_name, body=body)
    except ApiException as exc:
        if exc.status == 409:
            return _step(
                "create_service_account",
                "Create service account",
                status="success",
                action="already_exists",
                verified=False,
                detail=(
                    f'Service account "{service_account_name}" already exists (409 conflict).'
                ),
            )
        if exc.status == 403:
            api_error = format_api_exception(exc)
            return _step(
                "create_service_account",
                "Create service account",
                status="failed",
                action="failed",
                verified=False,
                detail=(
                    "TOKEN FOR CREATING SERVICE ACCOUNT lacks permission to create "
                    f'service accounts in namespace "{namespace_name}".'
                ),
                error=str(api_error),
            )
        api_error = format_api_exception(exc)
        return _step(
            "create_service_account",
            "Create service account",
            status="failed",
            action="failed",
            verified=False,
            detail="Kubernetes rejected the service account create request.",
            error=str(api_error),
        )

    return _step(
        "create_service_account",
        "Create service account",
        status="success",
        action="created",
        verified=False,
        detail=(
            f'Service account "{service_account_name}" created in namespace '
            f'"{namespace_name}".'
        ),
    )


def _create_token_secret(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
) -> ProvisionStepResult:
    from resources.services.sa_token import ensure_service_account_token_secret

    action, secret_name, error = ensure_service_account_token_secret(
        core_v1,
        namespace_name,
        service_account_name,
    )
    if error:
        return _step(
            "create_token_secret",
            "Create service account token secret",
            status="failed",
            action="failed",
            verified=False,
            detail=(
                f'Could not create secret "{secret_name}" in namespace "{namespace_name}".'
            ),
            error=error,
        )

    if action == "created":
        detail = (
            f'Secret "{secret_name}" (type kubernetes.io/service-account-token) created '
            f'in namespace "{namespace_name}" for service account "{service_account_name}".'
        )
    else:
        detail = (
            f'Secret "{secret_name}" already exists in namespace "{namespace_name}" '
            f'for service account "{service_account_name}".'
        )

    return _step(
        "create_token_secret",
        "Create service account token secret",
        status="success",
        action=action,
        verified=False,
        detail=detail,
    )


def _verify_token_secret(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
    *,
    create_step: ProvisionStepResult | None = None,
) -> ProvisionStepResult:
    from resources.services.sa_token import (
        SA_TOKEN_SECRET_ANNOTATION,
        SA_TOKEN_SECRET_TYPE,
        secret_name_for_service_account,
    )

    secret_name = secret_name_for_service_account(service_account_name)
    try:
        secret = core_v1.read_namespaced_secret(
            name=secret_name,
            namespace=namespace_name,
        )
    except ApiException as exc:
        if exc.status == 403 and create_step and create_step.status == "success":
            return _step(
                "verify_token_secret",
                "Verify service account token secret on cluster",
                status="success",
                action="verified",
                verified=True,
                detail=(
                    f'Secret "{secret_name}" {create_step.action.replace("_", " ")} in '
                    f'namespace "{namespace_name}". GET secrets is forbidden for this token; '
                    "accepted based on create response."
                ),
            )
        if exc.status == 404:
            return _step(
                "verify_token_secret",
                "Verify service account token secret on cluster",
                status="failed",
                action="not_found",
                verified=False,
                detail=(
                    f'Secret "{secret_name}" was not found in namespace "{namespace_name}".'
                ),
                error="Resource missing after create attempt.",
            )
        api_error = format_api_exception(exc)
        return _step(
            "verify_token_secret",
            "Verify service account token secret on cluster",
            status="failed",
            action="failed",
            verified=False,
            detail="Could not read token secret from the Kubernetes API.",
            error=str(api_error),
        )

    annotations = secret.metadata.annotations if secret.metadata else {}
    sa_annotation = (annotations or {}).get(SA_TOKEN_SECRET_ANNOTATION, "")
    secret_type = secret.type or ""
    if secret_type != SA_TOKEN_SECRET_TYPE:
        return _step(
            "verify_token_secret",
            "Verify service account token secret on cluster",
            status="failed",
            action="failed",
            verified=False,
            detail=(
                f'Secret "{secret_name}" has unexpected type "{secret_type}" '
                f'(expected "{SA_TOKEN_SECRET_TYPE}").'
            ),
            error="Invalid secret type.",
        )
    if sa_annotation != service_account_name:
        return _step(
            "verify_token_secret",
            "Verify service account token secret on cluster",
            status="failed",
            action="failed",
            verified=False,
            detail=(
                f'Secret "{secret_name}" is not annotated for service account '
                f'"{service_account_name}".'
            ),
            error="Secret annotation mismatch.",
        )

    return _step(
        "verify_token_secret",
        "Verify service account token secret on cluster",
        status="success",
        action="verified",
        verified=True,
        detail=(
            f'Secret "{secret_name}" exists in namespace "{namespace_name}" '
            f'and is linked to service account "{service_account_name}".'
        ),
    )


def _read_token_from_secret(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
) -> tuple[ProvisionStepResult, str]:
    from resources.services.sa_token import read_token_from_service_account_secret

    token, detail, error = read_token_from_service_account_secret(
        core_v1,
        namespace_name,
        service_account_name,
    )
    if not token:
        return (
            _step(
                "read_token_from_secret",
                "Read bearer token from secret",
                status="failed",
                action="failed",
                verified=False,
                detail="Token secret exists but the bearer token is not available yet.",
                error=error,
            ),
            "",
        )

    return (
        _step(
            "read_token_from_secret",
            "Read bearer token from secret",
            status="success",
            action="read",
            verified=False,
            detail=detail,
        ),
        token,
    )


def _save_token_step(token: str) -> ProvisionStepResult:
    if not token.strip():
        return _step(
            "save_token",
            "Save service account token",
            status="failed",
            action="failed",
            verified=False,
            detail="No bearer token was available to save.",
            error="Missing token.",
        )
    return _step(
        "save_token",
        "Save service account token",
        status="success",
        action="saved",
        verified=False,
        detail=(
            f"Bearer token saved to this provision record ({len(token.strip())} characters) "
            "for Argo Workflow submission."
        ),
    )


def _run_service_account_token_steps(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
) -> tuple[list[ProvisionStepResult], str, str]:
    """
    Ensure the SA token secret exists, verify it, read the bearer token, and record save step.

    Used for both initial provisioning and later verify/issue-token runs.
    """
    steps: list[ProvisionStepResult] = []

    secret_create = _create_token_secret(
        core_v1,
        namespace_name,
        service_account_name,
    )
    steps.append(secret_create)
    if secret_create.status == "failed":
        return steps, "", secret_create.error or secret_create.detail

    secret_verify = _verify_token_secret(
        core_v1,
        namespace_name,
        service_account_name,
        create_step=secret_create,
    )
    steps.append(secret_verify)
    if not secret_verify.verified:
        return steps, "", secret_verify.error or secret_verify.detail

    read_step, token = _read_token_from_secret(
        core_v1,
        namespace_name,
        service_account_name,
    )
    steps.append(read_step)
    if read_step.status == "failed":
        return steps, "", read_step.error or read_step.detail

    save_step = _save_token_step(token)
    steps.append(save_step)
    if save_step.status == "failed":
        return steps, "", save_step.error or save_step.detail

    return steps, token, ""


def _verify_role(
    rbac_v1: client.RbacAuthorizationV1Api,
    namespace_name: str,
    role_name: str,
    *,
    create_step: ProvisionStepResult | None = None,
) -> ProvisionStepResult:
    try:
        role = rbac_v1.read_namespaced_role(name=role_name, namespace=namespace_name)
    except ApiException as exc:
        if exc.status == 403 and create_step and create_step.status == "success":
            return _step(
                "verify_role",
                "Verify Argo Workflows role on cluster",
                status="success",
                action="verified",
                verified=True,
                detail=(
                    f'Role "{role_name}" {create_step.action.replace("_", " ")} in '
                    f'namespace "{namespace_name}". GET roles is forbidden for this token; '
                    "accepted based on create response."
                ),
            )
        if exc.status == 404:
            return _step(
                "verify_role",
                "Verify Argo Workflows role on cluster",
                status="failed",
                action="not_found",
                verified=False,
                detail=(
                    f'Role "{role_name}" was not found in namespace "{namespace_name}".'
                ),
                error="Resource missing after create attempt.",
            )
        api_error = format_api_exception(exc)
        return _step(
            "verify_role",
            "Verify Argo Workflows role on cluster",
            status="failed",
            action="failed",
            verified=False,
            detail="Could not read namespaced role from the Kubernetes API.",
            error=str(api_error),
        )

    rule_count = len(role.rules or [])
    return _step(
        "verify_role",
        "Verify Argo Workflows role on cluster",
        status="success",
        action="verified",
        verified=True,
        detail=(
            f'Role "{role.metadata.name}" confirmed in namespace "{namespace_name}" '
            f"({rule_count} rule{'s' if rule_count != 1 else ''})."
        ),
    )


def _create_role(
    rbac_v1: client.RbacAuthorizationV1Api,
    namespace_name: str,
    role_name: str,
) -> ProvisionStepResult:
    """Create a namespaced Role in the user's namespace."""
    body = client.V1Role(
        metadata=client.V1ObjectMeta(
            name=role_name,
            namespace=namespace_name,
            labels={"awf.io/managed": "true"},
        ),
        rules=argo_workflows_policy_rules(),
    )
    try:
        rbac_v1.create_namespaced_role(namespace=namespace_name, body=body)
    except ApiException as exc:
        if exc.status == 409:
            try:
                rbac_v1.replace_namespaced_role(
                    name=role_name,
                    namespace=namespace_name,
                    body=body,
                )
            except ApiException as replace_exc:
                if replace_exc.status == 403:
                    api_error = format_api_exception(replace_exc)
                    return _step(
                        "create_role",
                        "Create Argo Workflows role",
                        status="failed",
                        action="failed",
                        verified=False,
                        detail=(
                            f'Role "{role_name}" exists but could not be updated with '
                            "the current Argo Workflows policy rules."
                        ),
                        error=f"{api_error}\n\n{role_escalation_hint()}",
                    )
                api_error = format_api_exception(replace_exc)
                return _step(
                    "create_role",
                    "Create Argo Workflows role",
                    status="failed",
                    action="failed",
                    verified=False,
                    detail=(
                        f'Role "{role_name}" exists but could not be updated in '
                        f'namespace "{namespace_name}".'
                    ),
                    error=str(api_error),
                )
            return _step(
                "create_role",
                "Create Argo Workflows role",
                status="success",
                action="updated",
                verified=False,
                detail=(
                    f'Role "{role_name}" updated in namespace "{namespace_name}" '
                    "with current Argo Workflows policy rules."
                ),
            )
        if exc.status == 403:
            api_error = format_api_exception(exc)
            return _step(
                "create_role",
                "Create Argo Workflows role",
                status="failed",
                action="failed",
                verified=False,
                detail=(
                    "Cannot create namespaced Role with Argo Workflows permissions "
                    f'in namespace "{namespace_name}".'
                ),
                error=f"{api_error}\n\n{role_escalation_hint()}",
            )
        api_error = format_api_exception(exc)
        return _step(
            "create_role",
            "Create Argo Workflows role",
            status="failed",
            action="failed",
            verified=False,
            detail="Kubernetes rejected the namespaced role create request.",
            error=str(api_error),
        )

    return _step(
        "create_role",
        "Create Argo Workflows role",
        status="success",
        action="created",
        verified=False,
        detail=f'Role "{role_name}" created in namespace "{namespace_name}".',
    )


def _verify_role_binding(
    rbac_v1: client.RbacAuthorizationV1Api,
    namespace_name: str,
    role_binding_name: str,
    *,
    create_step: ProvisionStepResult | None = None,
) -> ProvisionStepResult:
    try:
        rb = rbac_v1.read_namespaced_role_binding(
            name=role_binding_name,
            namespace=namespace_name,
        )
    except ApiException as exc:
        if exc.status == 403 and create_step and create_step.status == "success":
            return _step(
                "verify_role_binding",
                "Verify Argo Workflows role binding on cluster",
                status="success",
                action="verified",
                verified=True,
                detail=(
                    f'RoleBinding "{role_binding_name}" {create_step.action.replace("_", " ")}. '
                    "GET rolebindings is forbidden for this token; "
                    "accepted based on create response."
                ),
            )
        if exc.status == 404:
            return _step(
                "verify_role_binding",
                "Verify Argo Workflows role binding on cluster",
                status="failed",
                action="not_found",
                verified=False,
                detail=(
                    f'RoleBinding "{role_binding_name}" was not found '
                    f'in namespace "{namespace_name}".'
                ),
                error="Resource missing after create attempt.",
            )
        api_error = format_api_exception(exc)
        return _step(
            "verify_role_binding",
            "Verify Argo Workflows role binding on cluster",
            status="failed",
            action="failed",
            verified=False,
            detail="Could not read role binding from the Kubernetes API.",
            error=str(api_error),
        )

    subject_names = [
        f'{s.kind}/{s.name}' for s in (rb.subjects or []) if s.name
    ]
    return _step(
        "verify_role_binding",
        "Verify Argo Workflows role binding on cluster",
        status="success",
        action="verified",
        verified=True,
        detail=(
            f'RoleBinding "{rb.metadata.name}" confirmed in namespace "{namespace_name}" '
            f'(subjects: {", ".join(subject_names) or "none"}).'
        ),
    )


def _create_role_binding(
    rbac_v1: client.RbacAuthorizationV1Api,
    namespace_name: str,
    role_binding_name: str,
    role_name: str,
    service_account_name: str,
) -> ProvisionStepResult:
    body = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(
            name=role_binding_name,
            namespace=namespace_name,
            labels={"awf.io/managed": "true"},
        ),
        subjects=[
            client.RbacV1Subject(
                kind="ServiceAccount",
                name=service_account_name,
                namespace=namespace_name,
            ),
        ],
        role_ref=client.V1RoleRef(
            api_group=RBAC_API_GROUP,
            kind="Role",
            name=role_name,
        ),
    )
    try:
        rbac_v1.create_namespaced_role_binding(namespace=namespace_name, body=body)
    except ApiException as exc:
        if exc.status == 409:
            return _step(
                "create_role_binding",
                "Create Argo Workflows role binding",
                status="success",
                action="already_exists",
                verified=False,
                detail=(
                    f'RoleBinding "{role_binding_name}" already exists (409 conflict).'
                ),
            )
        if exc.status == 403:
            api_error = format_api_exception(exc)
            return _step(
                "create_role_binding",
                "Create Argo Workflows role binding",
                status="failed",
                action="failed",
                verified=False,
                detail=(
                    "TOKEN FOR CREATING ROLE AND ROLEBINDING lacks permission to create "
                    f'role bindings in namespace "{namespace_name}".'
                ),
                error=str(api_error),
            )
        api_error = format_api_exception(exc)
        return _step(
            "create_role_binding",
            "Create Argo Workflows role binding",
            status="failed",
            action="failed",
            verified=False,
            detail="Kubernetes rejected the role binding create request.",
            error=str(api_error),
        )

    return _step(
        "create_role_binding",
        "Create Argo Workflows role binding",
        status="success",
        action="created",
        verified=False,
        detail=(
            f'RoleBinding "{role_binding_name}" created in namespace "{namespace_name}", '
            f'binding Role "{role_name}" to service account "{service_account_name}".'
        ),
    )


def _connect_step(
    api_client: client.ApiClient,
    cluster: K8sCluster,
    *,
    step_key: str = "connect",
    label: str = "Connect to cluster API",
    token_label: str = "cluster token",
    request_timeout: float = 30,
) -> ProvisionStepResult:
    try:
        check_api_server_reachable(api_client)
    except ApiException as exc:
        api_error = format_api_exception(exc)
        return _step(
            step_key,
            label,
            status="failed",
            action="failed",
            verified=False,
            detail=f"Could not reach API server at {cluster.api_server_url} ({token_label}).",
            error=str(api_error),
        )
    except Exception as exc:
        api_error = format_connection_error(
            exc,
            cluster_url=cluster.api_server_url,
            timeout=request_timeout,
        )
        return _step(
            step_key,
            label,
            status="failed",
            action="failed",
            verified=False,
            detail=f"Could not reach API server at {cluster.api_server_url} ({token_label}).",
            error=str(api_error),
        )

    return _step(
        step_key,
        label,
        status="success",
        action="verified",
        verified=True,
        detail=f"API server reachable at {cluster.api_server_url} ({token_label}).",
    )


def _run_provision_steps(
    cluster: K8sCluster,
    namespace_name: str,
    service_account_name: str,
    *,
    create_resources: bool,
    existing_token: str = "",
    namespace_only: bool = False,
    create_user_token: bool = False,
    prior_steps: list[dict[str, Any]] | None = None,
) -> ProvisionRunResult:
    steps: list[ProvisionStepResult] = []
    token = existing_token if not create_resources else ""
    ns_create_step: ProvisionStepResult | None = None
    sa_create_step: ProvisionStepResult | None = None
    role_create_step: ProvisionStepResult | None = None
    rb_create_step: ProvisionStepResult | None = None
    role_name = ARGO_WORKFLOWS_ROLE_NAME
    role_binding_name = ARGO_WORKFLOWS_ROLE_BINDING_NAME

    try:
        with k8s_client_for_cluster(
            cluster,
            token=cluster.namespace_creator_token,
        ) as ns_bundle:
            if create_resources:
                connect = _connect_step(
                    ns_bundle.api_client,
                    cluster,
                    step_key="connect_namespace_token",
                    label="Connect (namespace creator token)",
                    token_label="TOKEN FOR CREATING NAMESPACES",
                    request_timeout=ns_bundle.request_timeout,
                )
                steps.append(connect)
                if not connect.verified:
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=connect.error or connect.detail,
                    )

            if create_resources:
                ns_create_step = _create_namespace(ns_bundle.core_v1, namespace_name)
                steps.append(ns_create_step)
                if ns_create_step.status == "failed":
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=ns_create_step.error or ns_create_step.detail,
                    )

            ns_verify = _verify_namespace(
                ns_bundle.core_v1,
                namespace_name,
                create_step=ns_create_step if create_resources else None,
            )
            steps.append(ns_verify)
            if not ns_verify.verified:
                return ProvisionRunResult(
                    success=False,
                    namespace_name=namespace_name,
                    service_account_name=service_account_name,
                    steps=steps,
                    error_message=ns_verify.error or ns_verify.detail,
                )

        if namespace_only:
            return ProvisionRunResult(
                success=True,
                namespace_name=namespace_name,
                service_account_name=service_account_name,
                steps=steps,
            )

        sa_creator_token = cluster.service_account_creator_token.strip()
        if not sa_creator_token:
            step = _step(
                "connect_service_account_token",
                "Connect (service account creator token)",
                status="failed",
                action="failed",
                verified=False,
                detail="TOKEN FOR CREATING SERVICE ACCOUNT is not configured on this cluster.",
                error="Add the service account creator token in cluster settings.",
            )
            steps.append(step)
            return ProvisionRunResult(
                success=False,
                namespace_name=namespace_name,
                service_account_name=service_account_name,
                steps=steps,
                error_message=step.error or step.detail,
            )

        with k8s_client_for_cluster(
            cluster,
            token=sa_creator_token,
        ) as sa_bundle:
            if create_resources:
                sa_connect = _connect_step(
                    sa_bundle.api_client,
                    cluster,
                    step_key="connect_service_account_token",
                    label="Connect (service account creator token)",
                    token_label="TOKEN FOR CREATING SERVICE ACCOUNT",
                    request_timeout=sa_bundle.request_timeout,
                )
                steps.append(sa_connect)
                if not sa_connect.verified:
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=sa_connect.error or sa_connect.detail,
                    )

            if create_resources:
                sa_create_step = _create_service_account(
                    sa_bundle.core_v1,
                    namespace_name,
                    service_account_name,
                )
                steps.append(sa_create_step)
                if sa_create_step.status == "failed":
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=sa_create_step.error or sa_create_step.detail,
                    )

            sa_verify = _verify_service_account(
                sa_bundle.core_v1,
                namespace_name,
                service_account_name,
                create_step=sa_create_step if create_resources else None,
            )
            steps.append(sa_verify)
            if not sa_verify.verified:
                return ProvisionRunResult(
                    success=False,
                    namespace_name=namespace_name,
                    service_account_name=service_account_name,
                    steps=steps,
                    error_message=sa_verify.error or sa_verify.detail,
                )

        rb_creator_token = cluster.role_binding_creator_token.strip()
        if not rb_creator_token:
            step = _step(
                "connect_role_binding_token",
                "Connect (role and role binding creator token)",
                status="failed",
                action="failed",
                verified=False,
                detail=(
                    "TOKEN FOR CREATING ROLE AND ROLEBINDING is not configured on this cluster."
                ),
                error="Add the role and role binding creator token in cluster settings.",
            )
            steps.append(step)
            return ProvisionRunResult(
                success=False,
                namespace_name=namespace_name,
                service_account_name=service_account_name,
                steps=steps,
                error_message=step.error or step.detail,
            )

        with k8s_client_for_cluster(
            cluster,
            token=rb_creator_token,
        ) as rb_bundle:
            rbac_v1 = client.RbacAuthorizationV1Api(rb_bundle.api_client)
            if create_resources:
                rb_connect = _connect_step(
                    rb_bundle.api_client,
                    cluster,
                    step_key="connect_role_binding_token",
                    label="Connect (role and role binding creator token)",
                    token_label="TOKEN FOR CREATING ROLE AND ROLEBINDING",
                    request_timeout=rb_bundle.request_timeout,
                )
                steps.append(rb_connect)
                if not rb_connect.verified:
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=rb_connect.error or rb_connect.detail,
                    )

            if create_resources:
                role_create_step = _create_role(
                    rbac_v1,
                    namespace_name,
                    role_name,
                )
                steps.append(role_create_step)
                if role_create_step.status == "failed":
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=role_create_step.error or role_create_step.detail,
                    )

            role_verify = _verify_role(
                rbac_v1,
                namespace_name,
                role_name,
                create_step=role_create_step if create_resources else None,
            )
            steps.append(role_verify)
            if not role_verify.verified:
                return ProvisionRunResult(
                    success=False,
                    namespace_name=namespace_name,
                    service_account_name=service_account_name,
                    steps=steps,
                    error_message=role_verify.error or role_verify.detail,
                )

            if create_resources:
                rb_create_step = _create_role_binding(
                    rbac_v1,
                    namespace_name,
                    role_binding_name,
                    role_name,
                    service_account_name,
                )
                steps.append(rb_create_step)
                if rb_create_step.status == "failed":
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=rb_create_step.error or rb_create_step.detail,
                    )

            rb_verify = _verify_role_binding(
                rbac_v1,
                namespace_name,
                role_binding_name,
                create_step=rb_create_step if create_resources else None,
            )
            steps.append(rb_verify)
            if not rb_verify.verified:
                return ProvisionRunResult(
                    success=False,
                    namespace_name=namespace_name,
                    service_account_name=service_account_name,
                    steps=steps,
                    error_message=rb_verify.error or rb_verify.detail,
                )

        if create_user_token:
            with k8s_client_for_cluster(
                cluster,
                token=sa_creator_token,
            ) as sa_bundle:
                token_steps, issued_token, token_error = _run_service_account_token_steps(
                    sa_bundle.core_v1,
                    namespace_name,
                    service_account_name,
                )
                steps.extend(token_steps)
                if token_error:
                    return ProvisionRunResult(
                        success=False,
                        namespace_name=namespace_name,
                        service_account_name=service_account_name,
                        steps=steps,
                        error_message=token_error,
                    )
                token = issued_token
        elif existing_token:
            save_step = _save_token_step(existing_token)
            steps.append(save_step)

    except K8sAPIError as exc:
        steps.append(
            _step(
                "connect",
                "Connect to cluster API",
                status="failed",
                action="failed",
                verified=False,
                detail="Could not connect to the Kubernetes API.",
                error=str(exc),
            )
        )
        return ProvisionRunResult(
            success=False,
            namespace_name=namespace_name,
            service_account_name=service_account_name,
            steps=steps,
            error_message=str(exc),
        )
    except Exception as exc:
        from django.conf import settings

        timeout = float(getattr(settings, "K8S_API_TIMEOUT_SECONDS", 30))
        api_error = format_connection_error(
            exc,
            cluster_url=cluster.api_server_url,
            timeout=timeout,
        )
        steps.append(
            _step(
                "connect",
                "Connect to cluster API",
                status="failed",
                action="failed",
                verified=False,
                detail="Could not connect to the Kubernetes API.",
                error=str(api_error),
            )
        )
        return ProvisionRunResult(
            success=False,
            namespace_name=namespace_name,
            service_account_name=service_account_name,
            steps=steps,
            error_message=str(api_error),
        )

    if create_resources:
        required_keys = {"connect_namespace_token", "verify_namespace"}
        if not namespace_only:
            required_keys.update(
                {
                    "connect_service_account_token",
                    "create_service_account",
                    "verify_service_account",
                    "connect_role_binding_token",
                    "create_role",
                    "verify_role",
                    "create_role_binding",
                    "verify_role_binding",
                },
            )
    else:
        required_keys = {"verify_namespace"}
        if not namespace_only:
            required_keys.update(
                {
                    "verify_service_account",
                    "verify_role",
                    "verify_role_binding",
                },
            )
    if create_user_token and not namespace_only:
        required_keys.update(
            {
                "create_token_secret",
                "verify_token_secret",
                "read_token_from_secret",
                "save_token",
            },
        )
    elif existing_token:
        required_keys.add("save_token")

    required_verified = [s for s in steps if s.key in required_keys]
    success = bool(required_verified) and all(
        s.verified for s in required_verified if s.key.startswith("verify_") or s.key.startswith("connect_")
    )
    # create_* and other required non-verify steps must have succeeded when present
    for step in steps:
        if step.key not in required_keys:
            continue
        if step.key.startswith("create_") and step.status != "success":
            success = False
        if step.key in {"read_token_from_secret", "save_token"} and step.status != "success":
            success = False
    if create_user_token and not namespace_only:
        success = success and bool(token)

    return ProvisionRunResult(
        success=success,
        namespace_name=namespace_name,
        service_account_name=service_account_name,
        service_account_token=token,
        steps=steps,
    )


def provision_user_resources(
    cluster: K8sCluster,
    keycloak_sub: str,
    *,
    namespace_only: bool | None = None,
    create_user_token: bool | None = None,
) -> ProvisionRunResult:
    """Create and verify namespace, service account, Argo RBAC, and token on the cluster."""
    from django.conf import settings

    if namespace_only is None:
        namespace_only = getattr(settings, "RESOURCE_PROVISION_NAMESPACE_ONLY", False)
    if create_user_token is None:
        create_user_token = getattr(settings, "RESOURCE_PROVISION_CREATE_USER_TOKEN", True)

    namespace_name = namespace_name_from_sub(keycloak_sub)
    service_account_name = service_account_name_from_sub(keycloak_sub)
    return _run_provision_steps(
        cluster,
        namespace_name,
        service_account_name,
        create_resources=True,
        namespace_only=namespace_only,
        create_user_token=create_user_token,
    )


def verify_provision_on_cluster(provision: ResourceProvision) -> ProvisionRunResult:
    """Re-check whether recorded resources actually exist on the cluster."""
    from django.conf import settings

    namespace_only = getattr(settings, "RESOURCE_PROVISION_NAMESPACE_ONLY", False)
    create_user_token = getattr(settings, "RESOURCE_PROVISION_CREATE_USER_TOKEN", True)
    return _run_provision_steps(
        provision.cluster,
        provision.namespace_name,
        provision.service_account_name,
        create_resources=False,
        existing_token=provision.service_account_token,
        namespace_only=namespace_only,
        create_user_token=create_user_token,
        prior_steps=provision.provision_steps,
    )
