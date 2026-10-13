"""Adaptador reutilizável pelo futuro widget; somente bootstrap usa nuvem."""

import asyncio
import math

from msmart.cloud import ApiError, NetHomePlusCloud, SmartHomeCloud
from msmart.device import AirConditioner as AC
from msmart.discover import Discover
from msmart.lan import AuthenticationError, Security

from .config import DeviceConfig
from .journal import Journal, public
from .transport import VerifiedAC


def discovery_info(device) -> dict:
    # supported/online não são conclusivos na descoberta sem conexão.
    return public(
        {
            "host": device.ip,
            "device_id": device.id,
            "port": device.port,
            "version": device.version,
            "type": device.type,
            "name": device.name,
            "compatibility_candidate": isinstance(device, AC),
        }
    )


async def discover(*, host: str | None = None, timeout: float = 5) -> list:
    return await Discover.discover(
        target=host or "255.255.255.255",
        timeout=timeout,
        auto_connect=False,  # NÃO autenticar automaticamente pela nuvem.
    )


async def bootstrap(
    device,
    *,
    provider: str,
    account: str | None = None,
    password: str | None = None,
    shared_account: bool = False,
    cloud_appliance_id: int | None = None,
    region: str = "US",
    journal: Journal | None = None,
) -> DeviceConfig:
    if not isinstance(device, AC):
        raise ValueError("Este adaptador inicial contempla apenas ar-condicionado tipo 0xAC.")
    if device.version not in (2, 3):
        raise ValueError("Protocolo não contemplado.")
    if cloud_appliance_id is not None and (
        type(cloud_appliance_id) is not int or cloud_appliance_id <= 0
    ):
        raise ValueError("O ID cloud deve ser um inteiro positivo obtido da sua conta.")
    if not isinstance(device, VerifiedAC):
        device = VerifiedAC(
            ip=device.ip,
            port=device.port,
            device_id=device.id,
            version=device.version,
        )
    journal = journal or Journal()
    if device.version == 3:
        if shared_account and (account or password):
            raise ValueError("Não misture conta compartilhada com credenciais pessoais.")
        if not shared_account and not (account and password):
            raise ValueError("Informe sua conta e senha ou autorize explicitamente shared_account.")
        providers = {"smarthome": SmartHomeCloud, "nethome": NetHomePlusCloud}
        if provider not in providers:
            raise ValueError("Provedor inválido.")
        credentials = {} if shared_account else {"account": account, "password": password}
        cloud = providers[provider](region, **credentials)
        journal.record(
            "cloud.login",
            provider=provider,
            account_mode="shared" if shared_account else "personal",
        )
        await cloud.login()
        authenticated = False
        received_keys = False
        last_api_error = None
        for endian in ("little", "big"):
            udpid = Security.udpid(device.id.to_bytes(6, endian)).hex()
            journal.record("cloud.get_token", provider=provider, endian=endian)
            try:
                # applianceCodes usa o ID do catálogo cloud; udpid sempre deriva do LAN ID.
                lookup_id = device.id if cloud_appliance_id is None else cloud_appliance_id
                token, key = await cloud.get_token(udpid, lookup_id)
            except ApiError as error:
                # A outra ordem produz um udpid diferente; não repetir o mesmo pedido.
                last_api_error = error
                code = error.code if type(error.code) is int else None
                journal.record(
                    "cloud.get_token.failed",
                    provider=provider,
                    endian=endian,
                    code=code,
                )
                if code == 3201:
                    # Outra ordem de bytes não altera a autorização sobre applianceCodes.
                    raise
                continue
            received_keys = True
            try:
                journal.record("lan.authenticate")
                await device.authenticate(token, key)
            except AuthenticationError:
                continue
            authenticated = True
            break
        if not authenticated:
            if not received_keys and last_api_error is not None:
                raise last_api_error
            raise ValueError("Não foi possível autenticar o aparelho com as chaves recebidas.")
    await device.refresh_verified()
    if not device.online or not device.supported:
        raise ValueError("O aparelho não respondeu com estado reconhecido. Nada foi salvo.")
    journal.record("bootstrap.verified", state=device.to_dict())
    return DeviceConfig(
        host=device.ip,
        device_id=device.id,
        port=device.port,
        version=device.version,
        token=device.token,
        key=device.key,
    )


SWING_POSITIONS = ("OFF", "POS_1", "POS_2", "POS_3", "POS_4", "POS_5", "AUTO")


class Controller:
    def __init__(self, config: DeviceConfig, journal: Journal | None = None, *, factory=VerifiedAC):
        self.config = config
        self.journal = journal or Journal()
        self.device = factory(ip=config.host, port=config.port, device_id=config.device_id)
        self._lock = asyncio.Lock()
        self._authenticated = False

    async def _prepare(self):
        if self.config.version == 3 and not self._authenticated:
            self.journal.record("lan.authenticate")
            await self.device.authenticate(self.config.token, self.config.key)
            self._authenticated = True
        self.journal.record("lan.get_capabilities")
        await self.device.get_capabilities()
        self.journal.record("lan.refresh")
        await self.device.refresh_verified()
        self._check_online()

    def _check_online(self):
        if not self.device.online or not self.device.supported:
            raise ConnectionError(
                "Sem resposta de estado reconhecida. Verifique IP, Wi-Fi, isolamento de clientes "
                "e chaves. Nenhum sucesso foi confirmado."
            )

    def _state(self) -> dict:
        state = public(self.device.to_dict())
        if not self.device.ieco_fresh:
            state["ieco"] = None
        if not self.device.display_fresh:
            state["display_on"] = None
        if not self.device.vertical_angle_fresh:
            state["vertical_swing_angle"] = None
        if not self.device.swing_mode_fresh:
            state["swing_mode"] = None
        state["vertical_swing_state"] = self._vertical_swing_state()
        return state

    def _vertical_swing_state(self) -> str | None:
        if not self.device.swing_mode_fresh:
            return None
        if self.device.swing_mode in (AC.SwingMode.VERTICAL, AC.SwingMode.BOTH):
            return "AUTO"
        if not self.device.vertical_angle_fresh:
            return None
        angle = self.device.vertical_swing_angle
        return angle.name if angle in AC.SwingAngle.list() else None

    async def set_swing(self, position: str = "next", *, timeout: float = 30) -> dict:
        if position not in (*SWING_POSITIONS, "next"):
            raise ValueError("Posição de Swing inválida.")
        async with self._lock, asyncio.timeout(timeout):
            await self._prepare()
            if (
                not self.device.capabilities_received
                or not self.device.supports_vertical_swing_angle
                or AC.SwingMode.VERTICAL not in self.device.supported_swing_modes
            ):
                raise ValueError("Swing vertical com posições não foi anunciado pelo aparelho.")
            current = self._vertical_swing_state()
            if current not in SWING_POSITIONS:
                raise ConnectionError("Sem leitura nova do Swing. Atualize antes de alterar.")
            if not self.device.power_state:
                raise ValueError("Ligue o ar para ajustar Swing; não ligamos automaticamente.")
            desired = (
                SWING_POSITIONS[(SWING_POSITIONS.index(current) + 1) % len(SWING_POSITIONS)]
                if position == "next"
                else position
            )
            horizontal = self.device.swing_mode in (AC.SwingMode.HORIZONTAL, AC.SwingMode.BOTH)
            swing_mode = (
                (AC.SwingMode.BOTH if horizontal else AC.SwingMode.VERTICAL)
                if desired == "AUTO"
                else (AC.SwingMode.HORIZONTAL if horizontal else AC.SwingMode.OFF)
            )
            if swing_mode not in self.device.supported_swing_modes:
                raise ValueError("Modo de Swing não anunciado; nenhuma alteração enviada.")
            before = self._state()
            if desired != current:
                angle = AC.SwingAngle.OFF if desired == "AUTO" else AC.SwingAngle[desired]
                self.journal.record("lan.apply_swing", requested={"vertical_swing_state": desired})
                # AUTO: limpar posição antes de iniciar oscilação.
                # Fixa/OFF: parar só o eixo vertical antes de ajustar a posição.
                if desired == "AUTO":
                    await self.device.apply_vertical_angle(angle)
                    self.device.swing_mode = swing_mode
                    await self.device.apply()
                else:
                    if self.device.swing_mode != swing_mode:
                        self.device.swing_mode = swing_mode
                        await self.device.apply()
                    await self.device.apply_vertical_angle(angle)
                await self.device.refresh_verified()
                self._check_online()
            after = self._state()
            confirmed = (
                after["vertical_swing_state"] == desired
                and self.device.swing_mode == swing_mode
                and all(after[k] == before[k] for k in ("power", "mode", "target_temperature"))
                and all(
                    after[k] == before[k] for k in ("ieco", "display_on") if type(before[k]) is bool
                )
            )
            self.journal.record("control.result", after=after, confirmed=confirmed)
            if not confirmed:
                raise ConnectionError(
                    "A leitura nova do Swing não confirmou a alteração; confira antes de repetir."
                )
            return {"confirmed": True, "state": after}

    async def set_display(self, enabled: bool, *, timeout: float = 30) -> dict:
        if type(enabled) is not bool:
            raise ValueError("LED deve ser booleano.")
        async with self._lock, asyncio.timeout(timeout):
            await self._prepare()
            if not self.device.capabilities_received or not self.device.supports_display_control:
                raise ValueError("Controle de LED não foi anunciado pelo aparelho.")
            if not self.device.display_fresh or type(self.device.display_on) is not bool:
                raise ConnectionError("Sem leitura nova do LED. Atualize antes de alterar.")
            if self.device.display_on is not enabled:
                self.journal.record("lan.toggle_display", requested={"display_on": enabled})
                await self.device.toggle_display_once()
                await self.device.refresh_verified()
                self._check_online()
            after = self._state()
            confirmed = self.device.display_fresh and after.get("display_on") is enabled
            self.journal.record("control.result", after=after, confirmed=confirmed)
            if not confirmed:
                raise ConnectionError(
                    "A leitura nova do LED não confirmou a alteração; confira antes de repetir."
                )
            return {"confirmed": True, "state": after}

    async def set_ieco(self, enabled: bool, *, timeout: float = 30) -> dict:
        if type(enabled) is not bool:
            raise ValueError("iECO deve ser booleano.")
        async with self._lock, asyncio.timeout(timeout):
            await self._prepare()
            if not self.device.capabilities_received or not self.device.supports_ieco:
                raise ValueError("iECO não foi anunciado pelo aparelho.")
            if not self.device.ieco_fresh:
                raise ConnectionError("Sem leitura nova de iECO. Atualize antes de alterar.")
            if enabled and (
                not self.device.power_state
                or self.device.operational_mode != AC.OperationalMode.COOL
            ):
                raise ValueError(
                    "Ative IA com o ar ligado em Refrigerar. Não ligamos automaticamente."
                )
            self.journal.record("lan.apply_ieco", requested={"ieco": enabled})
            await self.device.apply_ieco(enabled)
            await self.device.refresh_verified()
            self._check_online()
            after = self._state()
            confirmed = self.device.ieco_fresh and after.get("ieco") is enabled
            self.journal.record("control.result", after=after, confirmed=confirmed)
            if not confirmed:
                raise ConnectionError(
                    "A leitura nova de iECO não confirmou a alteração; confira antes de repetir."
                )
            return {"confirmed": True, "state": after}

    async def status(self, *, timeout: float = 30) -> dict:
        async with self._lock, asyncio.timeout(timeout):
            await self._prepare()
            result = public(
                {
                    "state": self._state(),
                    "capabilities": {
                        **self.device.serialize_capabilities(),
                        "ieco_number": self.device.ieco_number,
                    },
                    "capabilities_from_device": self.device.capabilities_received,
                }
            )
            self.journal.record("status", **result)
            return result

    async def set(
        self,
        *,
        power: bool | None = None,
        temperature: float | None = None,
        mode: str | None = None,
        timeout: float = 30,
    ) -> dict:
        if power is None and temperature is None and mode is None:
            raise ValueError("Informe pelo menos uma alteração.")
        if power is not None and type(power) is not bool:
            raise ValueError("power deve ser booleano.")
        if temperature is not None and (
            not math.isfinite(temperature) or temperature * 2 != round(temperature * 2)
        ):
            raise ValueError("A temperatura deve ser finita e ter passos de 0,5 °C.")
        async with self._lock, asyncio.timeout(timeout):
            # apply envia estado completo: primeiro ler para não partir dos defaults.
            await self._prepare()
            before = public(self.device.to_dict())
            expected = {}
            if temperature is not None:
                minimum = self.device.min_target_temperature
                maximum = self.device.max_target_temperature
                if not minimum <= temperature <= maximum:
                    raise ValueError(
                        f"Temperatura fora do intervalo informado: {minimum}–{maximum} °C."
                    )
                expected["target_temperature"] = temperature
            if mode is not None:
                try:
                    enum_mode = AC.OperationalMode[mode.upper()]
                except KeyError:
                    raise ValueError("Modo inválido.") from None
                if enum_mode not in self.device.supported_operation_modes:
                    raise ValueError("Modo não contemplado pelas capacidades do aparelho.")
                expected["mode"] = enum_mode.name
            if power is not None:
                expected["power"] = power
            # Aplicar propriedades somente após validar todas as alterações.
            if temperature is not None:
                self.device.target_temperature = temperature
            if mode is not None:
                self.device.operational_mode = enum_mode
            if power is not None:
                self.device.power_state = power
            self.journal.record("lan.apply", before=before, requested=expected)
            await self.device.apply()
            self._check_online()
            self.journal.record("lan.refresh")
            await self.device.refresh_verified()
            self._check_online()
            after = self._state()
            confirmed = all(after.get(k) == v for k, v in expected.items())
            self.journal.record("control.result", after=after, confirmed=confirmed)
            if not confirmed:
                raise ConnectionError(
                    "O estado lido não confirmou a alteração. O comando pode ter sido enviado; "
                    "confira o aparelho antes de tentar novamente."
                )
            return {"confirmed": True, "state": after}
