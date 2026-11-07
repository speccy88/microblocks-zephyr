# Shared custom block help

## Contract and acceptance criteria

Every canonical custom `.ubl` block spec, including advanced blocks, and every
JavaScript SFC block has authored documentation. The existing context menu Help
item opens an offline page in a new tab, keyed by stable selector rather than
translated label or palette name. Built-in blocks keep upstream wiki Help.
User-defined functions without a catalog entry receive an explicit
documentation-not-yet-authored page, never a fabricated example.

The page describes inputs, results, prerequisites, examples and limitations.
Examples are displayed as text only. Opening Help does not import libraries,
modify a project, connect to hardware, upload code, reset a device or run an
example. Documentation does not establish physical hardware acceptance.

## Adding a block

1. Add the block spec in its canonical library source.
2. Add its selector to one JSON file under `docs/block-help/`. Use schema 1
   with a `blocks` object keyed by selector. Each entry requires `summary` and
   `returns` strings; `inputs`, `prerequisites`, and `notes` string arrays;
   and one or more `examples` with `title`, `code`, and `explanation` strings.
   `inputs` and `notes` may be empty. `prerequisites` must not be empty.
3. Give concrete, checked units/ranges and initialization steps. Explain how
   to recreate visual examples when code is descriptive rather than pasteable.
   State hardware/firmware requirements and distinguish measured behavior from
   candidate or unvalidated capability. Never include credentials.
4. Run `python tools/block_help.py` and `python tools/validate.py`.

`python tools/block_help.py --inventory` lists every required selector with its
source paths, labels and module names. Discovery scans canonical `.ubl` files
under boards, integration, libraries, linux and bilingual-kws, plus the shared
SFC adapter's specs. Private functions without specs are not reference entries.
Duplicate selector docs, unknown selectors, missing docs and incomplete examples
fail validation and packaging. A selector shared by native and simulation
libraries has one entry, so explain both contexts rather than claiming simulated
results are hardware evidence.

## Implementation and packaging

`tools/block_help.py` builds deterministic `block-help-data.js` from authored
JSON and current source metadata. `tools/js_editor_shared_assets.py` packages
the data, adapter, page, stylesheet and renderer in every shared editor consumer
(portal profiles, Linux, mobile and native shells). No pinned engine file is
patched. The adapter wraps only `MB_Editor.prototype.helpURLFor`; the existing
Help menu supplies navigation. Its hook assertion requires review on an engine
upgrade. Local page scripts render all content through text nodes, not HTML.
Only the small selector index loads in the editor; full documentation loads
on demand in the separate help tab, keeping it out of the interactive VM page.

The index is searchable and deep links encode selectors safely. Missing custom
documentation is clearly labelled at runtime, while repository blocks cannot
silently ship without authored content because the build guard fails first.
Documentation is English initially. No automatic example execution, translated
docs, firmware changes or board testing are part of this feature.
