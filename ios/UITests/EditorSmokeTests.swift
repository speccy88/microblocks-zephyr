// SPDX-License-Identifier: MIT
import XCTest
import CoreGraphics

final class EditorSmokeTests: XCTestCase {
    private func readyMenu(in web: XCUIElement) -> XCUIElement {
        let menu = web.buttons["Menu"]
        XCTAssertTrue(menu.waitForExistence(timeout: 30))
        // Toolbar existence precedes the real editor and loading overlay.
        // Wait for the product's ready state before sending the first tap.
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "enabled == true"), object: menu)
        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 30), .completed, web.debugDescription)
        return menu
    }

    func testBundledEditorAndConnectionSheet() {
        let app = XCUIApplication()
        app.launch()
        let web = app.webViews.firstMatch
        let menu = readyMenu(in: web)
        let connect = web.buttons["Connect board"]
        XCTAssertTrue(connect.waitForExistence(timeout: 30), "Bundled JS editor must launch offline")
        // WebKit exposes aria-pressed controls with a toggle accessibility
        // type, which is not necessarily XCUIElementTypeButton.
        XCTAssertTrue(web.descendants(matching: .any)["Blocks"].firstMatch.exists)
        // Wait for the real engine's project chrome, not just the local toolbar.
        menu.tap()
        XCTAssertTrue(web.buttons["Project"].waitForExistence(timeout: 20))
        menu.tap()
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
        let refusal = XCTAttachment(screenshot: app.screenshot())
        refusal.name = "Native private-address rejection"; refusal.lifetime = .keepAlways
        add(refusal)
        XCTAssertTrue(web.buttons["Connect"].isEnabled, "A refused link must allow retry in the visible sheet")
        web.buttons["Close connection sheet"].tap()
        connect.tap()
        web.buttons["Close connection sheet"].tap()
        XCUIDevice.shared.orientation = .landscapeLeft
        let landscape = XCTAttachment(screenshot: app.screenshot())
        landscape.name = "iPhone landscape editor"; landscape.lifetime = .keepAlways
        add(landscape)
        XCUIDevice.shared.orientation = .portrait
    }

    func testCompactControlsAndWorkspacePinch() {
        let app = XCUIApplication()
        app.launch()
        let web = app.webViews.firstMatch
        let menu = readyMenu(in: web)
        let view = web.buttons["View tools"]
        XCTAssertTrue(view.waitForExistence(timeout: 20))
        let workspace = web.descendants(matching: .any)["Programming workspace"].firstMatch
        XCTAssertTrue(workspace.waitForExistence(timeout: 10))
        for landscape in [false, true] {
            XCUIDevice.shared.orientation = landscape ? .landscapeLeft : .portrait
            for _ in 0..<3 {
                menu.tap()
                XCTAssertTrue(web.buttons["Project"].waitForExistence(timeout: 5))
                web.buttons["Hide controls"].tap()
                let restore = web.buttons["Show controls"]
                XCTAssertTrue(restore.waitForExistence(timeout: 5))
                XCTAssertTrue(restore.isHittable)
                restore.tap()
                XCTAssertTrue(menu.isHittable)
                let blocks = web.descendants(matching: .any)["Blocks"].firstMatch
                blocks.tap(); blocks.tap()
                view.tap(); view.tap()
            }
            menu.tap()
            workspace.coordinate(withNormalizedOffset: CGVector(dx: 0.96, dy: 0.5)).tap()
            XCTAssertFalse(web.buttons["Project"].isHittable, "Workspace touch must dismiss the menu before navigation")
            // A real WebKit touch sequence, with the engine scale exposed as
            // an accessible status. This is Simulator evidence, not hardware.
            let zoom = web.descendants(matching: .any).matching(
                NSPredicate(format: "label BEGINSWITH %@", "Workspace zoom ")).firstMatch
            XCTAssertTrue(zoom.waitForExistence(timeout: 5))
            let initial = zoom.label
            workspace.pinch(withScale: landscape ? 0.7 : 1.4, velocity: landscape ? -1 : 1)
            let changed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label != %@", initial), object: zoom)
            XCTAssertEqual(XCTWaiter.wait(for: [changed], timeout: 5), .completed, app.debugDescription)
            let capture = XCTAttachment(screenshot: app.screenshot())
            capture.name = landscape ? "Compact landscape after pinch" : "Compact portrait after pinch"
            capture.lifetime = .keepAlways; add(capture)
        }
        XCUIDevice.shared.orientation = .portrait
        menu.tap()
        web.buttons["Hide controls"].tap()
        XCUIDevice.shared.press(.home)
        app.activate()
        let restore = web.buttons["Show controls"]
        XCTAssertTrue(restore.waitForExistence(timeout: 10))
        restore.tap()
        web.buttons["Connect board"].tap()
        XCTAssertTrue(web.staticTexts["Program over Wi-Fi"].waitForExistence(timeout: 5))
        web.buttons["Close connection sheet"].tap()
    }
}
