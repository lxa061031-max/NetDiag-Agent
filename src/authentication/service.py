"""安全的账户校验、密码哈希与设备绑定服务。"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import string
from dataclasses import dataclass
from typing import Protocol


PASSWORD_ITERATIONS = 310_000
PASSWORD_SCHEME = f"pbkdf2_sha256${PASSWORD_ITERATIONS}"
USERNAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,31}$")
PASSWORD_ALLOWED_CHARACTERS = frozenset(string.ascii_letters + string.digits + string.punctuation)


class AuthenticationError(RuntimeError):
    """登录失败，避免暴露账号是否存在。"""


class RegistrationError(RuntimeError):
    """注册失败。"""


class UserRepository(Protocol):
    def get_user_by_username(self, username: str) -> dict[str, object] | None: ...

    def get_user_by_device(self, device_hash: str) -> dict[str, object] | None: ...

    def create_user(
        self,
        *,
        username: str,
        password_hash: bytes,
        password_salt: bytes,
        password_scheme: str,
        device_hash: str,
    ) -> dict[str, object]: ...

    def update_last_login(self, user_id: str) -> None: ...


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    username: str
    device_hash: str


def validate_username(username: str) -> str:
    """账号使用字母、数字和下划线，便于数据库唯一索引稳定比较。"""

    if not isinstance(username, str):
        raise RegistrationError("账号必须是文本。")
    normalized = username.strip()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise RegistrationError("账号需为3-32位字母、数字或下划线，并以字母或下划线开头。")
    return normalized


def validate_password(password: str) -> str:
    """执行用户指定的6-12位复合密码规则。"""

    if not isinstance(password, str):
        raise RegistrationError("密码必须是文本。")
    if not 6 <= len(password) <= 12:
        raise RegistrationError("密码长度必须为6-12位。")
    if not re.match(r"^[A-Za-z_]", password):
        raise RegistrationError("密码必须以字母或下划线开头。")
    if any(character not in PASSWORD_ALLOWED_CHARACTERS for character in password):
        raise RegistrationError("密码包含不支持的字符。")
    requirements = (
        (re.search(r"[A-Za-z]", password), "字母"),
        ("_" in password, "下划线"),
        (re.search(r"\d", password), "数字"),
        (any(character in string.punctuation and character != "_" for character in password), "特殊字符"),
    )
    missing = [label for matched, label in requirements if not matched]
    if missing:
        raise RegistrationError("密码还必须包含：" + "、".join(missing) + "。")
    return password


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes, str]:
    """使用PBKDF2-HMAC-SHA256生成不可逆密码摘要。"""

    validated = validate_password(password)
    active_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        validated.encode("utf-8"),
        active_salt,
        PASSWORD_ITERATIONS,
    )
    return digest, active_salt, PASSWORD_SCHEME


def verify_password(
    password: str,
    expected_hash: bytes,
    salt: bytes,
    scheme: str,
) -> bool:
    if scheme != PASSWORD_SCHEME or not isinstance(password, str):
        return False
    calculated = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return hmac.compare_digest(calculated, expected_hash)


def build_device_hash(
    *,
    secret: str,
    ip_address: str | None,
    headers: dict[str, str],
    locale: str | None,
    timezone: str | None,
) -> str:
    """从会话环境生成不可逆设备指纹，不保存原始IP和请求头。"""

    if not secret or len(secret) < 24:
        raise ValueError("AUTH_DEVICE_SECRET至少需要24个字符。")
    normalized_headers = {str(key).casefold(): str(value) for key, value in headers.items()}
    payload = {
        "ip": ip_address or "",
        "user_agent": normalized_headers.get("user-agent", ""),
        "accept_language": normalized_headers.get("accept-language", ""),
        "platform": normalized_headers.get("sec-ch-ua-platform", ""),
        "locale": locale or "",
        "timezone": timezone or "",
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()


class AuthenticationService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def register(
        self,
        *,
        username: str,
        password: str,
        password_confirmation: str,
        device_hash: str,
    ) -> AuthenticatedUser:
        validated_username = validate_username(username)
        validated_password = validate_password(password)
        if validated_password != password_confirmation:
            raise RegistrationError("两次输入的密码不一致。")
        if self.repository.get_user_by_device(device_hash):
            raise RegistrationError("当前设备已经绑定账号，不能再次创建账号。")
        if self.repository.get_user_by_username(validated_username):
            raise RegistrationError("该账号已存在，请更换账号名。")
        password_hash, salt, scheme = hash_password(validated_password)
        try:
            row = self.repository.create_user(
                username=validated_username,
                password_hash=password_hash,
                password_salt=salt,
                password_scheme=scheme,
                device_hash=device_hash,
            )
        except Exception as exc:
            if exc.__class__.__name__ in {"IntegrityError", "DatabaseConflictError"}:
                raise RegistrationError("账号或设备已被绑定，请刷新页面后重试。") from exc
            raise
        return AuthenticatedUser(
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            device_hash=str(row["device_hash"]),
        )

    def authenticate(
        self,
        *,
        username: str,
        password: str,
        device_hash: str,
    ) -> AuthenticatedUser:
        normalized_username = username.strip() if isinstance(username, str) else ""
        row = self.repository.get_user_by_username(normalized_username)
        if not row or str(row["device_hash"]) != device_hash:
            raise AuthenticationError("账号、密码或设备绑定不匹配。")
        if not verify_password(
            password,
            bytes(row["password_hash"]),
            bytes(row["password_salt"]),
            str(row["password_scheme"]),
        ):
            raise AuthenticationError("账号、密码或设备绑定不匹配。")
        user = AuthenticatedUser(
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            device_hash=str(row["device_hash"]),
        )
        self.repository.update_last_login(user.user_id)
        return user
