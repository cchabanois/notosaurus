You draw a Scratch script in Typst with the scratch function given: each block written as a line of text, drawn by it as Scratch draws it (its shape, its colour, its width). Answer the Typst only, exactly so:
{example}
- `language:` the language the lesson is written in (`"fr"`, `"en"`, `"de"`, `"es"`, `"it"`, `"pt"`), and each block written in the words Scratch shows in that language, exactly, in the description's order: a block Scratch doesn't have is refused;
- one block per line; a value in a round slot `(100)`, a text `[Bonjour]`, a variable or a list chosen in a menu `[score v]`, a condition `<(réponse) > (12)>`; the blocks inside a loop or a condition (`répéter`, `si … alors`, `sinon`) indented under it and closed by `fin` (`end` in any language); scripts apart separated by an empty line;
- a block of the lesson's own: defined by Scratch's define block (`définir carré (côté)`) followed by its blocks, and used by `call` then its name and its values (`call carré (50)`); its parameter a round slot `(côté)` where it is used;
- only the blocks the description gives, in its order, its values as it writes them; never a block, a value or a comment of your own, never a colour, a size or a position: the blocks are measured and drawn by the function;
- a script that is not Scratch (a flowchart, an algorithm in pseudo-code, Python) is not drawn with it.
