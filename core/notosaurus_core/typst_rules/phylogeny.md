You draw a phylogenetic tree in Typst with the phylogeny function given (cetz): the tree is built from what each species has, its branches and innovations placed by it. Answer the Typst only, exactly so:
{example}
- every species the description names, each with every character (innovation) it has among those the description names, `("Name", ("character", …))`, `()` for none; never a branch, a node or a position given yourself: the groups sharing a character are the tree's groups;
- a character the description puts on a branch is had by every species above that branch; one it puts on a single species' branch, by that species alone;
- `hidden: ("…",)` the species or characters a card asks for (written "?"), when the description says so; `root: [...]` only when the description names the root (a common ancestor).
