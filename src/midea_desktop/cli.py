"""CLI de investigação e controle explícito; stdout é JSON sem chaves."""

import argparse
import asyncio
import getpass
import json
import logging
import sys
from pathlib import Path

from msmart.cloud import ApiError, CloudError
from msmart.device.AC.command import GetCapabilitiesCommand, GetStateCommand, SetStateCommand

from .config import DeviceConfig, config_path, load_config, save_config
from .controller import SWING_POSITIONS, Controller, bootstrap, discover, discovery_info
from .journal import Journal, public
from .presentation import widget_report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="midea-desktop", description="Controle local Midea — projeto experimental Linux."
    )
    root.add_argument(
        "--config", type=Path, default=config_path(), help="Configuração privada local"
    )
    root.add_argument("--journal", type=Path, help="Diário JSONL sanitizado (opcional)")
    root.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="Limite por etapa de rede em segundos (padrão: 30)",
    )
    commands = root.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("discover", help="Descobrir pela LAN, sem nuvem e sem controle")
    scan.add_argument("--host", help="IPv4 ou broadcast da sub-rede; padrão: 255.255.255.255")
    scan.add_argument("--wait", type=float, default=5, help="Janela de descoberta em segundos")
    setup = commands.add_parser("configure", help="Salvar IP/ID e chaves obtidas previamente")
    setup.add_argument("--host", required=True)
    setup.add_argument("--id", required=True, type=int, dest="device_id")
    setup.add_argument("--version", type=int, choices=[2, 3], required=True)
    setup.add_argument("--port", type=int, default=6444)
    setup.add_argument("--replace", action="store_true", help="Autorizar sobrescrita")
    cloud = commands.add_parser(
        "bootstrap", help="Obter chaves pela nuvem e validar somente leitura LAN"
    )
    cloud.add_argument("--host", required=True)
    cloud.add_argument("--provider", choices=["smarthome", "nethome"], default="smarthome")
    cloud.add_argument(
        "--cloud-id",
        type=int,
        dest="cloud_appliance_id",
        help="ID do aparelho no catálogo da sua conta (pode ser diferente do ID LAN)",
    )
    cloud.add_argument(
        "--region", default="US", help="Região da biblioteca, não deduzida pelo idioma"
    )
    cloud.add_argument(
        "--shared-account",
        action="store_true",
        help="Autorizar conta compartilhada da biblioteca (sem suas credenciais; usa nuvem)",
    )
    cloud.add_argument("--replace", action="store_true", help="Autorizar sobrescrita")
    commands.add_parser("status", help="Consultar estado e capacidades pela LAN")
    commands.add_parser("on", help="Ligar explicitamente, preservando configurações lidas")
    commands.add_parser("off", help="Desligar explicitamente")
    change = commands.add_parser("set", help="Alterar parâmetros sem ligar automaticamente")
    change.add_argument("--temperature", type=float, help="Temperatura em °C, passos de 0,5")
    change.add_argument("--mode", choices=["auto", "cool", "dry", "heat", "fan_only", "smart_dry"])
    change.add_argument("--power", choices=["on", "off"])
    widget = commands.add_parser("widget", help="API local com JSON mínimo para a barra Omarchy")
    widget.add_argument(
        "action", choices=["status", "on", "off", "set", "ieco", "display", "swing"]
    )
    widget.add_argument("--enabled", choices=["on", "off"])
    widget.add_argument("--position", choices=["next", *SWING_POSITIONS], default="next")
    widget.add_argument("--temperature", type=float)
    widget.add_argument("--mode", choices=["auto", "cool", "dry", "heat", "fan_only", "smart_dry"])
    commands.add_parser("frames", help="Gerar frames de referência offline; não acessa a rede")
    return root


def reference_frames() -> dict:
    state = SetStateCommand()
    state.power_on = False
    state.target_temperature = 24
    state.operational_mode = 2  # COOL
    state.fan_speed = 102  # AUTO
    state.eco = False
    state.fahrenheit = False
    return {
        "source": "msmart-ng 2026.9.0",
        "offline": True,
        "warning": "Exemplos não capturados do seu aparelho; não incluem envelope LAN V2/V3.",
        "frames": {
            "get_capabilities": GetCapabilitiesCommand().tobytes().hex(),
            "get_state": GetStateCommand().tobytes().hex(),
            "set_state_example_off_cool_24c": state.tobytes().hex(),
        },
    }


def ensure_writable_config(args):
    if args.config.exists() and not args.replace:
        raise ValueError("Já existe configuração. Use --replace somente se desejar substituí-la.")


def configure(args) -> dict:
    ensure_writable_config(args)
    if args.version == 3 and not sys.stdin.isatty():
        raise ValueError("Execute configure em um terminal para informar as chaves com segurança.")
    token = getpass.getpass("Token LAN (hex, entrada oculta): ") if args.version == 3 else None
    key = getpass.getpass("Key LAN (hex, entrada oculta): ") if args.version == 3 else None
    config = DeviceConfig(
        host=args.host,
        device_id=args.device_id,
        port=args.port,
        version=args.version,
        token=token,
        key=key,
    )
    save_config(args.config, config, replace=args.replace)
    return {"saved": str(args.config), "verified": False, "next": "midea-desktop status"}


async def execute(args) -> dict | list:
    journal = Journal(args.journal)
    if args.command == "discover":
        if not 0 < args.wait < args.timeout:
            raise ValueError("--wait deve ser positivo e menor que --timeout.")
        async with asyncio.timeout(args.timeout):
            devices = await discover(host=args.host, timeout=args.wait)
        result = [discovery_info(d) for d in devices]
        journal.record("lan.discover", devices=result, cloud=False)
        return result
    if args.command == "bootstrap":
        ensure_writable_config(args)
        async with asyncio.timeout(args.timeout):
            devices = await discover(host=args.host)
        if len(devices) != 1:
            raise ValueError("Não foi encontrado exatamente um aparelho nesse IP.")
        device = devices[0]
        account = password = None
        if device.version == 3 and not args.shared_account:
            if not sys.stdin.isatty():
                raise ValueError(
                    "Execute bootstrap em um terminal para informar sua conta com segurança."
                )
            account = input("Conta Midea (e-mail/login): ").strip()
            password = getpass.getpass("Senha (não será salva): ")
        async with asyncio.timeout(args.timeout):
            config = await bootstrap(
                device,
                provider=args.provider,
                account=account,
                password=password,
                shared_account=args.shared_account,
                cloud_appliance_id=args.cloud_appliance_id,
                region=args.region,
                journal=journal,
            )
        save_config(args.config, config, replace=args.replace)
        return {"saved": str(args.config), "verified": True, "control": "LAN"}
    controller = Controller(load_config(args.config), journal)
    if args.command == "widget":
        if args.action == "status":
            result = await controller.status(timeout=args.timeout)
        elif args.action == "ieco":
            if args.enabled is None:
                raise ValueError("Informe --enabled on ou off para iECO.")
            result = await controller.set_ieco(args.enabled == "on", timeout=args.timeout)
        elif args.action == "display":
            if args.enabled is None:
                raise ValueError("Informe --enabled on ou off para LED.")
            result = await controller.set_display(args.enabled == "on", timeout=args.timeout)
        elif args.action == "swing":
            result = await controller.set_swing(args.position, timeout=args.timeout)
        elif args.action in ("on", "off"):
            result = await controller.set(power=args.action == "on", timeout=args.timeout)
        else:
            result = await controller.set(
                temperature=args.temperature,
                mode=args.mode,
                timeout=args.timeout,
            )
        return widget_report(result)
    if args.command == "status":
        return await controller.status(timeout=args.timeout)
    if args.command in ("on", "off"):
        return await controller.set(power=args.command == "on", timeout=args.timeout)
    if args.command == "set":
        return await controller.set(
            power=None if args.power is None else args.power == "on",
            temperature=args.temperature,
            mode=args.mode,
            timeout=args.timeout,
        )
    raise ValueError("Comando não reconhecido.")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    # A biblioteca tem logs de respostas cloud. Nunca habilitar debug de credenciais.
    logging.getLogger("msmart.cloud").setLevel(logging.CRITICAL)
    if args.command == "widget":
        # Logs internos podem conter IP/ID. Não enviá-los ao processo da barra.
        logging.getLogger("msmart").setLevel(logging.CRITICAL)
    try:
        if not 0 < args.timeout <= 180:
            raise ValueError("--timeout deve estar entre 0 e 180 segundos.")
        if args.command == "frames":
            result = reference_frames()
        elif args.command == "configure":
            result = configure(args)
        else:
            result = asyncio.run(execute(args))
        print(json.dumps(public(result), ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except CloudError as error:
        code = error.code if isinstance(error, ApiError) and type(error.code) is int else None
        suffix = f" (código API {code})" if code is not None else ""
        explanation = ""
        if code == 3201:
            explanation = (
                "Permissão negada: use a conta proprietária e verifique o ID cloud do aparelho. "
            )
        elif code == 9999 and getattr(args, "provider", None) == "nethome":
            explanation = (
                "Há relatos de falha do getToken NetHome Plus, mesmo com contas proprietárias. "
            )
        elif code == 3004:
            explanation = "A API recusou os parâmetros do pedido. "
        print(
            f"Falha na nuvem Midea{suffix}. {explanation}"
            "Nenhum comando de controle foi enviado; resposta e credenciais foram omitidas.",
            file=sys.stderr,
        )
    except (ValueError, ConnectionError) as error:
        print(f"Erro: {error}", file=sys.stderr)
    except TimeoutError:
        print(
            "Tempo limite. Se enviou controle, a alteração pode ter ocorrido; confira o estado.",
            file=sys.stderr,
        )
    except (KeyboardInterrupt, EOFError):
        print("Operação cancelada.", file=sys.stderr)
        return 130
    except Exception as error:
        # Mensagens e tracebacks da biblioteca podem conter material de autenticação.
        print(
            f"Falha ({type(error).__name__}). Verifique rede, conta e provedor. "
            "Detalhes sensíveis foram omitidos.",
            file=sys.stderr,
        )
    return 1
