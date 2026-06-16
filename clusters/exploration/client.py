"""Kubernetes API client construction from stored cluster credentials."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from django.conf import settings
from kubernetes import client
from kubernetes.client.rest import ApiException

from clusters.models import K8sCluster


class K8sAPIError(Exception):
    """Raised when the Kubernetes API returns an error."""

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class K8sClientBundle:
    """Holds configured kubernetes client API objects."""

    configuration: client.Configuration
    api_client: client.ApiClient
    core_v1: client.CoreV1Api
    request_timeout: float


def _default_request_timeout() -> float:
    return float(getattr(settings, "K8S_API_TIMEOUT_SECONDS", 30))


def _apply_request_timeout(api_client: client.ApiClient, timeout: float) -> None:
    """Ensure all Kubernetes API calls use a default timeout."""
    rest_client = api_client.rest_client
    original_request = rest_client.request

    def request_with_default_timeout(*args, **kwargs):
        if kwargs.get("_request_timeout") is None:
            kwargs["_request_timeout"] = timeout
        return original_request(*args, **kwargs)

    rest_client.request = request_with_default_timeout


def check_api_server_reachable(api_client: client.ApiClient) -> None:
    """Lightweight connectivity check (GET /version)."""
    client.VersionApi(api_client).get_code()


@contextmanager
def k8s_client_for_cluster(
    cluster: K8sCluster,
    *,
    token: str | None = None,
    request_timeout: float | None = None,
) -> Iterator[K8sClientBundle]:
    """Build a kubernetes client from a K8sCluster record."""
    if not cluster.is_active:
        raise K8sAPIError(f'Cluster "{cluster.name}" is inactive.')

    bearer_token = (token if token is not None else cluster.namespace_creator_token).strip()
    if not bearer_token:
        raise K8sAPIError("No bearer token configured for this cluster operation.")

    timeout = request_timeout if request_timeout is not None else _default_request_timeout()

    configuration = client.Configuration()
    configuration.host = cluster.api_server_url.rstrip("/")
    configuration.api_key = {
        "authorization": f"Bearer {bearer_token}",
    }

    ca_cert = cluster.ca_certificate.strip()
    temp_ca_path: str | None = None
    api_client: client.ApiClient | None = None

    try:
        if ca_cert:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".crt",
                delete=False,
            )
            temp_file.write(ca_cert)
            temp_file.flush()
            temp_file.close()
            temp_ca_path = temp_file.name
            configuration.ssl_ca_cert = temp_ca_path
            configuration.verify_ssl = True
        else:
            configuration.verify_ssl = False

        api_client = client.ApiClient(configuration)
        _apply_request_timeout(api_client, timeout)
        bundle = K8sClientBundle(
            configuration=configuration,
            api_client=api_client,
            core_v1=client.CoreV1Api(api_client),
            request_timeout=timeout,
        )
        yield bundle
    finally:
        if api_client is not None:
            api_client.close()
        if temp_ca_path:
            try:
                os.unlink(temp_ca_path)
            except OSError:
                pass


def format_api_exception(exc: ApiException) -> K8sAPIError:
    status = exc.status
    reason = exc.reason or "Unknown error"
    body = (exc.body or "").strip()
    message = f"Kubernetes API error ({status}): {reason}"
    if body:
        message = f"{message} — {body[:300]}"
    return K8sAPIError(message, status=status)


def format_connection_error(exc: Exception, *, cluster_url: str, timeout: float) -> K8sAPIError:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return K8sAPIError(
            f"Timed out reaching Kubernetes API at {cluster_url} after {timeout:g}s.",
        )
    return K8sAPIError(
        f"Could not reach Kubernetes API at {cluster_url}: {message}",
    )
