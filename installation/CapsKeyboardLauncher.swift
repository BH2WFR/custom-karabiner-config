import AppKit

// A UI-agent launcher keeps Dock launches from activating the Python keyboard.
final class Launcher: NSObject, NSApplicationDelegate {
    private var child: Process?
    private let topic = Notification.Name("com.personal-scripts.caps-keyboard.command")

    private func send(_ command: String) {
        DistributedNotificationCenter.default().postNotificationName(
            topic, object: String(getuid()), userInfo: ["command": command],
            deliverImmediately: true)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard let python = Bundle.main.object(forInfoDictionaryKey: "KeyboardPython") as? String,
              let script = Bundle.main.object(forInfoDictionaryKey: "KeyboardScript") as? String else {
            NSApp.terminate(nil)
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments = [script]
        var environment = ProcessInfo.processInfo.environment
        environment["CAPS_KEYBOARD_APP"] = "1"
        process.environment = environment
        process.terminationHandler = { _ in
            DispatchQueue.main.async { NSApp.terminate(nil) }
        }
        do {
            try process.run()
            child = process
        } catch {
            let alert = NSAlert()
            alert.messageText = "Cannot launch Caps Keyboard"
            alert.informativeText = error.localizedDescription
            alert.runModal()
            NSApp.terminate(nil)
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        send("show")
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let process = child, process.isRunning else { return .terminateNow }
        send("quit")
        // Let Python release its own keys before the launcher exits.
        return .terminateCancel
    }
}

let app = NSApplication.shared
let delegate = Launcher()
app.setActivationPolicy(.accessory)
app.delegate = delegate
app.run()
