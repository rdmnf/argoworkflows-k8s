from django.conf import settings


def provisioning_ui(request):
    return {
        "resource_provision_show_user_token": getattr(
            settings,
            "RESOURCE_PROVISION_SHOW_USER_TOKEN",
            False,
        ),
    }
