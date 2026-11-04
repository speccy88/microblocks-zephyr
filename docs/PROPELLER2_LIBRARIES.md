# Focused P2 libraries

The P2 editor loads five libraries instead of one long P2 Hardware palette:

| Library | Blocks |
|---|---|
| P2 Core | Board identity, cogs, shared values, pin ownership/readiness and generic Smart Pin/pad registers |
| P2 Signals | Frequency, PWM, servo signals, pulses, timing, counters, logic routing and filters |
| P2 Serial | UART, synchronous serial, word size, polarity and bit order |
| P2 Analog | ADC/DAC configuration, dither, level input, scaling and single-pin scope mode |
| P2 Capture | SINC streams, buffered scope and existing capture/record controls |

The default project has one copy of each library. Individual files are under
**Libraries → P2**; importing one loads only that library and its P2 Core
dependency. Advanced blocks remain advanced. This organization does not add
new modes or claim new physical validation of analog, USB or external hardware.

The version-0.11 packages are generated from the unchanged compatibility source
`boards/propeller2/integration/P2_Hardware.ubl`. All 79 function definitions and
all block selectors/specifications are retained. Old `.ubp` projects continue
to load. Their ordinary P2 Hardware library is reorganized by moving its own
function/specification objects, not by replacing them with current definitions.
Existing code, custom functions and the code manager's assigned function IDs
remain intact; the organizer does not contact the board.

Stateful/implementation libraries or a project already mixing old and new P2
layouts are preserved conservatively. No extra target libraries are added to
such a project automatically. Saved subsets of the five libraries are also
retained. **Load target blocks** remains an explicit refresh from the current
package. Export valuable customized libraries before replacing their definitions.

The legacy compatibility file remains available in Git and is still used by
the historical hardware fixtures. The standard palette does not load it alongside
the five focused libraries. The native extension and VM protocol are unchanged.

The [grouping acceptance record](../evidence/2026-11-04/propeller2/grouped-library.json)
includes actual browser startup, independent library loading and legacy-code
equivalence. Its focused hardware regression executes the grouped bytecode on
the installed extension-8 P2 using P0–P1 and P2–P3, including worker-cog and GC
checks, without firmware loading or a hardware reset. Other modes retain their
previous documented validation limits.
