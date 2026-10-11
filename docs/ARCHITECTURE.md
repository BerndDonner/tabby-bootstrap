# tabby-bootstrap – Architektur, Betrieb und Entwicklungsentscheidungen

**Stand: 11.10.2026 · Quelle: hochgeladenes `tabby-bootstrap02(1).zip` und
anschließender vereinbarter Umbau.** Dieses Dokument beschreibt den
Snapshot-/DAG-Ansatz. Der neue Normalmodus wurde am 11.10. auf Lambda
erfolgreich mit **41 s gesamter Deployment-Zeit** getestet. Die nachträgliche
Umstellung der Modell-Fortschrittsanzeige auf die Ollama-JSON-API hat bislang
nur Offline-Tests durchlaufen; sie benötigt noch einen separaten Live-Test.

> **An künftige Assistenten/Entwickler:** Nutzerinvarianten nicht ohne explizite
> Rücksprache ändern. Die GitHub-Clone-, Branch-Override- und Remote-Key-Logik
> wurde **absichtlich entfernt**. Bei Abweichungen zwischen Doku und Code die
> aktuelle Implementierung prüfen und Widersprüche benennen. Nicht aus dieser
> Datei ableiten, dass beliebige GPU-Container bereits unterstützt werden.

## 1. Zweck, Einsatzrealität und UX

Eine einzelne, kurzlebig gemietete GPU für Softwareentwicklungs- oder MCT-
Unterricht/Prüfung stellt zwei 7B-Modelle zentral für VS Code Continue bereit.
Typischer Unterricht dauert 3 × 45 Minuten; **die GPU wird privat bezahlt**.
Region und GPU nach Verfügbarkeit manuell im Lambda-Webinterface auswählen,
Instanz dort starten; am Ende **über die Website terminieren und verifizieren**.
Nicht einfach `poweroff` ausführen. Es gibt im Repository bewusst **keinen
Lambda-API-Key, keine Provider-API und keine automatische Terminierung**.

Standardablauf bleibt exakt:

```bash
nix develop                    # Default: Ollama
./deploy-seed.sh <IP>          # keine --branch- oder --target-Parameter
# GPU nach der Stunde auf der Provider-Website terminieren
```

`nix develop .#tabby` wählt weiterhin die geparkte historische Alternative;
Tabby erlaubt zurzeit nur `--debug`. `SSH_USER` und `SSH_KEY_PATH` sind optionale
Umgebungsvariablen für die **Verbindung** zur VM, keine neuen CLI-Parameter.

## 2. Entscheidungen und Motivation (KISS)

### 2.1 Local HEAD ist einzige Codequelle

- **Kein Remote-Git-Clone**: kein GitHub auf dem GPU-Server, kein Deploy-Key in
  Secret-Payload, kein `git fetch`, kein Remote-Branch und keine Historie.
- **Kein `--branch`**: immer den gerade lokal ausgecheckten `HEAD` archivieren.
  Branch und Commit-SHA sind nur **Diagnose-Metadaten**; Git kennt remote keinen
  Branch, weil `.git` nicht übertragen wird.
- **Kein Origin-Abgleich**: Ein unpublizierter lokaler Commit ist ausdrücklich
  zulässig. GitHub-Verfügbarkeit darf das Deployment nicht blockieren.
- **Clean Working Tree ist zwingend**, in beiden Modi: `git status --porcelain
  --untracked-files=all` darf nichts melden. Sonst committen oder stashen
  (inklusive untracked: `git stash push -u`). Ignorierte Dateien werden nicht
  übertragen. `git archive HEAD` nimmt ausschließlich versionierte Dateien im
  Commit und respektiert eventuelle `export-ignore`-Attribute.
- Die SHA-256-Prüfsumme des Tar-Archivs wird **vor dem Entpacken** auf dem
  GPU-Server überprüft. Sie garantiert Byteidentität des Transports, nicht
  die Identität mit einem anderen GitHub-Branch.

### 2.2 Statischer DAG statt Make, Ninja, systemd oder Custom-Framework

Alle Task-Skripte und `ollama_setup/tasks.json` kommen aus demselben Archiv.
Es gibt **keine dynamische Graph-Erweiterung** nach einem Git-Clone. Ein kleiner
Python-Runner verwendet ausschließlich die **Standardbibliothek** für DAG-
Validierung, parallele Subprozesse, Fehler-/Abbruchbehandlung, Live-Logs und
Task-spezifische Secret-Umgebungen. Keine Dependency-Scheduler-Abhängigkeit
auf jungfräulichen GPU-VMs. `systemd` bleibt auf klassischen Ubuntu-VMs für
den *dauerhaft laufenden* Ollama-Dienst zuständig, nicht für die Provisionierung.

### 2.3 Frühestmöglicher DNS-Start

Cloudflare DNS ist ein unabhängiger Task ohne Abhängigkeit von Ollama.
Er startet parallel zur Ollama-Installation, sobald der kleine Code-Snapshot
auf der VM verfügbar ist. **Nicht** auf Modelldownloads oder Readiness warten,
um DNS erst dann zu ändern: DNS-Propagation soll die lange Installation
überlappen. Der DNS-Task benötigt allein `CF_API_TOKEN` und `CF_ZONE_ID`.

## 3. Laufzeitarchitektur

```text
LOKAL: devShell (BOOTSTRAP_TARGET=ollama|tabby, SOPS cloudflare)
  deploy-seed.sh
    ├─ git status: clean? | git rev-parse HEAD | branch metadata
    ├─ bootstrap_payload.py --validate-only (IP, Secret-Pflicht, Tabby-Sperre)
    ├─ git archive --format=tar HEAD (keine Secrets, kein .git)
    ├─ sha256sum + scp (temporärer Tar)
    └─ ssh: sha256sum --check, tar entpacken, atomarer Arbeitsverzeichniswechsel
REMOTE: ~/tabby-bootstrap/{seed.py,task_runner.py,ollama_setup,...}
  SSH stdin: Target, IP, Branch/Commit-Metadaten, benötigte Secret-Werte
    seed.py
      ├─ --debug: ~/.config/tabby-bootstrap/debug.json (0600), kein Setup
      └─ normal: TaskExecutor.run() mit Secrets nur im RAM
                    ├─ dns -----------------------------------┐
                    └─ install_ollama -> configure_ollama     │
                                             ├─ pull_chat     │
                                             └─ pull_autocomplete
                                                    └─ cleanup_models
                                                      └─ ready <---------┘
```

**Transport:** `deploy-seed.sh` kopiert ein temporäres Tar nach
`~/tabby-bootstrap-source.tar`; SSH prüft dessen SHA-256 und entpackt in einen
Staging-Ordner. Beim Ersatz des alten Arbeitsverzeichnisses wird dessen vorige
Version unter `~/tabby-bootstrap.previous` abgelegt. Der SHA-Vergleich schützt
gegen beschädigte oder unvollständige Übertragung. In Debug bleibt die
Original-Tar-Datei zur Wiederherstellung; nach erfolgreichem Normalsetup wird
sie gelöscht. Bei Fehlern bleiben Dateien zur Untersuchung zurück, aber im
**Normalmodus keine Debug-Secret-Datei**.

**Über SSH authentifiziert sich der *lokale* Rechner** mit seinem vorhandenen
Schlüssel unter `~/.ssh/id_tabby_bootstrap`. Der Schlüssel bleibt **lokal**.
Es gibt kein SSH-Agent-Forwarding und keinen Remote-GitHub-Deploy-Key. Die
SSH-Verbindung verwendet für wechselnde Ephemeral-VM-IPs weiterhin
`StrictHostKeyChecking=no`, `UserKnownHostsFile=/dev/null` und `IdentitiesOnly=yes`
(**MITM-Risiko bewusst in Kauf genommen; nicht ungefragt ändern**). Das DNS-
Alias der Continue-Clients ist kein Argument, die Fingerprint-Policy beim
SSH-Transport ungeprüft zu ändern.

## 4. Secret-Lebenszyklus und Fehlergrenzen

**Lokal** lädt `nix develop` das Cloudflare-Secret-Set durch den in `flake.lock`
gepinnten `NixOS-Config`-Input mit SOPS/age; eine separate Secret-Kopie unter
`tabby-bootstrap/secrets` ist ausdrücklich verboten. Der private SSH-Schlüssel
kommt aus einem kleinen LUKS-Vault und dient nur dem **lokalen SSH-Login**.

1. `bootstrap_payload.py` liest `ollama_setup/tasks.json`, validiert es und
   bildet die Vereinigung der dort deklarierten Secret-Namen. Nur diese werden
   aus der DevShell-Umgebung in den JSON-Payload aufgenommen.
2. Das lokale Preflight prüft alle Werte, ohne etwas auszugeben. Ein zweiter
   Aufruf schreibt den JSON-Payload ausschließlich in die Pipe zu SSH-stdin.
   **Nie** `set -x`, Payload auf stdout anzeigen oder in Logs kopieren.
3. `seed.py` hält im **Normalmodus** den Payload nur im Prozessspeicher und
   übergibt ihn direkt an `task_runner.execute`. Keine Speicherung in `.env`,
   `/tmp`, im Git-Repo oder in Bash-History.
4. `TaskExecutor` entfernt die bekannten Secret-Namen aus der geerbten Umgebung
   und erstellt pro Subprozess eine eigene Env mit **nur den deklarierten
   Secrets**. DNS erhält CF_API_TOKEN/CF_ZONE_ID. Installer, Ollama-
   Konfiguration und Modelldownloads erhalten keine Cloudflare-Credentials.
5. Im **Debug-Modus** wird ausschließlich der geschützte Kontext unter
   `~/.config/tabby-bootstrap/debug.json` gespeichert (Dateimodus `0600`,
   Verzeichnis `0700`). Er beinhaltet **Klartext-Credentials**. Manuelle
   Aufrufe über `task_runner.py` lesen ihn, aber Login-Shells laden ihn **nicht**
   automatisch. Normaldeployment löscht eine eventuell vorhandene Debug-Datei.
   Die Debug-Instanz bleibt nicht unbegrenzt bestehen: anschließend in der
   Provider-Weboberfläche terminieren und ggf. Datei vorher löschen.

**Einschränkungen:** Prozess-Environment ist keine Sandbox gegenüber root oder
dem Benutzer, unter dem der Task läuft. Der Official-Ollama-Installer wird per
HTTPS geladen und ausgeführt und damit grundsätzlich fremdem Installationscode
vertraut. Die VM bietet zurzeit keinen Login-/API-Schutz am öffentlichen Port
11434. Eine Einschränkung auf nur Schul-IP würde Distanzschüler ausschließen;
ein optionales Auth-/Netzkonzept ist ein separates Projekt.

## 5. Task-Graph, Bedienung und Semantik

Manifest: `ollama_setup/tasks.json`, Format `{"version":1,"tasks":{...}}`.
Für jeden Task sind genau `script`, `after` und `secrets` vorgeschrieben.
IDs, Pfade (nur `.py` innerhalb des Repos), fehlende Kanten und Zyklen werden
**vor der Ausführung** validiert. Die Reihenfolge innerhalb eines DAG wird nur
durch `after` bestimmt. Präfixe alter Dateinamen haben keine Scheduling-Wirkung.

| Task-ID | Nach | Secrets / Aktion |
|---|---|---|
| `dns` | – | CF_API_TOKEN, CF_ZONE_ID; A-Record `ai.donner-lab.org`, TTL=60, `proxied=false` |
| `install_ollama` | – | keine; offiziellen Installer ggf. ausführen |
| `configure_ollama` | install_ollama | keine; Service auf `0.0.0.0:11434` konfigurieren, starten, lokale API prüfen |
| `pull_chat` | configure_ollama | keine; `qwen2.5-coder:7b` |
| `pull_autocomplete` | configure_ollama | keine; `deepseek-coder:6.7b` |
| `cleanup_models` | beide Pulls | keine; andere, nicht benötigte Modelle entfernen (historisches Verhalten) |
| `ready` | dns, cleanup_models | keine; lokale API und beide Modelle auf Vorhandensein prüfen |

Der Standard-Scheduler hat **vier Worker**. Tasks laufen in getrennten
Subprozessen, Ausgabe erhält ein `[task-id]`-Präfix. Unabhängige Tasks starten
früh; bei einem Fehler werden abhängige Tasks nicht gestartet, laufende
Prozessgruppen erhalten ein SIGTERM, und `seed.py` meldet einen Fehlerstatus.
Eine automatische Wiederholung, ein externes Prozess-Framework und Provider-
APIs sind **nicht implementiert**. Parallelität der beiden Ollama-Modell-Downloads kann
sich gegenseitig beeinflussen und muss live gemessen werden; bei Bedarf eine
explizite Ressourcensperre oder Kante einführen, **nicht** blind serialisieren.

**Logging:** Jeder Task hat genau einen gekapselten stdout/stderr-Stream. Der
Runner liest dessen Bytes inkrementell (UTF-8), entfernt Terminal-Steuerzeichen
und unterscheidet normale `\n`-Zeilen von `\r`-Fortschrittsständen (z. B.
`curl`). Normale Zeilen werden sofort mit `[task-id]` geloggt;
`\r`-Updates höchstens etwa alle 2 s, der abschließende Stand zusätzlich.
**Modell-Downloads** verwenden dagegen Ollamas lokale NDJSON-API `POST /api/pull`
(ohne weitere Python-Abhängigkeiten) und geben nur Phasenwechsel, etwa
alle zwei Sekunden einen aktuellen Fortschritt und Abschluss aus.
API-Fehler oder ein vorzeitiges Ende ohne `success` lassen den Task fehlschlagen.
Das Logging bleibt durch denselben Lock wie bisher serialisiert; bekannte
Secret-Werte werden vor dem Schreiben ersetzt. Jeder Task meldet seine
Wall-Clock-Dauer via `time.monotonic()`; `[bootstrap] TOTAL` folgt erst nach
Abschluss bzw. Abbruch aller Worker und umfasst nur den Remote-DAG.
`deploy-seed.sh` meldet zusätzlich die **Gesamtdauer einschließlich lokaler
Vorbereitung, SSH-Transport und Remote-Ausführung** (Bash `SECONDS`). Es gibt
keine zusätzliche Scheduler-Abhängigkeit und keine Änderungen am Task-Graphen.

**Manuelles Debugging:** nach `./deploy-seed.sh <IP> --debug` per SSH anmelden:

```bash
cd ~/tabby-bootstrap
python3 task_runner.py --list
python3 task_runner.py dns                 # genau EIN Task, keine Vorgänger
python3 task_runner.py install_ollama
python3 task_runner.py configure_ollama
python3 task_runner.py pull_chat
python3 task_runner.py pull_autocomplete
python3 task_runner.py cleanup_models
python3 task_runner.py ready
# oder alle Abhängigkeiten automatisch:
python3 task_runner.py --all
```

`--debug` selbst **führt keinen einzigen Setup-Task aus**, einschließlich DNS.
Es überträgt denselben Snapshot wie der Normalmodus und speichert lediglich
Klartext-Secrets geschützt für spätere Task-Aufrufe. Auf der GPU gibt es **kein
`.git`**, also auch kein `git status`, `git restore`, `git pull` oder eine
Historie; das Originalarchiv bleibt zur Wiederherstellung. Bei einem zweiten
Deploy wird der vorherige Arbeitsstand nach `.previous` verschoben. Alte
`tabby_setup/run_all.py` und `ollama_setup/20_setup_ollama.py` sind historische
bzw. manuelle Einstiegspunkte, nicht die Steuerung des neuen DAG.

## 6. Reale Betriebsgrenzen, Verfügbarkeit und Kosten

- Ollama lauscht auf `0.0.0.0:11434`, Domain `ai.donner-lab.org`, erreichbar
  über `http://ai.donner-lab.org:11434`, sofern Provider-Firewall und Netz den
  Zugriff erlauben. Continue-Konfiguration liegt unter `vscode_config/` und
  wird nicht automatisch an Schulgeräte verteilt.
- DNS-TTL 60 s senkt Caching, garantiert aber weder sofortige Propagation noch
  eine sofortige Client-Verbindung. DNS läuft absichtlich **früh parallel**.
- Readiness bestätigt nur den lokalen Ollama-API-Status und das Vorhandensein
  beider Modelle; sie testet nicht Ende-zu-Ende Continue-Chat/Autocomplete und
  nicht 10 parallele Schüler. GPU-Leistungsbenchmark wäre ein unabhängiger Task.
- Kurzlebige GPU: private Kosten! Lambda nach der Sitzung im Webinterface
  terminieren. `sudo poweroff` oder allein Dienste stoppen **nicht** als
  Terminierungsnachweis betrachten.
- RunPod-/Vast.ai-Container können ohne systemd laufen und können Port-Mappings
  und SSH-Ports anders behandeln. Der Python-Scheduler ist portabel, aber der
  gesamte Bootstrap ist dadurch **noch nicht automatisch hoster-neutral**.
  Capability-basierte Runtime-Auswahl und Port-Proxies sind ein späteres Thema.

## 7. Historie und bewusst nicht bearbeitete Komponenten

Früher war Tabby das zentrale System, inklusive Docker, Nutzeranlage, S3-
Backups über AWS-/Hetzner-Infrastruktur und aufwändiger Remote-Key-/Secret-
Mechanismen. Für gewöhnlichen Unterricht ist die kostenfreie Tabby-Lizenz
wegen fünf Seats nicht brauchbar; bei einer Abschlussprüfung mit etwa drei
Teilnehmenden möglicherweise interessant. Die alten Speicherzugänge sind
abgelaufen. Deshalb ist ein regulärer Tabby-Start **lokal blockiert**, während
`nix develop .#tabby` plus `--debug` den gemeinsamen Snapshot-Transport testen
kann. Tabby-Skripte sowie `backup/`, `restore/`, `include/` bleiben erhalten,
auch wenn insbesondere der alte `tabby_setup/run_all.py`-Importpfad inzwischen
nicht stimmt. **Nicht löschen und nicht als produktiv deklarieren.**

Die Flake/SOPS-Integration bleibt an `NixOS-Config` gebunden. Änderungen an
Secrets/SOPS-Architektur, Docker, Hetzner-Speichern, Tabby-Seats oder
`vscode_config/config.yaml` gehören nicht zu diesem Umbau.

## 8. Sicherheit und bekannte offene Risiken

- Das Deaktivieren der SSH-Host-Key-Prüfung schützt nicht vor MITM; für die
  wegwerfbaren dynamischen IPs wurde dies als pragmatischer Kompromiss gewählt.
- Ollama-Port 11434 ist derzeit öffentlich ohne starke Authentifizierung;
  unbedingt Provider-Firewall und Vertrauensgrenzen beachten. Distanzschüler
  können unterschiedliche öffentliche IPs haben.
- Im Debug-Modus bleiben Credentials absichtlich bis zur manuellen Entfernung
  oder Instanzterminierung auf der GPU. Keine Logs oder Shell-Ausgaben, die
  Payload, API-Token, Secret-Datei oder gesamte Umgebung ausgeben.
- Es gibt **keinen API-gestützten Kosten-Watchdog**. Separates späteres Projekt
  auf dem dauerhaften Forgejo/NixOS-Server `cloud` könnte GPU-Mietdauern
  überwachen und nach mehreren Stunden ggf. stoppen. Ein API-Key gehört nicht
  auf die GPU oder in diesen Bootstrap.
- Externe Installationsquelle `https://ollama.com/install.sh` und öffentliche
  Hoster bleiben Vertrauens-/Verfügbarkeitsrisiken.

## 9. Teststatus und Wartungscheckliste

Der vorherige SOPS-/Remote-Clone-Bootstrap lief am **09.10.2026** auf Lambda.
Am **11.10.2026** wurde auch der neue Snapshot-/DAG-Pfad auf Lambda erfolgreich
geprüft: `--debug` mit anschließendem manuellem `task_runner.py --all`,
parallelem DNS/Installer-Start, parallelen Modelldownloads und VS Code Continue.
`./deploy-seed.sh <IP>` **ohne `--debug`** wurde anschließend erfolgreich
ausgeführt: **41 s Gesamtdauer**, davon **35,1 s Remote-DAG**.
DNS: 0,5 s; Ollama-Installation: 9,5 s; Konfiguration: 2,8 s;
Chat-Modell: 13,9 s; Autocomplete-Modell: 22,6 s. Alle sieben Tasks erfolgreich.
Offline-Prüfung:

```bash
python3 -m unittest discover -s tests -v
bash -n deploy-seed.sh
```

Beim nächsten Live-Test die **strukturierte JSON-API-Modellausgabe** und
weiterhin DNS, GPU-Prozess, Ollama-API und echte Continue-Anfragen prüfen.
Time-to-Ready hat Vorrang vor kosmetischer Serialisierung. Bei Änderungen
immer Code, Tests, README und diese Datei zusammen aktualisieren.

**Offene Aufgaben:** JSON-Pull-Logging auf Lambda prüfen, Benchmark mit etwa zehn
Continue-Clients, robuste sichere Ollama-Port-Freigabe inkl. Distanzunterricht,
evtl. GPU-Container-Runtimes und dynamische Ports, Tabby-Reaktivierung (nur auf
Auftrag), unabhängiger Kosten-Watchdog auf `cloud`.
