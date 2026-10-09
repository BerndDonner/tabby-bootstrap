# tabby-bootstrap — Ollama and Tabby on temporary Lambda GPU instances

This repository bootstraps a **fresh GPU instance**. The GPU instance clones
this repository from GitHub and runs `ollama_setup/run_all.py` or
`tabby_setup/run_all.py`. There is no Lambda API dependency.

## Normal Ollama workflow

1. In the Lambda web UI, select and start a GPU instance; note its public IP.
2. On your NixOS machine, in this repository: `nix develop` (same as `nix develop .#ollama`).
3. Run `./deploy-seed.sh <IP>`.
4. **Terminate** the GPU instance in Lambda's web UI after class/exam.

`nix develop` requires `cloudflare.sops.env` in the pinned NixOS-Config.
It decrypts `CF_API_TOKEN` and `CF_ZONE_ID` in memory. The local key at
`~/.ssh/id_tabby_bootstrap` is already linked from the LUKS vault by Home
Manager; it is used for SSH to the GPU instance and is forwarded temporarily
so that the GPU instance can clone the private GitHub repository.

The deploy command takes **only** the IP address. It obtains the target from
`BOOTSTRAP_TARGET` set by the DevShell; it never takes a target argument.

## Testing a feature branch

On your workstation, switch to the feature branch and **push** it before
running the deploy command (the fresh GPU always clones from GitHub):

```bash
git switch feature/sops-target-shells
git push -u origin feature/sops-target-shells
nix develop
./deploy-seed.sh <IP> --branch feature/sops-target-shells --debug
./deploy-seed.sh <IP> --branch feature/sops-target-shells
```

The default ref is the currently checked-out **local branch**, not
implicitly `master`; `--branch <ref>` overrides it. You can use `--debug`
to verify the remote Git clone without launching Ollama.
The local `seed.py` is uploaded from your working copy; the target setup is
executed from the GitHub ref, so commit and push setup changes first.

## Tabby: parked, not deleted

`nix develop .#tabby` selects the Tabby target but does **not** require fake
or expired AWS/Hetzner secrets. For now, only a clone-only `--debug` deploy
is permitted. A normal Tabby deploy fails fast until its old restore path is
reworked and new real credentials are available. All Tabby setup/backup/restore
scripts remain in the repository.

## Secret migration prerequisite (NixOS-Config)

In your *NixOS-Config* working tree, create
`secrets/cloudflare.sops.env`, containing:

```dotenv
CF_API_TOKEN=<your real Cloudflare API token>
CF_ZONE_ID=<your real Cloudflare zone ID>
```

Encrypt with the existing `.sops.yaml` recipients; **never** commit the
plaintext values. Commit and push the encrypted file. Then update the
`nixos-config` input of this flake and commit the generated `flake.lock`:

```bash
nix flake lock
```

The private SSH key stays in the existing LUKS vault, not duplicated in SOPS.
The SSH public key is not a secret.

## Scope

The DevShell selects the target and its secret sets, while `deploy-seed.sh`
is target-agnostic. `bootstrap_payload.py` validates and selects which
variables are sent over SSH stdin; `seed.py` receives that JSON, installs the
GitHub deploy key, clones the repo, and dispatches to the requested setup.
No decrypted secrets are added to the Nix store or written into seed.py.

**TODO:** independent cost watchdog on `cloud` (not part of this change).
