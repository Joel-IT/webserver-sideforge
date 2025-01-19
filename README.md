# Mein Webserver

## Projektstruktur
- `server.py`: Hauptserver-Anwendung
- `templates/`: HTML-Vorlagen
- `static/`: 
  - `css/`: Stylesheet-Dateien
  - `js/`: JavaScript-Dateien

## Voraussetzungen
- Python 3.8+
- Flask

## Installation
1. Virtuelle Umgebung erstellen:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

3. Server starten:
```bash
python server.py
```

Zugriff über `http://localhost:5000`
