import json
from unittest.mock import AsyncMock, Mock

import pytest

from midea_desktop import cli
from midea_desktop.config import DeviceConfig, save_config
from midea_desktop.presentation import widget_report


def result():
    return {
        "state": {
            "online": True,
            "supported": True,
            "power": False,
            "mode": "COOL",
            "target_temperature": 24,
            "indoor_temperature": 25,
            "id": 123,
            "ip": "192.168.1.50",
            "name": "room",
            "sn": "SERIAL",
            "token": "SECRET",
            "key": "SECRET",
        },
        "capabilities": {
            "min_target_temperature": 16,
            "max_target_temperature": 30,
            "supported_modes": ["COOL"],
            "extra": "unused",
        },
        "capabilities_from_device": True,
    }


def test_presentation_contains_only_required_fields():
    report = widget_report(result())
    text = json.dumps(report)
    for unwanted in ["SECRET", "SERIAL", "192.168", '"id"', '"name"', '"extra"']:
        assert unwanted not in text
    assert report["state"]["power"] is False
    assert report["capabilities_from_device"] is True


@pytest.mark.parametrize("action", ["status", "on", "off", "set"])
def test_widget_routes_explicit_action(monkeypatch, tmp_path, capsys, action):
    path = tmp_path / "device.json"
    save_config(path, DeviceConfig("192.168.1.50", 123, 2))
    controller = Mock()
    controller.status = AsyncMock(return_value=result())
    controller.set = AsyncMock(return_value={"state": result()["state"], "confirmed": True})
    monkeypatch.setattr(cli, "Controller", Mock(return_value=controller))
    argv = ["--config", str(path), "widget", action]
    if action == "set":
        argv += ["--temperature", "23.5", "--mode", "cool"]
    assert cli.main(argv) == 0
    output = json.loads(capsys.readouterr().out)
    assert "token" not in output["state"] and "id" not in output["state"]
    if action == "status":
        controller.status.assert_awaited_once()
        controller.set.assert_not_awaited()
    elif action in ("on", "off"):
        controller.set.assert_awaited_once_with(power=action == "on", timeout=30)
    else:
        controller.set.assert_awaited_once_with(temperature=23.5, mode="cool", timeout=30)


def test_plugin_manifest_and_entrypoint():
    from pathlib import Path

    plugin = Path(__file__).resolve().parents[1] / "omarchy/victor.midea"
    manifest = json.loads((plugin / "manifest.json").read_text())
    assert manifest["id"] == "victor.midea"
    assert manifest["kinds"] == ["bar-widget"]
    assert manifest["barWidget"]["allowMultiple"] is False
    assert manifest["barWidget"]["defaults"]["refreshSeconds"] >= 30
    for entry in manifest["entryPoints"].values():
        assert (plugin / entry).is_file()
    assert not any(p.is_symlink() for p in plugin.iterdir())
