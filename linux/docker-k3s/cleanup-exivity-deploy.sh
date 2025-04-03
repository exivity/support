#!/bin/bash
set -e

echo "=== Cleaning up Exivity Kubernetes environment ==="

# Uninstall Helm releases
echo "- Uninstalling Helm releases..."
helm uninstall exivity --namespace exivity || true
helm uninstall nfs-server --namespace nfs-server || true

# Delete NGINX ingress controller and namespace
echo "- Deleting ingress-nginx controller..."
kubectl delete namespace ingress-nginx --ignore-not-found=true

# Delete namespaces
echo "- Deleting Exivity and NFS namespaces..."
kubectl delete namespace exivity --ignore-not-found=true
kubectl delete namespace nfs-server --ignore-not-found=true

# Remove k3s
echo "- Removing k3s..."
/usr/local/bin/k3s-uninstall.sh || true

# Remove docker
echo "- Stopping and removing Docker..."
systemctl stop docker || true
apt-get purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin docker-ce-rootless-extras || true
apt-get autoremove -y
rm -rf /var/lib/docker /etc/docker

# Clean leftover data
echo "- Cleaning up leftover files..."
rm -rf ~/.kube /etc/rancher /var/lib/kubelet /var/lib/rancher /usr/local/bin/k3s /usr/local/bin/kubectl
rm -f /usr/local/bin/helm

echo "✅ Cleanup complete. You can now re-run the installation script."
