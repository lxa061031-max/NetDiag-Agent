from __future__ import annotations

import pytest

from src.authentication import (
    AuthenticationError,
    AuthenticationService,
    RegistrationError,
    build_device_hash,
    hash_password,
    validate_password,
    verify_password,
)


class FakeRepository:
    def __init__(self):
        self.users = []

    def get_user_by_username(self, username):
        return next((row for row in self.users if row["username"] == username), None)

    def get_user_by_device(self, device_hash):
        return next((row for row in self.users if row["device_hash"] == device_hash), None)

    def create_user(self, **values):
        row = {"user_id": str(len(self.users) + 1), **values}
        self.users.append(row)
        return row

    def update_last_login(self, user_id):
        self.last_login_user_id = user_id


@pytest.mark.parametrize("password", ["A_1!bc", "_Ab1!x", "Net_9?"])
def test_password_policy_and_hash(password):
    assert validate_password(password) == password
    digest, salt, scheme = hash_password(password)
    assert password.encode("utf-8") != digest
    assert verify_password(password, digest, salt, scheme)
    assert not verify_password(password + "x", digest, salt, scheme)


@pytest.mark.parametrize("password", ["1Ab_!x", "Abcdef", "Ab_!xx", "Ab_123456789!", "Ab_1 中文!"])
def test_invalid_password_rejected(password):
    with pytest.raises(RegistrationError):
        validate_password(password)


def test_device_hash_is_deterministic_and_secret_bound():
    kwargs = {
        "ip_address": "127.0.0.1",
        "headers": {"User-Agent": "Browser", "Accept-Language": "zh-CN"},
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
    }
    first = build_device_hash(secret="a" * 24, **kwargs)
    assert first == build_device_hash(secret="a" * 24, **kwargs)
    assert first != build_device_hash(secret="b" * 24, **kwargs)


def test_one_device_one_account_and_login():
    repository = FakeRepository()
    service = AuthenticationService(repository)
    user = service.register(
        username="student_1",
        password="Net_1!",
        password_confirmation="Net_1!",
        device_hash="device-a",
    )
    assert user.username == "student_1"
    with pytest.raises(RegistrationError, match="设备"):
        service.register(
            username="student_2",
            password="Net_2!",
            password_confirmation="Net_2!",
            device_hash="device-a",
        )
    assert service.authenticate(username="student_1", password="Net_1!", device_hash="device-a") == user
    with pytest.raises(AuthenticationError):
        service.authenticate(username="student_1", password="Net_1!", device_hash="device-b")
