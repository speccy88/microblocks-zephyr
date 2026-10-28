# Linux JS project readback

Keep pinned upstream engine files unchanged. Normalize only a decompiled
reporter chunk (type2) whose sole command is `return` of one reporter expression.
Command scripts and function returns keep their original semantics.

Reading from the board must not upload or clear code. A newly read project has
a fresh code manager without script/chunk bindings. On an explicit script run,
flush pending edits and synchronize if that script still lacks a binding, then
use the original evaluation path. Cancel if the active project/manager/script
changes during the await. Existing bound scripts and palette evaluation retain
the upstream path. Install the adapter once and reject missing required hooks.

Test using the actual pinned compiler, decompiler, project and block classes.
Verify no sync during readback, lazy sync on first explicit run, no redundant
sync and cancellation on project replacement. Then repeat graphical Pi
readback, evaluate42, close/reconnect and fresh-page readback. Keep arbitrary
project/decompiler parity, autosave breadth and hardware peripherals separate.
