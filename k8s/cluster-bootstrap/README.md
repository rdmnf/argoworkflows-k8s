# Cluster bootstrap for Kubernetes Argo Workflows

Kubernetes manifests to create the three service accounts the **Kubernetes Argo Workflows** portal needs to provision user namespaces, service accounts, and Argo Workflows RBAC on a cluster.

Apply these once per cluster (with cluster-admin credentials) before registering the cluster in the portal. Users must sign in via **OIDC SSO** (e.g. Keycloak) before they can request resources; see the [main README](../README.md#secure-authentication-oidc-sso).

> **Development and testing only.** These manifests grant broad cluster-wide permissions to the bootstrap service accounts. Use only on dev/test clusters. **Not for production.**

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| `kubectl` | Configured for the target cluster |
| Cluster-admin (or equivalent) | To create ClusterRoles, ClusterRoleBindings, ServiceAccounts, and Secrets |
| **Argo Workflows** | **Required** on the cluster if users will submit workflows. The portal creates RBAC that matches Argo’s needs (`workflows`, `workflowtaskresults`, pod patch, etc.) but does not install the Argo controller. |
| Portal reachability | Kubernetes API URL registered in the portal must be reachable from the application process |
| Token controller | Cluster must fill `kubernetes.io/service-account-token` Secrets (see [Extract tokens manually](#extract-tokens-manually)) |

Full application and cluster requirements are listed in the [main README](../README.md#requirements).

## Files

| File | Purpose | Portal cluster field |
|------|---------|----------------------|
| `namespace.yaml` | Service account that can **create and list namespaces**. Used when a user requests a resource and when the cluster explorer lists namespaces. | **Token for creating namespaces** (`namespace_creator_token`) |
| `sa.yaml` | Service account that can **create service accounts and secrets** in any namespace. The portal creates `workflow-runner` and a `kubernetes.io/service-account-token` Secret to issue user workflow tokens. | **Token for creating service accounts** (`service_account_creator_token`) |
| `rbac.yaml` | Service account that can **create and update Roles and RoleBindings** in user namespaces. Rules mirror `argo_workflows_policy_rules` in the portal (workflows, workflow templates, task results, pod patch for the Argo emissary). | **Token for creating roles and role bindings** (`role_binding_creator_token`) |
| `install.sh` | Applies all three manifests in order and prints the three bearer tokens. | — |

Each YAML file defines four resources:

1. `ServiceAccount` — identity for the token
2. `ClusterRole` — permissions (cluster-scoped rules apply in every namespace)
3. `ClusterRoleBinding` — binds the SA to the ClusterRole
4. `Secret` (`type: kubernetes.io/service-account-token`) — long-lived token populated by the cluster’s service account token controller

## Quick start

```bash
cd k8s/cluster-bootstrap
chmod +x install.sh   # if needed
./install.sh
```

See [Register the cluster in the portal](#register-the-cluster-in-the-portal) below for where each printed token goes in the UI.

## Register the cluster in the portal

After `./install.sh` (or manual token extraction), add the cluster in the **Kubernetes Argo Workflows** web UI so the portal can provision user namespaces and workflows.

### Who can do this

Only users who signed in via **OIDC SSO** and belong to the IdP **`admin`** group (e.g. Keycloak group `admin`). The **Control** link appears in the nav when signed in as admin.

### Where to go

| Step | Location |
|------|----------|
| Admin home | **Control** in the top nav → [`/control/`](http://127.0.0.1:8000/control/) |
| Cluster list + add form | **Clusters** (or go directly to [`/control/clusters/`](http://127.0.0.1:8000/control/clusters/)) |
| Edit existing cluster | Cluster list → **Edit** on a row → [`/control/clusters/<id>/edit/`](http://127.0.0.1:8000/control/clusters/) |
| Test connectivity | Cluster list → **Open** → cluster explorer (namespace list) |

### Add cluster form — field mapping

Use the **Add cluster** form at the top of `/control/clusters/`. Each field maps to bootstrap output or cluster facts:

| Form label | Required | What to enter | Source |
|------------|----------|---------------|--------|
| **Name** | Yes | Short label for admins, e.g. `dev-local`, `production-east` | Your choice |
| **Api server url** | Yes | Kubernetes API URL, e.g. `https://192.168.1.10:6443` or `https://host.docker.internal:6443` if the portal runs in Docker | `kubectl cluster-info` → Kubernetes control plane URL; must be reachable **from the application process** |
| **TOKEN FOR CREATING NAMESPACES** | Yes | Bearer token (no `Bearer ` prefix) | `./install.sh` section *Token for creating namespaces*, or `namespace-creator-sa-token` secret — from `namespace.yaml` |
| **TOKEN FOR CREATING SERVICE ACCOUNT** | No* | Bearer token | `./install.sh` section *Token for creating service accounts*, or `sa-manager-token` — from `sa.yaml` |
| **TOKEN FOR CREATING ROLE AND ROLEBINDING** | No* | Bearer token | `./install.sh` section *Token for creating roles and role bindings*, or `rbac-manager-token` — from `rbac.yaml` |
| **Ca certificate** | No | PEM text (`-----BEGIN CERTIFICATE-----` … `-----END CERTIFICATE-----`) | Optional; enables TLS verification. From kubeconfig `certificate-authority-data` (base64-decode) or cluster CA file |
| **Default namespace** | Yes | Usually `default` | Default context namespace; rarely changed |
| **Description** | No | Free text notes | Your choice |
| **Is active** | Yes | Checked for clusters available to users | Uncheck to hide cluster from user resource requests |

\*The service account and role-binding tokens are optional on the form, but **user resource provisioning requires all three**. Leave them empty only if you are registering a cluster for namespace exploration alone.

### After saving

1. Click **Add cluster** (or **Save changes** when editing).
2. In **Registered clusters**, click **Open** on the new row.
3. Confirm the namespace list loads (uses the namespace creator token).
4. As a normal user (OIDC SSO, non-admin), open **My resources** ([`/my-resources/`](http://127.0.0.1:8000/my-resources/)) → select the cluster → **Request resource** to verify full provisioning.

If a step fails, open the provision detail on **My resources** or the admin user detail page; error messages reference which token lacked permission.

### Token ↔ manifest quick reference

| `install.sh` output label | Bootstrap file | Kubernetes secret |
|---------------------------|----------------|---------------------|
| Token for creating namespaces | `namespace.yaml` | `default` / `namespace-creator-sa-token` |
| Token for creating service accounts | `sa.yaml` | `kube-system` / `sa-manager-token` |
| Token for creating roles and role bindings | `rbac.yaml` | `kube-system` / `rbac-manager-token` |

## Manual apply

```bash
kubectl apply -f namespace.yaml
kubectl apply -f sa.yaml
kubectl apply -f rbac.yaml
```

Apply order does not matter; resources are independent.

## Extract tokens manually

After apply, the token controller fills each Secret’s `data.token` field (may take a few seconds).

**Namespace creator** (`default` / `namespace-creator-sa-token`):

```bash
kubectl -n default get secret namespace-creator-sa-token \
  -o jsonpath='{.data.token}' | base64 -d && echo
```

**Service account creator** (`kube-system` / `sa-manager-token`):

```bash
kubectl -n kube-system get secret sa-manager-token \
  -o jsonpath='{.data.token}' | base64 -d && echo
```

**Role binding creator** (`kube-system` / `rbac-manager-token`):

```bash
kubectl -n kube-system get secret rbac-manager-token \
  -o jsonpath='{.data.token}' | base64 -d && echo
```

If `jsonpath` returns empty, wait and retry:

```bash
kubectl -n kube-system get secret rbac-manager-token -w
```

## Verify RBAC (optional)

```bash
# Namespace creator can list namespaces
kubectl auth can-i list namespaces \
  --as=system:serviceaccount:default:namespace-creator-sa

# SA manager can create service accounts in a user namespace
kubectl auth can-i create serviceaccounts \
  --as=system:serviceaccount:kube-system:sa-manager \
  -n <user-namespace>

# RBAC manager can create roles in a user namespace
kubectl auth can-i create roles \
  --as=system:serviceaccount:kube-system:rbac-manager \
  -n <user-namespace>
```

## Security notes

- These tokens are **cluster-wide** credentials. Store them only in the portal database (or your secrets manager) and restrict who can view cluster settings.
- Rotate by deleting the token Secret; Kubernetes recreates it if the ServiceAccount annotation is present, or create a new Secret and update the cluster record in the portal.
- For production, consider narrower RBAC (e.g. delegate only to namespaces with a label) instead of cluster-wide Role rules; these manifests target dev/small clusters where simplicity is preferred.

## Uninstall

```bash
kubectl delete -f rbac.yaml
kubectl delete -f sa.yaml
kubectl delete -f namespace.yaml
```

User namespaces and resources created by the portal are not removed automatically.
