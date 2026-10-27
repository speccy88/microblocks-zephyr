# JavaScript project save/reopen contract

Preserve the existing `.ubp` text format and the pinned upstream JS engine.
The matrix input and its library default both remain ordinary quoted Strings
of 104 row-major brightness digits; leading zeros and digits 0 through 7 must
survive save/reopen. Unknown non-matrix slot types keep upstream behavior.

Use actual upstream project/parser/compiler classes in fresh isolated contexts.
Include a mixed-brightness matrix, the six embedded MicroDuck libraries, a typed
reading expression and ordinary arithmetic. Preserve script coordinates,
function definitions, declared defaults and repeated canonical save/load cycles.
Editing a restored matrix must not mutate the original project or palette.
All restored functions/scripts must compile while disconnected, with no I/O.

The first regression exposed that `specDefaultString` writes unknown custom
types as nil, then trims them: a matrix library default disappeared despite
the workspace image surviving. Extend only this dispatch through the local
overlay, using upstream string quoting. Reject a changed upstream hook instead
of patching the pinned engine or silently omitting the adaptation.

Graphical Save/download and reopen are separate acceptance checks. A saved-name
UI change without verified file bytes does not establish the full round trip.
Do not repeat uncertain browser actions, resume paused SFC, contact P4 hardware,
modify main or weaken security to complete acceptance.
