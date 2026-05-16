from pathlib import Path

from flask import Flask
from flask_jwt_extended import jwt_required

from .auth import auth_bp
from .config import BASE_DIR, Config
from .extensions import cors, db, jwt
from .problems import problems_bp
from .seed import seed_database


def create_app(config: type[Config] | dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
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

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/*": {"origins": app.config["CORS_ORIGINS"]}})

    app.register_blueprint(auth_bp)
    app.register_blueprint(problems_bp)

    @app.get("/")
    def index() -> str:
        return "Hello World!"

    @app.get("/hello")
    def hello() -> str:
        return "hello world"

    @app.get("/helloauth")
    @jwt_required()
    def hello_auth() -> str:
        return "hello world auth"

    @app.cli.command("init-db")
    def init_db_command() -> None:
        db.create_all()
        seed_database()
        print("Initialized database.")

    with app.app_context():
        Path(app.config["DESCRIPTION_DIR"]).mkdir(parents=True, exist_ok=True)
        if app.config["AUTO_CREATE_DB"]:
            db.create_all()
            if app.config["SEED_DATABASE"]:
                seed_database()

    return app
