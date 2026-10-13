import QtQuick
import QtTest
import "../../omarchy/victor.midea/icons" as Midea
import "../../omarchy/victor.midea/Model.js" as Model

TestCase {
    name: "SwingIcon"
    visible: true
    when: windowShown
    width: 50
    height: 50

    Midea.SwingIcon {
        id: icon
        width: 18
        height: 28
    }

    function test_states_data() {
        return Model.swingPositions.map(function(value) { return { tag: value, value: value }; });
    }

    function test_states(data) {
        icon.swingState = data.value;
        var count = 0;
        for (var i = 0; i < 5; i++) {
            var line = findChild(icon, "swingLine" + i);
            verify(line !== null);
            if (line.visible) count++;
            compare(line.visible, data.value === "AUTO" || data.value === "POS_" + (i + 1));
        }
        compare(count, data.value === "AUTO" ? 5 : data.value === "OFF" ? 0 : 1);
        compare(count, icon.activeLines);
    }

    function test_unknown_and_guards() {
        icon.swingState = "";
        compare(icon.activeLines, 0);
        verify(!Model.swingReady({ power: true, vertical_swing_state: null }, { supports_vertical_swing: true }));
        verify(!Model.swingReady({ power: false, vertical_swing_state: "OFF" }, { supports_vertical_swing: true }));
        verify(Model.swingReady({ power: true, vertical_swing_state: "POS_1" }, { supports_vertical_swing: true }));
        compare(Model.swingLabel("POS_5"), "Posição 5");
        compare(Model.swingLabel("AUTO"), "Oscilando");
    }
}
