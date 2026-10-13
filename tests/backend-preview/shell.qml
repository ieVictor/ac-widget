import QtQuick
import Quickshell
import Quickshell.Io
import "." as Midea

ShellRoot {
    id: root
    property var backend: Midea.Backend

    Component.onCompleted: {
        var fake = Quickshell.env("MIDEA_WIDGET_FAKE_EXECUTABLE");
        if (!fake.endsWith("/tests/fixtures/fake_widget_backend.py")) {
            backend.configure("/nonexistent-midea-test-backend", 600);
            throw new Error("Only the isolated fake backend is allowed");
        }
        backend.configure(fake, 600);
        backend.refresh();
    }

    IpcHandler {
        target: "midea-test"
        function status(): string {
            return JSON.stringify({
                fresh: root.backend.fresh,
                ready: root.backend.controlsReady,
                state: root.backend.state,
                error: root.backend.errorMessage,
                busy: root.backend.busy
            });
        }
        function power(value: string): string {
            return String(root.backend.setPower(value === "true"));
        }
        function swing(): string {
            return String(root.backend.cycleSwing());
        }
        function display(value: string): string {
            return String(root.backend.setDisplay(value === "true"));
        }
        function ieco(value: string): string {
            return String(root.backend.setIeco(value === "true"));
        }
        function apply(): string {
            return String(root.backend.apply(23.5, "DRY"));
        }
        function refresh(): void {
            root.backend.refresh();
        }
    }
}
