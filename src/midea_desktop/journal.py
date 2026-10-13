"""Diário semântico: não registra pacotes, credenciais nem identificadores."""

import json
import os
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

SECRET_FIELDS = {
    "token",
    "key",
    "password",
    "account",
    "access_token",
    "accesstoken",
    "session",
    "sn",
    "serial",
    "loginaccount",
}
IDENTITY_FIELDS = {
    "host",
    "ip",
    "id",
    "device_id",
    "name",
    "cloud_appliance_id",
    "appliancecodes",
    "udpid",
}


def public(value, *, anonymize: bool = False):
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, dict):
        excluded = SECRET_FIELDS | (IDENTITY_FIELDS if anonymize else set())
        return {
            str(k): public(v, anonymize=anonymize)
            for k, v in value.items()
            if str(k).lower() not in excluded
        }
    if isinstance(value, (list, tuple, set)):
        return [public(v, anonymize=anonymize) for v in value]
    return value


class Journal:
    def __init__(self, path: Path | None = None):
        self.path = path

    def record(self, operation: str, **details) -> None:
        if self.path is None:
            return
        event = {
            "time": datetime.now(UTC).isoformat(),
            "operation": operation,
            **public(details, anonymize=True),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW
        fd = os.open(self.path, flags, 0o600)
        with os.fdopen(fd, "a") as stream:
            if os.fstat(stream.fileno()).st_mode & 0o077:
                raise ValueError("O diário existente deve ter permissão 600.")
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
