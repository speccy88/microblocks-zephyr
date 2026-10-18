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
