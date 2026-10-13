from unittest.mock import AsyncMock, Mock

import pytest
from msmart.device import AirConditioner as AC
from msmart.device.AC.command import ToggleDisplayCommand
from test_controller import FakeAC

from midea_desktop import cli
from midea_desktop.config import DeviceConfig, save_config
from midea_desktop.controller import Controller
from midea_desktop.transport import VerifiedAC


class FakeDisplay(FakeAC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._capabilities.set(AC.Capability.DISPLAY_CONTROL, True)
        self.capabilities_received = True
        self.committed["display_on"] = True
        self.missing_display = False
        self.stale_display = False

    async def refresh(self):
        await super().refresh()
        self._display_on = self.committed["display_on"]
        if not self.missing_display and not (self.stale_display and "toggle_display" in self.calls):
            self.display_updates += 1

    async def toggle_display_once(self):
        self.calls.append("toggle_display")
        if not self.ignore_control:
            self.committed["display_on"] = not self.committed["display_on"]


@pytest.fixture
def controller():
    return Controller(DeviceConfig("192.168.1.50", 123, 2), factory=FakeDisplay)


@pytest.mark.parametrize("enabled", [True, False])
async def test_display_preserves_other_settings(controller, enabled):
    controller.device.committed["display_on"] = not enabled
    result = await controller.set_display(enabled)
    assert result["confirmed"] and result["state"]["display_on"] is enabled
    assert result["state"]["power"] is True
    assert result["state"]["target_temperature"] == 23
    assert result["state"]["mode"] == "COOL"
    assert controller.device.calls == ["capabilities", "refresh", "toggle_display", "refresh"]
    assert "apply" not in controller.device.calls


async def test_already_requested_state_never_toggles(controller):
    result = await controller.set_display(True)
    assert result["confirmed"]
    assert controller.device.calls == ["capabilities", "refresh"]


async def test_display_does_not_turn_on_appliance(controller):
    controller.device.committed["power"] = False
    result = await controller.set_display(False)
    assert result["state"]["power"] is False


@pytest.mark.parametrize("failure", ["unsupported", "missing", "capabilities"])
async def test_guard_before_toggle(controller, failure):
    if failure == "unsupported":
        controller.device._capabilities.set(AC.Capability.DISPLAY_CONTROL, False)
    elif failure == "capabilities":
        controller.device.capabilities_received = False
    else:
        controller.device.missing_display = True
    with pytest.raises((ValueError, ConnectionError)):
        await controller.set_display(False)
    assert "toggle_display" not in controller.device.calls


@pytest.mark.parametrize("failure", ["ignored", "stale"])
async def test_confirmation_requires_new_matching_led_state(controller, failure):
    controller.device.ignore_control = failure == "ignored"
    controller.device.stale_display = failure == "stale"
    with pytest.raises(ConnectionError, match="LED não confirmou"):
        await controller.set_display(False)
    assert controller.device.calls.count("toggle_display") == 1


async def test_invalid_boolean_never_accesses_device(controller):
    with pytest.raises(ValueError):
        await controller.set_display(1)
    assert controller.device.calls == []


async def test_missing_read_is_unknown(controller):
    controller.device.missing_display = True
    assert (await controller.status())["state"]["display_on"] is None


@pytest.mark.parametrize("lost_ack", [True, False])
async def test_toggle_disables_library_retransmission(lost_ack):
    d = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123)
    d._sound = False
    d._lan.send = AsyncMock(side_effect=TimeoutError if lost_ack else None)
    command = ToggleDisplayCommand()
    command.beep_on = False
    await d.toggle_display_once()
    d._lan.send.assert_awaited_once()
    assert d._lan.send.await_args.kwargs == {"retries": 1}
    # Sequência/CRC/checksum variam por frame, mas comando e payload são iguais.
    assert d._lan.send.await_args.args[0][:-3] == command.tobytes()[:-3]


@pytest.mark.parametrize("enabled", ["on", "off"])
def test_widget_routes_display_only(monkeypatch, tmp_path, capsys, enabled):
    path = tmp_path / "device.json"
    save_config(path, DeviceConfig("192.168.1.50", 123, 2))
    controller = Mock()
    controller.set_display = AsyncMock(
        return_value={"state": {"display_on": enabled == "on"}, "confirmed": True}
    )
    monkeypatch.setattr(cli, "Controller", Mock(return_value=controller))
    assert cli.main(["--config", str(path), "widget", "display", "--enabled", enabled]) == 0
    controller.set_display.assert_awaited_once_with(enabled == "on", timeout=30)
    controller.set.assert_not_called()
    capsys.readouterr()
