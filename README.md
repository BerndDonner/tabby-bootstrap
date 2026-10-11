# tabby-bootstrap

**Temporärer KI-Server für Unterricht und Prüfungen.** Ein lokaler, commitgetreuer
Code-Snapshot wird per SSH auf eine kurzfristig gemietete GPU-VM übertragen.
Dort installiert ein kleiner **Python-DAG-Scheduler** Ollama und die benötigten
Modelle; unabhängige Tasks wie das **Cloudflare-DNS-Update starten parallel**.
Das Repository wird **nicht auf der GPU von GitHub geklont**.

**Stand: 11.10.2026.** Der neue Snapshot-/DAG-Pfad wurde auf einer echten
Lambda-GPU mit `--debug`, anschließend `task_runner.py --all`, DNS-Update,
beiden Modellen und VS Code Continue erfolgreich getestet. Der **Normalmodus**
wird noch separat getestet. Tabby bleibt als historischer, momentan nicht
produktionsfähiger Pfad erhalten.

## Normaler Ablauf

1. Auf der Website von [Lambda Cloud](https://cloud.lambda.ai/) eine GPU-Instanz
   manuell starten und ihre **öffentliche IP** notieren.
2. Lokal im **sauberen, committeten Git-Checkout**:

   ```bash
   nix develop                     # Ollama, alternativ nix develop .#ollama
   ./deploy-seed.sh <IP>
   ```

3. Bei erfolgreichem Abschluss Continue mit `http://ai.donner-lab.org:11434`
   verbinden und nach Möglichkeit eine echte Chat- und Autocomplete-Anfrage testen.
4. **Nach dem Unterricht auf der Anbieter-Website die GPU terminieren und die
   Terminierung überprüfen.** Nur `shutdown`, SSH-Logout oder Stoppen von Ollama
   vermeidet nicht zuverlässig weitere Mietkosten.

Typischer Einsatz: **3 × 45 Minuten**. GPU-Typ, Region, Start und Terminierung
bleiben bewusst manuell. Dieses Repo verwendet **keine Provider-API**.

## Voraussetzungen und Secrets

- `nix develop` lädt aus der **externen** `NixOS-Config` über SOPS/age
  `CF_API_TOKEN` und `CF_ZONE_ID`. Keine Secrets in dieses Git-Repo kopieren.
- Der **lokale** SSH-Schlüssel `~/.ssh/id_tabby_bootstrap` (aus dem LUKS-Vault)
  authentifiziert den SSH-Zugang zur GPU. Er wird **nicht** auf die GPU kopiert;
  dort braucht es weder einen GitHub-Schlüssel noch Git.
- Die GPU ist über SSH erreichbar (Standarduser `ubuntu`), hat Python 3 und
  für Ollama eine geeignete NVIDIA-GPU. Das aktuelle Lambda-Setup nutzt sudo
  und systemd für den Ollama-Dienst. Port **11434/TCP** muss für Continue
  entsprechend geöffnet sein.
- Das lokale Repo muss **vollständig clean** sein: keine gestagten, unstaged
  oder nicht ignorierten unversionierten Dateien. Sonst wird **vor der
  Übertragung abgebrochen**. Änderungen vorher committen oder z. B.
  `git stash push -u` verwenden. `origin`, GitHub und Push-Status werden
  **nicht geprüft**. Der aktuelle lokale `HEAD` ist die einzige Codequelle.

Mit `nix flake update nixos-config` lässt sich die gepinnte zentrale
NixOS-Config nach Änderungen aktualisieren (und anschließend committen).

## So funktioniert das Deployment

```text
Lokal: nix develop → ./deploy-seed.sh <IP>
  ├── Git-Preflight: Working Tree clean, HEAD/Commit bestimmen
  ├── git archive HEAD → tar + SHA-256
  ├── SCP: ausschließlich Code-Snapshot, keine Secrets
  └── SSH: Prüfsumme verifizieren, Snapshot nach ~/tabby-bootstrap entpacken
        └── SSH-stdin: JSON-Payload mit Target/IP/Commit/Target-Secrets
              └── seed.py
                   ├── --debug: geschützten Secret-Kontext ablegen, STOP
                   └── normal: task_runner.py startet parallelen DAG
                       ├── dns ──────────────────────────────────────┐
                       └── install_ollama → configure_ollama         │
                                ├── pull_chat ──────────┐             │
                                └── pull_autocomplete ──┴→ cleanup ─┴→ ready
```

Alle Skripte, der Scheduler und `ollama_setup/tasks.json` kommen **aus demselben
lokalen Commit**. `git archive` enthält bewusst **keine `.git`-Historie**.
Archivbytes werden auf der GPU per SHA-256 geprüft. Bei Wiederholung wird das
vorherige Arbeitsverzeichnis unter `~/tabby-bootstrap.previous` abgelegt
(die vorherige Sicherung wird dabei ersetzt).

Task-IDs, Abhängigkeiten, Skripte und pro Task erlaubte Secrets stehen in
[`ollama_setup/tasks.json`](ollama_setup/tasks.json). Ein `ThreadPoolExecutor`
überwacht die externen Python-Prozesse; er implementiert **keine** Paketverwaltung.
Die Cloudflare-Credentials erreichen **nur** den DNS-Prozess. Normale Läufe
speichern sie nicht auf der GPU-Festplatte; die Übergabe erfolgt über SSH-stdin
und Prozessumgebungen. DNS-TTL **60 s**, Cloudflare-Proxy **aus**.

**Fortschritt und Laufzeiten:** Jede Ausgabe der Tasks erhält ein
`[task-id]`-Präfix. Normale Logzeilen erscheinen sofort. Die mit `\r`
überschriebenen Fortschrittsanzeigen von `curl`/`ollama pull` werden etwa alle
**2 Sekunden** protokolliert; der letzte Fortschrittsstand geht nicht verloren.
Jeder Task meldet `OK (12.3s)` bzw. `FAILED (exit 1, 12.3s)`. Nach dem gesamten
Graphen erscheint `[bootstrap] TOTAL ...` (nur **Remote-DAG**); die abschließende
`Total deployment time`-Zeile von `deploy-seed.sh` misst zusätzlich lokalen
Preflight, Übertragung und Remote-Ausführung. Beide Zeiten sind Wall-Clock-Zeiten:
parallel ausgeführte Taskdauern dürfen sich überlappen.

Die Ollama-Modelle bleiben:

| Verwendung | Modell |
|---|---|
| Autocomplete | `deepseek-coder:6.7b` |
| Chat | `qwen2.5-coder:7b` |

Die Beispiel-Konfiguration für VS Code Continue liegt unter
[`vscode_config/config.yaml`](vscode_config/config.yaml). Sie wird nicht an
Schulrechner verteilt. Ein lokaler Readiness-Test bestätigt Ollama und die
beiden Modellnamen; **externe Port-Erreichbarkeit und DNS-Propagation sind damit
nicht garantiert**. Gleichzeitige Schülerlast ist noch nicht gebenchmarkt.

## Debug-Modus: derselbe Snapshot, kein Setup

```bash
./deploy-seed.sh <IP> --debug
# danach auf der GPU (mit den gleichen SSH-Optionen wie beim Deploy):
cd ~/tabby-bootstrap
python3 task_runner.py --list
python3 task_runner.py dns
python3 task_runner.py install_ollama
python3 task_runner.py configure_ollama
python3 task_runner.py pull_chat
python3 task_runner.py pull_autocomplete
python3 task_runner.py cleanup_models
python3 task_runner.py ready
# oder ab hier vollständigen DAG ausführen:
python3 task_runner.py --all
```

`--debug` ändert **kein DNS**, installiert nichts und lädt keine Modelle.
Quellcode und das Originalarchiv `~/tabby-bootstrap-source.tar` bleiben für
Fehlersuche und Offline-Wiederherstellung erhalten. Ein Git-Checkout im engeren
Sinne existiert remote nicht: Skripte sind bearbeitbar, `git status`, `git pull`
usw. dort aber **nicht möglich**.

Damit die Secrets bei späteren SSH-Logins verfügbar bleiben, liegt **nur im
Debug-Modus** `~/.config/tabby-bootstrap/debug.json` (`0600`, Verzeichnis `0700`)
mit Klartext-Secrets. `task_runner.py` liest sie beim manuellen Aufruf und gibt
sie nur den deklarierten Tasks weiter. Sie werden **nicht in `.bashrc` geladen**.
Die Debug-Instanz ist **nicht für dauerhaften Betrieb** gedacht: nach Abschluss
terminieren; bei Bedarf die Datei vorher selbst löschen. Ein späterer normaler
Lauf entfernt einen eventuell noch vorhandenen Debug-Kontext.

Ein Einzel-Task-Aufruf startet **keine** Vorgänger automatisch. Er kann daher
fehlschlagen, wenn du notwendige Schritte überspringst. `--all` nutzt den DAG.

## Tabby (bewusst geparkt)

```bash
nix develop .#tabby
./deploy-seed.sh <IP> --debug   # Code-Snapshot + Debug-Umgebung
```

**Ohne `--debug` wird Tabby beim lokalen Preflight abgelehnt.** Die alten
AWS-/Hetzner-Zugänge existieren nicht mehr; es werden keine Dummy-Secrets
angelegt. `tabby_setup/`, `backup/`, `restore/`, `include/` und die historischen
Skripte bleiben für eine eventuelle spätere Reaktivierung erhalten. Die freie
Tabby-Edition ist für zehn Schüler wegen ihrer Seat-Grenze nicht geeignet.

## Tests und Dokumentation

```bash
python3 -m unittest discover -s tests -v    # Offline, ohne GPU
```

Für Hintergründe, Sicherheitsentscheidungen, das vereinbarte KISS-Design und
TODOs siehe **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**. Vor Änderungen
an Deployment oder Secret-Handling zuerst dieses Dokument lesen.
