#!/usr/bin/env python3
# ==========================================================
# 👩‍💻  30_create_students.py — Create Tabby Student Accounts
# ==========================================================
# Designed for classroom automation on ephemeral GPU servers.
#
# 💡 Usage (CLI mode):
#     python3 30_create_students.py
#
# 💡 Usage (Python module):
#     from setup.30_create_students import main
#     main()
#
# What it does:
#   1. Scans ../classes/ for all *.txt (or *.students) files.
#   2. For each entry of the form:
#        "Full Name" <firstname.lastname@sabel.education>
#      creates a Tabby user if not already present.
#   3. Writes a <filename>.tokens.csv report next to each source file.
#   4. (Optional) Sends login token emails if MAIL_ENABLED = True.
#
# Environment:
#   No arguments or variables required.
#   Database is expected at ~/tabbyclassmodels/ee/db.sqlite
# ==========================================================

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import os
import re
import csv
import smtplib
import secrets
import sqlite3
import subprocess
from datetime import datetime, UTC
from email.message import EmailMessage

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

CLASSES_DIR = Path(__file__).parent.parent / "classes"
DB_PATH = Path.home() / "tabbyclassmodels" / "ee" / "db.sqlite"

MAIL_ENABLED = False
SMTP_SERVER = "smtp.yourschool.de"
SMTP_PORT = 587
SMTP_USER = "teacher@sabel.education"
SMTP_PASS = "YOUR_SMTP_PASSWORD"
SENDER_NAME = "Tabby Classroom Server"

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------


def log(msg):
    print(msg, flush=True)


def parse_line(line: str):
    """Extract (name, email) from lines like: "Name" <email>"""
    match = re.match(r'"\s*([^"]+)\s*"\s*<([^>]+)>', line.strip())
    if match:
        name, email = match.groups()
        return name.strip(), email.strip().lower()
    return None, None


def get_repo_hash() -> str:
    """Return short git commit hash if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "n/a"


def send_token_mail(name, email, token):
    """Send email with login token to student (optional)."""
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
"""
    )
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        log(f"📨 Sent token to {email}")
    except Exception as e:
        log(f"⚠️  Failed to send mail to {email}: {e}")


# ---------------------------------------------------------------------
# Core functionality
# ---------------------------------------------------------------------


def create_students():
    """Create student accounts from all class lists."""
    if not DB_PATH.exists():
        log(f"❌ Database not found at {DB_PATH}")
        return False

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    repo_hash = get_repo_hash()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    log(f"📦 Version info: commit={repo_hash}, generated_at={timestamp}")

    student_files = sorted(CLASSES_DIR.glob("*.txt"))
    if not student_files:
        log(f"⚠️ No student list files found in {CLASSES_DIR}")
        return False

    for file in student_files:
        output_file = file.with_suffix(".tokens.csv")
        log(f"\n📂 Processing {file.name}")

        with open(output_file, "w", newline="", encoding="utf-8") as out_csv:
            writer = csv.writer(out_csv)
            writer.writerow(["name", "email", "auth_token", "generated_at", "repo_hash"])

            with open(file, encoding="utf-8") as f:
                for line in f:
                    name, email = parse_line(line)
                    if not email:
                        continue

                    existing = db.execute(
                        "SELECT auth_token FROM users WHERE email = ?", (email,)
                    ).fetchone()

                    if existing:
                        token = existing["auth_token"]
                        log(f"ℹ️  Existing: {name} ({email})")
                    else:
                        token = "auth_" + secrets.token_hex(16)
                        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
                        db.execute(
                            """
                            INSERT INTO users (email, name, is_admin, created_at, updated_at, auth_token, active)
                            VALUES (?, ?, 0, ?, ?, ?, 1)
                            """,
                            (email, name, now, now, token),
                        )
                        log(f"✅ Added {name} ({email})")

                    writer.writerow([name, email, token, timestamp, repo_hash])

                    if MAIL_ENABLED:
                        send_token_mail(name, email, token)

        log(f"🧾 Tokens written to {output_file.name}")

    db.commit()
    db.close()
    log("\n🎉 All students processed successfully.")
    return True


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------


def main():
    """CLI and run_all entry point."""
    success = create_students()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
