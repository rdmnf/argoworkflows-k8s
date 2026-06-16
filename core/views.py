from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import admin_required
from accounts.models import UserProfile
from clusters.models import K8sCluster
from workflows.models import WorkflowScript

User = get_user_model()


def home(request):
    return render(request, "core/home.html")


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    return render(
        request,
        "core/dashboard.html",
        {"profile": profile},
    )


@login_required
def profile(request):
    profile = getattr(request.user, "profile", None)
    return render(
        request,
        "core/profile.html",
        {"profile": profile},
    )


@admin_required
def admin_control(request):
    profiles = (
        UserProfile.objects.select_related("user")
        .prefetch_related("user__resource_provisions")
        .order_by("-updated_at")
    )
    return render(
        request,
        "core/admin_control.html",
        {
            "profiles": profiles,
            "total_users": User.objects.count(),
            "cluster_count": K8sCluster.objects.count(),
            "workflow_count": WorkflowScript.objects.count(),
        },
    )
