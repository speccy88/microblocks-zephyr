// SPDX-License-Identifier: MIT
import XCTest

final class EditorSmokeTests: XCTestCase {
    func testBundledEditorAndConnectionSheet() {
        let app = XCUIApplication()
        app.launch()
        let web = app.webViews.firstMatch
        let connect = web.buttons["Connect board"]
        XCTAssertTrue(connect.waitForExistence(timeout: 30), "Bundled JS editor must launch offline")
        // WebKit exposes aria-pressed controls with a toggle accessibility
        // type, which is not necessarily XCUIElementTypeButton.
        XCTAssertTrue(web.descendants(matching: .any)["Blocks"].firstMatch.exists)
        // Wait for the real engine's project chrome, not just the local toolbar.
        XCTAssertTrue(web.buttons["Project"].waitForExistence(timeout: 20))
        let portrait = XCTAttachment(screenshot: app.screenshot())
        portrait.name = "iPhone portrait editor"; portrait.lifetime = .keepAlways
        add(portrait)
        connect.tap()
        XCTAssertTrue(web.staticTexts["Program over Wi-Fi"].waitForExistence(timeout: 5))
        XCTAssertTrue(web.textFields.firstMatch.exists)
        // A public address is rejected before any radio/network request. This
        // exercises the real WK message handler and native-to-JS error path.
        let address = web.textFields.firstMatch
        address.tap()
        address.typeText("8.8.8.8")
        web.buttons["Connect"].tap()
        let rejected = web.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", "private IPv4")).firstMatch
        XCTAssertTrue(rejected.waitForExistence(timeout: 10), "Native validation must round-trip through the real bridge")
        connect.tap()
        web.buttons["Close connection sheet"].tap()
        XCUIDevice.shared.orientation = .landscapeLeft
        let landscape = XCTAttachment(screenshot: app.screenshot())
        landscape.name = "iPhone landscape editor"; landscape.lifetime = .keepAlways
        add(landscape)
        XCUIDevice.shared.orientation = .portrait
    }
}
