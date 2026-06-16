"""Helpers for applying provisioning results to database records."""

from resources.models import ResourceProvision
from resources.services.provisioner import ProvisionRunResult


def apply_provision_result(
    provision: ResourceProvision,
    result: ProvisionRunResult,
) -> ResourceProvision:
    provision.provision_steps = result.steps_as_dicts
    provision.namespace_name = result.namespace_name
    provision.service_account_name = result.service_account_name
    provision.error_message = result.error_message

    if result.success:
        provision.status = ResourceProvision.Status.ACTIVE
        if result.service_account_token:
            provision.service_account_token = result.service_account_token
    else:
        provision.status = ResourceProvision.Status.FAILED

    provision.save()
    return provision
