"""Observa respostas válidas da versão fixada da biblioteca, sem expor pacotes."""

import asyncio

from msmart.device import AirConditioner as AC
from msmart.device.AC.command import (
    PropertiesResponse,
    PropertyId,
    StateResponse,
    ToggleDisplayCommand,
)


class VerifiedAC(AC):
    """Não confundir online/supported persistidos com uma leitura nova.

    Hooks _update_state/_update_capabilities e API _apply_properties/_ieco_number
    dependem da msmart-ng 2026.9.0. Atualizações exigem revisar código e testes.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state_updates = 0
        self.capabilities_received = False
        self.ieco_updates = 0
        self.ieco_fresh = False
        self.display_updates = 0
        self.display_fresh = False
        self.vertical_angle_updates = 0
        self.swing_mode_updates = 0
        self.vertical_angle_fresh = False
        self.swing_mode_fresh = False

    def _update_state(self, response):
        super()._update_state(response)
        if isinstance(response, StateResponse):
            self.state_updates += 1
            if type(response.swing_mode) is int and response.swing_mode in (0, 3, 12, 15):
                self.swing_mode_updates += 1
            if type(response.display_on) is bool:
                self.display_updates += 1
        if isinstance(response, PropertiesResponse):
            if type(response.get_property(PropertyId.IECO)) is bool:
                self.ieco_updates += 1
            angle = response.get_property(PropertyId.SWING_UD_ANGLE)
            if type(angle) is int and angle in (0, 1, 25, 50, 75, 100):
                self.vertical_angle_updates += 1

    def _update_capabilities(self, response):
        super()._update_capabilities(response)
        self.capabilities_received = True

    @property
    def ieco_number(self) -> int:
        return self._ieco_number

    async def apply_ieco(self, enabled: bool):
        # Apenas propriedade iECO + buzzer, sem reenviar o estado completo.
        await self._apply_properties({PropertyId.IECO: (self._ieco_number, enabled)})

    async def apply_vertical_angle(self, angle: AC.SwingAngle):
        await self._apply_properties({PropertyId.SWING_UD_ANGLE: angle})

    async def toggle_display_once(self):
        # Toggle não é idempotente: evitar até as retransmissões da biblioteca.
        command = ToggleDisplayCommand()
        command.beep_on = self._sound
        try:
            await self._lan.send(command.tobytes(), retries=1)
        except TimeoutError:
            # Pode ter sido aplicado sem ACK; o Controller consulta para confirmar.
            if asyncio.current_task().cancelling():
                raise

    async def refresh_verified(self):
        previous = self.state_updates
        previous_ieco = self.ieco_updates
        previous_display = self.display_updates
        previous_angle = self.vertical_angle_updates
        previous_swing = self.swing_mode_updates
        self.vertical_angle_fresh = False
        self.swing_mode_fresh = False
        self.ieco_fresh = False
        self.display_fresh = False
        await self.refresh()
        self.ieco_fresh = self.ieco_updates > previous_ieco
        self.display_fresh = self.display_updates > previous_display
        self.vertical_angle_fresh = self.vertical_angle_updates > previous_angle
        self.swing_mode_fresh = self.swing_mode_updates > previous_swing
        if self.state_updates == previous:
            raise ConnectionError(
                "Nenhuma nova resposta de estado válida. O estado em cache não confirma "
                "a operação; se houve envio, confira o aparelho antes de repetir."
            )
