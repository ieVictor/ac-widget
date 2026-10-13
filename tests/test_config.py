import json
import stat

import pytest

from midea_desktop.config import DeviceConfig, load_config, save_config


def test_private_roundtrip(tmp_path):
    path = tmp_path / "device.json"
    config = DeviceConfig("192.168.1.50", 123, 3, token="ab" * 64, key="cd" * 32)
    save_config(path, config)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_config(path) == config
    assert "abab" not in repr(config)
    assert "cdcd" not in repr(config)


def test_overwrite_requires_consent(tmp_path):
    path = tmp_path / "device.json"
    first = DeviceConfig("192.168.1.50", 123, 2)
    other = DeviceConfig("192.168.1.51", 456, 2)
    save_config(path, first)
    with pytest.raises(FileExistsError):
        save_config(path, other)
    assert load_config(path) == first
    save_config(path, other, replace=True)
    assert load_config(path) == other
    assert not list(tmp_path.glob("*.tmp"))


def test_rejects_world_readable_config(tmp_path):
    path = tmp_path / "device.json"
    save_config(path, DeviceConfig("192.168.1.50", 123, 2))
    path.chmod(0o644)
    with pytest.raises(ValueError, match="privada"):
        load_config(path)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"version": 1},
        {"version": 3},
        {"device_id": 0},
        {"device_id": 2**48},
        {"device_id": True},
        {"port": 0},
        {"host": "255.255.255.255"},
        {"host": "224.0.0.1"},
        {"token": "not-hex", "key": "cd" * 32},
        {"token": "ab", "key": "cd"},
        {"token": "ab"},
    ],
)
def test_validation(kwargs):
    values = {"host": "192.168.1.50", "device_id": 123, "version": 2} | kwargs
    with pytest.raises(ValueError):
        DeviceConfig(**values)


def test_bad_json(tmp_path):
    path = tmp_path / "device.json"
    path.write_text(json.dumps({"unexpected": "value"}))
    path.chmod(0o600)
    with pytest.raises(ValueError, match="inválida"):
        load_config(path)
