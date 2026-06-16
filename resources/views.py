from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required
from accounts.models import UserProfile
from resources.forms import ResourceRequestForm
from resources.models import ResourceProvision
from resources.naming import (
    ARGO_WORKFLOWS_ROLE_BINDING_NAME,
    ARGO_WORKFLOWS_ROLE_NAME,
    namespace_name_from_sub,
    service_account_name_from_sub,
)
from resources.services.helpers import apply_provision_result
from resources.services.provisioner import provision_user_resources, verify_provision_on_cluster

User = get_user_model()


def _get_user_profile(user):
    return UserProfile.objects.filter(user=user).first()


def _provision_core_resources_verified(provision: ResourceProvision) -> bool:
    required_verify = {"verify_service_account", "verify_role_binding"}
    return all(
        any(
            step.get("key") == key and step.get("verified")
            for step in provision.provision_steps
        )
        for key in required_verify
    )


def _run_provision_request(provision, keycloak_sub):
    provision.keycloak_sub = keycloak_sub
    provision.namespace_name = namespace_name_from_sub(keycloak_sub)
    provision.service_account_name = service_account_name_from_sub(keycloak_sub)
    provision.status = ResourceProvision.Status.PENDING
    provision.error_message = ""
    provision.provision_steps = []
    provision.service_account_token = ""
    provision.save()

    result = provision_user_resources(provision.cluster, keycloak_sub)
    apply_provision_result(provision, result)
    return result


@login_required
def my_resources(request):
    profile = _get_user_profile(request.user)
    provisions = ResourceProvision.objects.filter(user=request.user).select_related(
        "cluster"
    )
    form = ResourceRequestForm()

    can_request = bool(profile and profile.keycloak_sub)
    active_clusters = form.fields["cluster"].queryset.count()

    if request.method == "POST":
        form = ResourceRequestForm(request.POST)
        if not profile or not profile.keycloak_sub:
            messages.error(
                request,
                "Your Keycloak subject (sub) is missing. Sign out and sign in again.",
            )
            return redirect("resources:my_resources")

        if form.is_valid():
            cluster = form.cleaned_data["cluster"]
            existing = ResourceProvision.objects.filter(
                user=request.user,
                cluster=cluster,
            ).first()

            if (
                existing
                and existing.status == ResourceProvision.Status.ACTIVE
                and _provision_core_resources_verified(existing)
                and existing.has_personal_token
            ):
                messages.info(
                    request,
                    f'You already have an active resource on cluster "{cluster.name}". '
                    "Use Verify on cluster to confirm it still exists.",
                )
                return redirect("resources:my_resources")

            provision = existing or ResourceProvision(
                user=request.user,
                cluster=cluster,
            )
            result = _run_provision_request(provision, profile.keycloak_sub)

            if result.success:
                messages.success(
                    request,
                    f'All provisioning steps succeeded on "{cluster.name}".',
                )
            else:
                messages.error(
                    request,
                    f"Provisioning failed: {result.error_message}",
                )
            return redirect("resources:my_resources")

    return render(
        request,
        "resources/my_resources.html",
        {
            "profile": profile,
            "provisions": provisions,
            "form": form,
            "can_request": can_request and active_clusters > 0,
            "active_clusters": active_clusters,
            "planned_namespace": (
                namespace_name_from_sub(profile.keycloak_sub)
                if profile and profile.keycloak_sub
                else None
            ),
            "planned_service_account": (
                service_account_name_from_sub(profile.keycloak_sub)
                if profile and profile.keycloak_sub
                else None
            ),
            "planned_role": ARGO_WORKFLOWS_ROLE_NAME,
            "planned_role_binding": ARGO_WORKFLOWS_ROLE_BINDING_NAME,
        },
    )


@login_required
def verify_provision(request, pk):
    provision = get_object_or_404(
        ResourceProvision,
        pk=pk,
        user=request.user,
    )
    result = verify_provision_on_cluster(provision)
    had_token = provision.has_personal_token
    apply_provision_result(provision, result)

    if result.success:
        if result.service_account_token and not had_token:
            messages.success(
                request,
                "Cluster verification passed and your personal service account token was saved.",
            )
        else:
            messages.success(request, "Cluster verification passed. All resources exist.")
    else:
        missing = any(
            step.get("action") == "not_found" for step in result.steps_as_dicts
        )
        if missing:
            messages.error(
                request,
                "Resources are missing on the cluster (local status updated to Failed). "
                "Click Request resource to re-provision.",
            )
        else:
            messages.error(
                request,
                f"Cluster verification failed: {result.error_message}",
            )
    return redirect("resources:my_resources")


@admin_required
def admin_verify_provision(request, pk):
    provision = get_object_or_404(ResourceProvision, pk=pk)
    result = verify_provision_on_cluster(provision)
    apply_provision_result(provision, result)

    if result.success:
        messages.success(request, "Cluster verification passed for this user.")
    else:
        messages.error(
            request,
            f"Cluster verification failed: {result.error_message}",
        )
    return redirect("core:admin_user_detail", user_id=provision.user_id)


@admin_required
def user_detail(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        raise Http404("User profile not found.")

    provisions = ResourceProvision.objects.filter(user=user).select_related("cluster")
    return render(
        request,
        "resources/admin_user_detail.html",
        {
            "profile_user": user,
            "profile": profile,
            "provisions": provisions,
        },
    )
