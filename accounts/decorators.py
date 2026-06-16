from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from accounts.access import user_has_group


def group_required(group_name, redirect_url="core:dashboard"):
    """Restrict a view to users in the given Keycloak/Django group."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if user_has_group(request.user, group_name):
                return view_func(request, *args, **kwargs)

            messages.error(
                request,
                f"You do not have access. Required group: {group_name}.",
            )
            return redirect(redirect_url)

        return wrapper

    return decorator


def admin_required(view_func):
    """Restrict a view to users in the configured admin group."""
    admin_group = getattr(settings, "KEYCLOAK_ADMIN_GROUP", "admin")
    return group_required(admin_group)(view_func)
