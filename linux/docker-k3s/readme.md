# Exivity Automated Installer for Morpheus

This script provides a fully unattended installation of **Exivity** in a lightweight Kubernetes environment using **k3s**. It is intended for execution as an **Automation Task within Morpheus**, and performs the following tasks:

## ✅ What It Does

- Installs **Docker** on the target Ubuntu system
- Installs **k3s** with Traefik as the Ingress controller
- Sets up an **NFS-based RWX storage class** using the Ganesha server provisioner
- Deploys **Exivity** via Helm with:
  - `demo` license key
  - self-signed TLS certificates
  - Ingress hostname `exivity.local`
  - `trustedProxy: "*"` for compatibility behind Traefik
- Opens firewall port `30789` for external access
- (Optionally) sets up `iptables` to forward port `443` to `30789` for clean HTTPS access

## 🌐 Accessing Exivity

Once installed, you can access Exivity in your browser:

```https://<your-k3s-host-ip>:30789```


For a cleaner URL, add this to your local machine's `/etc/hosts`:

```<your-k3s-host-ip>.exivity.local```

Then access:

```https://exivity.local```


> ⚠️ A self-signed certificate is used — your browser will display a security warning. You can safely bypass it in non-production environments.

## 🧩 Requirements

- Ubuntu 20.04 or 22.04 VM or bare metal
- Root or sudo access
- Executed as a Morpheus automation task (or other provisioning platform)

## 📥 License

The script uses a `demo` license by default. Contact [license@exivity.com](mailto:license@exivity.com) for a trial or production license key.