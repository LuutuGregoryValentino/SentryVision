from flask import Flask, jsonify, render_template
from marshmallow import ValidationError

from config import Config
from .extensions import db
from .routes import api_bp, telemetry_bp
from .seed import seed_database


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config["API_KEY"] = app.config.get("API_KEY") or "e52dc64913f9bbca16f37e4a27af776dee4b797db06e53abe99a9f5bc308e480"

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
        seed_database()

    return app
