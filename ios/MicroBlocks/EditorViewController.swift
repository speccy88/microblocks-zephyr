// SPDX-License-Identifier: MIT
import UIKit
import WebKit
import CoreFoundation

final class EditorViewController: UIViewController, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate {
    private var webView: WKWebView!
    private let transport = WirelessTransport()
    private var observers: [NSObjectProtocol] = []
    private var exporting = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        guard let root = Bundle.main.resourceURL?.appendingPathComponent("Editor"),
              FileManager.default.fileExists(atPath: root.appendingPathComponent("index.html").path) else {
            let label = UILabel(); label.text = "Editor bundle missing. Run tools/package_iphone_editor.py before building."
            label.numberOfLines = 0; label.frame = view.bounds; label.autoresizingMask = [.flexibleWidth, .flexibleHeight]
            view.addSubview(label); return
        }
        let configuration = WKWebViewConfiguration()
        configuration.setURLSchemeHandler(BundledEditor(root: root), forURLScheme: "microblocks-app")
        configuration.userContentController.add(self, name: "microblocks")
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.navigationDelegate = self; webView.uiDelegate = self
        webView.scrollView.isScrollEnabled = false
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: view.keyboardLayoutGuide.topAnchor)
        ])
        transport.emit = { [weak self] event, completion in self?.emit(event, completion: completion) }
        observers.append(NotificationCenter.default.addObserver(forName: UIApplication.didEnterBackgroundNotification,
            object: nil, queue: .main) { [weak self] _ in
                self?.transport.background()
                self?.webView.evaluateJavaScript("window.MicroBlocksIPhone?.close()", completionHandler: nil)
            })
        webView.load(URLRequest(url: URL(string: "microblocks-app://editor/index.html")!))
    }

    private func trusted(_ url: URL?) -> Bool { url?.scheme == "microblocks-app" && url?.host == "editor" }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, trusted(message.frameInfo.request.url),
              let body = message.body as? [String: Any], let type = body["type"] as? String,
              let id = body["id"] as? String, id.count <= 80 else { return }
        switch type {
        case "connect":
            guard let address = body["address"] as? String, address.count <= 64 else { return }
            transport.connect(address: address, id: id)
        case "write":
            guard let numbers = body["bytes"] as? [NSNumber], !numbers.isEmpty, numbers.count <= 1024,
                  numbers.allSatisfy({ CFGetTypeID($0) != CFBooleanGetTypeID() &&
                      $0.doubleValue == Double($0.intValue) && (0...255).contains($0.intValue) }) else {
                transport.close(id: id); emit(["type": "error", "id": id, "reason": "Invalid native binary write"]); return
            }
            transport.write(numbers.map { $0.uint8Value }, id: id)
        case "close": transport.close(id: id)
        case "export":
            guard !exporting, let name = body["name"] as? String, let text = body["text"] as? String,
                  name.count <= 200, text.utf8.count <= 4 * 1024 * 1024,
                  name.hasSuffix(".ubp") || name.hasSuffix(".ubl") else {
                emit(["type": "exported", "id": id, "saved": false]); return
            }
            export(text: text, name: name, id: id)
        default: break
        }
    }

    private func emit(_ event: [String: Any], completion: @escaping () -> Void = {}) {
        guard let data = try? JSONSerialization.data(withJSONObject: event, options: [.fragmentsAllowed]),
              let json = String(data: data, encoding: .utf8), webView != nil else { completion(); return }
        webView.evaluateJavaScript("window.MicroBlocksIPhone?.receive(\(json))") { [weak self] _, error in
            if error != nil { self?.transport.close() }
            completion()
        }
    }

    private func export(text: String, name: String, id: String) {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let safeName = (name as NSString).lastPathComponent
        let file = directory.appendingPathComponent(safeName)
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            try text.write(to: file, atomically: true, encoding: .utf8)
            exporting = true
            let share = UIActivityViewController(activityItems: [file], applicationActivities: nil)
            share.popoverPresentationController?.sourceView = view
            share.popoverPresentationController?.sourceRect = CGRect(x: view.bounds.midX, y: view.bounds.midY, width: 1, height: 1)
            share.completionWithItemsHandler = { [weak self] _, completed, _, _ in
                DispatchQueue.main.async {
                    self?.exporting = false
                    self?.emit(["type": "exported", "id": id, "saved": completed, "name": safeName])
                    try? FileManager.default.removeItem(at: directory)
                }
            }
            present(share, animated: true)
        } catch { emit(["type": "exported", "id": id, "saved": false]) }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if trusted(navigationAction.request.url) { decisionHandler(.allow); return }
        if navigationAction.navigationType == .linkActivated, let url = navigationAction.request.url,
           url.scheme == "https" { UIApplication.shared.open(url) }
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) { transport.close() }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { transport.close(); webView.reload() }
    deinit { observers.forEach(NotificationCenter.default.removeObserver) }
}
