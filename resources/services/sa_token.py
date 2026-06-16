"""Read personal service account tokens from Kubernetes secrets."""

from __future__ import annotations

import base64
import time

from kubernetes import client
from kubernetes.client.rest import ApiException

from clusters.exploration.client import format_api_exception

SA_TOKEN_SECRET_TYPE = "kubernetes.io/service-account-token"
SA_TOKEN_SECRET_ANNOTATION = "kubernetes.io/service-account.name"


def secret_name_for_service_account(service_account_name: str) -> str:
    base = f"{service_account_name}-token"
    return base[:253]


def _token_from_secret_data(secret: client.V1Secret) -> str:
    token_b64 = (secret.data or {}).get("token")
    if not token_b64:
        return ""
    return base64.b64decode(token_b64).decode("utf-8")


def ensure_service_account_token_secret(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
) -> tuple[str, str, str]:
    """
    Ensure a kubernetes.io/service-account-token Secret exists for the SA.

    Returns (action, secret_name, error) where action is "created" or "already_exists".
    """
    secret_name = secret_name_for_service_account(service_account_name)

    try:
        core_v1.read_namespaced_secret(name=secret_name, namespace=namespace_name)
        return "already_exists", secret_name, ""
    except ApiException as exc:
        if exc.status != 404:
            return "", secret_name, str(format_api_exception(exc))

    body = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=secret_name,
            namespace=namespace_name,
            annotations={
                SA_TOKEN_SECRET_ANNOTATION: service_account_name,
            },
            labels={"awf.io/managed": "true"},
        ),
        type=SA_TOKEN_SECRET_TYPE,
    )
    try:
        core_v1.create_namespaced_secret(namespace=namespace_name, body=body)
    except ApiException as create_exc:
        if create_exc.status == 409:
            return "already_exists", secret_name, ""
        return "", secret_name, str(format_api_exception(create_exc))

    return "created", secret_name, ""


def read_token_from_service_account_secret(
    core_v1: client.CoreV1Api,
    namespace_name: str,
    service_account_name: str,
    *,
    poll_attempts: int = 40,
    poll_interval_seconds: float = 0.75,
) -> tuple[str, str, str]:
    """
    Read the bearer token from the SA token secret, polling until populated.

    Returns (token, detail, error).
    """
    secret_name = secret_name_for_service_account(service_account_name)
    last_error = ""

    for _ in range(poll_attempts):
        try:
            secret = core_v1.read_namespaced_secret(
                name=secret_name,
                namespace=namespace_name,
            )
        except ApiException as exc:
            last_error = str(format_api_exception(exc))
            time.sleep(poll_interval_seconds)
            continue

        token = _token_from_secret_data(secret)
        if token:
            return (
                token,
                (
                    f'Read bearer token from secret "{secret_name}" '
                    f'for service account "{service_account_name}" '
                    f"({len(token)} characters)."
                ),
                "",
            )

        time.sleep(poll_interval_seconds)

    if last_error:
        return "", "", last_error
    return (
        "",
        "",
        (
            f'Timed out waiting for token controller to populate secret "{secret_name}" '
            f'in namespace "{namespace_name}".'
        ),
    )
