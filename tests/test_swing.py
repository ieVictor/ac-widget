from unittest.mock import AsyncMock, Mock

import pytest
from msmart.device import AirConditioner as AC
from msmart.device.AC.command import PropertiesResponse, PropertyId
from test_controller import FakeAC

from midea_desktop import cli
from midea_desktop.config import DeviceConfig, save_config
from midea_desktop.controller import SWING_POSITIONS, Controller
from midea_desktop.transport import VerifiedAC


class FakeSwing(FakeAC):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._capabilities.set(AC.Capability.SWING_VERTICAL_ANGLE, True)
        self.capabilities_received = True
        self.missing_angle = False
        self.stale_angle = False

    async def refresh(self):
        await super().refresh()
        self._swing_mode = self.committed["swing_mode"]
        self._vertical_swing_angle = self.committed["vertical_swing_angle"]
        self.swing_mode_updates += 1
        if not self.missing_angle and not (self.stale_angle and "angle" in self.calls):
            self.vertical_angle_updates += 1

    async def apply_vertical_angle(self, angle):
        self.calls.append("angle")
        if not self.ignore_control:
            self._vertical_swing_angle = angle
            self.committed["vertical_swing_angle"] = angle


@pytest.fixture
def controller():
    return Controller(DeviceConfig("192.168.1.50", 123, 2), factory=FakeSwing)


@pytest.mark.parametrize("position", SWING_POSITIONS)
async def test_seven_states_preserve_basic_settings(controller, position):
    result = await controller.set_swing(position)
    assert result["confirmed"]
    assert result["state"]["vertical_swing_state"] == position
    assert result["state"]["power"] is True
    assert result["state"]["target_temperature"] == 23
    assert result["state"]["mode"] == "COOL"


async def test_cycle_uses_new_read_not_previous_cached_state(controller):
    for desired in (*SWING_POSITIONS[1:], "OFF", "POS_1"):
        assert (await controller.set_swing())["state"]["vertical_swing_state"] == desired


async def test_horizontal_oscillation_is_preserved(controller):
    controller.device.committed["swing_mode"] = AC.SwingMode.HORIZONTAL
    assert (await controller.set_swing("AUTO"))["state"]["swing_mode"] == "BOTH"
    assert (await controller.set_swing("POS_2"))["state"]["swing_mode"] == "HORIZONTAL"


async def test_auto_does_not_require_absolute_position(controller):
    controller.device.committed["swing_mode"] = AC.SwingMode.VERTICAL
    controller.device.missing_angle = True
    assert (await controller.status())["state"]["vertical_swing_state"] == "AUTO"


async def test_fixed_position_only_uses_property(controller):
    await controller.set_swing("POS_2")
    assert controller.device.calls == ["capabilities", "refresh", "angle", "refresh"]


@pytest.mark.parametrize("failure", ["unsupported", "missing", "capabilities", "off"])
async def test_guards_before_sending(controller, failure):
    d = controller.device
    if failure == "unsupported":
        d._capabilities.set(AC.Capability.SWING_VERTICAL_ANGLE, False)
    elif failure == "capabilities":
        d.capabilities_received = False
    elif failure == "off":
        d.committed["power"] = False
    else:
        d.missing_angle = True
    with pytest.raises((ValueError, ConnectionError)):
        await controller.set_swing()
    assert "angle" not in d.calls and "apply" not in d.calls


@pytest.mark.parametrize("failure", ["ignored", "stale"])
async def test_requires_new_matching_angle(controller, failure):
    controller.device.ignore_control = failure == "ignored"
    controller.device.stale_angle = failure == "stale"
    with pytest.raises(ConnectionError, match="Swing não confirmou"):
        await controller.set_swing("POS_1")


async def test_unknown_position_never_uses_default_off(controller):
    controller.device.missing_angle = True
    assert (await controller.status())["state"]["vertical_swing_state"] is None


@pytest.mark.parametrize("value", [0, 1, 25, 50, 75, 100, 2, 255, None, True])
def test_property_counter_only_accepts_protocol_positions(value):
    d = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123)
    response = Mock(spec=PropertiesResponse)
    response.get_property.side_effect = lambda prop: (
        value if prop == PropertyId.SWING_UD_ANGLE else None
    )
    d._update_state(response)
    assert d.vertical_angle_updates == int(type(value) is int and value in (0, 1, 25, 50, 75, 100))


async def test_angle_encoding_is_protocol_value_not_index():
    d = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123)
    d._apply_properties = AsyncMock()
    await d.apply_vertical_angle(AC.SwingAngle.POS_2)
    d._apply_properties.assert_awaited_once_with({PropertyId.SWING_UD_ANGLE: AC.SwingAngle.POS_2})
    assert PropertyId.SWING_UD_ANGLE.encode(AC.SwingAngle.POS_2) == bytes([25])


def test_widget_routes_cycle_only(monkeypatch, tmp_path, capsys):
    path = tmp_path / "device.json"
    save_config(path, DeviceConfig("192.168.1.50", 123, 2))
    controller = Mock()
    controller.set_swing = AsyncMock(
        return_value={"state": {"vertical_swing_state": "POS_1"}, "confirmed": True}
    )
    monkeypatch.setattr(cli, "Controller", Mock(return_value=controller))
    assert cli.main(["--config", str(path), "widget", "swing"]) == 0
    controller.set_swing.assert_awaited_once_with("next", timeout=30)
    controller.set.assert_not_called()
    capsys.readouterr()
