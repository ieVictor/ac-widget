#!/usr/bin/env python3
"""Integração Quickshell isolada: somente JSON falso, nunca hardware."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if not shutil.which("quickshell") or not os.environ.get("WAYLAND_DISPLAY"):
        raise SystemExit("Execute na sessão Wayland com Quickshell instalado.")

    with tempfile.TemporaryDirectory(prefix="midea-widget-test-") as directory:
        temporary = Path(directory)
        config = temporary / "shell.qml"
        state = temporary / "state.json"
        shutil.copy2(ROOT / "tests/backend-preview/shell.qml", config)
        for filename in ("Backend.qml", "Model.js", "qmldir"):
            shutil.copy2(ROOT / "omarchy/victor.midea" / filename, temporary / filename)
        state.write_text(
            json.dumps(
                {
                    "state": {
                        "online": True,
                        "supported": True,
                        "power": False,
                        "mode": "COOL",
                        "target_temperature": 24,
                        "indoor_temperature": 25,
                        "ieco": False,
                        "display_on": True,
                        "vertical_swing_state": "OFF",
                    },
                    "calls": [],
                }
            )
        )
        environment = dict(os.environ)
        environment["MIDEA_WIDGET_FAKE_STATE"] = str(state)
        environment["MIDEA_WIDGET_FAKE_EXECUTABLE"] = str(
            ROOT / "tests/fixtures/fake_widget_backend.py"
        )

        def ipc(method: str, *arguments: str) -> str:
            result = subprocess.run(
                ["quickshell", "ipc", "-p", str(config), "call", "midea-test", method, *arguments],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip()

        def settled() -> dict:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    report = json.loads(ipc("status"))
                    if "busy" in report and not report["busy"]:
                        return report
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    pass
                time.sleep(0.1)
            raise AssertionError("O backend simulado não terminou a operação.")

        try:
            subprocess.run(
                ["quickshell", "-p", str(config), "-d", "--no-color"],
                check=True,
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
            )
            report = settled()
            assert report["ready"] and report["state"]["power"] is False
            assert ipc("display", "false") == "true"
            report = settled()
            assert report["state"]["display_on"] is False
            assert report["state"]["power"] is False
            assert ipc("display", "true") == "true"
            assert settled()["state"]["display_on"] is True
            assert ipc("power", "true") == "true"
            assert settled()["state"]["power"] is True
            for position in ["POS_1", "POS_2", "POS_3", "POS_4", "POS_5", "AUTO", "OFF"]:
                assert ipc("swing") == "true"
                report = settled()
                assert report["state"]["vertical_swing_state"] == position
                assert report["state"]["target_temperature"] == 24
            assert ipc("ieco", "true") == "true"
            report = settled()
            assert report["state"]["ieco"] is True and report["state"]["power"] is True
            assert report["state"]["target_temperature"] == 24
            assert ipc("ieco", "false") == "true"
            assert settled()["state"]["ieco"] is False
            assert ipc("apply") == "true"
            report = settled()
            assert report["state"]["target_temperature"] == 23.5
            assert report["state"]["mode"] == "DRY"
            assert ipc("ieco", "true") == "false"
            assert ipc("power", "false") == "true"
            assert settled()["state"]["power"] is False
            data = json.loads(state.read_text())
            data["fail"] = True
            state.write_text(json.dumps(data))
            assert ipc("power", "true") == "true"
            report = settled()
            assert not report["ready"] and not report["fresh"]
            assert report["state"]["power"] is False and report["error"]
            assert ipc("power", "true") == "false"
            data = json.loads(state.read_text())
            assert data["calls"] == (
                ["status", "display", "display", "on"]
                + ["swing"] * 7
                + ["ieco", "ieco", "set", "off", "on"]
            )
            data["fail"] = False
            state.write_text(json.dumps(data))
            ipc("refresh")
            assert settled()["ready"]
            print("Integração simulada passou: consulta, on/off, ajustes, falha e recuperação.")
        finally:
            subprocess.run(
                ["quickshell", "kill", "-p", str(config)],
                check=False,
                capture_output=True,
                timeout=5,
            )


if __name__ == "__main__":
    main()
