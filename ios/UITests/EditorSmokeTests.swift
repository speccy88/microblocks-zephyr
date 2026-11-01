// SPDX-License-Identifier: MIT
import XCTest

final class EditorSmokeTests: XCTestCase {
    func testBundledEditorAndUSBOnlyBoundary() {
        let app = XCUIApplication()
        app.launch()
        let web = app.webViews.firstMatch
        let connect = web.buttons["Connect board"]
        XCTAssertTrue(connect.waitForExistence(timeout: 30), "Bundled JS editor must launch offline")
        XCTAssertTrue(web.buttons["Blocks"].exists)
        // Wait for the real engine's project chrome, not just the local toolbar.
        XCTAssertTrue(web.buttons["Project"].waitForExistence(timeout: 20))
        let portrait = XCTAttachment(screenshot: app.screenshot())
        portrait.name = "iPhone portrait editor"; portrait.lifetime = .keepAlways
        add(portrait)
        connect.tap()
        XCTAssertTrue(web.staticTexts["Program over Wi-Fi"].waitForExistence(timeout: 5))
        XCTAssertTrue(web.textFields.firstMatch.exists)
        web.buttons["Close"].tap()
        XCUIDevice.shared.orientation = .landscapeLeft
        let landscape = XCTAttachment(screenshot: app.screenshot())
        landscape.name = "iPhone landscape editor"; landscape.lifetime = .keepAlways
        add(landscape)
        XCUIDevice.shared.orientation = .portrait
    }
}
