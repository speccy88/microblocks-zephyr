# Bounded SD file manager

The optional native P4 `profiles/sd-files.conf` profile extends the existing
Device files dialog with SD access through the same board connection and file
lease. Its matching hosted editor must be installed with the application:
the compiled application contains the exact editor partition header.

## Behavior and acceptance

- Files are confined to `SD:/MBFILES`, with uppercase 8.3 names and an 8192-byte
  limit. Listing returns at most eight files after at most 33 directory calls;
  the UI reports truncation. This count is not a free-space measurement.
- Opening reads bounded chunks into worker-owned storage. Text uses strict
  UTF-8; binary files are shown without a text editor.
- Saving uses `FA_CREATE_NEW`, syncs, closes, reopens and compares every byte.
  Saving an edited source requires a new name. Existing files are preserved.
- Removal requires an exact snapshot retained after a successful creation in
  this firmware session, and a fresh byte-for-byte comparison. At most eight
  creation snapshots are retained; none is evicted to gain deletion authority.
- Format, repartition, rename and overwrite are unavailable. Cancellation and
  deadlines are cooperative between filesystem calls. Failed or uncertain
  writes are not retried or automatically deleted. A partial file may remain.
- Disconnect detaches unsaved drafts and invalidates old transfer tokens.
  RAM and SD share the same monotonically increasing request IDs and controller.

Operations 11 through 20 append SD capabilities, begin, append, create, open,
status, chunk, remove-own, cancel and list to the existing MBFS v1 protocol.
The ordinary capabilities response continues to describe the RAM API; the
editor checks the separate SD capability before issuing SD jobs. Older
firmware remains explicitly unavailable.

The worker serializes file jobs with SD probes, joins before freeing its
internal stack, and uses an aligned internal 512-byte buffer for sector I/O.
CPU staging and successful creation snapshots live in PSRAM. The shared SDMMC
transaction mutex arbitrates card slot 0 and the existing C6 Wi-Fi slot 1.

Physical acceptance requires exclusive creation of a unique test name, complete
readback, a fresh open, removal of that same verified test file, and a concurrent
hash-checked editor asset transfer. Graphical acceptance separately requires
the actual board-hosted Device files dialog, SD selection, creation and reopen.
Host tests and native compilation alone do not establish those results.

Host checks: `tools/test_p4_sd_files.py`, `tools/test_p4_sd_file_worker.py`,
`tools/test_sd_wire.py`, `tools/test_storage_sd_bridge.py`, and
`tests/device_sd*.test.js`. The new task's build command, image identity,
memory audit and installation/physical receipts are retained under its
`resume-evidence` directory. This local continuation is not a published release.

The current local installation has passed those native and graphical checks.
The 8 KiB native file test and simultaneous hash-verified HTTP transfer are
recorded separately from the final UI image's 60-byte UTF-8 create/reopen test.
The final GUI file was independently reread and removed through COM5. The SD
backend source bytes are unchanged across the UI-only updates; see the
[curated evidence](../evidence/2026-10-27/p4-sd-files-summary.json).
