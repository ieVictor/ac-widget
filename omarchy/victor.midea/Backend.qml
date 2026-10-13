pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "Model.js" as Model

QtObject {
    id: root

    readonly property string defaultExecutable: Quickshell.env("HOME") + "/development/midea-desktop/.venv/bin/midea-desktop"
    property string executable: defaultExecutable
    property int refreshSeconds: 60
    property var state: null
    property var capabilities: null
    property bool capabilitiesFromDevice: false
    property string errorMessage: ""
    property double lastUpdated: 0
    property double clock: Date.now()
    property bool pendingControl: false
    property string pendingAction: ""
    property bool finishing: false
    property bool timedOut: false
    property string output: ""
    readonly property bool busy: runner.running || finishing
    readonly property bool fresh: state !== null && errorMessage === "" && lastUpdated > 0 && clock - lastUpdated <= Math.max(120000, refreshSeconds * 2000)
    readonly property bool controlsReady: fresh && capabilitiesFromDevice && Model.usableCapabilities(capabilities) && !busy
    property Process runner

    runner: Process {
        id: runner

        onExited: function (exitCode, exitStatus) {
            root.finishing = true;
            Qt.callLater(function () {
                root.finish(exitCode);
            });
        }

        stdout: StdioCollector {
            waitForEnd: true
            onStreamFinished: root.output = text
        }
        // Do not forward library stderr into the shared shell's logs or UI.

        stderr: StdioCollector {
            waitForEnd: true
        }
    }

    property Timer watchdog

    watchdog: Timer {
        interval: 40000
        onTriggered: {
            root.timedOut = true;
            root.errorMessage = Model.failureMessage(root.pendingControl);
            if (runner.running)
                runner.running = false;
            else
                root.finish(1);
        }
    }

    property Timer poll

    poll: Timer {
        interval: root.refreshSeconds * 1000
        repeat: true
        running: true
        onTriggered: root.refresh()
    }

    property Timer ageClock

    ageClock: Timer {
        interval: 5000
        repeat: true
        running: true
        onTriggered: root.clock = Date.now()
    }

    property IpcHandler diagnosticsIpc: IpcHandler {
        target: "midea-widget"
        function status(): string {
            return JSON.stringify({
                busy: root.busy,
                fresh: root.fresh,
                state: root.state,
                controlsReady: root.controlsReady,
                lastUpdated: root.lastUpdated,
                error: root.errorMessage,
                capabilitiesFromDevice: root.capabilitiesFromDevice
            });
        }
        function refresh(): void {
            root.refresh();
        }
    }

    signal confirmed

    function configure(path, seconds) {
        executable = path ? String(path) : defaultExecutable;
        var interval = Number(seconds);
        refreshSeconds = isFinite(interval) ? Math.max(30, Math.min(600, interval)) : 60;
    }

    function run(args, control) {
        if (busy)
            return false;

        pendingControl = control;
        pendingAction = args[0];
        timedOut = false;
        output = "";
        runner.command = [executable, "--timeout", "30", "widget"].concat(args);
        finishing = true;
        watchdog.restart();
        runner.running = true;
        return true;
    }

    function refresh() {
        return run(["status"], false);
    }

    function setPower(on) {
        if (!controlsReady || typeof on !== "boolean")
            return false;

        return run([on ? "on" : "off"], true);
    }

    function cycleSwing() {
        if (!controlsReady || !Model.swingReady(state, capabilities))
            return false;
        return run(["swing", "--position", "next"], true);
    }

    function setDisplay(on) {
        if (!controlsReady || typeof on !== "boolean" || !Model.displayReady(state, capabilities))
            return false;
        return run(["display", "--enabled", on ? "on" : "off"], true);
    }

    function setIeco(on) {
        if (!controlsReady || typeof on !== "boolean" || !Model.iecoReady(state, capabilities))
            return false;
        return run(["ieco", "--enabled", on ? "on" : "off"], true);
    }

    function apply(temperature, mode) {
        if (!controlsReady || !Model.validDraft(temperature, mode, capabilities))
            return false;

        return run(["set", "--temperature", String(temperature), "--mode", String(mode).toLowerCase()], true);
    }

    function finish(exitCode) {
        watchdog.stop();
        if (timedOut || exitCode !== 0) {
            errorMessage = Model.failureMessage(pendingControl);
        } else {
            try {
                var report = Model.parse(output, capabilities);
                state = report.state;
                capabilities = report.capabilities;
                if (report.capabilitiesFromDevice !== null)
                    capabilitiesFromDevice = report.capabilitiesFromDevice;

                errorMessage = "";
                lastUpdated = Date.now();
                clock = lastUpdated;
                confirmed();
            } catch (ignored) {
                errorMessage = Model.failureMessage(pendingControl);
            }
        }
        // No retry of writes. Future timer invocations only query state.
        output = "";
        pendingControl = false;
        pendingAction = "";
        finishing = false;
    }
}
