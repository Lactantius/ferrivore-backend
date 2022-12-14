"""Test API routes"""

from flask import request, session
from flask.testing import FlaskClient
import pytest

from .fixtures import app
from app.routes.ideas import get_idea


@pytest.fixture
def client(app) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def logged_in_user(client):
    user = client.post(
        "/api/users/login",
        json={
            "email": "ostewart@example.org",
            "password": "7(S7fOnb!q",
        },
    ).json
    return user


@pytest.fixture
def auth_headers(logged_in_user):
    token = logged_in_user["user"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    return headers


##############################################################################
# Auth
#


def test_can_signup(client: FlaskClient) -> None:
    """Can one sign up for a new account?"""

    with client:
        res = client.post(
            "/api/users/signup",
            json={
                "email": "apitest@apitest.com",
                "password": "apitest1",
                "username": "apitest1",
            },
        )
        assert res.status_code == 201
        assert res.json["user"]["email"] == "apitest@apitest.com"


def test_error_message_if_username_or_email_not_unique(client: FlaskClient) -> None:
    """Will correct error message show?"""

    with client:
        bad_username = client.post(
            "/api/users/signup",
            json={
                "email": "apitest@apitest.com",
                "password": "apitest1",
                "username": "user1",
            },
        )
        assert bad_username.status_code == 409
        assert "already exists" in bad_username.json["msg"]

        bad_email = client.post(
            "/api/users/signup",
            json={
                "email": "user1@user1.com",
                "password": "apitest1",
                "username": "apitest1",
            },
        )
        assert bad_email.status_code == 409
        assert "already exists" in bad_email.json["msg"]


def test_can_login(client: FlaskClient) -> None:
    """Can one login?"""

    with client:
        res = client.post(
            "/api/users/login",
            json={
                "email": "user1@user1.com",
                "password": "password1",
            },
        )
        assert res.status_code == 200
        assert res.json["user"]["email"] == "user1@user1.com"


def test_cannot_login_with_invalid_credentials(client: FlaskClient) -> None:
    """Is login refused with bad credentials?"""

    with client:
        bad_password = client.post(
            "/api/users/login",
            json={"email": "user1@user1.com", "password": "bad_password"},
        )
        assert bad_password.status_code == 401
        assert bad_password.json["msg"] == "Invalid username or password"

    with client:
        bad_email = client.post(
            "/api/users/login",
            json={"email": "invalid@invalid.com", "password": "password1"},
        )
        assert bad_email.status_code == 401
        assert bad_email.json["msg"] == "Invalid username or password"


##############################################################################
# User Info
#


def test_can_view_user_info(client: FlaskClient) -> None:
    """Can a user view user details?"""
    with client:
        user = client.post(
            "/api/users/login",
            json={
                "email": "user1@user1.com",
                "password": "password1",
            },
        ).json
        user_id = user["user"]["sub"]
        token = user["user"]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = client.get(f"/api/users/{user_id}", headers=headers)

        assert res.status_code == 200
        assert res.json["user"]["username"] == "user1"
        assert res.json["user"].get("password", None) is None


def test_cannot_view_user_info_without_proper_token(client: FlaskClient) -> None:
    """Can only the user view user details?"""

    with client:
        user1 = client.post(
            "/api/users/login",
            json={
                "email": "user1@user1.com",
                "password": "password1",
            },
        ).json
        user1_id = user1["user"]["sub"]

        no_token = client.get(f"/api/users/{user1_id}")

        assert no_token.status_code == 401
        assert no_token.json["msg"] == "Missing Authorization Header"

        user2 = client.post(
            "/api/users/login",
            json={
                "email": "user2@user2.com",
                "password": "password2",
            },
        ).json

        user2_id = user2["user"]["sub"]
        token = user2["user"]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = client.get(f"/api/users/{user1_id}", headers=headers)

        assert res.status_code == 403
        assert res.json["msg"] == "You are not authorized to view this resource"


def test_can_edit_user_info(client: FlaskClient) -> None:
    """Can a user edit user details?"""
    with client:
        user = client.post(
            "/api/users/login",
            json={
                "email": "user1@user1.com",
                "password": "password1",
            },
        ).json
        user_id = user["user"]["sub"]
        token = user["user"]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        res = client.patch(
            f"/api/users/{user_id}",
            json={
                "currentPassword": "password1",
                "newEmail": "updated@updated.com",
                "newUsername": "updated",
                "newPassword": "updatedpass",
            },
            headers=headers,
        )

        assert res.status_code == 200
        assert res.json["user"]["username"] == "updated"
        assert res.json["user"]["email"] == "updated@updated.com"
        assert res.json["user"].get("password", None) is None


##############################################################################
# Ideas
#


def test_get_random_idea(client: FlaskClient) -> None:
    """Can one get a random idea?"""

    with client:

        res = client.get("/api/ideas/random")

        assert res.status_code == 200
        assert res.json["idea"]["url"] is not None


def test_get_disagreeable_idea(client: FlaskClient, auth_headers) -> None:
    """Can one get a disagreeable idea?"""

    with client:

        res = client.get("/api/ideas/disagreeable", headers=auth_headers)

        assert res.status_code == 200
        assert res.json["idea"]["url"] is not None


def test_get_agreeable_idea(client: FlaskClient, auth_headers) -> None:
    """Can one get an agreeable idea?"""

    with client:

        res = client.get("/api/ideas/agreeable", headers=auth_headers)

        assert res.status_code == 200
        assert res.json["idea"]["url"] is not None


def test_like_idea(client: FlaskClient, auth_headers) -> None:
    """Can one like an idea?"""

    with client:
        idea_id = client.get("/api/ideas/disagreeable", headers=auth_headers).json[
            "idea"
        ]["ideaId"]
        res = client.post(
            f"/api/ideas/{idea_id}/react",
            json={"type": "like", "agreement": -2},
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json["reaction"]["agreement"] == -2


def test_dislike_idea(client: FlaskClient, auth_headers) -> None:
    """Can one dislike an idea?"""

    with client:
        idea_id = client.get("/api/ideas/disagreeable", headers=auth_headers).json[
            "idea"
        ]["ideaId"]
        res = client.post(
            f"/api/ideas/{idea_id}/react",
            json={"type": "dislike"},
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert res.json["reaction"]["type"] == "DISLIKES"


def test_get_viewed_ideas(client: FlaskClient, auth_headers) -> None:
    """Can one get all previously seen ideas?"""

    with client:
        res = client.get("/api/ideas/viewed", headers=auth_headers)
        assert res.status_code == 200
        assert res.json["ideas"] is not None


def test_delete_idea(client: FlaskClient, logged_in_user, auth_headers) -> None:
    """Can a user delete an idea?"""

    with client:
        user_id = logged_in_user["user"]["sub"]
        idea_id = client.get(f"/api/ideas/user/{user_id}", headers=auth_headers).json[
            "ideas"
        ][0]["ideaId"]
        res = client.delete(f"/api/ideas/{idea_id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json["deleted"] == idea_id


def test_can_get_posted_ideas(
    client: FlaskClient, logged_in_user, auth_headers
) -> None:
    """Can one view all ideas posted by a user?"""

    with client:
        id = logged_in_user["user"]["sub"]
        res = client.get(f"/api/ideas/user/{id}", headers=auth_headers)
        print(res.json)
        assert res.status_code == 200
        assert len(res.json["ideas"]) > 0


def test_can_get_idea_details(
    client: FlaskClient, logged_in_user, auth_headers
) -> None:
    """Can one view idea details?"""

    with client:
        user_id = logged_in_user["user"]["sub"]
        idea_id = client.get(f"/api/ideas/user/{user_id}", headers=auth_headers).json[
            "ideas"
        ][0]["ideaId"]
        res = client.get(f"/api/ideas/{idea_id}", headers=auth_headers)
        print(res.json)
        assert res.status_code == 200


def test_get_idea_details_with_reactions(
    client: FlaskClient, logged_in_user, auth_headers
) -> None:
    """Can one view idea details with reactions?"""

    with client:
        user_id = logged_in_user["user"]["sub"]
        idea_id = client.get(f"/api/ideas/user/{user_id}", headers=auth_headers).json[
            "ideas"
        ][0]["ideaId"]
        res = client.get(
            f"/api/ideas/{idea_id}?with-reactions=true", headers=auth_headers
        )
        print(res.json)
        assert res.status_code == 200


def test_get_idea_details_with_all_reactions(
    client: FlaskClient, logged_in_user, auth_headers
) -> None:
    """Can one view idea details with reactions?"""

    with client:
        user_id = logged_in_user["user"]["sub"]
        idea_id = client.get(f"/api/ideas/user/{user_id}", headers=auth_headers).json[
            "ideas"
        ][0]["ideaId"]
        res = client.get(
            f"/api/ideas/{idea_id}?with-reactions=true&with-user-reaction=true",
            headers=auth_headers,
        )
        print(res.json)
        assert res.status_code == 200
