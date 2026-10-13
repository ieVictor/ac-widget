import QtQuick
import QtTest
import "../../omarchy/victor.midea/Model.js" as Model

TestCase {
    name: "MideaModel"

    function report() {
        return {
            state: { online: true, supported: true, power: false, mode: "COOL",
                target_temperature: 24, indoor_temperature: 25,
                token: "SECRET", key: "SECRET", id: 123, ip: "192.168.1.50" },
            capabilities: { min_target_temperature: 16, max_target_temperature: 30,
                supported_modes: ["COOL", "UNKNOWN"] },
            capabilities_from_device: true
        };
    }

    function test_parse_and_redact() {
        var parsed = Model.parse(JSON.stringify(report()), null);
        compare(parsed.state.power, false);
        compare(parsed.state.target_temperature, 24);
        verify(parsed.state.token === undefined);
        verify(parsed.state.id === undefined);
        compare(parsed.capabilities.supported_modes.length, 1);
        verify(parsed.capabilitiesFromDevice);
    }

    function test_reject_invalid() {
        var failed = false;
        try { Model.parse("{invalid", null); } catch (error) { failed = true; }
        verify(failed);
        var data = report();
        data.state.online = false;
        failed = false;
        try { Model.parse(JSON.stringify(data), null); } catch (error) { failed = true; }
        verify(failed);
    }

    function test_control_requires_confirmation() {
        var data = report();
        delete data.capabilities;
        var failed = false;
        try { Model.parse(JSON.stringify(data), report().capabilities); }
        catch (error) { failed = true; }
        verify(failed);
        data.confirmed = true;
        compare(Model.parse(JSON.stringify(data), report().capabilities).state.power, false);
    }

    function test_temperature() {
        compare(Model.temperature(23.5), "23,5 °C");
        compare(Model.temperature(null), "—");
        compare(Model.clampTemperature(40, report().capabilities), 30);
        compare(Model.clampTemperature(10, report().capabilities), 16);
        compare(Model.clampTemperature(23.6, report().capabilities), 23.5);
        verify(Model.validDraft(23.5, "COOL", report().capabilities));
        verify(!Model.validDraft(23.1, "COOL", report().capabilities));
        verify(!Model.validDraft(23, "HEAT", report().capabilities));
        compare(Model.clampTemperature(24, null), null);
    }

    function test_ieco() {
        var d = report();
        d.state.ieco = true;
        d.capabilities.supports_ieco = true;
        d.capabilities.ieco_number = 8;
        var r = Model.parse(JSON.stringify(d), null);
        verify(r.state.ieco);
        compare(r.capabilities.ieco_number, 8);
        verify(Model.iecoReady(r.state, r.capabilities));
        r.state.ieco = null;
        verify(!Model.iecoReady(r.state, r.capabilities));
        r.state.ieco = false;
        verify(!Model.iecoReady(r.state, r.capabilities));
        r.state.power = true;
        verify(Model.iecoReady(r.state, r.capabilities));
        r.state.mode = "DRY";
        verify(!Model.iecoReady(r.state, r.capabilities));
        compare(Model.aiColor(Qt.rgba(0,0,0,1)), "#81c995");
        compare(Model.aiColor(Qt.rgba(1,1,1,1)), "#156b35");
    }

    function test_display() {
        var d = report();
        d.state.display_on = false;
        d.capabilities.supports_display_control = true;
        var r = Model.parse(JSON.stringify(d), null);
        compare(r.state.display_on, false);
        verify(Model.displayReady(r.state, r.capabilities));
        r.state.display_on = null;
        verify(!Model.displayReady(r.state, r.capabilities));
        r.state.display_on = true;
        r.capabilities.supports_display_control = false;
        verify(!Model.displayReady(r.state, r.capabilities));
    }

    function test_errors() {
        verify(Model.failureMessage(true).indexOf("antes de repetir") !== -1);
        verify(Model.failureMessage(false).indexOf("Atualizar") !== -1);
    }
}
