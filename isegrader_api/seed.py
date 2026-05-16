import base64
import json
from pathlib import Path

from flask import current_app
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Question, User

SEED_QUESTIONS = [
    {
        "name": "Sum Two Numbers",
        "cases": [
            ("1 2", "3"),
            ("5 7", "12"),
            ("-3 8", "5"),
        ],
        "description": [
            "Read two integers from standard input and print their sum.",
            "Input: one line containing two space-separated integers a and b.",
            "Output: one integer, a + b.",
            "Example: input '1 2' should produce output '3'.",
        ],
    },
    {
        "name": "FizzBuzz",
        "cases": [
            ("3", "Fizz"),
            ("5", "Buzz"),
            ("15", "FizzBuzz"),
            ("7", "7"),
        ],
        "description": [
            "Read one integer n from standard input.",
            "Print FizzBuzz if n is divisible by both 3 and 5.",
            "Print Fizz if n is divisible by 3 only.",
            "Print Buzz if n is divisible by 5 only.",
            "Otherwise, print n unchanged.",
        ],
    },
    {
        "name": "Reverse String",
        "cases": [
            ("hello", "olleh"),
            ("world", "dlrow"),
            ("a", "a"),
        ],
        "description": [
            "Read a string from standard input and print the characters in reverse order.",
            "The input is a single line.",
            "The output should contain exactly the reversed string.",
            "Example: input 'hello' should produce output 'olleh'.",
        ],
    },
]


def _encode(cases: list[tuple[str, str]]) -> str:
    payload = [{"Item1": item[0], "Item2": item[1]} for item in cases]
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(title: str, lines: list[str]) -> bytes:
    text_commands = [
        "BT",
        "/F2 18 Tf",
        "72 720 Td",
        f"({_escape_pdf_text(title)}) Tj",
        "/F1 11 Tf",
        "0 -32 Td",
    ]

    for index, line in enumerate(lines):
        if index:
            text_commands.append("0 -18 Td")
        text_commands.append(f"({_escape_pdf_text(line)}) Tj")

    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _seed_descriptions() -> None:
    description_dir = Path(current_app.config["DESCRIPTION_DIR"])
    description_dir.mkdir(parents=True, exist_ok=True)

    for seed_question in SEED_QUESTIONS:
        question = db.session.execute(
            db.select(Question).filter_by(name=seed_question["name"])
        ).scalar_one_or_none()
        if question is None:
            continue

        file_path = description_dir / str(question.id)
        if file_path.exists():
            continue

        file_path.write_bytes(
            _pdf_bytes(
                seed_question["name"],
                seed_question["description"],
            )
        )


def seed_database() -> None:
    if not db.session.execute(db.select(Question.id).limit(1)).first():
        db.session.add_all(
            [
                Question(name=seed_question["name"], test_case=_encode(seed_question["cases"]))
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
    _seed_descriptions()
