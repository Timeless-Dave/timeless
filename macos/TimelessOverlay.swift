import Cocoa
import WebKit

/// Borderless windows refuse key status unless this is overridden — without it, typing never reaches the form.
final class KeyableWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

final class OverlayController: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    let base = ProcessInfo.processInfo.environment["TIMELESS_URL"] ?? "http://127.0.0.1:8787"
    var window: KeyableWindow!
    var web: WKWebView!
    var timer: Timer?
    var currentPath: String = ""
    var isBlocking = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        let screen = NSScreen.main?.frame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        window = KeyableWindow(
            contentRect: screen,
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.isOpaque = true
        window.backgroundColor = NSColor(calibratedRed: 0.05, green: 0.06, blue: 0.07, alpha: 1)
        window.ignoresMouseEvents = false
        window.acceptsMouseMovedEvents = true
        window.hidesOnDeactivate = false

        let config = WKWebViewConfiguration()
        config.preferences.isElementFullscreenEnabled = false
        web = WKWebView(frame: screen, configuration: config)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        // drawsBackground=false leaves a blank white layer on some macOS builds before
        // the SPA paints; keep the window's dark plate visible underneath instead.
        if #available(macOS 12.0, *) {
            web.underPageBackgroundColor = window.backgroundColor
        }
        web.wantsLayer = true
        web.layer?.backgroundColor = window.backgroundColor?.cgColor
        window.contentView = web
        window.orderOut(nil)

        poll()
        timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.poll()
        }
    }

    func retryCurrentPage() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            guard let self, !self.currentPath.isEmpty else { return }
            self.showPage(self.currentPath)
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        retryCurrentPage()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        retryCurrentPage()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        window.makeKey()
        window.makeFirstResponder(web)
        webView.evaluateJavaScript(
            "document.querySelector('textarea,input')?.focus()",
            completionHandler: nil
        )
    }

    func poll() {
        guard let url = URL(string: base + "/api/today") else { return }
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            guard let self else { return }
            guard let data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else {
                return
            }
            DispatchQueue.main.async {
                let path: String
                if json["halt"] is [String: Any] {
                    path = "/halt"
                } else if json["needs_recap"] as? Bool ?? false {
                    path = "/recap"
                } else if json["needs_gate"] as? Bool ?? true {
                    path = "/gate"
                } else {
                    path = ""
                }
                self.applyPath(path)
            }
        }.resume()
    }

    var pendingPath: String = "\u{0}"
    var pendingHits: Int = 0

    func applyPath(_ path: String) {
        if path == pendingPath {
            pendingHits += 1
        } else {
            pendingPath = path
            pendingHits = 1
        }
        let already = path.isEmpty ? !window.isVisible : (currentPath == path && window.isVisible)
        if pendingHits < 2 && !already { return }
        if path.isEmpty {
            isBlocking = false
            currentPath = ""
            window.orderOut(nil)
            NSApp.setActivationPolicy(.accessory)
            NSApp.hide(nil)
            return
        }
        present(path)
    }

    func present(_ path: String) {
        let wasHidden = !window.isVisible
        isBlocking = true
        NSApp.setActivationPolicy(.accessory)
        if wasHidden {
            window.orderFrontRegardless()
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            window.makeFirstResponder(web)
        }
        showPage(path)
    }

    func showPage(_ path: String) {
        if currentPath == path, web.url != nil { return }
        currentPath = path
        if let url = URL(string: base + path) {
            web.load(URLRequest(url: url))
        }
    }
}

let app = NSApplication.shared
let delegate = OverlayController()
app.delegate = delegate
app.run()
