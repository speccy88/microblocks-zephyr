# Website design review and reuse boundary

The owner requested the look and feel of microblocks.fun and inspection of
both website repositories. This review is separate from the MPL-2.0 GP editor
that the portal actually runs.

## Public reference sources inspected

- [Archived GitHub website](https://github.com/bromagosa/microblocks-site),
  public Git clone at `56fa04cf2d5f94ebdf9ee54eea3f139d0c9960fa`.
  Root `LICENSE` contains GPL version 3. `static/reset.css` explicitly identifies
  Eric Meyer's reset as public domain. `static/LICENSE.txt` contains Apache-2.0
  boilerplate, with no clear grant assigning every logo, font or illustration
  to that license. A directory license file must not be treated as a blanket
  trademark or third-party artwork permission.
- [Newer GitLab website](https://gitlab.com/kram08980/microblocks-site): the web
  request redirects to GitLab sign-in. An actual anonymous HTTPS Git clone was
  attempted with terminal prompts disabled; it failed asking for a username.
  Its source, license and asset-specific exceptions could not be inspected.
  No login, alternate identity, bypass or copied GitLab content was used.
- [Current live website](https://microblocks.fun/), HTTP 200. Its HTML references
  `/main.css`, `/main.js`, `/assets/img/boardie/` and Space Grotesk/Inter font
  files. The old repository uses `static/style.css`, Roboto and Snippets
  templates. These facts demonstrate that the archived tree is not the
  currently served source layout; they do not prove a particular inaccessible
  GitLab revision is the deployed one.

Observed live HTML SHA256:
`826854594ce4f0be3dc54a5cb113118d28f37fbf6d7bdcd5476d3d0db848da44`.
Observed live CSS SHA256:
`d8095fd582ca8fa5e76490ab65018f8dcb6045b8d2d983729c8fa168346507fa`.
These identify the inspected responses, not a promise that the live site will
remain unchanged.

## What this portal reuses

### Exact notices and their scope

| Source file | Version or notice | Scope used for this review |
|---|---|---|
| Archived website `LICENSE` | GNU GPL, version 3, 29 June 2007 | Root software license text. No separate "or later" grant was inferred. No archived website software was copied. |
| Archived website `static/LICENSE.txt` | Apache License 2.0, January 2004 | License text located beside Roboto font files. It does not identify every covered file or grant trademark rights; it was not treated as permission for all site artwork. No font files were copied. |
| Archived website `static/reset.css` | Eric Meyer reset v2.0, 2011-01-26; explicit public-domain notice | This reset file only. The portal's CSS was independently written. |
| Newer GitLab repository | Unavailable to anonymous inspection | No license filename/version or deployed-source revision can be established from the sign-in page. No GitLab source or assets were copied. |
| Pinned editor `gettext.js` | MPL 2.0; copyright 2025 John Maloney, Bernat Romagosa and Jens Moenig | This editor component retains its original header. |
| Pinned editor `FileSaver.js` | MIT; Eli Grey; version `1.1.20151003` | The existing editor component retains its MIT attribution and upstream license link. This is not the license of the marketing site. |
| Portal `web/portal/*` and preparation changes | MPL-2.0 SPDX headers; full text in `licenses/MPL-2.0.txt` | Newly authored portal/adapter and modifications, alongside the separately licensed upstream components. |

The pinned editor asset manifest contains no `.ttf`, `.woff`, `.woff2` or
`.otf` files. The independently authored portal uses system fonts. These facts
do not imply that artwork or trademarks are generally relicensed as MPL.

The exact archived notice bytes have these SHA256s:

- `LICENSE`: `8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903`.
- `static/LICENSE.txt`: `3ddf9be5c28fe27dad143a5dc76eea25222ad1dd68934a047064e56ed2fa40c5`.
- `static/reset.css`: `f6222e9f5dfa8af53013c25a508e267316d68ef4283c9167d353b8acf2d9a2a7`.

### Correspondence with the live site

The observed live HTML/CSS hashes above identify the inspected deployment
responses. Their `/main.css`, `/main.js`, Boardie asset directory and
Space Grotesk/Inter font references differ from the archived GitHub tree's
Snippets templates, `static/style.css` and Roboto files. The archived
repository's own description points to the newer GitLab project. This is
evidence of succession and of a different deployed layout, not proof that a
particular GitLab commit matches the live site. That correspondence remains
unverified because the GitLab source was unavailable anonymously.

No website HTML, CSS, font binaries, mascot artwork, partner logos or photos
were copied. Its layout, responsive styles and simple block illustration are
independently authored. The visual reference is acknowledged through a link
to MicroBlocks, with a distinct "on Zephyr" label identifying this experimental
port. The general blue/orange/purple/teal color language and approachable
layout are design inspiration, not a representation of official affiliation.

The actual embedded GP editor is a separate upstream distribution. Its pinned
manifest, copyright headers, embedded GP source, existing editor graphics and
component notices are retained. The preparation patches and browser adapter
are supplied as source under their MPL-2.0 SPDX notices. Generated editor
assets are built from immutable verified source, rather than copied from the
current marketing website. See `LICENSES.md`, the `licenses/` directory and
`dependencies/ide-assets.json`.
