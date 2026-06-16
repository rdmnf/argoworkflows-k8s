from urllib.parse import urlparse

import requests
from django.contrib.auth.models import Group
from django.utils import timezone
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from accounts.models import UserProfile
from accounts.oidc import django_group_name, extract_groups


class KeycloakOIDCBackend(OIDCAuthenticationBackend):
    """Authenticate via Keycloak and persist user profile data in SQLite."""

    def _backchannel_headers(self, access_token: str) -> dict[str, str]:
        """Headers for server-side Keycloak calls from inside Docker."""
        from django.conf import settings

        headers = {"Authorization": f"Bearer {access_token}"}
        public_url = getattr(settings, "KEYCLOAK_PUBLIC_URL", "")
        host = urlparse(public_url).netloc if public_url else ""
        if host:
            headers["Host"] = host
        return headers

    def get_userinfo(self, access_token, id_token, payload):
        """
        Fetch userinfo from Keycloak.

        When Django runs in Docker against host Keycloak, the internal URL is often
        host.docker.internal while the browser uses localhost. Keycloak may reject
        userinfo unless the public Host header is sent. If userinfo still fails
        (e.g. lightweight access tokens), fall back to verified ID token claims.
        """
        user_response = requests.get(
            self.OIDC_OP_USER_ENDPOINT,
            headers=self._backchannel_headers(access_token),
            verify=self.get_settings("OIDC_VERIFY_SSL", True),
            timeout=self.get_settings("OIDC_TIMEOUT", None),
            proxies=self.get_settings("OIDC_PROXY", None),
        )

        if user_response.status_code == 401 and payload:
            return payload

        user_response.raise_for_status()

        if (
            user_response.headers.get("content-type", "")
            .lower()
            .startswith("application/jwt")
        ):
            return self.verify_token(user_response.text)

        return user_response.json()

    def filter_users_by_claims(self, claims):
        users = super().filter_users_by_claims(claims)
        if users.exists():
            return users

        sub = claims.get("sub")
        if not sub:
            return self.UserModel.objects.none()

        user_ids = UserProfile.objects.filter(keycloak_sub=sub).values_list(
            "user_id", flat=True
        )
        return self.UserModel.objects.filter(pk__in=user_ids)

    def create_user(self, claims):
        user = super().create_user(claims)
        self._apply_claims_to_user(user, claims)
        self._sync_profile(user, claims)
        return user

    def update_user(self, user, claims):
        user = super().update_user(user, claims)
        self._apply_claims_to_user(user, claims)
        self._sync_profile(user, claims)
        return user

    def _apply_claims_to_user(self, user, claims: dict) -> None:
        changed = []
        if "email" in claims:
            user.email = claims["email"]
            changed.append("email")
        if "given_name" in claims:
            user.first_name = claims["given_name"]
            changed.append("first_name")
        if "family_name" in claims:
            user.last_name = claims["family_name"]
            changed.append("last_name")
        if changed:
            user.save(update_fields=changed)

    def _sync_profile(self, user, claims: dict) -> None:
        sub = claims.get("sub", "")
        groups = extract_groups(claims)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.keycloak_sub = sub
        profile.preferred_username = claims.get("preferred_username", "")
        profile.email_verified = bool(claims.get("email_verified", False))
        profile.keycloak_groups = groups
        profile.last_oidc_login = timezone.now()
        profile.save()
        self._sync_django_groups(user, groups)

    def _sync_django_groups(self, user, keycloak_groups: list[str]) -> None:
        from django.conf import settings

        if not getattr(settings, "KEYCLOAK_SYNC_DJANGO_GROUPS", True):
            return

        django_groups = []
        for keycloak_group in keycloak_groups:
            name = django_group_name(keycloak_group)
            group, _ = Group.objects.get_or_create(name=name)
            django_groups.append(group)

        user.groups.set(django_groups)
