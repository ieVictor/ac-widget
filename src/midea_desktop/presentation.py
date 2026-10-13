"""Saída mínima para a barra: nenhum identificador, chave ou resposta bruta."""

STATE_FIELDS = (
    "online",
    "supported",
    "power",
    "mode",
    "target_temperature",
    "indoor_temperature",
    "ieco",
    "display_on",
    "vertical_swing_state",
)
CAPABILITY_FIELDS = (
    "min_target_temperature",
    "max_target_temperature",
    "supported_modes",
    "ieco_number",
)


def widget_report(result: dict) -> dict:
    report = {"state": {key: result["state"].get(key) for key in STATE_FIELDS}}
    if "capabilities" in result:
        report["capabilities"] = {key: result["capabilities"].get(key) for key in CAPABILITY_FIELDS}
        report["capabilities"]["supports_ieco"] = "IECO" in result["capabilities"].get(
            "additional_capabilities", []
        )
        report["capabilities"]["supports_display_control"] = "DISPLAY_CONTROL" in result[
            "capabilities"
        ].get("additional_capabilities", [])
        report["capabilities"]["supports_vertical_swing"] = (
            "SWING_VERTICAL_ANGLE" in result["capabilities"].get("additional_capabilities", [])
            and "VERTICAL" in result["capabilities"].get("supported_swing_modes", [])
            and "OFF" in result["capabilities"].get("supported_swing_modes", [])
        )
        report["capabilities_from_device"] = result.get("capabilities_from_device", False)
    if "confirmed" in result:
        report["confirmed"] = result["confirmed"] is True
    return report
