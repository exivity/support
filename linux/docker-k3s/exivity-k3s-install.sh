#!/bin/bash
set -e

### === System Prep ===
echo "=== Updating system and installing dependencies ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get install -y \
  curl gnupg2 ca-certificates apt-transport-https \
  software-properties-common lsb-release iptables ufw \
  nfs-common

### === Install Docker ===
echo "=== Installing Docker ==="
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io

### === Install k3s (without Traefik) ===
echo "=== Installing k3s ==="
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

### === Install Helm ===
echo "=== Installing Helm ==="
curl -fsSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash

### === Add Helm Repos ===
helm repo add exivity https://charts.exivity.com
helm repo add nfs-ganesha-server-and-external-provisioner https://kubernetes-sigs.github.io/nfs-ganesha-server-and-external-provisioner
helm repo update

### === Deploy NFS Provisioner (RWX support) ===
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

### === Installing NGINX Ingress Controller ===
echo "=== Installing NGINX Ingress Controller ==="
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/baremetal/deploy.yaml

### === Wait for Ingress Controller Ready ===
kubectl rollout status deployment ingress-nginx-controller -n ingress-nginx --timeout=180s

### === Patch ingress controller to expose ports 80/443 ===
echo "=== Patching ingress-nginx-controller to bind to host ports ==="
kubectl patch deployment ingress-nginx-controller -n ingress-nginx \
  --type=json \
  -p='[
    {"op": "add", "path": "/spec/template/spec/containers/0/ports/0/hostPort", "value": 80},
    {"op": "add", "path": "/spec/template/spec/containers/0/ports/1/hostPort", "value": 443}
  ]'

### === Wait for admission webhook to be available ===
echo "=== Waiting for ingress-nginx admission webhook to become available ==="
kubectl wait --namespace ingress-nginx \
  --for=condition=complete job/ingress-nginx-admission-create \
  --timeout=90s || true

kubectl wait --namespace ingress-nginx \
  --for=condition=complete job/ingress-nginx-admission-patch \
  --timeout=90s || true

sleep 5

### === Installing Exivity ===
echo "=== Installing Exivity ==="
EXTERNAL_IP=$(hostname -I | awk '{print $1}')
EXTERNAL_HOSTNAME=$(hostname -f)
helm upgrade --install exivity exivity/exivity \
  --namespace exivity \
  --create-namespace \
  --wait \
  --set licence=demo \
  --set ingress.enabled=true \
  --set ingress.host=${EXTERNAL_HOSTNAME} \
  --set ingress.trustedProxy="*" \
  --set ingress.annotations."kubernetes\.io/ingress\.class"=nginx \
  --set ingress.ingressClassName=nginx \
  --set ingress.tls.enabled=true \
  --set ingress.tls.secret="exivity-tls" \
  --set storage.storageClass=nfs-client

echo "=== Deployment complete. Exivity should now be accessible at:"
echo "    https://${EXTERNAL_HOSTNAME}"
echo ""
echo "Note: If the hostname is not resolvable, you can add the following line to your /etc/hosts file:"
echo "    ${EXTERNAL_IP} ${EXTERNAL_HOSTNAME}"
