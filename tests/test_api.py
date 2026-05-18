import base64
import io
import json

import pytest

from isegrader_api import create_app


@pytest.fixture()
def app(tmp_path):
    resource_dir = tmp_path / "resourcefiles"
    resource_dir.mkdir()
    (resource_dir / "00_intro_2024-1832-17229153700352.pdf").write_bytes(b"%PDF-1.4 resource")

    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "JWT_SECRET_KEY": "test-jwt-secret-with-at-least-32-bytes",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DESCRIPTION_DIR": str(tmp_path / "graderfiles"),
            "RESOURCE_DIR": str(resource_dir),
            "AUTO_CREATE_DB": True,
            "SEED_DATABASE": True,
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    response = client.post(
        "/login",
        json={"email": "alice@example.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    token = response.get_json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _encoded_cases(cases):
    payload = [{"Item1": item[0], "Item2": item[1]} for item in cases]
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def test_seeded_user_can_login_and_access_auth_route(client, auth_headers):
    response = client.get("/helloauth", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "hello world auth"


def test_register_then_login_new_user(client):
    response = client.post(
        "/register",
        json={"email": "charlie@example.com", "password": "Password123!"},
    )
    assert response.status_code == 200

    response = client.post(
        "/login",
        json={"email": "charlie@example.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    assert response.get_json()["tokenType"] == "Bearer"


def test_refresh_accepts_refresh_token_in_body(client):
    login = client.post(
        "/login",
        json={"email": "alice@example.com", "password": "Password123!"},
    ).get_json()

    response = client.post("/refresh", json={"refreshToken": login["refreshToken"]})

    assert response.status_code == 200
    assert response.get_json()["accessToken"]


def test_getquestion_creates_progress_rows(client, auth_headers):
    response = client.get("/problems/getquestion", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == [
        {"id": 1, "name": "Sum Two Numbers", "progress": 0},
        {"id": 2, "name": "FizzBuzz", "progress": 0},
        {"id": 3, "name": "Reverse String", "progress": 0},
    ]


def test_progress_is_monotonic(client, auth_headers):
    assert client.post("/problems/postprogress?id=1&progress=40", headers=auth_headers).status_code == 200
    assert client.post("/problems/postprogress?id=1&progress=10", headers=auth_headers).status_code == 200

    response = client.get("/problems/getprogress/1", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == 40


def test_code_can_be_saved_and_fetched(client, auth_headers):
    code = "print(input())"

    response = client.post("/problems/postcode?id=1", data=code, headers=auth_headers)
    assert response.status_code == 200

    response = client.get("/problems/getcode/1", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() == code


def test_testcases_are_decoded(client):
    response = client.get("/problems/gettestcase/1")

    assert response.status_code == 200
    assert response.get_json()[0] == {"item1": "1 2", "item2": "3"}


def test_seeded_question_description_is_available(client):
    response = client.get("/description/1")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.get_data().startswith(b"%PDF-1.4")


def test_postquestion_stores_description_file(client):
    encoded = _encoded_cases([("2 2", "4")])

    response = client.post(
        "/problems/postquestion",
        data={
            "name": "Add Again",
            "testCase": encoded,
            "description": (io.BytesIO(b"%PDF-1.4 test"), "description.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200

    response = client.get("/description/4")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.get_data() == b"%PDF-1.4 test"


def test_resources_list_files(client):
    response = client.get("/resources")

    assert response.status_code == 200
    assert response.get_json() == [
        {
            "filename": "00_intro_2024-1832-17229153700352.pdf",
            "size": 17,
            "title": "00 Intro 2024",
            "updatedAt": response.get_json()[0]["updatedAt"],
            "url": "/resources/files/00_intro_2024-1832-17229153700352.pdf",
        }
    ]


def test_resource_file_is_available(client):
    response = client.get("/resources/files/00_intro_2024-1832-17229153700352.pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.get_data() == b"%PDF-1.4 resource"
