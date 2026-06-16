"""Namespace queries against a Kubernetes cluster."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kubernetes.client.rest import ApiException

from clusters.exploration.client import K8sAPIError, format_api_exception, k8s_client_for_cluster
from clusters.models import K8sCluster


@dataclass(frozen=True)
class NamespaceSummary:
    name: str
    status: str
    created_at: datetime | None
    labels: dict[str, str]


def list_namespaces(cluster: K8sCluster) -> list[NamespaceSummary]:
    """Return all namespaces visible to the cluster service account."""
    try:
        with k8s_client_for_cluster(cluster) as bundle:
            response = bundle.core_v1.list_namespace()
    except ApiException as exc:
        raise format_api_exception(exc) from exc
    except K8sAPIError:
        raise
    except Exception as exc:
        raise K8sAPIError(f"Failed to connect to cluster: {exc}") from exc

    namespaces: list[NamespaceSummary] = []
    for item in response.items:
        metadata = item.metadata
        status = item.status
        namespaces.append(
            NamespaceSummary(
                name=metadata.name if metadata else "—",
                status=status.phase if status and status.phase else "Unknown",
                created_at=metadata.creation_timestamp if metadata else None,
                labels=dict(metadata.labels or {}) if metadata else {},
            )
        )

    return sorted(namespaces, key=lambda ns: ns.name.lower())
