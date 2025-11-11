#!/usr/bin/env python3
# ==========================================================
# 🧩  inspect_db.py — Database Schema & Column Inspector
# ==========================================================
# Purpose:
#   Inspect the structure of a Tabby SQLite database.
#   Lists all tables, shows CREATE statements, and key columns
#   for quick debugging (e.g. detecting 'key' vs 'name' fields).
#
# Usage:
#   python3 utils/inspect_db.py [path/to/db.sqlite]
#
# Notes:
#   - Designed for manual inspection only.
#   - Does not modify the database.
# ==========================================================

import sqlite3
import sys
from pathlib import Path

# --- Get DB path ---
db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("db.sqlite")

if not db_path.exists():
    print(f"❌ Database not found: {db_path}")
    sys.exit(1)

print(f"🔍 Inspecting database: {db_path.resolve()}")

db = sqlite3.connect(db_path)

# --- List tables ---
print("\n=== TABLES ===")
tables = [t for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table';")]
for t in tables:
    print("-", t)

# --- Show CREATE statements for key tables ---
def show_schema(table_name: str):
    rows = db.execute("SELECT sql FROM sqlite_master WHERE name=?;", (table_name,)).fetchall()
    if not rows:
        print(f"\n=== SCHEMA ({table_name}) — not found ===")
        return
    print(f"\n=== SCHEMA ({table_name}) ===")
    for (sql,) in rows:
        print(sql)

# --- Show columns of a table ---
def show_columns(table_name: str):
    try:
        cols = db.execute(f"PRAGMA table_info({table_name});").fetchall()
        print(f"\n=== COLUMNS ({table_name}) ===")
        for cid, name, ctype, notnull, dflt, pk in cols:
            print(f"{name:20} {ctype:10} {'PRIMARY KEY' if pk else ''}")
    except sqlite3.OperationalError:
        print(f"⚠️ Could not inspect columns for {table_name}")

# --- Inspect all tables (short version) ---
for t in tables:
    show_columns(t)

# --- Focused inspection for known Tabby tables ---
if "server_setting" in tables:
    cols = [name for _, name, *_ in db.execute("PRAGMA table_info(server_setting);")]
    print()
    if "key" in cols:
        print("✅ server_setting uses column 'key'")
    elif "name" in cols:
        print("✅ server_setting uses column 'name'")
    else:
        print("⚠️ server_setting has neither 'key' nor 'name' column")

if "users" in tables:
    print("\n✅ 'users' table detected (auth info present)")

db.close()
print("\n🎉 Done. Database structure inspection complete.")
