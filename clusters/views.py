from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required
from clusters.forms import K8sClusterForm
from clusters.models import K8sCluster


@admin_required
def cluster_list(request):
    clusters = K8sCluster.objects.select_related("created_by").order_by("name")
    form = K8sClusterForm()

    if request.method == "POST":
        form = K8sClusterForm(request.POST)
        if form.is_valid():
            cluster = form.save(commit=False)
            cluster.created_by = request.user
            cluster.save()
            messages.success(request, f'Cluster "{cluster.name}" added successfully.')
            return redirect("clusters:cluster_list")

    return render(
        request,
        "clusters/cluster_list.html",
        {
            "clusters": clusters,
            "form": form,
        },
    )


@admin_required
def cluster_edit(request, pk):
    cluster = get_object_or_404(K8sCluster, pk=pk)

    if request.method == "POST":
        form = K8sClusterForm(request.POST, instance=cluster)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cluster "{cluster.name}" updated successfully.')
            return redirect("clusters:cluster_list")
    else:
        form = K8sClusterForm(instance=cluster)

    return render(
        request,
        "clusters/cluster_form.html",
        {
            "form": form,
            "cluster": cluster,
            "is_edit": True,
        },
    )


@admin_required
def cluster_delete(request, pk):
    cluster = get_object_or_404(K8sCluster, pk=pk)

    if request.method == "POST":
        name = cluster.name
        cluster.delete()
        messages.success(request, f'Cluster "{name}" deleted.')
        return redirect("clusters:cluster_list")

    return render(
        request,
        "clusters/cluster_confirm_delete.html",
        {"cluster": cluster},
    )
