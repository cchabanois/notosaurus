"""Generated inputs (Hypothesis) against the two most exposed filters: the Host check
(app/hosts.py: DNS rebinding) and the SVG cleaner (figures.clean: the AI's figures,
shown in the page and in Anki)."""

import ipaddress
import os
import re
from contextlib import contextmanager
from unittest import mock
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from hypothesis import given, settings
from hypothesis import strategies as st

from app.hosts import HOST_HEADER, allowed
from notosaurus_core import figures

fast = settings(max_examples=200, deadline=None)  # the whole file: about a second

# --- The Host check ---------------------------------------------------------------

PUBLIC = "pc.example.ts.net"  # NOTOSAURUS_PUBLIC_URL's name (Docker, a proxy)


@contextmanager
def public_url(url=f"https://{PUBLIC}/"):
    with mock.patch.dict(os.environ, {"NOTOSAURUS_PUBLIC_URL": url}):
        yield


def is_ip(name: str) -> bool:
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


ports = st.one_of(st.just(""), st.integers(1, 65535).map(lambda p: f":{p}"))
bad_ports = st.one_of(
    st.sampled_from([":", ":0", ":00000", ": 80", ":80 ", ":-1", ":+80", ":8o", "::80", ":80:80"]),
    st.integers(65536, 99999).map(lambda p: f":{p}"),
    st.integers(10**5, 10**9).map(lambda p: f":{p}"),
)
labels = st.from_regex(r"[a-z0-9]([a-z0-9-]{0,15}[a-z0-9])?", fullmatch=True)
dns_names = (
    st.lists(labels, min_size=1, max_size=4)
    .map(".".join)
    .filter(lambda name: not is_ip(name) and name not in ("localhost", PUBLIC))
)
# Names close to the allowed ones: a rebinding site may pick any
lookalikes = st.one_of(
    st.tuples(labels, st.sampled_from(["localhost", PUBLIC])).map(lambda t: f"{t[0]}.{t[1]}"),
    st.tuples(st.sampled_from(["localhost", PUBLIC]), labels).map(lambda t: f"{t[0]}.{t[1]}"),
    st.tuples(labels, st.sampled_from(["localhost", PUBLIC])).map(lambda t: f"{t[0]}-{t[1]}"),
    st.sampled_from(["localhost.", f"{PUBLIC}.", "127.0.0.1.nip.io", "0x7f000001", "2130706433", "127.1"]),
)


def ip_host(ip) -> str:
    return f"[{ip}]" if ip.version == 6 else str(ip)


good_hosts = st.one_of(
    st.ip_addresses().map(ip_host),
    st.sampled_from(["localhost", "LocalHost", PUBLIC, PUBLIC.upper()]),
)


@fast
@given(ip=st.ip_addresses(), port=ports)
def test_any_ip_address_passes(ip, port):
    with public_url(""):
        assert allowed(ip_host(ip) + port)


@fast
@given(name=st.sampled_from(["localhost", "LOCALHOST", PUBLIC]), port=ports)
def test_localhost_and_the_public_name_pass(name, port):
    with public_url():
        assert allowed(name + port)


@fast
@given(name=st.one_of(dns_names, lookalikes), port=ports)
def test_any_other_name_never_passes(name, port):
    with public_url():
        assert not allowed(name + port)
    with public_url(""):  # no public name: not even it
        assert not allowed(PUBLIC + port)


@fast
@given(host=good_hosts, port=bad_ports)
def test_a_bad_port_never_passes(host, port):
    with public_url():
        assert not allowed(host + port)


@fast
@given(
    host=good_hosts,
    port=ports,
    junk=st.sampled_from(["@", " ", "\t", "/", "\\", "?", "#", "%", "\x00", "\n", ",", ";", "_"]),
    where=st.integers(0, 60),
    user=st.one_of(dns_names, st.just("")),
)
def test_odd_characters_never_pass(host, port, junk, where, user):
    full = host + port
    with public_url():
        at = where % (len(full) + 1)
        assert not allowed(full[:at] + junk + full[at:])
        assert not allowed(f"{user}@{full}")  # user info: "localhost@evil.example" is evil.example's
        assert not allowed(f"{full}@{user or 'evil.example'}")


@fast
@given(
    host=st.one_of(
        st.text(max_size=60),
        st.from_regex(HOST_HEADER, fullmatch=True),  # shaped like a host: past the first check
        st.from_regex(r"\[[0-9a-f:.]{0,12}\](:\d{1,5})?", fullmatch=True),  # "[1.2.3.4]": no IPv6 in brackets
    )
)
def test_any_header_passes_only_as_an_address_localhost_or_the_public_name(host):
    """Any Host header at all: never an exception (a 500 in the middleware), and when it
    passes it is an IP address, localhost or the public name, with a valid port."""
    with public_url():
        if not allowed(host):
            return
    match = re.fullmatch(r"\[(?P<v6>[^\]]+)\](:(?P<p6>\d+))?|(?P<name>[^:\[\]]+)(:(?P<port>\d+))?", host)
    assert match, host
    name = (match["v6"] or match["name"]).lower()
    port = match["p6"] or match["port"]
    assert (
        (match["v6"] and ipaddress.ip_address(name).version == 6)
        or name in ("localhost", PUBLIC.lower())
        or (is_ip(name) and ipaddress.ip_address(name).version == 4)
    )
    assert port is None or 0 < int(port) < 65536


# --- The SVG cleaner ----------------------------------------------------------------

TAGS = [
    *sorted(figures.ELEMENTS),
    "script", "SCRIPT", "a", "image", "foreignObject", "use", "animate", "set", "animateTransform", "iframe",
    "style", "feImage", "html:script", "xlink:a",
]  # fmt: skip
ATTRIBUTES = [
    *sorted(figures.GEOMETRY | figures.PRESENTATION),
    "onclick", "onload", "ONLOAD", "onmouseover", "onbegin", "href", "xlink:href", "src", "style", "begin",
    "attributeName", "values", "to", "from", "xml:base", "requiredExtensions", "formaction",
]  # fmt: skip
VALUES = [
    "javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:x", "java\tscript:x", "url(http://evil.test/x)",
    "url( http://evil.test )", "url('http://evil.test')", 'url("//evil.test")', "url(#hatch)", "url( #a.b-c )",
    "url(#a) url(http://evil.test)", "expression(alert(1))", "rotate(30 1 2) translate(1,2)",
    "rotate(30) url(http://evil.test)", "red", "none", "#fff", "1e309", "NaN", "https://evil.test/x.png",
    "data:image/svg+xml;base64,PHN2Zz4=", "&#106;avascript:x", "fill:url(http://evil.test)", "fill:red;stroke:url(#a)",
    "stroke:red;background:url(http://evil.test)", "fill:url(#a)", "\\75rl(http://evil.test)",
]  # fmt: skip
VIEWBOXES = ["0 0 400 300", "0,0,200,100", "-10 -10 420 320", "0 0 NaN 1", "a b c d", "0 0 0 1", ""]

xml_text = st.text(st.characters(exclude_categories=["Cs", "Cc"]) | st.sampled_from("\t\n"), max_size=30)
values = st.one_of(st.sampled_from(VALUES), xml_text)
texts = xml_text


def element(depth: int):
    children = st.lists(element(depth - 1), max_size=3) if depth else st.just([])
    return st.builds(
        lambda tag, attributes, text, kids: (
            f"<{tag}{''.join(f' {name}={quoteattr(value)}' for name, value in attributes)}>"
            f"{escape(text)}{''.join(kids)}</{tag}>"
        ),
        st.sampled_from(TAGS),
        st.lists(st.tuples(st.sampled_from(ATTRIBUTES), values), max_size=4, unique_by=lambda a: a[0]),
        texts,
        children,
    )


svg_documents = st.builds(
    lambda namespaced, viewbox, attributes, kids: (
        "<svg"
        + (' xmlns="http://www.w3.org/2000/svg"' if namespaced else "")
        + ' xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:html="http://www.w3.org/1999/xhtml"'
        + (f" viewBox={quoteattr(viewbox)}" if viewbox else "")
        + "".join(f" {name}={quoteattr(value)}" for name, value in attributes)
        + ">"
        + "".join(kids)
        + "</svg>"
    ),
    st.booleans(),
    st.one_of(st.just("0 0 400 300"), st.sampled_from(VIEWBOXES)),  # mostly a good one: the rest gets cleaned
    st.lists(st.tuples(st.sampled_from(ATTRIBUTES), values), max_size=3, unique_by=lambda a: a[0]),
    st.lists(element(2), max_size=4),
)
# (the spaces inside the lookahead: "\s*" before it could give one back and match "url( #a )")
EXTERNAL = re.compile(r"url\((?!\s*#[\w.-]+\s*\))", re.IGNORECASE)  # url(…) to anything but a part of the figure


def cleaned(svg: str) -> str | None:
    try:
        return figures.clean(svg)
    except figures.FigureError:
        return None  # refused: nothing shown


def assert_harmless(svg: str) -> None:
    assert "<script" not in svg.lower()
    for node in ElementTree.fromstring(svg).iter():
        assert node.tag.rsplit("}", 1)[-1] in figures.ELEMENTS, node.tag
        for name, value in node.attrib.items():
            local = name.rsplit("}", 1)[-1]
            assert not local.lower().startswith("on"), (local, value)
            assert local not in ("href", "src"), (local, value)
            assert "javascript" not in value.lower(), (local, value)
            assert not EXTERNAL.search(value), (local, value)


@fast
@given(svg=svg_documents)
def test_a_cleaned_figure_runs_and_loads_nothing(svg):
    out = cleaned(svg)
    if out is not None:
        assert_harmless(out)
        assert figures.clean(out) == out  # cleaning again changes nothing


@fast
@given(svg=st.one_of(st.text(max_size=200), st.text(alphabet="<>/=\"' svgonclickhref:#()url", max_size=200)))
def test_any_text_is_refused_or_harmless(svg):
    """Not even an SVG: refused (figure.invalid), never another error."""
    out = cleaned(svg)
    if out is not None:
        assert_harmless(out)
        assert figures.clean(out) == out
