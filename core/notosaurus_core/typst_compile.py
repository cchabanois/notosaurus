"""A figure compiled by Typst in a process of its own (figures_typst.compile_svg), so that a
figure that loops or takes all the memory never stops the server: its SVG on stdout, else
Typst's message on stderr and exit code 1.

Run as a script, `-P` (its folder never on sys.path: `typst/` there is the packages'
archives, not the library): `python -P typst_compile.py <memory> <figure.typ> <root>
<packages> <fonts>`. Only the standard library and typst: nothing of notosaurus_core."""

import sys


def main(memory: int, path: str, root: str, packages: str, fonts: str) -> int:
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
        sys.stderr.write(str(e))
        return 1
    sys.stdout.buffer.write(svg)
    return 0


if __name__ == "__main__":
    memory, path, root, packages, fonts = sys.argv[1:]
    sys.exit(main(int(memory), path, root, packages, fonts))
