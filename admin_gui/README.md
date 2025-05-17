# Wedding Admin GUI

A Streamlit-based web interface for managing the Wedding Web Application.

## Features

- Dashboard with statistics and charts
- CSV guest import
- View and filter RSVPs
- Export RSVPs to CSV
- Real-time API health monitoring

## Installation

1. Install Python dependencies:
```bash
cd admin_gui
pip install -r requirements.txt
```

## Usage

### 1. Running locally

Run the admin web interface locally:
```bash
cd admin_gui
streamlit run admin_gui.py
```

Then open your browser at http://localhost:8501

### 2. Using Docker

Use Docker Compose to start all services including the admin interface:
```bash
docker compose -f docker-compose.all.yml up -d
```

Then access the admin interface at http://localhost:8501

## Components

- `admin_gui.py`: Streamlit web application
- `api_client.py`: HTTP client for communicating with the backend API
- `requirements.txt`: Python dependencies

## Configuration

By default, the GUI connects to the API at `http://localhost:8000`. You can modify this in the `ApiClient` initialization if needed.

## Authentication

The admin endpoints are protected with HTTP Basic Authentication. Credentials are loaded from your `.env` file with the following variables:

```
PRIMARY_ADMIN_EMAIL=your-admin-email
PRIMARY_ADMIN_PASSWORD=your-admin-password
```