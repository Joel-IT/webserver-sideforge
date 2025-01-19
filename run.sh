#!/bin/bash
# Get the absolute path of the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Set Flask environment
export FLASK_APP="$SCRIPT_DIR/server.py"

# Ensure database file exists with correct permissions
sudo touch "$SCRIPT_DIR/sideforge.db"
sudo chown ubuntu:ubuntu "$SCRIPT_DIR/sideforge.db"

# Initialize database if needed
flask db upgrade

# Start Advanced Security in background
sudo "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/advanced_security.py" &

# Start the server
sudo "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/server.py"
