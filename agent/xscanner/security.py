import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from .config import allowed_origins


@dataclass
class Session:
    created: float
    tech_until: float = 0


class Security:
    def __init__(self) -> None:
        self.pair_code = f"{secrets.randbelow(1_000_000):06d}"
        self.pair_until = time.monotonic() + 600
        self.sessions: dict[str, Session] = {}
        self.failed_pairs = 0
        self.last_pair = 0.0
        self.failed_tech = 0
        self.last_tech = 0.0

    def check_origin(self, request: Request) -> None:
        origin = request.headers.get("origin", "")
        if origin not in allowed_origins():
            raise HTTPException(403, "Origen no autorizado")

    def pair(self, code: str) -> str:
        now = time.monotonic()
        if self.failed_pairs >= 5 and now - self.last_pair < 60:
            raise HTTPException(429, "Demasiados intentos; espera un minuto")
        if now > self.pair_until or not hmac.compare_digest(code, self.pair_code):
            self.failed_pairs += 1
            self.last_pair = now
            raise HTTPException(401, "Código inválido o vencido")
        token = secrets.token_urlsafe(32)
        self.sessions[token] = Session(now)
        self.pair_code = ""
        self.pair_until = 0
        return token

    def require(self, request: Request) -> Session:
        self.check_origin(request)
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(401, "Se requiere vinculación")
        session = self.sessions.get(header[7:])
        if not session:
            raise HTTPException(401, "Sesión inválida")
        return session

    def require_tech(self, request: Request) -> Session:
        session = self.require(request)
        if session.tech_until < time.monotonic():
            raise HTTPException(403, "Modo técnico bloqueado")
        session.tech_until = time.monotonic() + 900
        return session

    def check_tech_attempt(self) -> None:
        now = time.monotonic()
        if self.failed_tech >= 5 and now - self.last_tech < 60:
            raise HTTPException(429, "Demasiados intentos; espera un minuto")
        if now - self.last_tech >= 60:
            self.failed_tech = 0

    def tech_failure(self) -> None:
        self.failed_tech += 1
        self.last_tech = time.monotonic()


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 350_000)
    return salt.hex() + ":" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split(":", 1)
        candidate = password_hash(password, bytes.fromhex(salt)).split(":", 1)[1]
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False
