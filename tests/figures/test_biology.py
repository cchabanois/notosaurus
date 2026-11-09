"""The sequence and phylogeny families (our sequences and phylogeny functions)."""

import pytest

from notosaurus_core import figures_typst


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
