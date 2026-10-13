#!/usr/bin/env python3
"""Backend estritamente simulado: não importa a biblioteca nem abre sockets."""

import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--timeout")
parser.add_argument("kind", choices=["widget"])
parser.add_argument("action", choices=["status", "on", "off", "set", "ieco", "display", "swing"])
parser.add_argument("--temperature", type=float)
parser.add_argument("--mode")
parser.add_argument("--position", default="next")
parser.add_argument("--enabled", choices=["on", "off"])
args = parser.parse_args()
path = Path(os.environ["MIDEA_WIDGET_FAKE_STATE"])
data = json.loads(path.read_text())
data.setdefault("calls", []).append(args.action)
if data.get("fail"):
    path.write_text(json.dumps(data))
    raise SystemExit(1)
if args.action == "swing":
    positions = ["OFF", "POS_1", "POS_2", "POS_3", "POS_4", "POS_5", "AUTO"]
    current = data["state"]["vertical_swing_state"]
    data["state"]["vertical_swing_state"] = (
        positions[(positions.index(current) + 1) % len(positions)]
        if args.position == "next"
        else args.position
    )
elif args.action == "display":
    data["state"]["display_on"] = args.enabled == "on"
elif args.action == "ieco":
    data["state"]["ieco"] = args.enabled == "on"
elif args.action in ("on", "off"):
    data["state"]["power"] = args.action == "on"
elif args.action == "set":
    data["state"]["target_temperature"] = args.temperature
    data["state"]["mode"] = args.mode.upper()
path.write_text(json.dumps(data))
report = {"state": data["state"]}
if args.action == "status":
    report["capabilities"] = {
        "min_target_temperature": 16,
        "max_target_temperature": 30,
        "supported_modes": ["COOL", "DRY"],
        "supports_ieco": True,
        "supports_vertical_swing": True,
        "supports_display_control": True,
        "ieco_number": 8,
    }
    report["capabilities_from_device"] = True
else:
    report["confirmed"] = True
print(json.dumps(report))
