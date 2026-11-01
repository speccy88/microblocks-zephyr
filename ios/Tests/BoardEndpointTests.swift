// SPDX-License-Identifier: MIT
import XCTest
@testable import MicroBlocks

final class BoardEndpointTests: XCTestCase {
    func testPrivateLANAndExactOrigin() throws {
        for address in ["10.0.0.2", "172.16.0.2", "172.31.255.2", "192.168.1.42"] {
            let endpoint = try BoardEndpoint(address)
            XCTAssertEqual(endpoint.origin, "http://\(address)")
            XCTAssertEqual(endpoint.socket.absoluteString, "ws://\(address)/ws/vm")
        }
        XCTAssertEqual(try BoardEndpoint("192.168.1.42:8080").origin, "http://192.168.1.42:8080")
        XCTAssertEqual(try BoardEndpoint("192.168.1.42:80").origin, "http://192.168.1.42")
    }
    func testRejectsPublicCredentialAndAmbiguousAddresses() {
        for value in ["", "127.0.0.1", "8.8.8.8", "169.254.1.2", "172.15.0.2", "172.32.0.2",
                      "192.168.1.255", "192.168.001.2", "192.168.1.256", "192.168.1.2:0",
                      "192.168.1.2:65536", "192.168.1.2:080", "http://192.168.1.2", "192.168.1.2/ws/vm",
                      "user@192.168.1.2", "board.local", "[::1]", "192.168.1.2?x", "192.168.1.2#x"] {
            XCTAssertThrowsError(try BoardEndpoint(value), value)
        }
    }
}
