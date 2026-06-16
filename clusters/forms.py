from django import forms

from clusters.models import K8sCluster

TOKEN_WIDGET = forms.PasswordInput(
    render_value=True,
    attrs={
        "autocomplete": "off",
    },
)


class K8sClusterForm(forms.ModelForm):
    namespace_creator_token = forms.CharField(
        label="TOKEN FOR CREATING NAMESPACES",
        widget=TOKEN_WIDGET,
        help_text="Bearer token for the service account that creates user namespaces.",
    )
    service_account_creator_token = forms.CharField(
        label="TOKEN FOR CREATING SERVICE ACCOUNT",
        widget=TOKEN_WIDGET,
        required=False,
        help_text="Bearer token for the service account that creates user service accounts.",
    )
    role_binding_creator_token = forms.CharField(
        label="TOKEN FOR CREATING ROLE AND ROLEBINDING",
        widget=TOKEN_WIDGET,
        required=False,
        help_text="Bearer token for the service account that creates roles and role bindings.",
    )

    class Meta:
        model = K8sCluster
        fields = [
            "name",
            "api_server_url",
            "namespace_creator_token",
            "service_account_creator_token",
            "role_binding_creator_token",
            "ca_certificate",
            "default_namespace",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "production-east"}),
            "api_server_url": forms.URLInput(
                attrs={"placeholder": "https://kubernetes.example.com:6443"},
            ),
            "ca_certificate": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
                },
            ),
            "default_namespace": forms.TextInput(attrs={"placeholder": "default"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Optional notes about this cluster"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["namespace_creator_token"].widget.attrs["placeholder"] = (
            "Paste namespace creator token"
        )
        self.fields["service_account_creator_token"].widget.attrs["placeholder"] = (
            "Paste service account creator token"
        )
        self.fields["role_binding_creator_token"].widget.attrs["placeholder"] = (
            "Paste role and role binding creator token"
        )
