import sqlite3

db = sqlite3.connect("db.sqlite")

print("\n=== TABLES ===")
for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table';"):
    print("-", t)

print("\n=== SCHEMA (users) ===")
rows = db.execute("SELECT sql FROM sqlite_master WHERE name='users';").fetchall()
for (sql,) in rows:
    print(sql)

