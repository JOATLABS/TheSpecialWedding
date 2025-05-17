FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire app and scripts
COPY ./app ./app
COPY ./scripts ./scripts

# Run admin setup script via entrypoint (env-driven, optional)
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "python scripts/setup_admin_user.py --auto-create && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# Expose the port the app runs on
EXPOSE 8000