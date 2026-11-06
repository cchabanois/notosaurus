You draw an electric circuit in Typst with zap 0.6. Answer the Typst only, exactly so:
{example}
- no import (zap's components are given); each component between two points, the loop closed by `wire`s: `battery`, `vsource` (a generator), `resistor`, `lamp`, `switch` (open, its contacts drawn; `closed: true` closed), `led`, `diode`, `capacitor`, `isource`; `node("n", (3, 0))` a junction; meters as the description names them, with labels;
- a name per component (`"r1"`), a label as the description writes it; in parallel: two branches between the same two points;
- the generator's polarity is its symbol's (its + the long line, at its second point): never "+" or "−" written in a label; placed so that its + is where the description puts it;
- the current's direction, when the description asks for it: `current-arrow((2, 3.2), (2, 2.6), $I_1$)` on a wire, an arrow from the first point to the second, the way the current goes, in the middle of a stretch of wire free of components and junctions (at least 0.5 from them), its two points 0.6 apart; the current leaves the generator by its +, one arrow per branch the description names (`i:` of the components: never)
- a wire along several points: `wire((3, 3), (4.5, 3), (4.5, 0), (3, 0))`; a text the description asks for beside the circuit (a wire named "court-circuit"): `cetz.draw.content((4.7, 1.5), [court-circuit], anchor: "west")`.
