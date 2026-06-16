import re

MAX_K8S_NAME_LENGTH = 63


def sanitize_k8s_name(value: str, *, max_length: int = MAX_K8S_NAME_LENGTH) -> str:
    """Convert a Keycloak subject into a valid Kubernetes name (letters and digits only)."""
    name = re.sub(r"[^a-z0-9]", "", value.lower().strip())

    if not name:
        name = "user"

    return name[:max_length]


def namespace_name_from_sub(keycloak_sub: str) -> str:
    return sanitize_k8s_name(keycloak_sub)


ARGO_WORKFLOWS_ROLE_NAME = "argo-workflows-role"
ARGO_WORKFLOWS_ROLE_BINDING_NAME = "argo-workflows-rb"
USER_WORKFLOW_SERVICE_ACCOUNT_NAME = "workflow-runner"


def service_account_name_from_sub(_keycloak_sub: str) -> str:
    """Return the standard service account name used in every user namespace."""
    return USER_WORKFLOW_SERVICE_ACCOUNT_NAME
