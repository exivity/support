# Exivity Automated Deployment (with NGINX Ingress + NFS RWX + K3s)

This project provides a fully automated shell script to deploy [Exivity](https://www.exivity.com/) on a single Ubuntu host using:

- [K3s](https://k3s.io/) (Lightweight Kubernetes)
- [Docker](https://www.docker.com/)
- [Helm](https://helm.sh/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- NFS server + dynamic RWX provisioning
- Self-signed TLS for HTTPS (port 443)
- Hostname binding based on the detected system hostname

## ⚙️ Requirements

- Ubuntu 22.04+
- Internet access for downloading packages and container images
- Script should be run with root privileges (or via Morpheus automation task)

## 🚀 Usage

1. Run the script on a fresh VM or system.
2. Access the Exivity UI using:

```https://<your-hostname> (⚠️ self-signed cert)```

> 💡 If your client machine doesn't resolve the hostname, add it to your `/etc/hosts` file:

```<ip-address> <hostname>```

Example:
`192.168.2.250 exivity.localdomain`

## 📦 What gets installed

- K3s with Traefik disabled
- NGINX Ingress Controller patched to expose ports 80 and 443 using hostPorts
- Exivity Helm chart with NFS-based RWX storage
- Firewall rules allowing inbound traffic on ports 80 and 443
- StorageClass `nfs-client` for dynamic RWX provisioning

## 🧹 Clean Up

To reset the system before a fresh run, use the provided cleanup script:

```./cleanup-exivity-deploy.sh```
This removes Kubernetes resources, Helm releases, Docker volumes, and resets services.

Support: For license requests or Exivity trial assistance, email license@exivity.com

Note: This script is intended for lab, trial, and PoC environments only. Do not use it for production without appropriate review and hardening.