# 🐈‍⬛ tabby-bootstrap

Helper scripts to **bootstrap Tabby** (the self-hosted code model server)
on GPU instances across different cloud providers (Lambda, Hetzner, Scaleway, etc.).

## 🚀 Features
- Automated environment setup (`setup/`)
- Model backup and restore via S3 (`backup/`, `restore/`)
- Verified uploads with checksum support
- Provider-independent design (set credentials via environment variables)

## 📦 Quickstart

```bash
git clone https://github.com/<youruser>/tabby-bootstrap.git
cd tabby-bootstrap/backup
chmod +x backup_tabby_to_hetzner.sh
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
./backup_tabby_to_hetzner.sh

