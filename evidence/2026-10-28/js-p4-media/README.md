# JavaScript P4 inline media and compiler/readback checkpoint

Base:a2d2275. The final combined revision passes **504 tests, no failures or
skips** through the unchanged `python3 tools/validate.py`, with2,274 exact
repository inputs checked before and after execution in both the Linux replica
and working tree. See `combined-final-full.log`, `combined-final-receipt.json`,
`combined-final-source-inputs.json` and the copied runner. The runner uses the
existing verified local VM binary695fc61a…02a1; it does not use SSH or a Pi.

Twelve focused cases use the actual pinned JS compiler, decompiler, code manager
and morph classes, with protocol-faithful RPC208/209 fixtures. Coverage includes
nested producers, preserved p4TakePicture helper calls, hidden library bodies,
source invariance, bytecode readback unwrapping, namespace restoration, malformed
wrappers, fresh-run sessions, cancellation during project replacement, copied
and restored blocks, expiry, zoom, cache/audio limits and URL/buffer disposal.
The final project-switch cancellation guard was added after the first502-test
pass and is covered by the final504-test run.

The actual IAB graphical test uses an isolated local fixture entry. It renders
known RGB bars and generated4-second silent PCM on block-owned views; explicit
Play then Pause changes the controls as expected. Dragging retains the image;
collapse/zoom work. Expiry clears both views. Reopening the saved source keeps
source unchanged and restores no pixels, PCM or site IDs. Screenshots and final
AX state are included. The console warning/error list is empty. The graphical
entry and its fixture script are absent from product packages. UI evidence
precedes only the nonvisual final project-switch guard, tested in the actual
code-manager regression case.

The final P4 package has592 manifest entries plus its manifest; all550 pinned
upstream files and13 local service copies match source. `package-audit.json`
records its manifest SHA348da289…b64ab and the MicroDuck package audit. No
upstream engine, shared GP media source, native firmware or live website changed.
Protected P4 checkout, COM5/COM12, Pi processes and paused SFC were untouched.
Public refs were read-only verified: migration2c060b7, gp3905dc1, main6e2b4f9.

Prior results are retained. The first502-test pass is an earlier revision, not
final acceptance. Early focused development caught Morphic's stale parent
pointer after deletion; checking real tree membership fixed it. A helper-import
test initially concatenated duplicate main modules; using the real library
import path corrected the fixture. Those early errors were observed in tool
output; these notes are a transcription, not invented raw logs. Initial preview
server processes ended or were unreachable; the owned host-loopback server
resolved this. An error-page data URL reload was blocked by browser URL policy;
that blocked operation was not retried. Final checks used a fresh known local
fixture URL. Temporary servers and successful fixture tabs are closed.

Physical camera/microphone/speaker, real USB/WSS, TFLM inference and graphical
board readback are **not established** by these fixtures. Reconcile the P4
owner's current firmware before hardware acceptance. Broader embedded-library
readback combinations remain open. No new release, push, deployment, reboot,
security change or denied Pi numeric-suite action was performed.

The companion [MicroDuck starter evidence](../microduck-starter/README.md)
records the next tested daemon-library abstraction layer.

Evidence text copies are normalized to UTF-8/LF with trailing line whitespace
removed for repository checks. Exact pre-normalization bytes, including original
receipts and failed logs, are retained in [raw-text-evidence.zip](../js-p4-media/raw-text-evidence.zip).
The normalization manifest records both hashes; JSON values are unchanged.
