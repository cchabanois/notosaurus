You draw a clock in Typst with the clock function given (cetz): its hands are placed by the time. Answer the Typst only, exactly so:
{example}
- the time the description gives, `clock(hour, minute)`: the hour a whole number from 0 to 23 (as the description says it: `15` or `3`, the face is the same), the minute from 0 to 59 ("half past ten": `clock(10, 30)`, "a quarter to nine": `clock(8, 45)`); never an angle, never a hand drawn yourself;
- `numbers: false` only when the description says the face has no numbers; `minutes: true` when it asks for the minutes written around the face (5, 10… 55); `hour-color: red`, `minute-color: blue` only when it gives the hands' colours.
