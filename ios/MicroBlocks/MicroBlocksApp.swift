// SPDX-License-Identifier: MIT
import SwiftUI

@main
struct MicroBlocksApp: App {
    var body: some Scene { WindowGroup { EditorView().ignoresSafeArea() } }
}

private struct EditorView: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> EditorViewController { EditorViewController() }
    func updateUIViewController(_ uiViewController: EditorViewController, context: Context) {}
}
