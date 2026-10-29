You draw an electric circuit in Typst with zap 0.6. Answer the Typst only, exactly so:
{example}
- no import (zap's components are given); each component between two points, the loop closed by `wire`s: `battery`, `vsource` (a generator), `resistor`, `lamp`, `switch` (open, its contacts drawn; `closed: true` closed), `led`, `diode`, `capacitor`, `isource`; `node("n", (3, 0))` a junction; meters as the description names them, with labels;
- a name per component (`"r1"`), a label as the description writes it; in parallel: two branches between the same two points.
