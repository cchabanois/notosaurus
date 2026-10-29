You draw a molecule's formula in Typst with alchemist 0.2. Answer the Typst only, exactly so:
{example}
- `fragment("CH_3")` an atom or group (subscripts with `_`); bonds between them: `single()`, `double()`, `triple()`, each with `angle: 1` (×45°, from the horizontal: 0 right, 2 up, -2 down) or `absolute: 30deg`; `branch({ ... })` a side chain from the last fragment; `cycle(6, { single(); double(); ... })` a ring;
- a developed formula: every atom and bond; semi-developed: the groups, as the description says.
