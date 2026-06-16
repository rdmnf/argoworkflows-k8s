from django import forms

from clusters.models import K8sCluster


class ResourceRequestForm(forms.Form):
    cluster = forms.ModelChoiceField(
        queryset=K8sCluster.objects.filter(is_active=True),
        empty_label=None,
        help_text="Select the cluster where your namespace will be created.",
    )
