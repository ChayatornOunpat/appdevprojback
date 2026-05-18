import base64
import json

from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Question, User

# Sampled from https://github.com/isechula/2190101-comprog-grader.
# Description PDFs are expected to already exist at DESCRIPTION_DIR/<question id>.
SEED_QUESTIONS = [
    {
        "id": 1,
        "name": "Arabic Numerals",
        "cases": [
            ("0", "0 --> zero"),
            ("5", "5 --> five"),
            ("9", "9 --> nine"),
        ],
    },
    {
        "id": 2,
        "name": "USDate",
        "cases": [
            ("31/12/2024", "December 31, 2024"),
            ("1/1/2026", "January 1, 2026"),
            ("15/8/2025", "August 15, 2025"),
        ],
    },
    {
        "id": 3,
        "name": "NDigits",
        "cases": [
            ("123\n5", "00123"),
            ("98765\n3", "98765"),
            ("7\n4", "0007"),
        ],
    },
    {
        "id": 4,
        "name": "WeeklySales",
        "cases": [
            ("10 20 30 40", "100"),
            ("1 2 3 4 5", "15"),
            ("100", "100"),
        ],
    },
    {
        "id": 5,
        "name": "Next15Days",
        "cases": [
            ("20 12 2566", "4/1/2567"),
            ("14 2 2567", "29/2/2567"),
            ("20 2 2567", "6/3/2567"),
        ],
    },
]


def _encode(cases: list[tuple[str, str]]) -> str:
    payload = [{"Item1": item[0], "Item2": item[1]} for item in cases]
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def seed_database() -> None:
    if not db.session.execute(db.select(Question.id).limit(1)).first():
        db.session.add_all(
            [
                Question(
                    id=seed_question["id"],
                    name=seed_question["name"],
                    test_case=_encode(seed_question["cases"]),
                )
                for seed_question in SEED_QUESTIONS
            ]
        )

    seed_users = [
        ("alice@example.com", "Password123!"),
        ("bob@example.com", "Password123!"),
    ]
    for email, password in seed_users:
        existing = db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
        if existing is None:
            db.session.add(
                User(
                    email=email,
                    user_name=email,
                    password_hash=generate_password_hash(password),
                    email_confirmed=True,
                )
            )

    db.session.commit()
