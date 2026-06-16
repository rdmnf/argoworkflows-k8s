import yaml
from django import forms

from clusters.models import K8sCluster
from resources.models import ResourceProvision
from workflows.models import WorkflowScript

DEFAULT_WORKFLOW_MANIFEST = """apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: hello-world-
spec:
  entrypoint: whalesay
  templates:
    - name: whalesay
      container:
        image: docker/whalesay:latest
        command: [cowsay]
        args: ["hello world"]
"""


class WorkflowScriptForm(forms.ModelForm):
    class Meta:
        model = WorkflowScript
        fields = ["subject", "description", "cluster", "status", "manifest"]
        widgets = {
            "subject": forms.TextInput(
                attrs={"placeholder": "Weekly data pipeline"},
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Optional notes about this workflow",
                },
            ),
            "manifest": forms.Textarea(
                attrs={
                    "rows": 18,
                    "class": "code-input",
                    "spellcheck": "false",
                },
            ),
            "status": forms.Select(),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["cluster"].queryset = K8sCluster.objects.filter(is_active=True)
        if not self.instance.pk and not self.initial.get("manifest"):
            self.initial.setdefault("manifest", DEFAULT_WORKFLOW_MANIFEST)

    def clean_manifest(self):
        manifest = self.cleaned_data["manifest"].strip()
        if not manifest:
            raise forms.ValidationError("Workflow manifest cannot be empty.")

        try:
            parsed = yaml.safe_load(manifest)
        except yaml.YAMLError as exc:
            raise forms.ValidationError(f"Invalid YAML: {exc}") from exc

        if not isinstance(parsed, dict):
            raise forms.ValidationError("Workflow manifest must be a YAML mapping (object).")

        kind = parsed.get("kind", "")
        if kind and kind != "Workflow":
            raise forms.ValidationError(
                f'Expected kind "Workflow", got "{kind}".'
            )

        api_version = parsed.get("apiVersion", "")
        if api_version and not str(api_version).startswith("argoproj.io/"):
            raise forms.ValidationError(
                "Expected apiVersion argoproj.io/v1alpha1 (or compatible)."
            )

        return manifest

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned

        user = self.user
        cluster = cleaned.get("cluster")
        if user and cluster:
            provision = ResourceProvision.objects.filter(
                user=user,
                cluster=cluster,
                status=ResourceProvision.Status.ACTIVE,
            ).first()
            if provision:
                cleaned["namespace_name"] = provision.namespace_name
            else:
                self.add_error(
                    "cluster",
                    "You need an active resource provision on this cluster first. "
                    "Request one under My resources.",
                )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.user = self.user
        instance.namespace_name = self.cleaned_data.get("namespace_name", "")
        if commit:
            instance.save()
        return instance
