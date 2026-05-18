from pathlib import Path

from flask import Flask, send_from_directory
from flask_jwt_extended import jwt_required

from .auth import auth_bp
from .config import BASE_DIR, Config
from .extensions import cors, db, jwt
from .problems import problems_bp
from .resources import resources_bp
from .seed import seed_database

WEB_DIR = BASE_DIR / "web"


def create_app(config: type[Config] | dict | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder=None,
    )
    app.config.from_object(Config)

    if config is not None:
        if isinstance(config, dict):
            app.config.update(config)
        else:
            app.config.from_object(config)

    description_dir = Path(app.config["DESCRIPTION_DIR"])
    if not description_dir.is_absolute():
        description_dir = BASE_DIR / description_dir
    app.config["DESCRIPTION_DIR"] = str(description_dir)

    resource_dir = Path(app.config["RESOURCE_DIR"])
    if not resource_dir.is_absolute():
        resource_dir = BASE_DIR / resource_dir
    app.config["RESOURCE_DIR"] = str(resource_dir)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/*": {"origins": app.config["CORS_ORIGINS"]}})

    app.register_blueprint(auth_bp)
    app.register_blueprint(problems_bp)
    app.register_blueprint(resources_bp)

    @app.get("/hello")
    def hello() -> str:
        return "hello world"

    @app.get("/helloauth")
    @jwt_required()
    def hello_auth() -> str:
        return "hello world auth"

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path: str):
        target = WEB_DIR / path
        if path and target.is_file():
            return send_from_directory(WEB_DIR, path)
        return send_from_directory(WEB_DIR, "index.html")

    @app.cli.command("init-db")
    def init_db_command() -> None:
        db.create_all()
        seed_database()
        print("Initialized database.")

    with app.app_context():
        Path(app.config["DESCRIPTION_DIR"]).mkdir(parents=True, exist_ok=True)
        Path(app.config["RESOURCE_DIR"]).mkdir(parents=True, exist_ok=True)
        if app.config["AUTO_CREATE_DB"]:
            db.create_all()
            if app.config["SEED_DATABASE"]:
                seed_database()

    return app
