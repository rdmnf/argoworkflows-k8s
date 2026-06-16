from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import resolve_url
from django.utils import timezone


def extract_groups(claims: dict | None) -> list[str]:
    """Read Keycloak group membership from OIDC userinfo/id token claims."""
    if not claims:
        return []

    claim_name = getattr(settings, "KEYCLOAK_GROUPS_CLAIM", "groups")
    raw = claims.get(claim_name, [])

    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]

    groups: list[str] = []
    for item in raw:
        if isinstance(item, str):
            name = item.strip()
            if name:
                groups.append(name)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("path") or item.get("id")
            if name:
                groups.append(str(name).strip())

    return sorted(set(groups))


def django_group_name(keycloak_group: str) -> str:
    """Map a Keycloak group path to a Django auth Group name."""
    name = keycloak_group.strip().strip("/")
    if not name:
        return keycloak_group[:150]
    return name.replace("/", " - ")[:150]


def generate_username(email, claims=None) -> str:
    """Build a stable Django username from Keycloak claims.

    mozilla-django-oidc calls this as generate_username(email, claims) when
    the function accepts two arguments.
    """
    claims = claims or {}
    preferred = claims.get("preferred_username", "").strip()
    if preferred:
        return preferred

    email = (email or claims.get("email", "")).strip()
    if email:
        return email.split("@")[0]

    sub = claims.get("sub", "").strip()
    if sub:
        return f"user_{sub[:32]}"

    return f"user_{timezone.now().timestamp():.0f}"


def provider_logout(request) -> str:
    """Build Keycloak RP-initiated logout URL with id_token_hint."""
    logout_url = settings.OIDC_OP_LOGOUT_ENDPOINT
    oidc_id_token = request.session.get("oidc_id_token")

    if not oidc_id_token:
        return logout_url

    post_logout_redirect_uri = request.build_absolute_uri(
        resolve_url(settings.LOGOUT_REDIRECT_URL)
    )
    params = {
        "id_token_hint": oidc_id_token,
        "post_logout_redirect_uri": post_logout_redirect_uri,
        "client_id": settings.OIDC_RP_CLIENT_ID,
    }
    return f"{logout_url}?{urlencode(params)}"
