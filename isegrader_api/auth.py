from http import HTTPStatus

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    decode_token,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, jwt
from .models import User

auth_bp = Blueprint("auth", __name__)


def _request_data() -> dict:
    return request.get_json(silent=True) or request.form.to_dict() or {}


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _validation_error(errors: dict[str, list[str]]):
    return jsonify({"errors": errors}), HTTPStatus.BAD_REQUEST


def _token_response(user: User) -> dict:
    access_token = create_access_token(identity=user.id, additional_claims={"email": user.email})
    refresh_token = create_refresh_token(identity=user.id)
    expires = int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds())
    return {
        "tokenType": "Bearer",
        "accessToken": access_token,
        "expiresIn": expires,
        "refreshToken": refresh_token,
    }


@jwt.user_lookup_loader
def _load_user(_jwt_header: dict, jwt_data: dict) -> User | None:
    identity = jwt_data.get("sub")
    if identity is None:
        return None
    return db.session.get(User, identity)


@jwt.unauthorized_loader
def _missing_token(reason: str):
    return jsonify({"detail": reason}), HTTPStatus.UNAUTHORIZED


@jwt.invalid_token_loader
def _invalid_token(reason: str):
    return jsonify({"detail": reason}), HTTPStatus.UNAUTHORIZED


@jwt.expired_token_loader
def _expired_token(_jwt_header: dict, _jwt_data: dict):
    return jsonify({"detail": "Token has expired"}), HTTPStatus.UNAUTHORIZED


@auth_bp.post("/register")
def register():
    data = _request_data()
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    errors: dict[str, list[str]] = {}

    if not email:
        errors["email"] = ["Email is required."]
    if not password:
        errors["password"] = ["Password is required."]
    if errors:
        return _validation_error(errors)

    if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
        return _validation_error({"email": ["A user with this email already exists."]})

    user = User(
        email=email,
        user_name=email,
        password_hash=generate_password_hash(password),
        email_confirmed=True,
    )
    db.session.add(user)
    db.session.commit()
    return "", HTTPStatus.OK


@auth_bp.post("/login")
def login():
    data = _request_data()
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    user = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"detail": "Invalid email or password."}), HTTPStatus.UNAUTHORIZED

    return jsonify(_token_response(user))


@auth_bp.post("/refresh")
def refresh():
    data = _request_data()
    refresh_token = data.get("refreshToken")

    if refresh_token:
        decoded = decode_token(refresh_token)
        if decoded.get("type") != "refresh":
            return jsonify({"detail": "Expected a refresh token."}), HTTPStatus.UNAUTHORIZED
        user_id = decoded.get("sub")
    else:
        verify_jwt_in_request(refresh=True)
        user_id = get_jwt_identity()

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"detail": "User not found."}), HTTPStatus.UNAUTHORIZED

    return jsonify(_token_response(user))


@auth_bp.get("/manage/info")
@jwt_required()
def manage_info():
    return jsonify(
        {
            "email": current_user.email,
            "isEmailConfirmed": current_user.email_confirmed,
        }
    )
