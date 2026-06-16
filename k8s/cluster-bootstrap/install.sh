#!/usr/bin/env bash
# Apply Kubernetes Argo Workflows cluster bootstrap manifests and print bearer tokens.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

wait_for_token() {
  local namespace="$1"
  local secret_name="$2"
  local token_data=""

  for _ in $(seq 1 30); do
    token_data="$(kubectl -n "${namespace}" get secret "${secret_name}" \
      -o jsonpath='{.data.token}' 2>/dev/null || true)"
    if [[ -n "${token_data}" ]]; then
      echo "${token_data}" | base64 -d
      return 0
    fi
    sleep 2
  done

  echo "ERROR: Secret ${secret_name} in namespace ${namespace} has no token after 60s." >&2
  return 1
}

print_token() {
  local label="$1"
  local namespace="$2"
  local secret_name="$3"

  echo "=== ${label} ==="
  wait_for_token "${namespace}" "${secret_name}"
  echo ""
}

echo "Applying cluster bootstrap manifests ..."
kubectl apply -f "${SCRIPT_DIR}/namespace.yaml"
kubectl apply -f "${SCRIPT_DIR}/sa.yaml"
kubectl apply -f "${SCRIPT_DIR}/rbac.yaml"

echo ""
echo "Waiting for service account token secrets ..."
echo ""

print_token \
  "Token for creating namespaces (namespace_creator_token)" \
  "default" \
  "namespace-creator-sa-token"

print_token \
  "Token for creating service accounts (service_account_creator_token)" \
  "kube-system" \
  "sa-manager-token"

print_token \
  "Token for creating roles and role bindings (role_binding_creator_token)" \
  "kube-system" \
  "rbac-manager-token"

echo "Paste the three tokens into Kubernetes Argo Workflows under Control → Clusters when registering this cluster."
