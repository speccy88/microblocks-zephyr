# JavaScript editor beside GP

`tools/package_js_site.py` copies an existing built GP artifact unchanged and
adds `js-preview/index.html` and eight explicit target directories from
`dependencies/editor-targets.json`. It does not publish or edit a workflow. The public GP
site remains at main `6e2b4f9`; the separate JS source pin and sync workflow in
[JS_EDITOR_MIGRATION.md](JS_EDITOR_MIGRATION.md) remain unchanged.

```sh
python3 tools/package_js_site.py --source /path/to/pinned-js-git \
  --gp-site /path/to/existing-gp-build --output /new/combined-site
python3 -m http.server 18898 --bind 127.0.0.1 --directory /new/combined-site
```

Open `/js-preview/` for the new hub. The root stays the existing GP portal.
The site manifest binds every copied GP file, target identity and generated
asset. All targets retain the exact upstream engine bytes and licenses. The
unprofiled upstream HTML entry is preserved as non-executable source text in
explicit profiles; use their generated `index.html` or `microblocks.html`.

Pi 5 excludes the custom MicroDuck bundle and needs no robot services. Its
connection guard admits only the existing explicit loopback transport. For a
real session, pass the **Pi profile directory**, rather than the combined site
root, to `linux/arm64/session.py --editor`. The static preview has no VM.
The HTTPS profile permits offline editing by policy; graphical HTTPS acceptance
and hosted WSS are not commissioned by this slice.

MicroDuck includes the coherent six-library bundle in Add Library. Importing it
loads140 actual functions across six categories. It is a disconnected placeholder
even on loopback: the CommPort adapter rejects serial, BLE, Boardie and Linux
connections before opening any provider. This is a target guard, not robot
authentication or physical acceptance. The existing development profile remains
available for the previously tested native VM fixtures.

Fruit Jam, Waveshare RLCD, P2, ESP32-P4 and XRP offer an explicit USB chooser
with a matching board/version gate before uploads. **Load target blocks** imports
the complete bundle; exact constituent sources and hashes accompany it. P2
requires v405 and never asserts DTR. XRP uses the production library and native
actuator protections remain in the runtime. The UNO Q reference is offline.
These USB paths are fixture-tested; physical JS board acceptance remains pending.
Board-hosted network/WSS transport is not ported by this checkpoint. P4 extended
media/files/NN views remain in GP while their JavaScript adapters are developed.

Seven provider-policy cases and three actual pinned compiler/port cases cover
the guard, including no provider allocation for hosted Pi or placeholder paths.
The actual pinned importer compiles the existing140 functions. Local graphical
acceptance imported the same six categories with connection disabled. A browser
canvas input call took about12 minutes to return; no approval or denial was
reported, and the operation was not duplicated. No Pi process was started.

Future deployment should build GP into one staging directory, run this compositor
into a separate final directory, then upload only that completed directory. Do
not merge main's five-board GP compositor blindly into the migration branch's
seven-board GP packager. Review the resulting source-only publication separately;
local screenshots and lab evidence are outside the existing deployment approval.
