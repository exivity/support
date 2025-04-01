#!/bin/bash

set -euo pipefail

echo "=== Updating system and installing dependencies ==="
apt-get update -y
apt-get install -y curl gnupg lsb-release ca-certificates apt-transport-https software-properties-common nfs-common ufw iptables

echo "=== Installing Docker ==="
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /usr/share/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io
usermod -aG docker "${SUDO_USER:-ubuntu}"

echo "=== Installing k3s ==="
/usr/bin/curl -sfL https://get.k3s.io | sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Waiting for k3s to become ready ==="
for i in {1..30}; do
    if kubectl get nodes >/dev/null 2>&1; then
        echo "✅ k3s is ready."
        break
    fi
    echo "⏳ Waiting for k3s... (${i}/30)"
    sleep 5
done

echo "=== Installing Helm ==="
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

echo "=== Adding Helm repos ==="
helm repo add exivity https://charts.exivity.com/
helm repo add nfs-ganesha-server-and-external-provisioner https://kubernetes-sigs.github.io/nfs-ganesha-server-and-external-provisioner/
helm repo update

echo "=== Installing NFS RWX provisioner ==="
helm install nfs-server nfs-ganesha-server-and-external-provisioner/nfs-server-provisioner \
  --namespace nfs-server \
  --create-namespace \
  --wait \
  --set persistence.enabled=true \
  --set persistence.size=5Gi \
  --set storageClass.name=nfs-client \
  --set storageClass.allowVolumeExpansion=true \
  --set 'storageClass.mountOptions[0]=nfsvers=4.2' \
  --set 'storageClass.mountOptions[1]=rsize=4096' \
  --set 'storageClass.mountOptions[2]=wsize=4096' \
  --set 'storageClass.mountOptions[3]=hard' \
  --set 'storageClass.mountOptions[4]=retrans=3' \
  --set 'storageClass.mountOptions[5]=proto=tcp' \
  --set 'storageClass.mountOptions[6]=noatime' \
  --set 'storageClass.mountOptions[7]=nodiratime'

# Detect IP of host for ingress (safe for Morpheus VMs)
EXIVITY_HOST=$(hostname -I | awk '{print $1}')
echo "=== Using ingress host: $EXIVITY_HOST ==="

echo "=== Installing Exivity Helm chart ==="
helm upgrade --install exivity exivity/exivity \
  --namespace exivity \
  --create-namespace \
  --set licence=demo \
  --set storage.storageClass=nfs-client \
  --set ingress.enabled=true \
  --set ingress.host="$EXIVITY_HOST" \
  --set ingress.tls.enabled=true \
  --set ingress.tls.secret="-" \
  --set ingress.tls.hosts[0]="$EXIVITY_HOST" \
  --set ingress.trustedProxy="*" \
  --wait

echo "=== Opening NodePort 30789 in UFW ==="
ufw allow 30789/tcp || true

echo "=== (Optional) Forwarding port 443 to 30789 via iptables ==="
iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 30789 || true

echo "=== ✅ Exivity is installed and ready ==="
echo "Access it at: https://$EXIVITY_HOST:30789"
echo "Or configure DNS/hosts entry pointing to: $EXIVITY_HOST"
