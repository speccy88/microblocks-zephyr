// SPDX-License-Identifier: MIT
import Foundation

struct BoardEndpoint: Equatable {
    let socket: URL
    let origin: String

    init(_ address: String) throws {
        // This slice deliberately uses the IP printed by the board, which is
        // also the firmware's exact Origin. No URL credentials or DNS redirects.
        let parts = address.split(separator: ":", omittingEmptySubsequences: false)
        guard parts.count == 1 || parts.count == 2 else { throw EndpointError.invalid }
        let host = String(parts[0])
        let octets = host.split(separator: ".", omittingEmptySubsequences: false)
        guard octets.count == 4 else { throw EndpointError.invalid }
        let numbers = try octets.map { part -> Int in
            guard let n = Int(part), (0...255).contains(n), String(n) == part else {
                throw EndpointError.invalid
            }
            return n
        }
        let privateAddress = numbers[0] == 10 ||
            (numbers[0] == 172 && (16...31).contains(numbers[1])) ||
            (numbers[0] == 192 && numbers[1] == 168)
        guard privateAddress, numbers[3] != 255 else { throw EndpointError.invalid }
        let port = parts.count == 2 ? Int(parts[1]) : 80
        guard let port, (1...65535).contains(port),
              parts.count == 1 || String(port) == parts[1] else { throw EndpointError.invalid }
        let authority = host + (port == 80 ? "" : ":\(port)")
        socket = URL(string: "ws://\(authority)/ws/vm")!
        origin = "http://\(authority)"
    }

    enum EndpointError: LocalizedError {
        case invalid
        var errorDescription: String? {
            "Enter the board's private IPv4 address, for example 192.168.1.42. An optional port is allowed."
        }
    }
}
