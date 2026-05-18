from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
import re
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, send_from_directory

resources_bp = Blueprint("resources", __name__)


def _resource_dir() -> Path:
    return Path(current_app.config["RESOURCE_DIR"])


def _display_name(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.rsplit("-", maxsplit=2)
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        stem = parts[0]
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem.replace("_", " "))
    words = [
        word if word.isupper() or word.isdigit() else word[:1].upper() + word[1:]
        for word in stem.split()
    ]
    return " ".join(words)


@resources_bp.get("/resources")
def list_resources():
    resources = []
    for file_path in sorted(_resource_dir().iterdir(), key=lambda path: path.name.casefold()):
        if not file_path.is_file():
            continue

        stat = file_path.stat()
        resources.append(
            {
                "filename": file_path.name,
                "title": _display_name(file_path.name),
                "size": stat.st_size,
                "updatedAt": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "url": f"/resources/files/{quote(file_path.name)}",
            }
        )

    return jsonify(resources)


@resources_bp.get("/resources/files/<path:filename>")
def get_resource_file(filename: str):
    file_path = _resource_dir() / filename
    if not file_path.is_file() or file_path.parent != _resource_dir():
        return jsonify({"detail": "File not found"}), HTTPStatus.NOT_FOUND

    return send_from_directory(
        _resource_dir(),
        filename,
        as_attachment=False,
    )
