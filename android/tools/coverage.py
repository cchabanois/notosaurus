"""The Android unit tests' coverage, per source file, from JaCoCo's report
(./gradlew createDebugUnitTestCoverageReport): lines run by the tests, the least
covered first; the total last. Markdown, for the CI's summary or a terminal.

    python3 tools/coverage.py [app/build/reports/coverage/test/debug/report.xml]
"""

import sys
import xml.etree.ElementTree as ET

REPORT = "app/build/reports/coverage/test/debug/report.xml"


def lines(element) -> tuple[int, int]:
    """(covered, missed) lines of a JaCoCo element."""
    for counter in element.findall("counter"):
        if counter.get("type") == "LINE":
            return int(counter.get("covered")), int(counter.get("missed"))
    return 0, 0


def main(path: str) -> None:
    root = ET.parse(path).getroot()
    files = []
    for package in root.findall("package"):
        for source in package.findall("sourcefile"):
            covered, missed = lines(source)
            if covered + missed:
                files.append((covered / (covered + missed), source.get("name"), covered, missed))
    print("| File | Lines | Covered |\n|---|---:|---:|")
    for share, name, covered, missed in sorted(files):
        print(f"| {name} | {covered + missed} | {share:.0%} |")
    covered, missed = lines(root)
    print(f"| **Total** | {covered + missed} | **{covered / (covered + missed):.0%}** |")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else REPORT)
