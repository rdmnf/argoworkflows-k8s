"""Kubernetes authorization checks (can-i) for cluster tokens."""

from __future__ import annotations

from dataclasses import dataclass, field

from kubernetes import client
from kubernetes.client.rest import ApiException

from clusters.exploration.client import K8sAPIError, format_api_exception, k8s_client_for_cluster
from clusters.models import K8sCluster

RBAC_API_GROUP = "rbac.authorization.k8s.io"


@dataclass(frozen=True)
class CanICheck:
    key: str
    label: str
    query: str
    allowed: bool
    reason: str = ""


@dataclass
class TokenAuthReport:
    token_label: str
    configured: bool
    error: str = ""
    checks: list[CanICheck] = field(default_factory=list)
    resource_rules: list[str] = field(default_factory=list)
    non_resource_rules: list[str] = field(default_factory=list)


NAMESPACE_TOKEN_CHECKS = (
    {
        "key": "create_namespaces",
        "label": "Create namespaces",
        "verb": "create",
        "resource": "namespaces",
    },
    {
        "key": "get_namespaces",
        "label": "Get namespaces",
        "verb": "get",
        "resource": "namespaces",
    },
    {
        "key": "list_namespaces",
        "label": "List namespaces",
        "verb": "list",
        "resource": "namespaces",
    },
)

SA_TOKEN_CHECKS = (
    {
        "key": "create_serviceaccounts",
        "label": "Create serviceaccounts (in sample namespace)",
        "verb": "create",
        "resource": "serviceaccounts",
        "use_namespace": True,
    },
    {
        "key": "get_serviceaccounts",
        "label": "Get serviceaccounts (in sample namespace)",
        "verb": "get",
        "resource": "serviceaccounts",
        "use_namespace": True,
    },
    {
        "key": "create_secrets",
        "label": "Create secrets (in sample namespace)",
        "verb": "create",
        "resource": "secrets",
        "use_namespace": True,
    },
    {
        "key": "get_secrets",
        "label": "Get secrets (in sample namespace)",
        "verb": "get",
        "resource": "secrets",
        "use_namespace": True,
    },
)

ROLE_BINDING_TOKEN_CHECKS = (
    {
        "key": "create_roles",
        "label": "Create roles (in sample namespace)",
        "verb": "create",
        "resource": "roles",
        "group": RBAC_API_GROUP,
        "use_namespace": True,
    },
    {
        "key": "get_roles",
        "label": "Get roles (in sample namespace)",
        "verb": "get",
        "resource": "roles",
        "group": RBAC_API_GROUP,
        "use_namespace": True,
    },
    {
        "key": "create_rolebindings",
        "label": "Create rolebindings (in sample namespace)",
        "verb": "create",
        "resource": "rolebindings",
        "group": RBAC_API_GROUP,
        "use_namespace": True,
    },
    {
        "key": "get_rolebindings",
        "label": "Get rolebindings (in sample namespace)",
        "verb": "get",
        "resource": "rolebindings",
        "group": RBAC_API_GROUP,
        "use_namespace": True,
    },
)


def _format_resource_rule(rule: client.V1ResourceRule) -> str:
    verbs = ", ".join(rule.verbs or ["*"])
    api_groups = ", ".join(rule.api_groups or ["core"])
    resources = ", ".join(rule.resources or ["*"])
    names = f' ({", ".join(rule.resource_names)})' if rule.resource_names else ""
    return f"{verbs} · {api_groups}/{resources}{names}"


def _format_non_resource_rule(rule: client.V1NonResourceRule) -> str:
    verbs = ", ".join(rule.verbs or ["*"])
    paths = ", ".join(rule.non_resource_urls or ["*"])
    return f"{verbs} · {paths}"


def _run_can_i(
    auth_v1: client.AuthorizationV1Api,
    *,
    verb: str,
    resource: str,
    namespace: str = "",
    group: str = "",
    resource_name: str = "",
) -> tuple[bool, str]:
    resource_type, _, subresource = resource.partition("/")
    resource_attributes = client.V1ResourceAttributes(
        verb=verb,
        group=group or None,
        resource=resource_type,
        subresource=subresource or None,
        namespace=namespace or None,
        name=resource_name or None,
    )
    spec = client.V1SelfSubjectAccessReviewSpec(
        resource_attributes=resource_attributes,
    )

    try:
        response = auth_v1.create_self_subject_access_review(
            body=client.V1SelfSubjectAccessReview(spec=spec),
        )
    except ApiException as exc:
        api_error = format_api_exception(exc)
        return False, str(api_error)

    status = response.status
    allowed = bool(status.allowed) if status else False
    reason = (status.reason if status and status.reason else "") or (
        "Allowed" if allowed else "Not allowed"
    )
    return allowed, reason


def _fetch_rules(
    auth_v1: client.AuthorizationV1Api,
    namespace: str = "",
) -> tuple[list[str], list[str]]:
    spec = client.V1SelfSubjectRulesReviewSpec()
    if namespace:
        spec.namespace = namespace

    try:
        response = auth_v1.create_self_subject_rules_review(
            body=client.V1SelfSubjectRulesReview(spec=spec),
        )
    except ApiException as exc:
        raise format_api_exception(exc) from exc

    status = response.status
    resource_rules = [
        _format_resource_rule(rule) for rule in (status.resource_rules or [])
    ]
    non_resource_rules = [
        _format_non_resource_rule(rule) for rule in (status.non_resource_rules or [])
    ]
    return resource_rules, non_resource_rules


def analyze_token(
    cluster: K8sCluster,
    token: str,
    token_label: str,
    check_specs: tuple[dict, ...],
    *,
    sample_namespace: str = "",
) -> TokenAuthReport:
    if not token.strip():
        return TokenAuthReport(
            token_label=token_label,
            configured=False,
            error="Token is not configured for this cluster.",
        )

    checks: list[CanICheck] = []
    resource_rules: list[str] = []
    non_resource_rules: list[str] = []

    try:
        with k8s_client_for_cluster(cluster, token=token) as bundle:
            auth_v1 = client.AuthorizationV1Api(bundle.api_client)

            for spec in check_specs:
                namespace = sample_namespace if spec.get("use_namespace") else ""
                group = spec.get("group", "")
                resource_name = spec.get("resource_name", "")
                query = f"can-i {spec['verb']} {spec['resource']}"
                if group:
                    query += f".{group}"
                if namespace:
                    query += f" -n {namespace}"
                if resource_name:
                    query += f" --resource-name={resource_name}"

                allowed, reason = _run_can_i(
                    auth_v1,
                    verb=spec["verb"],
                    resource=spec["resource"],
                    namespace=namespace,
                    group=group,
                    resource_name=resource_name,
                )
                checks.append(
                    CanICheck(
                        key=spec["key"],
                        label=spec["label"],
                        query=query,
                        allowed=allowed,
                        reason=reason,
                    )
                )

            cluster_rules, cluster_non_resource = _fetch_rules(auth_v1)
            resource_rules.extend(cluster_rules)
            non_resource_rules.extend(cluster_non_resource)

            if sample_namespace:
                ns_rules, ns_non_resource = _fetch_rules(auth_v1, namespace=sample_namespace)
                for rule in ns_rules:
                    resource_rules.append(f"[ns/{sample_namespace}] {rule}")
                for rule in ns_non_resource:
                    non_resource_rules.append(f"[ns/{sample_namespace}] {rule}")

    except K8sAPIError as exc:
        return TokenAuthReport(
            token_label=token_label,
            configured=True,
            error=str(exc),
            checks=checks,
        )

    return TokenAuthReport(
        token_label=token_label,
        configured=True,
        checks=checks,
        resource_rules=sorted(set(resource_rules)),
        non_resource_rules=sorted(set(non_resource_rules)),
    )


def analyze_cluster_tokens(cluster: K8sCluster) -> dict[str, TokenAuthReport]:
    sample_ns = cluster.default_namespace or "default"
    return {
        "namespace_token": analyze_token(
            cluster,
            cluster.namespace_creator_token,
            "TOKEN FOR CREATING NAMESPACES",
            NAMESPACE_TOKEN_CHECKS,
        ),
        "service_account_token": analyze_token(
            cluster,
            cluster.service_account_creator_token,
            "TOKEN FOR CREATING SERVICE ACCOUNT",
            SA_TOKEN_CHECKS,
            sample_namespace=sample_ns,
        ),
        "role_binding_token": analyze_token(
            cluster,
            cluster.role_binding_creator_token,
            "TOKEN FOR CREATING ROLE AND ROLEBINDING",
            ROLE_BINDING_TOKEN_CHECKS,
            sample_namespace=sample_ns,
        ),
    }
