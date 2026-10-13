import json

from midea_desktop.cli import main


def test_frames_offline(capsys):
    assert main(["frames"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["offline"] is True
    for frame in output["frames"].values():
        assert bytes.fromhex(frame)[0] == 0xAA


def test_missing_config_is_actionable(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "missing.json"), "status"]) == 1
    assert "não configurado" in capsys.readouterr().err


def test_invalid_timeout(capsys):
    assert main(["--timeout", "nan", "discover"]) == 1
    assert "timeout" in capsys.readouterr().err


def test_discovery_json(monkeypatch, capsys):
    import midea_desktop.cli as cli

    async def empty(**kwargs):
        return []

    monkeypatch.setattr(cli, "discover", empty)
    assert main(["discover"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_library_error_does_not_leak(monkeypatch, capsys):
    import midea_desktop.cli as cli

    async def fail(args):
        raise RuntimeError("token=SECRET")

    monkeypatch.setattr(cli, "execute", fail)
    assert main(["status"]) == 1
    assert "SECRET" not in capsys.readouterr().err
