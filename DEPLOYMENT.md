# Sentry Vision deployment guide

This guide is tailored to the current Sentry Vision repository layout. The Flask backend serves the dashboard, stores detection logs and device telemetry in SQLite by default, and runs the bundled Edge Impulse WebAssembly export through Node.js.

## 1. Confirm the runtime versions

The repository was validated with:

- Python 3.12.3
- Node.js v24.14.0

Use a Python 3.10+ environment. Python 3.12 is a good fit for this project.

## 2. Create the deployment environment

```bash
git clone <your-repo-url> sentry-vision
cd sentry-vision
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you are deploying on Ubuntu or Debian, install Node.js first if it is not already installed:

```bash
node --version
```

If Node.js is missing, install it before continuing.

## 3. Configure environment variables

Copy the example environment file and adjust it for your host:

```bash
cp .env.example .env
```

Key values to review:

- `SECRET_KEY`: use a strong random value in production.
- `DATABASE_URL`: leave the SQLite default for local deployment or set PostgreSQL for production.
- `PUBLIC_BASE_URL`: must match the public URL the mail links and dashboard will use.
- `EMAIL_NOTIFICATION_ENABLED`: set to `true` when you want unauthorized detection alerts by email.
- `VISIBLE_DEVICE_NAMES`: keep the default `ESP32-CAM,Ultrasonic Sensor,Buzzer` unless you want to expose more devices.

Example production email settings:

```text
EMAIL_NOTIFICATION_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=true
SMTP_USER=your-account@gmail.com
SMTP_PASSWORD=your-app-password
MAIL_FROM_ADDRESS=your-account@gmail.com
PUBLIC_BASE_URL=https://your.domain.com
```

## 4. Initialize the database and seed the demo data

```bash
export FLASK_APP=run.py
flask init-db
```

This creates the tables and seeds the personnel and telemetry defaults used by the dashboard.

## 5. Test the app locally

```bash
python run.py
```

Visit:

- http://localhost:5000/
- http://localhost:5000/api/v1/health/

The dashboard should load and the recognition endpoint should accept uploaded images.

## 6. Run in production with Gunicorn

Install and run Gunicorn behind a reverse proxy:

```bash
pip install gunicorn
```

```bash
gunicorn --workers 4 --bind 0.0.0.0:8000 run:app
```

A typical systemd service is:

```ini
[Unit]
Description=Sentry Vision Flask app
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/sentry-vision
EnvironmentFile=/opt/sentry-vision/.env
ExecStart=/opt/sentry-vision/.venv/bin/gunicorn --workers 4 --bind unix:/opt/sentry-vision/sentryvision.sock run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 7. Use Nginx as a reverse proxy

A minimal Nginx configuration is:

```nginx
server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://unix:/opt/sentry-vision/sentryvision.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 8. Deployment checklist

- Make sure Node.js is installed and on `PATH`.
- Keep `PUBLIC_BASE_URL` aligned with the public domain.
- Use a real `SECRET_KEY` and non-default SMTP credentials.
- Do not run the Flask development server in production.
- Keep the database directory and uploaded image directory outside the repository if you need persistent storage beyond the default local setup.
