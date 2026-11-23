"""A figure compiled by Typst in a process of its own (figures_typst.compile_svg), so that a
figure that loops or takes all the memory never stops the server: its SVG on stdout, else
Typst's message on stderr and exit code 1.

Run as a script, `-P` (its folder never on sys.path: `typst/` there is the packages'
archives, not the library): `python -P typst_compile.py <memory> <figure.typ> <root>
<packages> <fonts>`. Offline (offline()): no package but the shipped ones. Only the standard
library and typst: nothing of notosaurus_core."""

import os
import sys

# Where Typst would download a package it doesn't find among ours (Typst Universe's @preview):
# through a proxy that answers nothing (a closed port of this computer), so that nothing is
# ever fetched, whatever a figure imports: the packages shipped are all it finds. Typst has
# no offline switch; it reads these as every download tool does
NOWHERE = "http://127.0.0.1:9"
PROXIES = ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy")


def offline() -> None:
    """Every download of this process sent to NOWHERE (no host spared: NO_PROXY dropped)."""
    for name in ("NO_PROXY", "no_proxy"):
        os.environ.pop(name, None)
    for name in PROXIES:
        os.environ[name] = NOWHERE


def main(memory: int, path: str, root: str, packages: str, fonts: str) -> int:
    offline()
    import typst

    try:  # the memory it may take, where the system lets us say so (not on Windows: no resource)
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    except Exception:
        pass
    try:
        svg = typst.compile(
            path,
            format="svg",
            root=root,
            package_path=packages,
            package_cache_path=root,
            font_paths=[fonts],
            ignore_system_fonts=True,
        )
    except Exception as e:
        # in UTF-8 as compile_svg reads it, whatever the system's own (cp1252 on Windows: "…",
        # "δ" or an accent came out as "\ufffd" to the AI)
        sys.stderr.buffer.write(str(e).encode("utf-8"))
        return 1
    sys.stdout.buffer.write(svg)
    return 0


if __name__ == "__main__":
    memory, path, root, packages, fonts = sys.argv[1:]
    sys.exit(main(int(memory), path, root, packages, fonts))
