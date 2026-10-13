from unittest.mock import AsyncMock

import pytest
from msmart.device import AirConditioner as AC

from midea_desktop import controller as module
from midea_desktop.config import DeviceConfig
from midea_desktop.controller import Controller, bootstrap, discover
from midea_desktop.transport import VerifiedAC


class FakeAC(VerifiedAC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._min_target_temperature = 16
        self._max_target_temperature = 30
        self._supported_op_modes = [AC.OperationalMode.COOL, AC.OperationalMode.FAN_ONLY]
        self._power_state = True
        self._target_temperature = 23
        self._operational_mode = AC.OperationalMode.COOL
        self._fan_speed = AC.FanSpeed.LOW
        self.committed = self.to_dict()
        self.calls = []
        self.reachable = True
        self.ignore_control = False
        self.stale_after_apply = False

    async def authenticate(self, token, key):
        self.calls.append("authenticate")

    async def get_capabilities(self):
        self.calls.append("capabilities")

    async def refresh(self):
        self.calls.append("refresh")
        self._online = self._supported = self.reachable
        if self.reachable and not (self.stale_after_apply and "apply" in self.calls):
            self.state_updates += 1
        self._power_state = self.committed["power"]
        self._target_temperature = self.committed["target_temperature"]
        self._operational_mode = self.committed["mode"]
        self._fan_speed = self.committed["fan_speed"]

    async def apply(self):
        self.calls.append("apply")
        self._online = self.reachable
        if not self.ignore_control:
            self.committed = self.to_dict()


@pytest.fixture
def controller():
    return Controller(DeviceConfig("192.168.1.50", 123, 2), factory=FakeAC)


async def test_read_before_write_preserves_settings(controller):
    result = await controller.set(power=False)
    assert controller.device.calls == ["capabilities", "refresh", "apply", "refresh"]
    assert result["confirmed"]
    assert result["state"]["power"] is False
    assert result["state"]["target_temperature"] == 23
    assert result["state"]["mode"] == "COOL"
    assert result["state"]["fan_speed"] == "LOW"
    assert "key" not in result["state"]
    assert "token" not in result["state"]


async def test_status_never_controls(controller):
    result = await controller.status()
    assert controller.device.calls == ["capabilities", "refresh"]
    assert result["state"]["power"] is True


@pytest.mark.parametrize("temperature", [15, 31, 23.1, float("nan"), float("inf")])
async def test_bad_temperature_never_controls(controller, temperature):
    with pytest.raises(ValueError):
        await controller.set(temperature=temperature)
    assert "apply" not in controller.device.calls


async def test_unsupported_mode_never_controls(controller):
    with pytest.raises(ValueError):
        await controller.set(mode="heat")
    assert "apply" not in controller.device.calls


async def test_offline_never_controls(controller):
    controller.device.reachable = False
    with pytest.raises(ConnectionError):
        await controller.set(power=False)
    assert "apply" not in controller.device.calls


async def test_unconfirmed_command_is_not_success(controller):
    controller.device.ignore_control = True
    with pytest.raises(ConnectionError, match="não confirmou"):
        await controller.set(power=False)


async def test_stale_flags_cannot_confirm_control(controller):
    controller.device.stale_after_apply = True
    with pytest.raises(ConnectionError, match="Nenhuma nova resposta"):
        await controller.set(power=False)


async def test_timeout_never_controls(controller):
    import asyncio

    async def delayed():
        await asyncio.sleep(1)

    controller.device.get_capabilities = delayed
    with pytest.raises(TimeoutError):
        await controller.set(power=False, timeout=0.01)
    assert "apply" not in controller.device.calls


async def test_local_discovery_disables_cloud(monkeypatch):
    call = AsyncMock(return_value=[])
    monkeypatch.setattr(module.Discover, "discover", call)
    assert await discover() == []
    call.assert_awaited_once_with(target="255.255.255.255", timeout=5, auto_connect=False)


async def test_v3_uses_saved_keys_only():
    instance = Controller(
        DeviceConfig("192.168.1.50", 123, 3, token="ab" * 64, key="cd" * 32),
        factory=FakeAC,
    )
    await instance.status()
    await instance.status()
    assert instance.device.calls.count("authenticate") == 1


async def test_bootstrap_smarthome_uses_own_account(monkeypatch):
    device = FakeAC(ip="192.168.1.50", port=6444, device_id=123, version=3)
    cloud = type(
        "Cloud",
        (),
        {
            "login": AsyncMock(),
            "get_token": AsyncMock(return_value=("ab" * 64, "cd" * 32)),
        },
    )()
    received = {}

    def factory(region, **kwargs):
        received.update(region=region, **kwargs)
        return cloud

    async def authenticate(token, key):
        device._lan._token = bytes.fromhex(token)
        device._lan._key = bytes.fromhex(key)

    device.authenticate = authenticate
    monkeypatch.setattr(module, "SmartHomeCloud", factory)
    config = await bootstrap(device, provider="smarthome", account="user", password="SECRET")
    assert received == {"region": "US", "account": "user", "password": "SECRET"}
    assert config.token == "ab" * 64
    cloud.login.assert_awaited_once()
    assert "apply" not in device.calls
