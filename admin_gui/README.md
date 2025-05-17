# Wedding Admin GUI

A PyQt6-based graphical interface for managing the Wedding Web Application.

## Features

- Docker container management (start/stop)
- CSV guest import
- View all RSVPs
- Export RSVPs to CSV
- Real-time API health monitoring
- Log panel for operation history

## Installation

1. Install Python dependencies:
```bash
cd admin_gui
pip install -r requirements.txt
```

## Usage

Run the admin GUI:
```bash
python admin_gui.py
```

## Components

- `admin_gui.py`: Main GUI application
- `api_client.py`: HTTP client for communicating with the backend API
- `requirements.txt`: Python dependencies

## Configuration

By default, the GUI connects to the API at `http://localhost:8000`. You can modify this in the `ApiClient` initialization if needed.

## API Key

The admin endpoints are protected with an API key. The default key is `secureadminkey123`. This should be changed in production.