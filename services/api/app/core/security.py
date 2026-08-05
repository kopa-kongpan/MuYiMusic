import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import jwt

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
JWT_ALGORITHM = "HS256"
TokenSubjectType = Literal["admin", "user"]


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        PASSWORD_ITERATIONS,
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode()
    encoded_digest = base64.urlsafe_b64encode(digest).decode()
    return "$".join(
        (
            PASSWORD_ALGORITHM,
            str(PASSWORD_ITERATIONS),
            encoded_salt,
            encoded_digest,
        )
    )


def verify_password(password: str, encoded_password: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_digest = encoded_password.split(
            "$", maxsplit=3
        )
        if algorithm != PASSWORD_ALGORITHM:
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode())
        expected_digest = base64.urlsafe_b64decode(encoded_digest.encode())
        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual_digest, expected_digest)


def create_access_token(
    subject_id: UUID,
    secret: str,
    expires_in_minutes: int,
    subject_type: TokenSubjectType = "admin",
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject_id),
        "type": subject_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_in_minutes),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(
    token: str,
    secret: str,
    expected_subject_type: TokenSubjectType = "admin",
) -> UUID:
    payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != expected_subject_type:
        raise jwt.InvalidTokenError("Token subject type is invalid")
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise jwt.InvalidTokenError("Token subject is missing")
    try:
        return UUID(subject)
    except ValueError as error:
        raise jwt.InvalidTokenError("Token subject is invalid") from error
