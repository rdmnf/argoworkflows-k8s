from django.db import transaction

from workflows.models import WorkflowRun, WorkflowScript
from workflows.services.submitter import SubmitResult, submit_workflow_to_cluster


def record_workflow_run(workflow: WorkflowScript, result: SubmitResult) -> WorkflowRun:
    with transaction.atomic():
        return WorkflowRun.objects.create(
            workflow=workflow,
            user=workflow.user,
            cluster=workflow.cluster,
            status=(
                WorkflowRun.Status.SUBMITTED
                if result.success
                else WorkflowRun.Status.FAILED
            ),
            namespace_name=result.namespace_name or workflow.namespace_name,
            service_account_name=result.service_account_name,
            k8s_workflow_name=result.k8s_workflow_name,
            error_message=result.error_message,
        )
