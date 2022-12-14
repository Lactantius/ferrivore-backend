"""User model"""

from datetime import datetime
import jwt
import bcrypt
from flask import current_app
from neo4j.exceptions import ConstraintError

from app.exceptions.validation_exception import ValidationException
from app.types import RegistrationData, User, UserToken, UserData

##############################################################################
# Transaction functions
#


def create_user(tx, email: str, encrypted: str, username: str) -> User:
    """Transaction function for adding a new user to the database"""
    return tx.run(
        """
        CREATE (u:User {
            userId: randomUuid(),
            email: $email,
            password: $encrypted,
            username: $username
        })
        RETURN u
        """,
        email=email,
        encrypted=encrypted,
        username=username,
    ).single()


def user_by_email(tx, email: str) -> User | None:
    """
    Transaction function for getting a user from the database
    TODO: Let user be found by username as well
    """
    user = tx.run(
        """
        MATCH (u:User {email: $email})
        RETURN u {
            .*
        }
        """,
        email=email,
    ).single()

    if user is None:
        return None

    return user.get("u")


def user_by_id(tx, user_id: str) -> User | None:
    """Transaction function for getting a user from the database"""
    user = tx.run(
        """
        MATCH (u:User {userId: $user_id})
        RETURN u {
            .*
        }
        """,
        user_id=user_id,
    ).single()

    if user is None:
        return None

    return user.get("u")


##############################################################################
# Main functions
#


def register(driver, data: RegistrationData) -> UserToken:
    """Register a new user"""

    encrypted = bcrypt.hashpw(data["password"].encode("utf8"), bcrypt.gensalt()).decode(
        "utf8"
    )

    try:
        with driver.session() as session:
            result = session.execute_write(
                create_user, data["email"], encrypted, data["username"]
            )

    except ConstraintError as err:
        raise ValidationException(err.message, {"email": err.message})

    user = result["u"]

    payload = {
        "userId": user["userId"],
        "email": user["email"],
        "username": user["username"],
    }

    # Generate Token
    payload["token"] = generate_token(payload)

    return payload


def authenticate(driver, email: str, password: str) -> UserToken | bool:
    """
    Find user by email address, hash password, and check against stored hash.
    If sucessful, return a dictionary containing the keys userId, email, username, and token.
    If unsuccessful, return False
    """

    with driver.session() as session:
        user = session.execute_read(user_by_email, email)

    if user is None:
        return False

    if (
        bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8"))
        is False
    ):
        return False

    payload = {
        "userId": user["userId"],
        "email": user["email"],
        "username": user["username"],
    }

    payload["token"] = generate_token(payload)

    return payload


def find_user(driver, user_id: str) -> User | None:
    with driver.session() as session:
        return session.execute_read(user_by_id, user_id)


def edit_user(
    driver,
    user_id: str,
    current_password: str,
    new_username: str | None = None,
    new_email: str | None = None,
    new_password: str | None = None,
) -> UserToken:
    """Edit an existing user"""

    def update_username(tx, user_id: str, username: str):
        return tx.run(
            """
            MATCH (u:User {userId: $user_id})
            SET u.username = $username
            RETURN u {
                userId: u.userId,
                username: u.username,
                email: u.email
            }
            """,
            user_id=user_id,
            username=username,
        ).single()[0]

    def update_email(tx, user_id: str, email: str):
        return tx.run(
            """
            MATCH (u:User {userId: $user_id})
            SET u.email = $email
            RETURN u {
                userId: u.userId,
                username: u.username,
                email: u.email
            }
            """,
            user_id=user_id,
            email=email,
        ).single()[0]

    def update_password(tx, user_id: str, password: str):
        return tx.run(
            """
            MATCH (u:User {userId: $user_id})
            SET u.password = $password
            RETURN u {
                userId: u.userId,
                username: u.username,
                email: u.email
            }
            """,
            user_id=user_id,
            password=password,
        ).single()[0]

    with driver.session() as session:

        user = session.execute_read(user_by_id, user_id)

        if user is None:
            raise ValidationException(
                "Invalid password",
                {"details": None},
            )

        if (
            bcrypt.checkpw(
                current_password.encode("utf-8"), user["password"].encode("utf-8")
            )
            is False
        ):
            raise ValidationException(
                "Invalid password",
                {"details": None},
            )

        try:
            if new_username:
                user = session.execute_write(update_username, user_id, new_username)
            if new_email:
                user = session.execute_write(update_email, user_id, new_email)

        except ConstraintError as err:
            raise ValidationException(err.message, {"email": err.message})

        if new_password:
            encrypted = bcrypt.hashpw(
                new_password.encode("utf8"), bcrypt.gensalt()
            ).decode("utf8")
            user = session.execute_write(update_password, user_id, encrypted)

        payload = {
            "userId": user["userId"],
            "email": user["email"],
            "username": user["username"],
        }

        # Generate Token
        # token = generate_token(user_data)
        # return token
        payload["token"] = generate_token(payload)

        return payload


##############################################################################
# Helper functions
#


def generate_token(payload: UserData) -> UserToken:
    """
    Generate a JWT
    TODO Change this from the Neo4j example project to be functional
    """
    iat = datetime.utcnow()
    jwt_secret = current_app.config.get("JWT_SECRET_KEY")

    # token_data = {
    #     **data,
    #     "sub": data["userId"],
    #     "iat": iat,
    #     "nbbf": iat,
    #     "ext": iat + current_app.config.get("JWT_EXPIRATION_DELTA"),
    # }
    # token = {
    #     **token_data,
    #     "token": jwt.encode(token_data, jwt_secret, algorithm="HS256"),
    # }

    # return token
    payload["sub"] = payload["userId"]
    payload["iat"] = iat
    payload["nbf"] = iat
    payload["exp"] = iat + current_app.config.get("JWT_EXPIRATION_DELTA")

    jwt_secret = current_app.config.get("JWT_SECRET_KEY")

    return jwt.encode(payload, jwt_secret, algorithm="HS256")  # .decode("ascii")


def decode_token(auth_token, jwt_secret):
    """Attempt to decode a JWT"""

    try:
        payload = jwt.decode(auth_token, jwt_secret)
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
