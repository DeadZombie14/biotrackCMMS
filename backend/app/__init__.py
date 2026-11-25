import click
from flask import Flask, jsonify
from app.config import Config
from app.extensions import cors, db, jwt, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # Register blueprints
    from app.api.auth_bp import auth_bp
    from app.api.assets_bp import assets_bp
    from app.api.incidents_bp import incidents_bp
    from app.api.work_orders_bp import work_orders_bp
    from app.api.oncall_bp import oncall_bp
    from app.api.analytics_bp import analytics_bp
    from app.api.audit_bp import audit_bp
    from app.api.public_bp import public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(work_orders_bp)
    app.register_blueprint(oncall_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(public_bp)

    @app.get("/api/v1/health")
    def health():
        return jsonify({"status": "ok", "service": "BioTrack CMMS API"})

    # CLI commands for migrations/triggers & deterministic seeding
    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Limpiar datos existentes antes de sembrar.")
    def seed_command(reset: bool):
        """Sembrar datos hospitalarios deterministas para BioTrack CMMS."""
        from app.seed import run_seed

        run_seed(reset=reset)
        click.echo("BioTrack CMMS: datos sembrados exitosamente.")

    @app.cli.command("install-triggers")
    def install_triggers_command():
        """Instalar triggers de inmutabilidad en MariaDB sobre audit_events."""
        from app.services.audit_service import install_mariadb_immutability_triggers

        install_mariadb_immutability_triggers()
        click.echo("Triggers de inmutabilidad instalados en audit_events.")

    return app
