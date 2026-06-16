from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required
from accounts.models import UserProfile
from workflows.forms import WorkflowScriptForm
from workflows.models import WorkflowRun, WorkflowScript
from workflows.services.helpers import record_workflow_run
from workflows.services.submitter import can_submit_workflow, submit_workflow_to_cluster


def _user_workflows(user):
    return WorkflowScript.objects.filter(user=user).select_related("cluster")


@login_required
def my_workflows(request):
    workflows = _user_workflows(request.user)
    form = WorkflowScriptForm(user=request.user)

    if request.method == "POST":
        form = WorkflowScriptForm(request.POST, user=request.user)
        if form.is_valid():
            workflow = form.save()
            messages.success(request, f'Workflow "{workflow.subject}" saved.')
            return redirect("workflows:my_workflows")

    return render(
        request,
        "workflows/my_workflows.html",
        {
            "workflows": workflows,
            "form": form,
        },
    )


@login_required
def workflow_edit(request, pk):
    workflow = get_object_or_404(WorkflowScript, pk=pk, user=request.user)
    form = WorkflowScriptForm(
        request.POST or None,
        instance=workflow,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Workflow "{workflow.subject}" updated.')
        return redirect("workflows:my_workflows")

    return render(
        request,
        "workflows/workflow_form.html",
        {
            "form": form,
            "workflow": workflow,
            "is_create": False,
        },
    )


@login_required
def workflow_detail(request, pk):
    workflow = get_object_or_404(
        WorkflowScript.objects.select_related("cluster").prefetch_related("runs"),
        pk=pk,
        user=request.user,
    )
    can_submit, submit_block_reason, provision = can_submit_workflow(workflow)
    return render(
        request,
        "workflows/workflow_detail.html",
        {
            "workflow": workflow,
            "runs": workflow.runs.all()[:20],
            "provision": provision,
            "can_edit": True,
            "can_submit": can_submit,
            "submit_block_reason": submit_block_reason,
        },
    )


@login_required
def workflow_submit(request, pk):
    if request.method != "POST":
        return redirect("workflows:workflow_detail", pk=pk)

    workflow = get_object_or_404(WorkflowScript, pk=pk, user=request.user)

    can_submit, submit_block_reason, _provision = can_submit_workflow(workflow)
    if not can_submit:
        messages.error(request, submit_block_reason)
        return redirect("workflows:workflow_detail", pk=workflow.pk)

    result = submit_workflow_to_cluster(workflow)
    record_workflow_run(workflow, result)

    if result.success:
        messages.success(
            request,
            f'Workflow submitted to namespace "{result.namespace_name}" as '
            f'"{result.k8s_workflow_name}".',
        )
    else:
        messages.error(
            request,
            f"Workflow submission failed: {result.error_message}",
        )
    return redirect("workflows:workflow_detail", pk=workflow.pk)


@login_required
def workflow_delete(request, pk):
    workflow = get_object_or_404(WorkflowScript, pk=pk, user=request.user)

    if request.method == "POST":
        subject = workflow.subject
        workflow.delete()
        messages.success(request, f'Workflow "{subject}" deleted.')
        return redirect("workflows:my_workflows")

    return render(
        request,
        "workflows/workflow_confirm_delete.html",
        {"workflow": workflow},
    )


@admin_required
def admin_workflows(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    workflows = (
        WorkflowScript.objects.select_related("user", "cluster")
        .prefetch_related("runs")
        .order_by("-updated_at")
    )
    if query:
        workflows = workflows.filter(
            Q(subject__icontains=query)
            | Q(description__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
            | Q(namespace_name__icontains=query)
        )
    if status in WorkflowScript.Status.values:
        workflows = workflows.filter(status=status)

    return render(
        request,
        "workflows/admin_workflows.html",
        {
            "workflows": workflows,
            "query": query,
            "status_filter": status,
            "status_choices": WorkflowScript.Status.choices,
            "total_count": WorkflowScript.objects.count(),
            "draft_count": WorkflowScript.objects.filter(
                status=WorkflowScript.Status.DRAFT,
            ).count(),
            "ready_count": WorkflowScript.objects.filter(
                status=WorkflowScript.Status.READY,
            ).count(),
            "submission_count": WorkflowRun.objects.filter(
                status=WorkflowRun.Status.SUBMITTED,
            ).count(),
        },
    )


@admin_required
def admin_workflow_detail(request, pk):
    workflow = get_object_or_404(
        WorkflowScript.objects.select_related("user", "cluster").prefetch_related("runs"),
        pk=pk,
    )
    profile = UserProfile.objects.filter(user=workflow.user).first()
    return render(
        request,
        "workflows/workflow_detail.html",
        {
            "workflow": workflow,
            "runs": workflow.runs.all()[:20],
            "profile": profile,
            "can_edit": False,
            "admin_view": True,
        },
    )
