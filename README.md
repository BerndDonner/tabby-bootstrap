# 🐈‍⬛ tabby-bootstrap

Helper scripts to **bootstrap, restore, and launch a self-hosted Tabby server**  
(CodeLlama + Mistral) on remote GPU instances (Lambda, Hetzner, Scaleway, etc.).

---

## ⚠️ BIG FAT WARNING – READ BEFORE CLONING

This repository uses a **Git clean filter** to automatically strip secrets  
(API keys, JWT tokens, private SSH keys) before committing.

You **must enable the filter once per clone** before working with this repo:

```bash
git config include.path .gitconfig.strip-secrets
```

Without this include, commits will **not** be sanitized and you may leak secrets.

The filter logic lives in:
```
.utils/strip-secrets.sh
.utils/inject-secrets.sh
.gitconfig.strip-secrets
```

---

## 🚀 Overview

| Folder | Purpose |
|---------|----------|
| `setup/` | start Tabby on the target server |
| `restore/` | restore model data from Hetzner S3 |
| `backup/` | backup trained models to S3 |
| `utils/` | helper scripts for secret management |
| `secrets/` | local-only secrets (never committed) |

---

## 🧩 Workflow Summary

1. **seed.sh** is a first-stage bootstrap script that:
   - installs SSH keys and Git config
   - clones this repo to the target server
   - restores model data from Hetzner
   - launches Tabby

2. **strip-secrets.sh** removes real secrets before commit  
   (run automatically by Git).

3. **inject-secrets.sh** re-inserts them locally for deployment.

4. **deploy-seed.sh** uploads and runs the seed script on the remote instance.

---

## 📦 Typical Usage

```bash
# 1️⃣ Clone the repository
git clone git@github.com:BerndDonner/tabby-bootstrap.git
cd tabby-bootstrap

# 2️⃣ Enable the clean filter (must be done once per clone!)
git config include.path .gitconfig.strip-secrets

# 3️⃣ Inject your local secrets for testing or deployment
./utils/inject-secrets.sh secrets/seed.sh secrets/seed.env secrets/id_tabby_bootstrap > seed_local.sh

# 4️⃣ Deploy seed.sh to your GPU instance
./deploy-seed.sh <REMOTE_IP> secrets/seed.sh
```

---

## 🧠 Key Concepts

- **Seed script (`seed.sh`)**  
  First-stage bootstrapper, executed remotely.  
  Automatically clones this repo and runs the local setup chain.

- **S3 Integration**  
  Backup and restore handled via `restore/restore_tabby_from_hetzner.sh`.

- **Server Startup**  
  Managed through `setup/start_tabby.sh`.

---

## 🔐 Secret Management Summary

| Component | Purpose | Stored in Git? |
|------------|----------|----------------|
| `seed.sh` | Logic only (no secrets) | ✅ |
| `secrets/seed.env` | AWS + JWT secrets | ❌ |
| `secrets/id_tabby_bootstrap` | SSH private key | ❌ |
| `utils/strip-secrets.sh` | Removes secrets | ✅ |
| `utils/inject-secrets.sh` | Re-inserts secrets | ✅ |
| `.gitconfig.strip-secrets` | Defines Git filter | ✅ |

---

## ✅ Safety Checks Before Commit

To verify that `seed.sh` is sanitized before pushing:

```bash
git show :secrets/seed.sh | less
# or
git diff --cached -- secrets/seed.sh
```

You should only see `<REDACTED>` placeholders and the line  
`# 🔒 <PRIVATE SSH KEY REDACTED>` — never real credentials.

---

## 🧾 License

MIT © 2025 Bernd Donner
