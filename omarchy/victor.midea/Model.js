.pragma library

var modeLabels = {
    "COOL": "Refrigerar", "DRY": "Desumidificar", "FAN_ONLY": "Ventilar",
    "AUTO": "Automático", "HEAT": "Aquecer", "SMART_DRY": "Secagem inteligente"
};

var swingPositions = ["OFF", "POS_1", "POS_2", "POS_3", "POS_4", "POS_5", "AUTO"];

function swingLabel(position) {
    if (position === "OFF") return "Desativado";
    if (position === "AUTO") return "Oscilando";
    if (swingPositions.indexOf(position) > 0) return "Posição " + position.slice(-1);
    return "Estado não confirmado";
}

function swingReady(state, caps) {
    return state && state.power && caps && caps.supports_vertical_swing === true
        && swingPositions.indexOf(state.vertical_swing_state) >= 0;
}

function finite(value) {
    return typeof value === "number" && isFinite(value);
}

function temperature(value) {
    return finite(value) ? String(value).replace(".", ",") + " °C" : "—";
}

function temperatureNumber(value) {
    return finite(value) ? String(value).replace(".", ",") : "—";
}

function modes(capabilities) {
    var list = capabilities && capabilities.supported_modes;
    if (!Array.isArray(list)) return [];
    return list.filter(function(mode) { return modeLabels[mode] !== undefined; })
        .map(function(mode) { return { value: mode, label: modeLabels[mode] }; });
}

// Whitelist: never retain identifiers or credentials inside the QML scene.
function parse(raw, previousCapabilities) {
    var response = JSON.parse(raw);
    var state = response.state;
    if (!state || state.online !== true || state.supported !== true
            || typeof state.power !== "boolean" || !finite(state.target_temperature))
        throw new Error("Invalid confirmed state");
    var isRead = response.capabilities !== undefined;
    if (!isRead && response.confirmed !== true)
        throw new Error("Control not confirmed");
    var source = isRead ? response.capabilities : previousCapabilities;
    if (!source) throw new Error("Missing capabilities");
    return {
        state: {
            power: state.power, mode: state.mode,
            ieco: typeof state.ieco === "boolean" ? state.ieco : null,
            display_on: typeof state.display_on === "boolean" ? state.display_on : null,
            vertical_swing_state: swingPositions.indexOf(state.vertical_swing_state) >= 0
                ? state.vertical_swing_state : null,
            target_temperature: state.target_temperature,
            indoor_temperature: finite(state.indoor_temperature) ? state.indoor_temperature : null
        },
        capabilities: {
            supports_ieco: source.supports_ieco === true,
            supports_vertical_swing: source.supports_vertical_swing === true,
            supports_display_control: source.supports_display_control === true,
            ieco_number: finite(source.ieco_number) ? source.ieco_number : null,
            min_target_temperature: source.min_target_temperature,
            max_target_temperature: source.max_target_temperature,
            supported_modes: modes(source).map(function(option) { return option.value; })
        },
        capabilitiesFromDevice: isRead ? response.capabilities_from_device === true : null
    };
}

function usableCapabilities(caps) {
    return caps && finite(caps.min_target_temperature) && finite(caps.max_target_temperature)
        && caps.min_target_temperature <= caps.max_target_temperature
        && modes(caps).length > 0;
}

function clampTemperature(value, caps) {
    if (!finite(value) || !usableCapabilities(caps)) return null;
    return Math.max(caps.min_target_temperature,
        Math.min(caps.max_target_temperature, Math.round(value * 2) / 2));
}

function validDraft(value, mode, caps) {
    return clampTemperature(value, caps) === value
        && modes(caps).some(function(option) { return option.value === mode; });
}

function displayReady(state, caps) {
    return state && caps && caps.supports_display_control === true
        && typeof state.display_on === "boolean";
}

function iecoReady(state, caps) {
    return state && caps && caps.supports_ieco === true
        && typeof state.ieco === "boolean"
        && (state.ieco || (state.power && state.mode === "COOL"));
}

function aiColor(background) {
    function luminance(r, g, b) {
        function linear(v) { return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
        return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
    }
    var bg = luminance(background.r, background.g, background.b);
    var colors = [
        { color: "#81c995", r: 129/255, g: 201/255, b: 149/255 },
        { color: "#156b35", r: 21/255, g: 107/255, b: 53/255 },
        { color: "#fafffb", r: 250/255, g: 1, b: 251/255 },
        { color: "#000400", r: 0, g: 4/255, b: 0 }
    ];
    for (var i = 0; i < colors.length; i++) {
        var c = colors[i], fg = luminance(c.r, c.g, c.b);
        if ((Math.max(bg, fg) + 0.05) / (Math.min(bg, fg) + 0.05) >= 4.5)
            return c.color;
    }
    return "#000400";
}

function failureMessage(control) {
    return control
        ? "Não foi possível confirmar a alteração. Confira o aparelho e atualize antes de repetir."
        : "Sem leitura confirmada. Confira a conexão e clique em Atualizar.";
}
