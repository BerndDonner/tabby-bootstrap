#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create student accounts in Tabby from a UTF-8 list like:
    "Huber Alexander" <Alexander.Huber@sabel.education>
    "Günther Engelmaier" <Engelmaier.Guenther@sabel.education>

Usage:
    python create_students.py students.txt
"""

import sys, sqlite3, secrets, csv, re, smtplib, subprocess
from datetime import datetime, UTC
from email.message import EmailMessage
from pathlib import Path

# ---------------------------------------------------------------------
# Optional mail settings (disabled by default)
# ---------------------------------------------------------------------
MAIL_ENABLED = False
SMTP_SERVER = "smtp.yourschool.de"
SMTP_PORT = 587
SMTP_USER = "teacher@sabel.education"
SMTP_PASS = "YOUR_SMTP_PASSWORD"
SENDER_NAME = "Tabby Classroom Server"

DB_PATH = Path("db.sqlite")

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def print_help():
    print("""
Usage:  python create_students.py students.txt

Reads a UTF-8 encoded file with lines of the form:
    "Full Name" <firstname.lastname@sabel.education>

Each student receives a new auth_XXXXXXXX token if not yet present.
Results (including existing students) are written to:
    <filename>.tokens.csv

Version and timestamp are automatically included.
""")

def parse_line(line: str):
    """Extract name and email from lines like "Name" <email>"""
    match = re.match(r'"\s*([^"]+)\s*"\s*<([^>]+)>', line.strip())
    if match:
        name, email = match.groups()
        return name.strip(), email.strip().lower()
    return None, None

def get_repo_hash() -> str:
    """Return short git commit hash if available"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        return "n/a"

def send_token_mail(name, email, token):
    """Send email with login token to student (stub)"""
    msg = EmailMessage()
    msg["Subject"] = "Your Tabby access token"
    msg["From"] = f"{SENDER_NAME} <{SMTP_USER}>"
    msg["To"] = email
    msg.set_content(
f"""Hello {name},

you have been added to the Tabby coding server.

Login using:
    Email: {email}
    Token: {token}

Please keep this token confidential.

Best regards,
{SENDER_NAME}
""")
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"📨 Sent token to {email}")
    except Exception as e:
        print(f"⚠️  Failed to send mail to {email}: {e}")

# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

if len(sys.argv) != 2:
    print_help()
    sys.exit(1)

STUDENTS_FILE = Path(sys.argv[1])

if not STUDENTS_FILE.exists():
    print(f"❌ File not found: {STUDENTS_FILE}")
    sys.exit(1)

OUTPUT_FILE = STUDENTS_FILE.with_suffix(".tokens.csv")

# ---------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

repo_hash = get_repo_hash()
timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

print(f"📦 Version info: commit={repo_hash}, generated_at={timestamp}")

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as out:
    writer = csv.writer(out)
    writer.writerow(["name", "email", "auth_token", "generated_at", "repo_hash"])

    with open(STUDENTS_FILE, encoding="utf-8") as f:
        for line in f:
            name, email = parse_line(line)
            if not email:
                continue

            existing = db.execute("SELECT auth_token FROM users WHERE email = ?", (email,)).fetchone()

            if existing:
                token = existing["auth_token"]
                print(f"ℹ️  Existing: {name} ({email})")
            else:
                token = "auth_" + secrets.token_hex(16)
                now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
                db.execute("""
                    INSERT INTO users (email, name, is_admin, created_at, updated_at, auth_token, active)
                    VALUES (?, ?, 0, ?, ?, ?, 1)
                """, (email, name, now, now, token))
                print(f"✅ Added {name} ({email})")

            writer.writerow([name, email, token, timestamp, repo_hash])

            if MAIL_ENABLED:
                send_token_mail(name, email, token)

db.commit()
print(f"\nAll students processed. Tokens written to {OUTPUT_FILE}")

