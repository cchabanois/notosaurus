"""The sequence and phylogeny families (our sequences and phylogeny functions)."""

import re

import pytest

from notosaurus_core import figures, figures_typst


def test_sequences_differences_are_computed_and_framed():
    """Aligned sequences: the letters where variants of the same kind differ are framed,
    computed from the letters, never placed; a strand and its transcript or its complement
    (different everywhere) are no variants, never framed; a protein under its codons."""
    seq = lambda rows, extra="": figures_typst.compile_svg("sequence", f"#sequences({extra}rows: ({rows}))")  # noqa: E731
    alleles = '("1", "ATG GCA TTC"), ("2", "ATG GCG TTC")'
    assert seq(alleles) != seq(alleles, "framed: false, ")
    assert seq(alleles) != seq('("1", "ATG GCA TTC"), ("2", "ATG GGA TTC")')  # elsewhere, framed elsewhere
    same = '("1", "ATG GCA TTC"), ("2", "ATG GCA TTC")'
    assert seq(same) == seq(same, "framed: false, ")
    strand = '("ADN", "TAC GGA CTT"), '
    for unlike in (strand + '("ARNm", "AUG CCU GAA")', strand + '("Brin", "ATG CCT GAA")'):
        assert seq(unlike) == seq(unlike, "framed: false, ")
    codons = '("ARNm", "AUG CCU GAA"), ("Protéine", {})'
    assert seq(codons.format('"Met-Pro-Glu"')) == seq(codons.format('("Met", "Pro", "Glu")'))
    with pytest.raises(figures_typst.Unusable, match="aligned"):
        seq('("1", "ATG GCA TTC"), ("2", "ATG GA TTC")')


def test_sequences_letters_or_amino_acids_whatever_their_case():
    """A sequence's letters and its amino acids told apart by their structure, never by their
    case: DNA in lowercase is letters (its difference framed as in capitals), an amino-acid
    chain in capitals is words (one per codon, as written in mixed case); every form the rule
    gives still drawn as before."""
    seq = lambda rows, extra="": figures_typst.compile_svg("sequence", f"#sequences({extra}rows: ({rows}))")  # noqa: E731
    # one letter per column, aligned with the same letters written without spaces (as words,
    # "atg gca ttc" was three to its one: refused as not aligned)
    lower = '("1", "atg gca ttc"), ("2", "atggcgttc")'
    assert seq(lower) != seq(lower, "framed: false, ")
    codons = '("ARNm", "AUG CCU GAA"), ("Protéine", {})'
    mixed = seq(codons.format('"Met-Pro-Glu"'))
    for written in ('"MET-PRO-GLU"', '"Met Pro Glu"', '"MET PRO GLU"', '("MET", "PRO", "GLU")'):
        assert seq(codons.format(written)) != seq(codons.format('"Met-Pro-Gln"'))  # compiles, one per codon
    assert mixed == seq(codons.format('("Met", "Pro", "Glu")'))
    caps = seq('("ARNm", "AUG CCU GAA"), ("Protéine", "MET-PRO-GLU")')
    assert caps == seq('("ARNm", "AUG CCU GAA"), ("Protéine", ("MET", "PRO", "GLU"))')
    # letters still: DNA with a gap, RNA, a protein in one letter each
    assert seq('("1", "ATG GCA TTC"), ("2", "ATG -CA TTC")') != seq(
        '("1", "ATG GCA TTC"), ("2", "ATG -CA TTC")', "framed: false, "
    )
    assert seq('("1", "AT-GCA"), ("2", "ATTGCA")', "group: 0, ").startswith("<svg")
    assert seq('("1", "MKVLLA"), ("2", "MKVLPA")', "group: 0, ") != seq(
        '("1", "MKVLLA"), ("2", "MKVLPA")', "group: 0, framed: false, "
    )


def test_a_sequences_asked_letter_is_not_shown():
    """A card asking which letter: written "?", whatever it was."""
    body = '#sequences(ask: (("2", 6),), rows: (("1", "ATG GCA TTC"), ("2", "ATG GC{} TTC")))'
    asked = figures_typst.compile_svg("sequence", body.format("G"))
    assert asked == figures_typst.compile_svg("sequence", body.format("T"))
    assert asked != figures_typst.compile_svg("sequence", body.format("G").replace('ask: (("2", 6),), ', ""))


def test_a_phylogenetic_tree_is_built_from_what_each_species_has():
    """The groups sharing a character are the tree's groups, computed: the order the
    characters are listed in changes nothing, a lone character written without its comma
    neither; characters whose groups overlap without nesting are refused (no tree has both),
    never drawn at a guess."""
    tree = '#phylogeny(species: (("Truite", ()), ("Grenouille", {}), ("Chat", {})))'
    ladder = figures_typst.compile_svg("phylogeny", tree.format('("membres",)', '("membres", "poils")'))
    assert ladder == figures_typst.compile_svg("phylogeny", tree.format('("membres")', '("poils", "membres")'))
    assert ladder != figures_typst.compile_svg("phylogeny", tree.format('("membres",)', '("membres",)'))
    overlapping = tree.format('("membres", "poils")', '("membres",)').replace("()", '("poils",)')
    with pytest.raises(figures_typst.Unusable, match="overlap without nesting"):
        figures_typst.compile_svg("phylogeny", overlapping)


def test_a_phylogenetic_trees_hidden_names_are_not_shown():
    """A card asking which species or which innovation: written "?", not its name."""
    tree = '#phylogeny({}species: (("Truite", ()), ("Grenouille", ("membres",)), ("Chat", ("membres", "poils"))))'
    bare = figures_typst.compile_svg("phylogeny", tree.format(""))
    for hidden in ('"poils"', '"Chat"'):
        body = tree.format(f"hidden: ({hidden},), ")
        asked = figures_typst.compile_svg("phylogeny", body)
        assert asked != bare
        assert asked == figures_typst.compile_svg("phylogeny", body.replace(hidden, '"x"'))


def _lines(body: str) -> int:
    return len(re.findall(r"<path", figures.clean(figures_typst.compile_svg("sequence", body))))


def test_two_strands_face_to_face_each_pair_joined():
    """A DNA's two strands face to face, each pair joined: written as two rows of `sequences`,
    its letters were aligned but no pair joined, no strand drawn (0 drawings in 3). `strands`
    computes the bottom strand from the top one, joins each pair, draws each backbone."""
    computed = figures_typst.compile_svg("sequence", '#strands(top: "A T G C C A")')
    assert computed == figures_typst.compile_svg("sequence", '#strands(top: "ATGCCA", bottom: "TACGGT")')

    def joined(top: str, bottom: str, extra: str = "") -> int:
        """The lines drawn between the strands and under the bottom one, its bases given."""
        gaps = "-" * len(top)
        with_ = _lines(f'#strands(top: "{top}", bottom: "{bottom}"{extra})')
        return with_ - _lines(f'#strands(top: "{top}", bottom: "{gaps}"{extra})')

    # a link a pair and a backbone under the bottom strand; a base not there yet joined to nothing
    assert joined("ATGCCA", "TACGGT") == 6 + 1
    assert joined("ATGCCA", "TAC---") == 3 + 1
    # the hydrogen bonds counted: two between A and T, three between G and C
    assert joined("ATAT", "TATA", ", bonds: true") == 8 + 1
    assert joined("GCGC", "CGCG", ", bonds: true") == 12 + 1
    # against an RNA, A pairs with U
    assert figures_typst.compile_svg("sequence", '#strands(top: "ATG", rna: true)') == figures_typst.compile_svg(
        "sequence", '#strands(top: "ATG", bottom: "UAC", rna: true)'
    )


def test_two_strands_asked_bases_are_not_shown():
    """A card asking which base: written "?", whatever it was (its answer never on the
    figure), on the strand named."""
    drawn = lambda body: figures_typst.compile_svg("sequence", f"#strands({body})")  # noqa: E731
    pair = 'top: "{}", ask: (("top", 2), ("bottom", 2))'
    assert drawn(pair.format("ATG")) == drawn(pair.format("AAG"))  # T–A or A–T: the same "?"s
    bottom = drawn('top: "ATG", ask: (("bottom", 2),)')
    assert bottom != drawn('top: "ATG"') and bottom != drawn('top: "ATG", ask: (("top", 2),)')
    named = 'top: "ATG", names: ("brin 1", "brin 2"), ask: (("{}", 2),)'
    assert drawn(named.format("brin 2")) == drawn(named.format("bottom"))


def test_two_strands_ends_written_when_asked():
    """`ends: true`: the strands' 5' and 3' ends written beside them."""
    drawn = lambda body: figures_typst.compile_svg("sequence", f"#strands({body})")  # noqa: E731
    assert drawn('top: "ATG", ends: true') != drawn('top: "ATG"')


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ('#strands(top: "ATG", bottom: "TAA")', "position 3: G faces A"),
        ('#strands(top: "ATGC", bottom: "TAC")', "as many bases"),
        ('#strands(top: "ATX")', "not X"),
        # a DNA strand being made written with U (a replication makes DNA)
        ('#strands(top: "TACGGA", bottom: "AUG---")', "U is an RNA's base"),
    ],
)
def test_two_strands_not_paired_refused_saying_where(body, said):
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("sequence", body)


VERTEBRATES = (
    '("Lamproie", ()), ("Truite", ("mâchoires",)), ("Grenouille", ("mâchoires", "membres")), '
    '("Lézard", ("mâchoires", "membres", "amnios")), ("Chat", ("mâchoires", "membres", "amnios", "poils"))'
)


def test_a_phylogenetic_trees_groups_outlined():
    """A group outlined in a colour, its name above (« the tetrapods outlined in green »): the
    AI wrote groups:, refused, and drew the tree without (0 in 2). Each group a frame around its
    part of the tree, in its colour, groups inside others within theirs."""
    bare = figures.clean(figures_typst.compile_svg("phylogeny", f"#phylogeny(species: ({VERTEBRATES}))"))
    one = figures.clean(
        figures_typst.compile_svg(
            "phylogeny",
            f'#phylogeny(species: ({VERTEBRATES}), groups: (("Tétrapodes", ("Grenouille", "Lézard", "Chat"), green),))',
        )
    )
    assert 'stroke="#2ecc40"' in one and 'stroke="#2ecc40"' not in bare  # green
    nested = figures.clean(
        figures_typst.compile_svg(
            "phylogeny",
            f'#phylogeny(species: ({VERTEBRATES}), groups: (("Amniotes", ("Lézard", "Chat"), red), '
            '("Tétrapodes", ("Grenouille", "Lézard", "Chat"), green)))',
        )
    )
    assert 'stroke="#ff4136"' in nested and 'stroke="#2ecc40"' in nested
    # a group without a colour given (none): outlined all the same
    grey = figures.clean(
        figures_typst.compile_svg(
            "phylogeny", f'#phylogeny(species: ({VERTEBRATES}), groups: (("Amniotes", ("Lézard", "Chat"), none),))'
        )
    )
    assert grey != bare and grey.count("<path") > bare.count("<path")
    # the same groups in any order: the same drawing
    assert nested == figures.clean(
        figures_typst.compile_svg(
            "phylogeny",
            f'#phylogeny(species: ({VERTEBRATES}), groups: (("Tétrapodes", ("Chat", "Lézard", "Grenouille"), green), '
            '("Amniotes", ("Lézard", "Chat"), red)))',
        )
    )


@pytest.mark.parametrize(
    ("groups", "said"),
    [
        # not a group of the tree: said, and which are
        ('(("X", ("Truite", "Chat"), red),)', r"Truite, Chat is no group of the tree.*\(Lézard, Chat\)"),
        ('(("X", ("Requin",), red),)', r'"Requin" is none of the species'),
        ('(("X", ("Lézard", "Chat"), "red"),)', r"groups: each \(name, \(species…\), colour\)"),
    ],
)
def test_a_phylogenetic_trees_group_refused_saying_why(groups, said):
    """A group that isn't one of the tree's, a species not in it, a group written otherwise:
    refused saying why (Typst's message given back to the AI)."""
    with pytest.raises(figures_typst.Unusable, match=said):
        figures_typst.compile_svg("phylogeny", f"#phylogeny(species: ({VERTEBRATES}), groups: {groups})")
