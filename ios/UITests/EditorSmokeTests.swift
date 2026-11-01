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
        // Use the on-screen decimal keypad: WKWebView on iOS 18 can accept
        // typeText into the AX cache while leaving the required DOM field empty.
        for character in ["8", ".", "8", ".", "8", ".", "8"] {
            let key = character == "." ? app.keys.matching(NSPredicate(format: "label IN %@",
                [".", "period", "Decimal", "Decimal point", "decimal point"])).firstMatch : app.keys[character]
            XCTAssertTrue(key.waitForExistence(timeout: 5), app.keyboards.debugDescription)
            key.tap()
        }
        XCTAssertEqual(address.value as? String, "8.8.8.8")
        if app.buttons["Done"].exists { app.buttons["Done"].tap() }
        let entered = XCTAttachment(screenshot: app.screenshot())
        entered.name = "Address entry before native validation"; entered.lifetime = .keepAlways
        add(entered)
        web.buttons["Connect"].tap()
        let rejected = web.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@", "private IPv4")).firstMatch
        let receivedError = rejected.waitForExistence(timeout: 10)
        if !receivedError { print(app.debugDescription) }
        XCTAssertTrue(receivedError, "Native validation must round-trip through the real bridge")
        connect.tap()
        web.buttons["Close connection sheet"].tap()
        XCUIDevice.shared.orientation = .landscapeLeft
        let landscape = XCTAttachment(screenshot: app.screenshot())
        landscape.name = "iPhone landscape editor"; landscape.lifetime = .keepAlways
        add(landscape)
        XCUIDevice.shared.orientation = .portrait
    }
}
