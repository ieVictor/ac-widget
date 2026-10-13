import json
from unittest.mock import AsyncMock, Mock

import pytest
from msmart.cloud import ApiError

from midea_desktop import cli
from midea_desktop import controller as module
from midea_desktop.config import DeviceConfig, load_config
from midea_desktop.transport import VerifiedAC


@pytest.fixture
def device():
    instance = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123, version=3)
    instance._online = instance._supported = True
    instance.refresh_verified = AsyncMock()
    instance.apply = AsyncMock()

    async def authenticate(token, key):
        instance._lan._token = bytes.fromhex(token)
        instance._lan._key = bytes.fromhex(key)

    instance.authenticate = AsyncMock(side_effect=authenticate)
    return instance


async def test_shared_bootstrap_requires_explicit_opt_in(monkeypatch, device):
    factory = Mock()
    monkeypatch.setattr(module, "SmartHomeCloud", factory)
    with pytest.raises(ValueError, match="explicitamente"):
        await module.bootstrap(device, provider="smarthome")
    factory.assert_not_called()
    device.apply.assert_not_awaited()


async def test_shared_bootstrap_rejects_personal_credentials(monkeypatch, device):
    factory = Mock()
    monkeypatch.setattr(module, "SmartHomeCloud", factory)
    with pytest.raises(ValueError, match="Não misture"):
        await module.bootstrap(
            device, provider="smarthome", shared_account=True, account="personal", password="SECRET"
        )
    factory.assert_not_called()


async def test_shared_bootstrap_uses_upstream_credentials_and_only_reads(monkeypatch, device):
    cloud = Mock()
    cloud.login = AsyncMock()
    cloud.get_token = AsyncMock(return_value=("ab" * 64, "cd" * 32))
    factory = Mock(return_value=cloud)
    monkeypatch.setattr(module, "SmartHomeCloud", factory)
    config = await module.bootstrap(device, provider="smarthome", shared_account=True)
    factory.assert_called_once_with("US")
    cloud.login.assert_awaited_once()
    device.authenticate.assert_awaited_once_with("ab" * 64, "cd" * 32)
    device.refresh_verified.assert_awaited_once()
    device.apply.assert_not_awaited()
    assert config.token == "ab" * 64


async def test_other_endian_is_tried_after_api_rejection(monkeypatch, device):
    cloud = Mock()
    cloud.login = AsyncMock()
    cloud.get_token = AsyncMock(side_effect=[ApiError("SECRET", code=3004), ("ab" * 64, "cd" * 32)])
    monkeypatch.setattr(module, "SmartHomeCloud", Mock(return_value=cloud))
    await module.bootstrap(device, provider="smarthome", shared_account=True)
    assert cloud.get_token.await_count == 2
    calls = cloud.get_token.await_args_list
    assert calls[0].args[0] != calls[1].args[0]
    device.apply.assert_not_awaited()


async def test_permission_denied_stops_without_endian_retry(monkeypatch, device):
    cloud = Mock()
    cloud.login = AsyncMock()
    cloud.get_token = AsyncMock(side_effect=ApiError("SECRET", code=3201))
    monkeypatch.setattr(module, "SmartHomeCloud", Mock(return_value=cloud))
    with pytest.raises(ApiError):
        await module.bootstrap(device, provider="smarthome", shared_account=True)
    assert cloud.get_token.await_count == 1
    device.authenticate.assert_not_awaited()
    device.refresh_verified.assert_not_awaited()
    device.apply.assert_not_awaited()


async def test_cloud_id_and_lan_id_are_kept_separate(monkeypatch, device):
    from msmart.lan import Security

    cloud = Mock()
    cloud.login = AsyncMock()
    cloud.get_token = AsyncMock(return_value=("ab" * 64, "cd" * 32))
    monkeypatch.setattr(module, "SmartHomeCloud", Mock(return_value=cloud))
    config = await module.bootstrap(
        device,
        provider="smarthome",
        account="owner",
        password="SECRET",
        cloud_appliance_id=456,
    )
    expected_udpid = Security.udpid(device.id.to_bytes(6, "little")).hex()
    cloud.get_token.assert_awaited_once_with(expected_udpid, 456)
    assert config.device_id == 123
    device.apply.assert_not_awaited()


@pytest.mark.parametrize("cloud_id", [0, -1, True, "456"])
async def test_invalid_cloud_id_never_contacts_cloud(monkeypatch, device, cloud_id):
    factory = Mock()
    monkeypatch.setattr(module, "SmartHomeCloud", factory)
    with pytest.raises(ValueError, match="ID cloud"):
        await module.bootstrap(
            device,
            provider="smarthome",
            shared_account=True,
            cloud_appliance_id=cloud_id,
        )
    factory.assert_not_called()


def test_shared_cli_does_not_prompt_or_leak_keys(monkeypatch, tmp_path, capsys, device):
    monkeypatch.setattr(cli, "discover", AsyncMock(return_value=[device]))
    setup = AsyncMock(
        return_value=DeviceConfig("192.168.1.50", 123, 3, token="ab" * 64, key="cd" * 32)
    )
    monkeypatch.setattr(cli, "bootstrap", setup)

    def forbidden(*args, **kwargs):
        raise AssertionError("Não deve pedir senha pessoal nem controlar o aparelho")

    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr(cli.getpass, "getpass", forbidden)
    monkeypatch.setattr(cli.Controller, "set", forbidden)
    path = tmp_path / "device.json"
    assert (
        cli.main(["--config", str(path), "bootstrap", "--host", "192.168.1.50", "--shared-account"])
        == 0
    )
    output = capsys.readouterr().out
    assert json.loads(output)["verified"] is True
    assert "abab" not in output and "cdcd" not in output
    assert load_config(path).version == 3
    assert setup.await_args.kwargs["shared_account"] is True
    assert setup.await_args.kwargs["account"] is None
    assert setup.await_args.kwargs["password"] is None


@pytest.mark.parametrize(
    ("code", "provider", "message"),
    [
        (3201, "smarthome", "conta proprietária"),
        (9999, "nethome", "relatos de falha"),
        (3004, "smarthome", "parâmetros"),
    ],
)
def test_cloud_failure_is_actionable_without_raw_message(
    monkeypatch,
    tmp_path,
    capsys,
    device,
    code,
    provider,
    message,
):
    monkeypatch.setattr(cli, "discover", AsyncMock(return_value=[device]))
    monkeypatch.setattr(cli, "bootstrap", AsyncMock(side_effect=ApiError("SECRET", code=code)))
    path = tmp_path / "device.json"
    assert (
        cli.main(
            [
                "--config",
                str(path),
                "bootstrap",
                "--host",
                "192.168.1.50",
                "--shared-account",
                "--provider",
                provider,
            ]
        )
        == 1
    )
    output = capsys.readouterr()
    assert message in output.err
    assert "SECRET" not in output.err + output.out
    assert not path.exists()


def test_cloud_failure_does_not_save_or_leak(monkeypatch, tmp_path, capsys, device):
    monkeypatch.setattr(cli, "discover", AsyncMock(return_value=[device]))
    monkeypatch.setattr(cli, "bootstrap", AsyncMock(side_effect=ApiError("SECRET", code=3101)))
    path = tmp_path / "device.json"
    assert (
        cli.main(["--config", str(path), "bootstrap", "--host", "192.168.1.50", "--shared-account"])
        == 1
    )
    output = capsys.readouterr()
    assert "3101" in output.err
    assert "SECRET" not in output.err + output.out
    assert not path.exists()
    device.apply.assert_not_awaited()
