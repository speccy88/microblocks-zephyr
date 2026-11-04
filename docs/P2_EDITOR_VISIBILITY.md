# P2 blocks in the JavaScript editor

The published root immediately offers eight board choices. Selecting
**Parallax Propeller 2** opens a separate JavaScript editor tab that shows
the five [focused P2 libraries](PROPELLER2_LIBRARIES.md), including their
Smart Pin and cog blocks, without connecting hardware or manually importing a
library. A new P2 project receives the same groups. Existing project scripts and
definitions are preserved; reorganizing a saved library must not replace its code.

The runtime JavaScript profile and its JSON receipt must name the same current
functions. Versioned library and profile requests must avoid reusing older Pages
cache entries. The pinned upstream JavaScript engine and firmware remain unchanged.

The active site must not publish the GP landing page, GP editor engines or their
Linux preview. Historical source, commits, branches and local projects remain
untouched. The reviewed GP archive is still a verified build input; its editor
files are omitted from the final deployment artifact.

Acceptance uses a fresh browser context at the normal root, selects P2 through
the portal, checks the visible library and representative new palette blocks,
creates a new project, opens a project with existing code, and verifies that no
serial connection is requested. Both direct P2 entry and cancelled target changes
remain covered. Removed GP URLs must return 404. Browser results do not establish
physical P2 execution; this change requires no flashing or board interaction.

The [2026-11-04 browser record](../evidence/2026-11-04/propeller2/editor-visibility.json)
reproduces the old startup failure and records the passing current palette,
project-preservation, mobile, compiler and 404 checks, with a P2 palette screenshot.
