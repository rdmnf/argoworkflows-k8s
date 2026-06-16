"""Views for exploring a registered Kubernetes cluster."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, render

from accounts.decorators import admin_required
from clusters.exploration.authorization import analyze_cluster_tokens
from clusters.exploration.client import K8sAPIError
from clusters.exploration.namespaces import list_namespaces
from clusters.models import K8sCluster


@admin_required
def cluster_explore(request, pk):
    cluster = get_object_or_404(K8sCluster, pk=pk)
    namespaces = []
    api_error = None
    ssl_mode = "verified" if cluster.ca_certificate.strip() else "unverified"
    token_auth = analyze_cluster_tokens(cluster)

    try:
        namespaces = list_namespaces(cluster)
    except K8sAPIError as exc:
        api_error = str(exc)
        messages.error(request, api_error)

    return render(
        request,
        "clusters/exploration/cluster_explore.html",
        {
            "cluster": cluster,
            "namespaces": namespaces,
            "api_error": api_error,
            "ssl_mode": ssl_mode,
            "namespace_count": len(namespaces),
            "token_auth": token_auth,
            "sample_namespace": cluster.default_namespace or "default",
        },
    )
