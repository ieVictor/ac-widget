from unittest.mock import AsyncMock, Mock

import pytest
from msmart.device import AirConditioner as AC
from msmart.device.AC.command import PropertiesResponse, PropertyId
from test_controller import FakeAC

from midea_desktop import cli
from midea_desktop.config import DeviceConfig, save_config
from midea_desktop.controller import Controller
from midea_desktop.transport import VerifiedAC


class FakeIeco(FakeAC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._capabilities.set(AC.Capability.IECO, True)
        self._ieco_number = 8
        self.capabilities_received = True
        self.missing_ieco = False
        self.stale_ieco = False

    async def refresh(self):
        await super().refresh()
        if not self.missing_ieco and not (self.stale_ieco and "ieco" in self.calls):
            self._ieco = self.committed["ieco"]
            self.ieco_updates += 1

    async def apply_ieco(self, enabled):
        self.calls.append("ieco")
        if not self.ignore_control:
            self.committed["ieco"] = enabled


@pytest.fixture
def controller():
    return Controller(DeviceConfig("192.168.1.50", 123, 2), factory=FakeIeco)


@pytest.mark.parametrize("enabled", [True, False])
async def test_ieco_only_changes_property(controller, enabled):
    result = await controller.set_ieco(enabled)
    assert result["confirmed"] and result["state"]["ieco"] is enabled
    assert result["state"]["power"] is True
    assert result["state"]["target_temperature"] == 23
    assert result["state"]["mode"] == "COOL"
    assert controller.device.calls == ["capabilities", "refresh", "ieco", "refresh"]
    assert "apply" not in controller.device.calls


@pytest.mark.parametrize("failure", ["unsupported", "off", "mode", "missing", "capabilities"])
async def test_ieco_guards_before_writing(controller, failure):
    d = controller.device
    if failure == "unsupported":
        d._capabilities.set(AC.Capability.IECO, False)
    elif failure == "off":
        d.committed["power"] = False
    elif failure == "capabilities":
        d.capabilities_received = False
    elif failure == "mode":
        d.committed["mode"] = AC.OperationalMode.FAN_ONLY
    else:
        d.missing_ieco = True
    with pytest.raises((ValueError, ConnectionError)):
        await controller.set_ieco(True)
    assert "ieco" not in d.calls


@pytest.mark.parametrize("failure", ["ignored", "stale"])
async def test_ieco_requires_new_property_and_matching_value(controller, failure):
    controller.device.ignore_control = failure == "ignored"
    controller.device.stale_ieco = failure == "stale"
    with pytest.raises(ConnectionError, match="não confirmou"):
        await controller.set_ieco(True)


async def test_missing_ieco_is_unknown_not_default_false(controller):
    controller.device.missing_ieco = True
    result = await controller.status()
    assert result["state"]["ieco"] is None


async def test_property_write_encoding_does_not_apply_full_state():
    d = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123)
    d._ieco_number = 8
    d._apply_properties = AsyncMock()
    await d.apply_ieco(True)
    d._apply_properties.assert_awaited_once_with({PropertyId.IECO: (8, True)})
    assert PropertyId.IECO.encode((8, True)) == bytes([0, 8, 1]) + bytes(10)


async def test_property_counter_requires_actual_ieco(monkeypatch):
    d = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123)
    response = Mock(spec=PropertiesResponse)
    response.get_property.side_effect = lambda prop: False if prop == PropertyId.IECO else None
    d._update_state(response)
    assert d.ieco_updates == 1
    response.get_property.return_value = None
    response.get_property.side_effect = None
    d._update_state(response)
    assert d.ieco_updates == 1


@pytest.mark.parametrize("enabled", ["on", "off"])
def test_widget_ieco_routes_only_explicit_flag(monkeypatch, tmp_path, capsys, enabled):
    path = tmp_path / "device.json"
    save_config(path, DeviceConfig("192.168.1.50", 123, 2))
    controller = Mock()
    controller.set_ieco = AsyncMock(
        return_value={"state": {"ieco": enabled == "on"}, "confirmed": True}
    )
    monkeypatch.setattr(cli, "Controller", Mock(return_value=controller))
    assert cli.main(["--config", str(path), "widget", "ieco", "--enabled", enabled]) == 0
    controller.set_ieco.assert_awaited_once_with(enabled == "on", timeout=30)
    controller.set.assert_not_called()
    capsys.readouterr()
