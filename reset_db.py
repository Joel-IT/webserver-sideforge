#!/usr/bin/env python3
import os
import sys
import sqlite3

# Use sudo to ensure we have write permissions
if os.geteuid() != 0:
    print("Rerunning with sudo...")
    os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

DB_PATH = '/var/www/html/webserver-sideforge/instance/sideforge.db'

def reset_database():
    # Connect to the SQLite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get list of all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    # Drop all tables
    for table in tables:
        table_name = table[0]
        print(f"Dropping table: {table_name}")
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")

    # Commit changes and close connection
    conn.commit()
    conn.close()

    print("Database tables have been reset successfully.")

if __name__ == '__main__':
    reset_database()
