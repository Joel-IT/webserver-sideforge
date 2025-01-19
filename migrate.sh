#!/bin/bash
source venv/bin/activate
export FLASK_APP=server.py
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
