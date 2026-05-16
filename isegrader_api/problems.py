import base64
import binascii
import json
from http import HTTPStatus
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file
from flask_jwt_extended import current_user, jwt_required

from .extensions import db
from .models import Question, UserQuestionProgress

problems_bp = Blueprint("problems", __name__)


def _decode_test_cases(encoded: str) -> list[dict[str, str]]:
    try:
        raw = base64.b64decode(encoded, validate=True)
        decoded = json.loads(raw.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid base64 JSON test cases.") from exc

    if not isinstance(decoded, list):
        raise ValueError("Test cases must be a list.")

    cases: list[dict[str, str]] = []
    for item in decoded:
        if isinstance(item, dict):
            input_value = item.get("item1", item.get("Item1"))
            output_value = item.get("item2", item.get("Item2"))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            input_value, output_value = item
        else:
            raise ValueError("Each test case must contain input and output.")

        if input_value is None or output_value is None:
            raise ValueError("Each test case must contain input and output.")
        cases.append({"item1": str(input_value), "item2": str(output_value)})

    return cases


def _description_path(question_id: int) -> Path:
    return Path(current_app.config["DESCRIPTION_DIR"]) / str(question_id)


def _get_int_param(name: str) -> int | None:
    value = request.args.get(name)
    if value is None:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        value = data.get(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_progress_param() -> int | None:
    value = request.args.get("progress")
    if value is None:
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        value = data.get("progress")
    try:
        progress = int(value)
    except (TypeError, ValueError):
        return None
    if progress < 0 or progress > 100:
        return None
    return progress


def _get_or_create_progress(question_id: int, default_code: str = "") -> UserQuestionProgress:
    row = db.session.get(UserQuestionProgress, (current_user.id, question_id))
    if row is not None:
        return row

    row = UserQuestionProgress(
        user_id=current_user.id,
        question_id=question_id,
        progress=0,
        code=default_code,
    )
    db.session.add(row)
    return row


@problems_bp.get("/description/<int:question_id>")
def description(question_id: int):
    file_path = _description_path(question_id)
    if not file_path.exists():
        return jsonify({"detail": "File not found"}), HTTPStatus.NOT_FOUND
    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{question_id}.pdf",
    )


@problems_bp.get("/problems/getname/<int:question_id>")
def get_name(question_id: int):
    question = db.session.get(Question, question_id)
    return Response("" if question is None else question.name, mimetype="text/plain")


@problems_bp.get("/problems/getprogress/<int:question_id>")
@jwt_required()
def get_progress(question_id: int):
    row = db.session.get(UserQuestionProgress, (current_user.id, question_id))
    return jsonify(0 if row is None else row.progress)


@problems_bp.get("/problems/getcode/<int:question_id>")
@jwt_required()
def get_code(question_id: int):
    row = db.session.get(UserQuestionProgress, (current_user.id, question_id))
    return jsonify(None if row is None else row.code)


@problems_bp.get("/problems/gettestcase/<int:question_id>")
def get_testcase(question_id: int):
    question = db.session.get(Question, question_id)
    if question is None:
        return jsonify({"detail": "Question not found."}), HTTPStatus.NOT_FOUND
    try:
        return jsonify(_decode_test_cases(question.test_case))
    except ValueError:
        return jsonify({"detail": "Invalid test case data."}), HTTPStatus.BAD_REQUEST


@problems_bp.post("/problems/postprogress")
@jwt_required()
def post_progress():
    question_id = _get_int_param("id")
    progress = _get_progress_param()
    if question_id is None or progress is None:
        return "", HTTPStatus.BAD_REQUEST

    row = _get_or_create_progress(question_id)
    if row.progress <= progress:
        row.progress = progress
    db.session.commit()
    return "", HTTPStatus.OK


@problems_bp.post("/problems/postcode")
@jwt_required()
def post_code():
    question_id = _get_int_param("id")
    if question_id is None:
        return "", HTTPStatus.BAD_REQUEST

    data = request.get_json(silent=True)
    if isinstance(data, dict) and "code" in data:
        code = data["code"]
    else:
        code = request.get_data(as_text=True)

    row = _get_or_create_progress(question_id, default_code=str(code))
    row.code = str(code)
    db.session.commit()
    return "", HTTPStatus.OK


@problems_bp.get("/problems/getquestion")
@jwt_required()
def get_question():
    questions = db.session.execute(db.select(Question).order_by(Question.id)).scalars().all()
    missing = [
        UserQuestionProgress(
            user_id=current_user.id,
            question_id=question.id,
            progress=0,
            code="",
        )
        for question in questions
        if db.session.get(UserQuestionProgress, (current_user.id, question.id)) is None
    ]
    if missing:
        db.session.add_all(missing)
        db.session.commit()

    rows = (
        db.session.execute(
            db.select(Question.id, Question.name, UserQuestionProgress.progress)
            .join(
                UserQuestionProgress,
                (UserQuestionProgress.question_id == Question.id)
                & (UserQuestionProgress.user_id == current_user.id),
            )
            .order_by(Question.id)
        )
        .mappings()
        .all()
    )
    return jsonify(
        [
            {
                "id": row["id"],
                "name": row["name"],
                "progress": row["progress"],
            }
            for row in rows
        ]
    )


@problems_bp.post("/problems/postquestion")
def post_question():
    name = request.values.get("name")
    test_case = request.values.get("testCase")
    description_file = request.files.get("description")

    if not name or not test_case or description_file is None:
        return "", HTTPStatus.BAD_REQUEST

    try:
        _decode_test_cases(test_case)
    except ValueError:
        return "", HTTPStatus.BAD_REQUEST

    question = Question(name=name, test_case=test_case)
    db.session.add(question)
    db.session.commit()

    file_path = _description_path(question.id)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    description_file.save(file_path)

    return "", HTTPStatus.OK
