"""Configuração local privada, sem credenciais da conta SmartHome."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from ipaddress import IPv4Address
from pathlib import Path


def config_path() -> Path:
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "midea-desktop/device.json"
    )


@dataclass(frozen=True)
class DeviceConfig:
    host: str
    device_id: int
    version: int
    port: int = 6444
    token: str | None = field(default=None, repr=False)
    key: str | None = field(default=None, repr=False)

    def __post_init__(self):
        address = IPv4Address(self.host)
        if address.is_unspecified or address.is_multicast or int(address) == 0xFFFFFFFF:
            raise ValueError("Use o IPv4 unicast do aparelho.")
        if type(self.device_id) is not int or not 0 < self.device_id < 2**48:
            raise ValueError("O ID deve ser um inteiro positivo de até 48 bits.")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("Porta inválida.")
        if type(self.version) is not int or self.version not in (2, 3):
            raise ValueError("Somente protocolos V2 e V3 são contemplados.")
        if self.version == 3 and not (self.token and self.key):
            raise ValueError("V3 exige token e key; execute bootstrap ou configure manualmente.")
        if bool(self.token) != bool(self.key):
            raise ValueError("Forneça token e key juntos.")
        for name, value in (("token", self.token), ("key", self.key)):
            if value is not None:
                try:
                    decoded = bytes.fromhex(value)
                except (ValueError, TypeError):
                    raise ValueError(f"{name} deve ser hexadecimal.") from None
                if not decoded:
                    raise ValueError(f"{name} não pode ser vazio.")
                if name == "key" and len(decoded) not in (16, 24, 32):
                    raise ValueError("key deve ter 16, 24 ou 32 bytes.")


def load_config(path: Path) -> DeviceConfig:
    if not path.exists():
        raise ValueError(
            "Aparelho não configurado. Execute discover e depois bootstrap ou configure."
        )
    if path.stat().st_mode & 0o077:
        raise ValueError(f"Configuração deve ser privada. Execute: chmod 600 {path}")
    try:
        return DeviceConfig(**json.loads(path.read_text()))
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Configuração inválida. Refaça bootstrap ou configure.") from None


def save_config(path: Path, config: DeviceConfig, *, replace: bool = False) -> None:
    """Publica um arquivo 0600 completo; não sobrescreve sem consentimento."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".device-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(asdict(config), stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # Link atômico também impede sobrescrita em caso de corrida.
            os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
