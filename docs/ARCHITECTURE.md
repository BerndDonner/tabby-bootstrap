# tabby-bootstrap – Architektur, Betrieb, Begründungen und Übergabe an künftige Assistenten

**Stand:** 09.10.2026 · **Sprache:** Deutsch · **Geltungsbereich:** `tabby-bootstrap`, Feature-Branch `feature/sops-target-shells` (Basis: vom Nutzer bereitgestelltes `tabby-bootstrap02.zip`; ZIP-Kommentar `9f0709de…`).

> **Für künftige KI-Assistenten und Entwickler:** Dies ist kein allgemeiner Architekturvorschlag. Es ist eine Bestandsaufnahme des tatsächlich implementierten und teilweise live getesteten Systems mit expliziten Nutzerentscheidungen. **Nicht** die Architektur ungefragt umstellen oder die Tabby-Altlast löschen. Bei neuen Aufgaben erst diese Datei und die aktuelle Implementierung lesen. Ein ZIP ist nur eine Momentaufnahme; neuere Commits können davon abweichen.

## 1. Zweck und reale Betriebsbedingungen

### 1.1 Wofür das System da ist

Der Nutzer unterrichtet Softwareentwicklung/Microcontrollertechnik und möchte in **VS Code mit dem Continue-Plugin** zentral bereitgestellte Code-KI nutzen. Für Unterricht und möglicherweise Abschlussprüfungen soll kurzfristig ein GPU-Server mit Ollama erreichbar sein. Die Schüler-Clients richten ihre Anfragen an einen stabilen DNS-Namen, obwohl sich die GPU-Instanz und ihre IP von Einsatz zu Einsatz ändern.

- **GPU-Anbieter:** Lambda Cloud (`lambda.ai`), kurzfristig angemietete **frische On-Demand-Instanz**.
- **Typische Nutzung:** ungefähr **3 × 45 Minuten**; die GPU wird **privat** bezahlt.
- **Auswahl des Servers:** **manuell im Webinterface**. GPU-Typ, Standort/Region und Verfügbarkeit sind variabel; Unterricht und Prüfung haben unterschiedliche Lastprofile. Üblicherweise wird **eine** Instanz gestartet.
- **Provisionierung:** Das Repository wird auf die neue Instanz **remote von GitHub geklont** und dort ausgeführt. Ein kleines Seed-Skript überbrückt die Zeit, bevor das Repository auf der VM existiert.
- **Öffentliche Client-Adresse:** `ai.donner-lab.org`, derzeit Ollama an `http://ai.donner-lab.org:11434`.
- **Beenden:** Nach Gebrauch **im Lambda-Webinterface terminieren**, Erfolg dort überprüfen. Nicht einfach `shutdown`/`poweroff`: das ist bei Lambda **keine** korrekte Terminierung und kann die Abrechnung weiterlaufen lassen. Eine vergessene GPU kann nach wenigen Tagen über 100 € kosten.
- **Wichtiges Nicht-Ziel:** **keine Lambda-API im `tabby-bootstrap`-Repository**; der Nutzer wählt GPU und Standort bewusst selbst. Ein späterer unabhängiger Watchdog ist davon getrennt.

### 1.2 Gewollter minimaler Bedienablauf

```bash
# Schritt 1 (Web): Lambda-Instanz manuell mit geeigneter GPU/Region starten; IP kopieren

# Schritt 2 (lokal, im Repo):
nix develop                          # = nix develop .#ollama

# Schritt 3 (lokal; startet Remote-Bootstrap):
./deploy-seed.sh <LAMBDA_PUBLIC_IP>

# Schritt 4 (Web): nach Unterricht/Prüfung Instanz terminieren, Terminierung überprüfen
```

**UX-Invariante:** Gegenüber dem alten Ablauf soll lediglich `nix develop` als zusätzlicher Schritt nötig sein. Kein `--target`, keine expliziten Secret-Dateien, keine Lambda-API-Keys für diesen Standardweg. Die manuelle Website-Bedienung ist **Absicht**, kein zu beseitigender Mangel.

## 2. Historische Entwicklung – warum heißt das Repo „tabby-bootstrap“?

1. Vor etwa einem Jahr wurde zunächst **Tabby** für den KI-Einsatz aufgebaut. Der Nutzer hält die frühere Empfehlung im Rückblick für eine Fehlentscheidung, weil die **kostenlose Tabby-Edition nur fünf Seats** erlaubt – für regulären Klassenunterricht ein Ausschlusskriterium.
2. Aufbauhistorie: Tabby-Setup, Schülerkonten, Modelle/DB, Backups/Restore über AWS-kompatibles Object Storage und später Hetzner. Es entstanden `tabby_setup/`, `backup/`, `restore/`, `include/s3_utils.py`, Docker- und S3-Skripte sowie besondere Secret-Injektionsmechanismen.
3. Für den normalen Unterricht wurde **Ollama** zum produktiven Target, das von VS-Code-Continue verwendet wird. Die Ollama-Pipeline benötigt aktuell nur Cloudflare-Zugangsdaten und den GitHub-/Lambda-SSH-Zugang.
4. Tabby bleibt **absichtlich** im Repository. In der freiwilligen **Microcontrollertechnik-Abschlussprüfung** nehmen mitunter nur **drei Personen** teil; die Seat-Grenze könnte dort unproblematisch sein. Die alten Tabby-Skripte dürfen **nicht** nur wegen fehlender aktueller Nutzung gelöscht werden.
5. Im Oktober 2026 erfolgte die Umstellung von selbst gebauter Secret-Injektion (`inject-secrets.sh`, `strip-secrets.sh`, redacted/generiertes Seed, Git-Hooks und Filter) auf **SOPS/age + lokalen LUKS-Vault + SSH-stdin-Transport**.
6. AWS- und Hetzner-Speicherdienste/Zugangsdaten wurden inzwischen **gekündigt**. Für Tabby wird **kein funktionsloses Fake-Secret in SOPS** angelegt. Die Tabby-DevShell ist zunächst eine deklarierte Option ohne echte Secret-Sets und nur für `--debug` nutzbar.

## 3. Architektur in einem Bild

```text
                       LOKAL (NixOS: kitty / tracy)

    NixOS-Config (über flake.lock gepinnt)     LUKS-Vault
    SOPS/age: cloudflare.sops.env             ~/.ssh/id_tabby_bootstrap
      CF_API_TOKEN, CF_ZONE_ID                    │
             │                                    │
             └── nix develop (Ollama) ────────────┘
                         │ BOOTSTRAP_TARGET=ollama
                         ▼
                  ./deploy-seed.sh <IP>
                    │          │
           SCP: seed.py       JSON über SSH-stdin
           (KEINE Secrets)   {target, remote_ip, ref, debug,
                    │         env, git_ssh_key}
                    └──────────┬───────────────┐
                               ▼               │
                      LAMBDA (neue VM)          │
                 /tmp/tabby-bootstrap-seed.py   │
                               │◄──────────────┘
                               ▼
                       seed.py (Stage 2)
                     ~/.ssh/id_tabby_bootstrap
                               │
                        GitHub-SSH-Clone
                       ~/tabby-bootstrap
                               │
                   Target/Ref aus dem Payload
                             Stage 3
                  ┌────────────┴────────────┐
                  ▼                         ▼
        ollama_setup/run_all.py    tabby_setup/run_all.py
                produktiv           derzeit gesperrt
                  │
          Cloudflare-DNS-Update
          Ollama + Modell-Download
                  │
           ai.donner-lab.org:11434
                  │
         Continue-Chat/Autocomplete
```

**Wichtige Unterscheidung:** IP-Adresse ist das **SSH-/SCP-Ziel** beim Deployment; der **DNS-Name** ist der **stabile KI-Client-Endpunkt**. Das sind unterschiedliche Verbindungen.

## 4. Die drei Stages – genaue technische Abläufe

### Stage 1 – lokal: DevShell, Validierung, Übertragung

**`flake.nix`:**

- Importiert `nixos-config` von `github:BerndDonner/NixOS-Config` und folgt deren `nixpkgs`; konkrete Version über `flake.lock`.
- `mkTargetShell "ollama" [ "cloudflare" ]` wird zu `.default` **und** `.ollama`.
- `mkTargetShell "tabby" [ ]` wird zu `.tabby` – momentan bewusst **keine** Tabby-Secrets.
- Die DevShell setzt `BOOTSTRAP_TARGET=ollama|tabby` per `extraShellHook`. **Dies ist die einzige normale Target-Auswahl.**
- Der zentrale NixOS-Helper `mkPythonDevShell` lädt das passende SOPS-Set beim Eintritt in die Shell. Aktuelle Loader-Implementierung der beigefügten NixOS-Config: `sops decrypt --output-type dotenv`, dann Shell-`eval` auf vertraute, entschlüsselte Daten. **Das `eval` ist ein möglicher späterer Härtungspunkt in der NixOS-Config**, kein Anlass, `tabby-bootstrap` erneut mit eigener Secret-Verwaltung auszustatten.
- Die `flake.lock` macht die zentrale Konfiguration reproduzierbar. Neue SOPS-Sets müssen dort bekannt/gepinnt sein; nach einer Änderung `nix flake update nixos-config`, `flake.lock` committen.

**`deploy-seed.sh`:**

1. Erwartet `./deploy-seed.sh <IP> [--debug] [--branch <ref>]` (IP als einziges Pflichtargument).
2. Validiert `BOOTSTRAP_TARGET` (`ollama` oder `tabby`), benötigte lokale Programme, `~/.ssh/id_tabby_bootstrap` (oder `SSH_KEY_PATH`) und `seed.py`.
3. Ohne `--branch` bestimmt es den lokal ausgecheckten **Git-Branch** über `git symbolic-ref --short HEAD`. Bei detached HEAD ist `--branch` Pflicht. Kein stillschweigender Rückfall auf `master`.
4. Prüft mit `git ls-remote origin`, ob Branch/Tag auf GitHub existiert; bei einem SHA prüft es die **lokale** Existenz des Commits. **Wichtig:** Der Code vergleicht nicht die lokale Commit-ID mit der Remote-Branchspitze. „Branch ist veröffentlicht“ bedeutet nicht zwingend „jeder lokale Commit ist gepusht“.
5. Baut über `bootstrap_payload.py` zuerst eine Payload als **Preflight** (Ausgabe verworfen); fehlende Secrets/ungültige IP/falscher Schlüssel stoppen den Deploy vor dem Netztransfer.
6. Kopiert die lokale `seed.py` mit `scp` zur VM nach `/tmp/tabby-bootstrap-seed.py`. Dieses Skript enthält **keine** eingebetteten Secrets.
7. Erzeugt erneut die JSON-Payload (ohne sie zu loggen) und pipet sie an `ssh -T ... "python3 -u '/tmp/tabby-bootstrap-seed.py'"`.
8. Die SSH-Optionen enthalten bewusst `StrictHostKeyChecking=no`, `UserKnownHostsFile=/dev/null`, `LogLevel=ERROR`, `IdentitiesOnly=yes`, `-i "$SSH_KEY_PATH"`. Gründe und Risiko siehe Abschnitt 7.

**`bootstrap_payload.py`:**

- Prüft IPv4/IPv6-Syntax über `ipaddress.ip_address` (kein Hostname als Pflichtargument).
- Gibt Ollama ausschließlich `CF_API_TOKEN` und `CF_ZONE_ID` weiter, selbst wenn andere Secrets in der lokalen Umgebung existieren.
- Liest den privaten Schlüssel als Text aus `SSH_KEY_PATH`, prüft grob dessen PEM-/OpenSSH-Header und transportiert ihn in `git_ssh_key`.
- Liefert die Felder `target`, `remote_ip`, `ref`, `debug`, `env`, `git_ssh_key`.
- Blockiert **Tabby ohne `--debug`** mit einer ausdrücklichen Fehlermeldung, weil dessen alte S3-/JWT-Infrastruktur nicht wiederhergestellt wurde.
- Schreibt JSON **nur für die SSH-Pipeline** nach stdout. Ausgabe nie in Terminal, Log, Issue oder Shell-History umleiten!

### Stage 2 – remote: `seed.py` + Git-Klon

**`seed.py` stammt in dieser Stage aus dem lokalen Checkout**, nicht vom GitHub-Stand. Es wird per SCP übertragen und liest seine Konfiguration per `json.load(sys.stdin)` ein.

1. Prüft das Target und das JSON-`env`-Objekt und setzt `os.environ` für nachfolgende Kindprozesse; `REMOTE_IP` und `CF_DNS_NAME=ai.donner-lab.org` werden ebenfalls gesetzt.
2. Schreibt `git_ssh_key` nach `~/.ssh/id_tabby_bootstrap` mit Modus `0600`, erzeugt `~/.ssh/config` für GitHub mit diesem Key; diese Datei darf auf der **jungfräulichen** VM überschrieben werden.
3. Füllt `~/.ssh/known_hosts` für `github.com` via `ssh-keyscan`; `StrictHostKeyChecking accept-new` gilt für GitHub in der Remote-SSH-Konfiguration. **Eine Host-Schlüsselaufnahme allein ist keine unabhängige Identitätsprüfung.** Siehe Sicherheitsnotizen.
4. Klont `git@github.com:BerndDonner/tabby-bootstrap.git` nach `~/tabby-bootstrap`, falls noch nicht vorhanden, und `git fetch origin --prune --tags`.
5. Ist `origin/<ref>` ein Remote-Branch, wird er deterministisch mit `git checkout -B <ref> origin/<ref>` ausgecheckt; andernfalls versucht das Skript `git checkout --detach <ref>` für Commit/Tag.
6. Bei `debug=true`: Meldung „cloned repository, skipping setup“, **keine** Stage 3. Sonst startet `run_setup(target)`.

**Persistenz auf der VM:** Der kopierte SSH-Private-Key bleibt derzeit in `~/.ssh/id_tabby_bootstrap`; `seed.py` in `/tmp` bleibt ebenfalls bestehen (enthält selbst keine Secrets). Die Payload wird nicht absichtlich in einer Datei gespeichert. Es gibt **kein Agent-Forwarding** und derzeit keine Key-Cleanup-Logik. Das wird bewusst im Kontext der **anschließend zu terminierenden Wegwerf-VM** betrachtet. Ein getrennt auf das Repo beschränkter GitHub-Deploy-Key wäre für eine spätere Sicherheitsverbesserung sinnvoll, ist aber **keine** Voraussetzung für die laufende SOPS-Migration.

### Stage 3 – remote: das frisch geklonte Repo läuft

`seed.py` ruft `python3 ~/tabby-bootstrap/<target>_setup/run_all.py` auf; der Name stammt aus der internen `TARGET_RUNNERS`-Tabelle.

**Ollama (`ollama_setup/run_all.py`):**

- Entdeckt alle numerisch präfixierten Python-Module im eigenen Verzeichnis, sortiert diese nach Nummer und ruft `main()` auf. Aktuell sind es **zwei** Schritte.
- `10_update_dns.py`: Cloudflare-A-Record `ai.donner-lab.org` per API lesen und vorhandenen Record updaten oder neu erzeugen; `ttl=60`, `proxied=False`, Ziel-IP ist `REMOTE_IP` aus Stage 1. Ein aktiver Token allein reicht nicht; für Änderungen braucht er passende DNS-Schreibrechte.
- `20_setup_ollama.py`: Installiert ggf. Ollama mit dessen Installationsskript, setzt einen systemd-Override `OLLAMA_HOST=0.0.0.0`, startet/neustartet den Dienst, lädt **`deepseek-coder:6.7b`** (Autocomplete) und **`qwen2.5-coder:7b`** (Chat) und entfernt andere lokal installierte Modelle. Das Entfernen ist auf der frischen Wegwerf-VM unproblematisch, auf einer langfristig genutzten Maschine **nicht**.
- Die Continue-Beispielkonfiguration ist `vscode_config/config.yaml`; sie enthält die zwei Model-Rollen und `apiBase: http://ai.donner-lab.org:11434`. Dieses Setup **verteilt die Continue-Datei nicht automatisch** an Schüler-/Schulrechner.

**Tabby (`tabby_setup/run_all.py`):**

- Historische Pipeline in nummerierten Schritten (AWS-Environment, S3-DB- und Modell-Restore, Schülerkonten, IP-Korrektur, Docker, Image-Auswahl, Start).
- Der produktive Aufruf ist **absichtlich vorher blockiert** (`bootstrap_payload.py`). Außerdem ist derzeit der Importpfad `importlib.import_module(f"setup.{name}")` veraltet: Das Paket heißt `tabby_setup`. Weitere Pfade benötigen eine eigenständige Überarbeitung, insbesondere wegen gekündigter AWS-/Hetzner-Dienste.
- Backup/Restore, `include/s3_utils.py`, `tabby_setup/`, `vscode_config/` und Hilfsskripte **nicht ungefragt entfernen**. Vor einer Reaktivierung echte Infrastruktur/Secrets/Abhängigkeiten neu definieren und gesondert testen.

## 5. Secret-Modell – vorher/nachher und Lebenszyklus

| Wert | Quelle lokal | Lokal benötigt | An GPU übertragen | Auf GPU verwendet |
|---|---|---|---|---|
| `CF_API_TOKEN` | `cloudflare.sops.env` (SOPS/age, NixOS-Config) | Ja (Ollama-DevShell) | Ja, im JSON-stdin | Cloudflare-A-Record |
| `CF_ZONE_ID` | `cloudflare.sops.env` | Ja | Ja, im JSON-stdin | Cloudflare-Zone (kein geheimer Token, aber Konfiguration) |
| `id_tabby_bootstrap` (privat) | lokaler LUKS-Vault, verlinkt nach `~/.ssh/` | Ja | Ja, als `git_ssh_key` | GitHub-Klon; nach Bootstrap weiterhin vorhanden |
| `id_tabby_bootstrap` (öffentlich) | SSH-Key-Paar | Bei initialer Berechtigung/Registrierung | Nicht als Payload-Feld | Kein Secret |
| `REMOTE_IP` | Lambda-Webinterface | Ja | Ja | DNS-Zieladresse |
| `CF_DNS_NAME` | Konstant in `seed.py` | Nein | Nicht als Secret | `ai.donner-lab.org` |
| `AWS_*`, `TABBY_*`, `SMTP_PASS` | Alte Tabby-Infrastruktur – aktuell nicht gültig | Nein im Ollama-Modus | **Nein** im Ollama-Modus | Tabby produktiv gesperrt |
| Lambda-API-Key | **Nicht eingerichtet** | Nein | **Nein** | Nicht Teil des Repos |

**Kritische Trennung:** SOPS/age ist **nur lokal** erforderlich, nicht auf Lambda. Der LUKS-Vault schützt den SSH-Private-Key langfristig auf dem lokalen Rechner. Git enthält normalen Programmcode und die Flake, **keinen** Secret-Klartext. `.gitignore` schützt vor versehentlich hinzugefügten lokalen `.env`, `*.key` etc.; bereits getrackte Geheimnisse würde das nicht aus Git entfernen.

**SOPS-Schlüssel im Nix-Store:** `flake.nix` bezieht die **verschlüsselte** Secret-Datei aus der gepinnten NixOS-Config. Die zentrale DevShell entschlüsselt beim Eintritt und exportiert die Werte in die **lokale Prozessumgebung**. Die tatsächlichen Klartextwerte sollen nicht als Nix-Derivationsargumente, Kommandozeilenargumente, Shell-Trace, Log oder Commit auftauchen. Lokale Prozesse des eigenen Nutzers und Root können unter Umständen Umgebungsvariablen lesen; das ist kein garantiert hermetisches Secret-Sandboxing.

**Einfacher Recovery-Weg:** Wenn der Cloudflare-Token erneuert wird: SOPS-Datei nur in der NixOS-Config aktualisieren, diese pushen, danach in `tabby-bootstrap` `nix flake update nixos-config` + `flake.lock` committen. Kein Seed-Template anfassen. Der lokale SSH-Key wird nicht in SOPS dupliziert.

## 6. Git und Feature-Branch-Semantik

- Die produktive Änderung wurde zunächst auf `feature/sops-target-shells` gebaut, damit ein früherer `master` als Reserve erhalten bleibt.
- DevShell-Auswahl = Target-Auswahl; Branch-Auswahl = **Git-Ref** der Stage-3-Programme. Das sind **orthogonale** Entscheidungen.
- Default-Ref ist **lokaler aktueller Branch**. `--branch <ref>` nur, wenn absichtlich ein anderes Ref benutzt werden soll. `--debug` testet Stage 2 ohne die volle Setup-Pipeline.
- **Geteilte Code-Wahrheit:** Stage 2 verwendet `seed.py` aus dem **lokalen Checkout**, Stage 3 verwendet `~/tabby-bootstrap` aus dem **veröffentlichten GitHub-Ref**. Deshalb sind uncommittete oder ungepushte Änderungen an `ollama_setup/` remote unsichtbar. `git ls-remote` prüft Existenz des Refs, nicht Commit-Gleichheit.
- Bei neu aufgesetztem Lambda-Server ist `~/tabby-bootstrap` leer; bei wiederholtem Deployment auf dieselbe Instanz erfolgt `fetch` und deterministischer Checkout des gewünschten Branchs. Dadurch kann ein `--debug`-Test und ein folgender Normal-Deploy auf derselben Instanz stattfinden.
- `flake.lock` wird von Git getrackt; neue Env-Definitionen in der NixOS-Config werden nur nach Update des Inputs sichtbar.
- **Historische Git-Altlasten entfernt:** `inject-secrets.sh`, `strip-secrets.sh`, `.gitconfig.strip-secrets`, `.githooks/*`, das alte `secrets/`-Verzeichnis sowie Sonderregeln `export-ignore` in `.gitattributes`.
- `.gitattributes` soll nur Text-/LF-Normalisierung enthalten; `.gitignore` nur allgemeine lokale Credentials, Python-Cache, Editoren und Logs. `git archive` soll daher die **getrackten** `.gitignore`- und `.gitattributes`-Dateien ganz normal enthalten.

## 7. SSH-Host-Keys: konkrete Entscheidung und kritische Einordnung

### 7.1 Gegenstand

In **`deploy-seed.sh` (lokal → Lambda)** gelten derzeit:

```bash
-o StrictHostKeyChecking=no
-o UserKnownHostsFile=/dev/null
-o LogLevel=ERROR
```

**Warum:** Lambda liefert bei jedem Anmieten eine **neue VM mit neuem SSH-Host-Key**. Frühere Deployments scheiterten bei geänderten Host-Schlüsseln/alten `known_hosts`-Einträgen. Zusätzlich können öffentliche IP-Adressen neu vergeben werden. Die Instanzen sind ausschließlich für kurzzeitige Nutzung gedacht; der Nutzer möchte **keinen interaktiven Host-Key-Abgleich vor Unterrichtsbeginn**, der den Start blockieren kann.

**Präzisierung zur DNS-Begründung:** Für SCP und SSH verwendet das Deployment ausdrücklich die **direkte Lambda-IP** aus dem Webinterface; `ai.donner-lab.org` wird erst in der Cloudflare-DNS-Phase als Client-Endpunkt aktualisiert. Der gemeinsame DNS-Name ist also **nicht die technische Ursache** der SSH-Host-Key-Konflikte. Ursache sind die neue VM, neue SSH-Host-Keys und möglicherweise wiederverwendete IPs/alte `known_hosts`-Einträge.

**Ist Abschalten zwingend?** Nein. Man könnte pro Deployment eine **frische temporäre Known-Hosts-Datei** mit `StrictHostKeyChecking=accept-new` nutzen. Sie würde alte Schlüsselkonflikte vermeiden, aber ohne zusätzliche vertrauenswürdige Host-Fingerprint-Quelle **nur TOFU (trust on first use)** ermöglichen; ein aktiver MITM beim ersten Kontakt könnte weiterhin unentdeckt bleiben. Ein wirklicher Sicherheitsgewinn erfordert eine **unabhängig verifizierte Host-Identität**, etwa einen vom Provider vertrauenswürdig bereitgestellten Fingerprint (dessen Verfügbarkeit ist hier nicht nachgewiesen).

**Bewusste Entscheidung für den aktuellen Stand:** Die bestehende SSH-Verbindungsstrategie **nicht heimlich härten oder ändern**: Sie ist im Live-Deployment erprobt und priorisiert kurze, reproduzierbare Starts. Risiko bleibt: Ohne Prüfung der Remote-Host-Identität kann ein MITM prinzipiell den Bootstrap und die übertragenen Secrets abfangen. Besonders beachten, dass der GitHub-Schlüssel über dieselbe SSH-Verbindung übertragen wird. Jede spätere Änderung muss diese Abwägung offen ansprechen und auf echten Lambda-Instanzen testen.

### 7.2 Separates Thema: Remote-VM → GitHub

`seed.py` lädt den `github.com`-Host-Key derzeit per `ssh-keyscan` in `~/.ssh/known_hosts` und setzt für GitHub `StrictHostKeyChecking accept-new`. **Das ist nicht dasselbe** wie die bewusste Deaktivierung der Prüfung für lokal → Lambda. Ein ungeprüfter `ssh-keyscan` verifiziert die Identität nicht unabhängig; falls später abgesichert, GitHubs veröffentlichte Host-Fingerprints **out-of-band** abgleichen. Auch das nicht ungeprüft mitten vor einer Unterrichtswoche umbauen.

**Quellen zum Verhalten:** [OpenSSH `ssh_config(5)`](https://man7.org/linux/man-pages/man5/ssh_config.5.html), [Lambda: Creating/managing instances](https://docs.lambda.ai/public-cloud/on-demand/creating-managing-instances/).

## 8. Netzwerk, Sicherheit, Kosten: operationelle Abwägungen

### 8.1 Continue-Verbindung

- Ollama lauscht laut `20_setup_ollama.py` mit `OLLAMA_HOST=0.0.0.0` auf Port `11434`. Das ist für externe Continue-Clients nötig.
- DNS-A-Record `ai.donner-lab.org` erhält die aktuelle Instanz-IP, TTL 60 Sekunden und `proxied=False`.
- Continue nutzt derzeit `http://` und die nackte Ollama-API **ohne integriertes Login oder HTTPS**. Zugriff sollte über Lambdas Netz-/Firewallregeln nur für tatsächlich berechtigte Netze/IPs erlaubt werden. Nicht unbesehen weltweit Port 11434 freigeben; zum Schutz von Schülerdaten und gegen fremde GPU-Nutzung sinnvollerweise eine sichere Zugangsschicht/Netzbegrenzung vorsehen.
- Die Client-Konfiguration ist ein **Beispiel im Git-Repo**, keine automatische VS-Code-Verteilung.
- Eventuelle Schul-Prüfungsnetz-Restriktionen müssen getrennt abgestimmt werden; hier wird die schulische Firewall nicht verändert.

### 8.2 Reihenfolge/Erfolgsmeldung

Cloudflare-DNS wird **vor** Ollama-Installation und Modell-Pulls aktualisiert. Währenddessen kann der DNS-Name also schon auf eine VM zeigen, auf der Ollama **noch nicht** einsatzbereit ist. Auch ein erfolgreiches `Bootstrap complete` bedeutet noch nicht, dass Clients aus dem Schulnetz Port 11434 erreichen. Teste daher danach **Continue-Chat und Autocomplete** oder eine echte Modellanfrage über das vorgesehene Netz.

### 8.3 Kosten- und Terminierungsrisiko

- Laufzeit meistens ca. **135 Minuten** zuzüglich Setup, nicht dauerhaft 24/7.
- GPU-Kosten trägt der Nutzer **privat**. Manuelles Verlassen der SSH-Sitzung, Stoppen von Ollama oder `sudo poweroff` **terminiert keine Lambda-Instanz**.
- Gewollt ist **Webinterface-Start und Webinterface-Terminierung mit Kontrolle**; das offene Browser-Tab dient als Erinnerung.
- **TODO, separat:** Kosten-Watchdog auf dem voraussichtlich stets laufenden NixOS-/Forgejo-Server `cloud`, der Lambda-Instanzen per API z. B. alle 15–60 Minuten prüft und spätestens nach einem konfigurierten Grenzwert von etwa 5 Stunden zuverlässig zu terminieren versucht und den Endzustand kontrolliert. Noch **kein Lambda-API-Key vorhanden**. Das ist weder implementiert noch Teil von `tabby-bootstrap`; niemals den API-Key an Lambda-GPU-Instanzen übertragen.
- Der Wächter wird das Vergessen reduzieren, kann aber bei Ausfall von `cloud`/Lambda-API keine absolute Kostengarantie liefern.

**Externe Grundlage:** [Lambda Billing](https://docs.lambda.ai/public-cloud/billing/), [Lambda Termination](https://docs.lambda.ai/public-cloud/on-demand/creating-managing-instances/). Quelle und Status bei künftigen Umbauten neu prüfen.

## 9. Erprobter Stand vs. noch nicht getestet

### Vom Nutzer am 09.10.2026 real bestätigt

1. `nix develop` lädt `cloudflare` und setzt `BOOTSTRAP_TARGET=ollama`.
2. Feature-Branch `feature/sops-target-shells` wurde auf GitHub veröffentlicht; `--debug`-Deployment auf einer Lambda-Instanz kopierte `seed.py`, installierte GitHub-Zugang und klonte/checkoutete **wirklich den Feature-Branch**.
3. Vollständiger Bootstrap aktualisierte den Cloudflare-DNS-A-Record, installierte/konfigurierte Ollama und zog beide Modelle erfolgreich.
4. **VS-Code-Continue-Chat** über Qwen funktionierte.
5. **VS-Code-Continue-Autocomplete** über DeepSeek funktionierte ebenfalls.
6. Die Git-Clean-/Secret-Injektions-Altlasten und das `secrets/`-Verzeichnis wurden im Feature-Branch entfernt; `.gitignore`/`.gitattributes` wurden anschließend vereinfacht.

### Nicht daraus ableiten

- Tabby sei wieder funktionsfähig: **nein**.
- Prüfsituation mit mehreren Schülern/sehr hoher gleichzeitiger Last sei durch einen Einzelclient-Test bestätigt: **nein**.
- Lambda-Firewall sei für alle Schulstandorte sicher/korrekt gesetzt: **nicht nachgewiesen**.
- Die Instanz sei vom Bootstrap automatisch terminiert worden: **nein**.
- Ein unabhängiger Watchdog existiere bereits: **nein**.
- Der Upload enthalte automatisch lokale Änderungen der Remote-Setup-Pipeline: **nein**.

### Offline-Selbsttests

```bash
python3 -m unittest discover -s tests -v
```

Sie decken Payload-Auswahl, Minimal-Secrets, Preflight und `seed.py`-Dispatch mit Mocks ab. **Kein Ersatz für den echten Netz-/GPU-/Continue-Test.** Tests dürfen weder reale Zugangsdaten ausgeben noch eine GPU-Instanz ungefragt starten.

## 10. Datei-Inventar und Zuständigkeiten

| Pfad | Rolle |
|---|---|
| `flake.nix`, `flake.lock` | Zwei Target-DevShells, NixOS-Config-Pin |
| `deploy-seed.sh` | Lokaler universeller Bootstrap-Orchestrator, Branch/Debug/IP, SCP+SSH |
| `bootstrap_payload.py` | Validiert und filtert nur target-notwendige Secrets, erzeugt stdin-JSON |
| `seed.py` | Remote-Minimalbootstrap, Schlüsselinstallation, Git-Klon, Target-Dispatch |
| `ollama_setup/run_all.py` | Dynamischer Runner nummerierter Ollama-Setup-Module |
| `ollama_setup/10_update_dns.py` | Cloudflare-DNS-Upsert |
| `ollama_setup/20_setup_ollama.py` | Ollama-Install, externes Listening, Models, Cleanup |
| `tabby_setup/*` | Historischer, geparkter Tabby-Setup-Pfad (noch nicht produktiv) |
| `backup/*`, `restore/*`, `include/s3_utils.py` | Historische Backup-/Restore-/S3-Infrastruktur, aktuell teils ohne echte Credentials |
| `vscode_config/config.yaml` | Continue-Beispiel-Konfiguration; wird nicht automatisch verteilt |
| `tests/test_bootstrap.py` | Offline-Tests für die neuen Stage-Grenzen |
| `.gitignore`, `.gitattributes` | Allgemeine Git-Hygiene, keine Secret-Injektionslogik |
| `docs/ARCHITECTURE.md` | Dieses Dokument: Entscheidungen, Invarianten, Handover |

## 11. Häufige Fehler und Diagnose

| Symptom | Ursache/Prüfung |
|---|---|
| `No bootstrap target selected` | Vorher `nix develop` bzw. `. #tabby` (ohne Leerzeichen: `.#tabby`) starten |
| `Missing required Ollama secrets` | DevShell oder gepinnte NixOS-Config falsch; SOPS-Set `cloudflare` prüfen |
| `SSH key missing` | LUKS-Vault entsperrt? Home-Manager-Symlink `~/.ssh/id_tabby_bootstrap` vorhanden? |
| `Git ref ... not published` | Feature-Branch committen und nach `origin` pushen; nicht nur lokal anlegen |
| Setup ignoriert lokale Änderung | Remote-Setup wird aus GitHub geklont; lokalen Code committen/pushen; evtl. Ref explizit wählen |
| `--debug` erfolgreich, kein DNS/Modell | Erwartetes Verhalten: `--debug` überspringt Stage 3 |
| DNS stimmt, aber Continue nicht erreichbar | Dienst noch nicht fertig, Lambda-Port 11434 nicht freigegeben, Netzfilter, Continue-Konfiguration |
| Tabby Normaldeploy scheitert früh | Erwarteter Schutz: alte S3-/JWT-Konfiguration nicht nutzbar; nur `--debug` |
| GitHub fragt nach Passphrase `bernds-desktop` | Lokales `git ls-remote origin` kann den **lokalen GitHub-Schlüssel** benutzen; `-i ~/.ssh/id_tabby_bootstrap` ist hingegen der separate Bootstrap-SSH-Aufruf. Nicht automatisch von einem einzigen Key ausgehen. |

**Nie** `set -x` in Secret-Pipelines einschalten oder `bootstrap_payload.py` unkontrolliert auf dem Terminal ausgeben: Es würde den privaten Schlüssel und Cloudflare-Token im Klartext darstellen.

## 12. Architektur-Invarianten – bitte bei künftigen Änderungen beachten

1. **Drei Stages beibehalten:** lokale Vorbereitung/Übertragung → Remote-Klon → Ausführung des remote geklonten Repos.
2. **GitHub bleibt Quelle der Remote-Setup-Programme**; nicht kommentarlos `git archive`/`rsync` des gesamten Repos statt Remote-Klon einführen.
3. **Target wird in der DevShell bestimmt**, nicht jedes Mal zusätzlich auf der CLI; `deploy-seed.sh` bleibt target-agnostisch.
4. **Standard-Bedienung bleibt** Website → `nix develop` → `./deploy-seed.sh <IP>` → Website terminieren.
5. **Ollama: echte SOPS-Secrets**, Tabby: **keine Fake-Secrets**, bis der historische Pfad ausdrücklich neu aufgebaut wird.
6. **SSH-Lambda-Host-Key-Entscheidung nicht stillschweigend rückgängig machen**; ephemeral-host-Probleme, MITM-Risiko und Live-Test berücksichtigen.
7. **Tabby/Backup/Restore-Code nicht ungefragt löschen**; Prüfungseinsatz mit drei Kandidaten bleibt eine Option.
8. **Kein Lambda-API-Key in `tabby-bootstrap`**. Eventueller Watchdog gehört als unabhängige Infrastruktur auf `cloud`.
9. **Privat bezahlte Minuten sind ein Designparameter**: unnötige Tests auf echter GPU vermeiden; keine Hintergrund-Provisionierung ohne Anweisung.
10. **Erfolg differenzieren:** Setup-Log ≠ Netzwerk-Erreichbarkeit ≠ funktionierende Continue-Clientfunktion unter Unterrichtslast.
11. **SOPS nur zentral in NixOS-Config** und privater SSH-Schlüssel im LUKS-Vault; keine neue Secret-Generierung in Python-Quellcode.
12. **Keine Secrets in Logs, Commit, Nix-Store oder Testartefakten**; wenn ein Secret möglicherweise committed wurde, eigene Incident-Prüfung durchführen (Git-Historie, Rotation).

## 13. Offene Aufgaben (nicht Teil des gegenwärtigen Dokumentations-Updates)

- **Watchdog auf `cloud`:** Separates Projekt. Nach manuellem Lambda-Start überwachen; Zeitgrenze und Alarm-/Terminierungslogik später festlegen. Vorher Lambda-API-Key beschaffen und sicher speichern; keine Abhängigkeit für Ollama-Deploy einbauen.
- **Tabby reaktivieren:** S3-/Restore-Konzept ersetzen, alte Importpfade korrigieren, Docker-/Lizenz-/Seat-Situation aktuell überprüfen, echte Secrets neu definieren. Erst dann Produktions-Target freischalten.
- **Optionale Sicherheitsverbesserungen:** Host-Fingerprints unabhängig prüfen, GitHub-Host-Fingerprints pinnen, getrennten read-only GitHub-Deploy-Key verwenden, Schlüssel am Ende des Bootstrap entfernen, HTTP/Ollama mit Netzwerkregeln/Proxy absichern. Keine ungeprüften Ad-hoc-Änderungen kurz vor Unterricht/Prüfung.
- **Automatische Readiness-Checks** mit Ollama-Modellanfrage über den tatsächlichen Client-Zugriffsweg.
- **Zentrale SOPS-DevShell-Härtung:** `eval` im NixOS-Config-Loader langfristig durch sichere Datenverarbeitung ersetzen; **nicht** lokal doppelt implementieren.

## 14. Quellen und Verifizierungsstatus

**Primärquellen:** Tatsächliche Python-/Shell-/Nix-Dateien in `tabby-bootstrap02.zip` und `nixos-config13(1).zip`, ergänzt durch die vom Nutzer am 09.10.2026 geteilten erfolgreichen Terminal-Logs und Continue-Screenshots. Historische Gründe und Betriebspräferenzen stammen aus der expliziten Nutzererklärung, nicht aus dem Code. Keine Secret-Klartexte sind in dieser Dokumentation enthalten.

**Externe Referenzen:** [OpenSSH ssh_config(5)](https://man7.org/linux/man-pages/man5/ssh_config.5.html), [Lambda-Instanzen starten/verwalten/terminieren](https://docs.lambda.ai/public-cloud/on-demand/creating-managing-instances/), [Lambda-Abrechnung](https://docs.lambda.ai/public-cloud/billing/), [Nix Flake Update](https://nix.dev/manual/nix/2.31/command-ref/new-cli/nix3-flake-update.html). Externe Dienste ändern sich; Daten künftig erneut prüfen.

**Dokumentationsregel für zukünftige Assistenten:** Bei Projektfragen zuerst README + diese Architektur lesen, danach **aktuelle** Dateien untersuchen. Bei Widersprüchen zwischen Doku und Code den Nutzer darauf hinweisen, statt einen der beiden Stände stillschweigend als Wahrheit auszugeben. Nutzerziel und Kostenrestriktionen haben Vorrang vor abstrakter „sauberer“ Neugestaltung.
