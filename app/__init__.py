import os

from flask import Flask, jsonify, render_template
from marshmallow import ValidationError
from sqlalchemy import inspect, text

from config import Config
from .extensions import db
from .routes import api_bp, telemetry_bp
from .seed import seed_database


def ensure_detection_log_columns():
    """Apply the two small SQLite-compatible columns used by the capture gallery."""
    columns = {column["name"] for column in inspect(db.engine).get_columns("detection_logs")}
    required_columns = {
        "image_filename": "VARCHAR(255)",
        "confidence": "FLOAT",
    }
    with db.engine.begin() as connection:
        for name, column_type in required_columns.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE detection_logs ADD COLUMN {name} {column_type}"))


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config["API_KEY"] = app.config.get("API_KEY") or os.getenv("API_KEY")

    db.init_app(app)
    app.register_blueprint(api_bp)
    app.register_blueprint(telemetry_bp)

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.cli.command("init-db")
    def init_db_command():
        """Create tables and seed personnel and device status rows."""
        with app.app_context():
            db.create_all()
            ensure_detection_log_columns()
            seed_database()
        print("Database initialized and seeded.")

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return jsonify({"error": "Invalid request payload", "details": error.messages}), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    with app.app_context():
        db.create_all()
        ensure_detection_log_columns()

    return app
