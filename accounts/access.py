from django.conf import settings


def normalize_group_name(group: str) -> str:
    return group.strip().strip("/")


def django_group_name_for(group: str) -> str:
    name = normalize_group_name(group)
    if not name:
        return group[:150]
    return name.replace("/", " - ")[:150]


def user_has_group(user, group_name: str) -> bool:
    """Check Django groups and synced Keycloak groups on the user profile."""
    if not user.is_authenticated:
        return False

    target = normalize_group_name(group_name)
    django_name = django_group_name_for(group_name)

    if user.groups.filter(name__in=[django_name, target]).exists():
        return True

    profile = getattr(user, "profile", None)
    if not profile or not profile.keycloak_groups:
        return False

    for keycloak_group in profile.keycloak_groups:
        normalized = normalize_group_name(keycloak_group)
        if normalized == target:
            return True

    return False


def user_is_admin(user) -> bool:
    admin_group = getattr(settings, "KEYCLOAK_ADMIN_GROUP", "admin")
    return user_has_group(user, admin_group)
