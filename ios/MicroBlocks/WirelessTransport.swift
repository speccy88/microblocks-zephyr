// SPDX-License-Identifier: MIT
import Foundation

// All state and bridge callbacks run on the main queue. Each asynchronous
// callback checks a generation as well as the JS session ID, including reloads.
final class WirelessTransport: NSObject, URLSessionTaskDelegate {
    var emit: (([String: Any], @escaping () -> Void) -> Void)?
    private var session: URLSession?
    private var socket: URLSessionWebSocketTask?
    private var generation = UUID()
    private var identifier = ""
    private var ready = false
    private var queue: [Data] = []
    private var queuedBytes = 0
    private var sending = false
    private var deadline: DispatchWorkItem?

    func connect(address: String, id: String) {
        close()
        identifier = id
        do {
            let endpoint = try BoardEndpoint(address)
            let configuration = URLSessionConfiguration.ephemeral
            configuration.waitsForConnectivity = false
            configuration.timeoutIntervalForRequest = 10
            configuration.timeoutIntervalForResource = 86400
            configuration.httpShouldSetCookies = false
            let session = URLSession(configuration: configuration, delegate: self, delegateQueue: .main)
            self.session = session
            var request = URLRequest(url: endpoint.socket)
            request.setValue(endpoint.origin, forHTTPHeaderField: "Origin")
            let task = session.webSocketTask(with: request)
            task.maximumMessageSize = 4096
            socket = task
            let token = generation
            let timeout = DispatchWorkItem { [weak self] in
                guard let self, self.generation == token else { return }
                self.fail("Board connection timed out. Check Wi-Fi and Local Network permission.")
            }
            deadline = timeout
            DispatchQueue.main.asyncAfter(deadline: .now() + 10, execute: timeout)
            task.resume()
            receive(token)
        } catch { fail(error.localizedDescription) }
    }

    func write(_ bytes: [UInt8], id: String) {
        guard id == identifier, ready, socket != nil else { return }
        guard !bytes.isEmpty, bytes.count <= 1024, queuedBytes + bytes.count <= 32768 else {
            fail("Native output buffer limit exceeded"); return
        }
        queue.append(Data(bytes))
        queuedBytes += bytes.count
        drain(generation)
    }

    func close(id: String? = nil) {
        if let id, id != identifier { return }
        generation = UUID()
        deadline?.cancel(); deadline = nil
        ready = false; queue.removeAll(); queuedBytes = 0; sending = false
        socket?.cancel(with: .goingAway, reason: nil); socket = nil
        session?.invalidateAndCancel(); session = nil
    }

    func background() {
        guard socket != nil else { return }
        fail("Link closed when app left the foreground. Connect to resume.")
    }

    private func fail(_ reason: String) {
        let id = identifier
        close()
        emit?(["type": "error", "id": id, "reason": reason], {})
    }

    private func receive(_ token: UUID) {
        socket?.receive { [weak self] result in
            DispatchQueue.main.async {
                guard let self, self.generation == token else { return }
                switch result {
                case .failure(let error): self.fail(error.localizedDescription)
                case .success(let message):
                    if !self.ready {
                        guard case .string("ready") = message else {
                            self.fail("Board did not send the MicroBlocks readiness marker"); return
                        }
                        self.deadline?.cancel(); self.deadline = nil; self.ready = true
                        self.sendEvent(["type": "ready"], token: token)
                    } else {
                        guard case .data(let data) = message, !data.isEmpty, data.count <= 4096 else {
                            self.fail("Board sent an invalid binary frame"); return
                        }
                        self.sendEvent(["type": "data", "bytes": Array(data)], token: token)
                    }
                }
            }
        }
    }

    private func sendEvent(_ fields: [String: Any], token: UUID) {
        var event = fields
        event["id"] = identifier
        // Only request another native frame after WebKit has consumed this
        // event. JS independently enforces the total unread 128 KiB bound.
        emit?(event) { [weak self] in
            guard let self, self.generation == token else { return }
            self.receive(token)
        }
    }

    private func drain(_ token: UUID) {
        guard !sending, let data = queue.first, let socket else { return }
        sending = true
        socket.send(.data(data)) { [weak self] error in
            DispatchQueue.main.async {
                guard let self, self.generation == token else { return }
                if let error { self.fail(error.localizedDescription); return }
                self.queue.removeFirst(); self.queuedBytes -= data.count; self.sending = false
                self.emit?(["type": "sent", "id": self.identifier, "count": data.count], {})
                self.drain(token)
            }
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}
