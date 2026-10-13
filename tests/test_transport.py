from unittest.mock import AsyncMock

import pytest
from msmart.device.AC.command import Response, StateResponse

from midea_desktop.transport import VerifiedAC


def test_counts_only_state_responses():
    device = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123)
    payload = bytearray(22)
    payload[0] = 0xC0
    payload[1] = 1
    payload[2] = (2 << 5) | 8  # COOL, 24 °C
    payload[3] = 40
    device._update_state(StateResponse(memoryview(payload)))
    assert device.state_updates == 1
    assert device.power_state is True
    assert device.target_temperature == 24
    device._update_state(Response(memoryview(bytes([0]))))
    assert device.state_updates == 1


async def test_stale_cache_is_rejected_even_if_online_and_supported():
    device = VerifiedAC(ip="192.168.1.50", port=6444, device_id=123)
    device._online = device._supported = True
    device.refresh = AsyncMock()
    with pytest.raises(ConnectionError, match="Nenhuma nova resposta"):
        await device.refresh_verified()
