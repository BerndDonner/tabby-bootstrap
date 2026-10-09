# tabby-bootstrap

**Temporärer KI-Server für Unterricht und Prüfungen.** Das Repository richtet auf einer frisch gestarteten GPU-Instanz bei [Lambda Cloud](https://cloud.lambda.ai/) entweder **Ollama** oder – perspektivisch – **Tabby** ein. Die Instanz klont dieses Repository selbst und führt die gewählte Setup-Pipeline aus. Die Auswahl des Targets erfolgt **einmalig in der Nix-DevShell**; `deploy-seed.sh` ist target-unabhängig.

**Status (09.10.2026):** Ollama wurde auf einer echten Lambda-Instanz erfolgreich installiert; VS-Code-Continue funktioniert sowohl für **Chat** als auch für **Autocomplete**. Tabby bleibt als historische Alternative erhalten, ist aber derzeit **nicht produktiv startbar**.

## Normaler Ablauf: Ollama

1. Auf der **Lambda-Website** die passende **Region und GPU** nach Verfügbarkeit, Schülerzahl und Einsatzzweck auswählen; Instanz starten und öffentliche IP notieren.
2. Lokal im Repository die Ollama-DevShell betreten:

   ```bash
   nix develop                 # identisch mit: nix develop .#ollama
   ```

3. Bootstrap ausführen:

   ```bash
   ./deploy-seed.sh <IP>
   ```

4. Nach Unterricht/Prüfung die Instanz **auf der Lambda-Website terminieren und die Terminierung kontrollieren**. Nicht nur ausloggen, den Ollama-Dienst stoppen oder `shutdown` ausführen: Solange die Instanz nicht terminiert ist, können GPU-Kosten entstehen.

Der übliche Einsatz dauert ungefähr **3 × 45 Minuten**. Die GPU wird privat bezahlt; deshalb **nach dem Einsatz sofort terminieren**. Start und Terminierung bleiben bewusst manuell. Ein unabhängiger Kosten-Watchdog auf `cloud` ist nur ein **TODO**; dieses Repository verwendet **keine Lambda-API**.

## Voraussetzung und Zugangsdaten

Auf dem lokalen NixOS-Rechner müssen eingerichtet sein:

- Zugriff auf die im `flake.lock` gepinnte **NixOS-Config** mit funktionierendem **SOPS/age**. `nix develop` lädt für Ollama das Secret-Set `cloudflare` mit `CF_API_TOKEN` und `CF_ZONE_ID`.
- Der private Schlüssel `~/.ssh/id_tabby_bootstrap` aus dem **lokalen LUKS-Vault** (von Home Manager bereitgestellt); der öffentliche Schlüssel allein ist kein Secret.
- SSH-Zugang zur frisch gestarteten Lambda-Instanz, im Standardfall als Benutzer `ubuntu`, sowie Berechtigung zum Klonen von `git@github.com:BerndDonner/tabby-bootstrap.git` mit dem übertragenen Deploy-Key.
- Für Continue: Netzfreigabe auf Lambda für Port **11434/TCP** im nötigen Umfang.

**Keine echten Secrets liegen in diesem Repository.** Der private Schlüssel und die beiden Cloudflare-Werte werden über SSH an den Remote-Bootstrap übertragen, **nicht** in `seed.py` hineingeschrieben. Der Schlüssel wird auf der kurzlebigen Instanz unter `~/.ssh/id_tabby_bootstrap` abgelegt, um den GitHub-Klon zu ermöglichen. Das ist **kein SSH-Agent-Forwarding**.

Wenn sich die SOPS-Inhalte der zentralen NixOS-Config ändern, wird der gepinnte Input mit `nix flake update nixos-config` aktualisiert und die geänderte `flake.lock` committed.

## Was der Bootstrap macht

```text
Lokal: nix develop → deploy-seed.sh <IP>
           │
           ├── SCP: seed.py (nur Programmcode)
           └── SSH-stdin: JSON (Target, Git-Ref, Schlüssel, benötigte Secrets)
                              │
                              ▼
Lambda: seed.py → GitHub-SSH-Key installieren → Repository klonen/aktualisieren
                              │
                    Target aus Payload
                      ├── ollama_setup/run_all.py
                      └── tabby_setup/run_all.py (derzeit gesperrt)
```

Für **Ollama** führt `run_all.py` die nummerierten Schritte aus:

1. `10_update_dns.py`: Cloudflare-A-Record `ai.donner-lab.org` auf die aktuelle Instanz-IP setzen (TTL 60 s, ohne Cloudflare-Proxy).
2. `20_setup_ollama.py`: Ollama installieren/konfigurieren, auf `0.0.0.0:11434` bereitstellen und Modelle laden.

Die Modelle sind `deepseek-coder:6.7b` (**Autocomplete**) und `qwen2.5-coder:7b` (**Chat**). Die zugehörige Continue-Beispielkonfiguration liegt unter `vscode_config/config.yaml`; sie wird **nicht automatisch auf die Schulrechner verteilt**. Der Continue-Endpunkt lautet:

```text
http://ai.donner-lab.org:11434
```

**Wichtig:** Ein erfolgreiches DNS-Update allein garantiert noch keinen nutzbaren Ollama-Server. Bei der Bereitstellung sollten der vollständige Setup-Durchlauf und mindestens eine Continue-Anfrage überprüft werden.

## Feature-Branches und Tests

Die GPU klont von **GitHub**, nicht vom lokalen Arbeitsverzeichnis. Deshalb Änderungen an Remote-Setup-Skripten **committen und pushen**. Ohne `--branch` wird der **aktuell ausgecheckte lokale Branch** auf der GPU ausgewählt:

```bash
nix develop
./deploy-seed.sh <IP> --debug    # Git-Klon, aber kein Ollama/Tabby-Setup
./deploy-seed.sh <IP>            # vollständiger Ollama-Start
```

`--branch <ref>` kann die Auswahl explizit überschreiben. Auch Tags und Commits sind im Remote-Bootstrap vorgesehen. `--debug` kontaktiert und verändert die GPU-Instanz bereits (Schlüsselinstallation und Git-Klon), lädt aber noch keine Modelle und ändert kein DNS.

Lokale Tests ohne kostenpflichtige GPU:

```bash
python3 -m unittest discover -s tests -v
```

## Tabby bleibt absichtlich erhalten

Tabby war die frühere Lösung. Die **kostenlose Tabby-Version ist auf fünf Seats begrenzt** und deshalb für den regulären Klassenunterricht ungeeignet. Bei einer **MCT-Abschlussprüfung mit beispielsweise drei Teilnehmenden** könnte Tabby dagegen erneut interessant werden.

Die früheren AWS-/Hetzner-Speicherzugänge existieren nicht mehr. Es werden deshalb **keine Fake-Secrets** in SOPS angelegt. `nix develop .#tabby` wählt das Target, gestattet aktuell aber nur einen **Clone-Test mit `--debug`**; ein echter Tabby-Start wird bewusst abgelehnt. Die Tabby-, Backup- und Restore-Skripte bleiben für eine spätere Reaktivierung im Repository.

## Dokumentation für Wartung und spätere Weiterentwicklung

**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** hält die vollständige Drei-Stage-Architektur, Secret-Lebenszyklen, die Entscheidungen zur SSH-Host-Key-Prüfung, den historischen Hintergrund, die Risiken, bekannte Altlasten und offene TODOs fest. **Bei Änderungen am Bootstrap bitte zuerst diese Datei lesen.**
