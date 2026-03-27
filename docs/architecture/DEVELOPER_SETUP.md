# Developer Setup Guide

## Quick Start

We provide multiple setup options including a GUI-based setup wizard.

### Option 1: GUI Setup Wizard (Easiest)

```bash
# Requires PyQt6 to be installed
pip install PyQt6
python gui_setup.py
```

The GUI wizard will walk you through:

- Environment configuration
- Admin credentials setup
- MongoDB configuration
- Automatic dependency installation
- Creating startup scripts

### Option 2: Command Line Setup

#### Unix/Linux/macOS:

```bash
cd /path/to/WeddingWebApp
./scripts/setup_dev.sh
```

#### Windows:

```cmd
cd \path\to\WeddingWebApp
python scripts\setup_dev.py
```

The setup script will:

1. Create a Python virtual environment
2. Install all dependencies
3. Set up your environment configuration
4. Generate a secure SECRET_KEY
5. Configure your admin credentials
6. Check/start MongoDB
7. Create your admin user
8. Create convenience startup scripts

### Option 2: Manual Setup

If you prefer to set up manually or the script fails:

1. **Create virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   cd admin_gui && pip install -r requirements.txt && cd ..
   ```
3. **Set up environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```
4. **Generate SECRET_KEY:**

   ```python
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   # Copy to SECRET_KEY in .env
   ```
5. **Start MongoDB:**

   ```bash
   docker-compose up -d mongo
   # Or install and start MongoDB locally
   ```
6. **Create admin user:**

   ```bash
   python scripts/setup_admin_user.py --auto-create
   ```

7. **Create test accounts manually through the frontend flows when needed**

   The `TEST_*` entries in `.env` are manual QA fixtures only.

   They are not created by startup scripts or app startup. Use them when testing:
   - planner signup
   - subscription / payment checkout
   - vendor signup
   - couple invite + setup
   - team member invite + acceptance

   Only the root admin is bootstrap-created automatically.

## Starting Development

After setup, use the generated scripts:

### Unix/Linux/macOS:

- Start API: `./start_api.sh`
- Start GUI: `./start_gui.sh`

### Windows:

- Start API: `start_api.bat`
- Start GUI: `start_gui.bat`

## Accessing the Application

- API Documentation: http://localhost:8000/docs
- Admin GUI: Launch using the start scripts

## Troubleshooting

### MongoDB Issues

- Ensure Docker is running, or
- Install MongoDB locally from https://www.mongodb.com/docs/manual/installation/

### Permission Issues (Unix/Linux/macOS)

```bash
chmod +x scripts/setup_dev.sh
chmod +x start_api.sh
chmod +x start_gui.sh
```

### Module Import Errors

Ensure you're using the virtual environment:

```bash
source venv/bin/activate  # Unix/Linux/macOS
venv\Scripts\activate     # Windows
```

## Environment Variables

Key environment variables in `.env`:

- `SECRET_KEY`: JWT signing key (auto-generated)
- `ROOT_ADMIN_EMAIL`: Your admin email
- `ROOT_ADMIN_PASSWORD`: Your admin password
- `MONGO_URI`: MongoDB connection string
- `MONGO_DB`: Database name (default: wedding)

## Security Notes

- Never commit `.env` to version control
- Use strong passwords for production
- Keep SECRET_KEY confidential
- Regularly update dependencies
