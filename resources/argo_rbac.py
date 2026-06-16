"""Argo Workflows RBAC definitions used during user provisioning."""

from __future__ import annotations

from kubernetes import client

RBAC_API_GROUP = "rbac.authorization.k8s.io"


def argo_workflows_policy_rules() -> list[client.V1PolicyRule]:
    """Namespaced Role rules for workflow-runner in each user namespace."""
    return [
        client.V1PolicyRule(
            api_groups=["argoproj.io"],
            resources=[
                "workflows",
                "workflows/finalizers",
                "workflows/status",
            ],
            verbs=["create", "get", "list", "watch", "update", "patch", "delete"],
        ),
        client.V1PolicyRule(
            api_groups=["argoproj.io"],
            resources=[
                "workflowtemplates",
                "clusterworkflowtemplates",
            ],
            verbs=["get", "list", "watch"],
        ),
        client.V1PolicyRule(
            api_groups=["argoproj.io"],
            resources=[
                "workflowtaskresults",
                "workflowtasksets",
            ],
            verbs=["create", "get", "list", "watch", "update", "patch", "delete"],
        ),
        client.V1PolicyRule(
            api_groups=[""],
            resources=["pods", "pods/log"],
            verbs=["get", "list", "watch", "patch"],
        ),
    ]


def role_escalation_hint() -> str:
    return (
        "RBAC escalation: the token can create roles but cannot grant Argo Workflows "
        "permissions it does not already hold. Grant the RBAC manager service account "
        "the same argoproj.io rules, then retry. The portal only creates namespaced "
        "Roles and RoleBindings in each user's namespace."
    )
