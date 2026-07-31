from pathlib import Path
import importlib
import config

repo_root = Path(__file__).resolve().parent
app_env_path = repo_root / "app" / ".env"
original_content = app_env_path.read_text(encoding="utf-8") if app_env_path.exists() else None
try:
    app_env_path.write_text(
        "ADMIN_EMAIL=alerts@example.com\n"
        "MAIL_PASSWORD=sendgrid-secret\n"
        "MAIL_DEFAULT_SENDER=alerts@example.com\n"
        "EMAIL_NOTIFICATION_ENABLED=true\n",
        encoding="utf-8",
    )
    importlib.reload(config)
    print('MAIL_PASSWORD=', config.Config.MAIL_PASSWORD)
finally:
    if original_content is None:
        app_env_path.unlink(missing_ok=True)
    else:
        app_env_path.write_text(original_content, encoding="utf-8")
    importlib.reload(config)
