"""check_citations.py - STUDENT IMPLEMENTS `check`.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import re
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"

_GROUP = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")   # [3]  [1, 2]  [1-3]  [2-3]; not [3](link)
_CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
_REF_HEADING = re.compile(r"(?m)^##[ \t]+References[ \t]*$")


def _group_numbers(group):
    numbers = []
    for part in re.split(r"\s*,\s*", group):
        span = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if span:
            a, b = int(span.group(1)), int(span.group(2))
            numbers.extend(range(a, b + 1) if 0 <= b - a <= 200 else [a, b])
        else:
            numbers.append(int(part))
    return numbers


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK)."""
    problems = []

    # 1. Check sources list
    if not isinstance(sources, list) or len(sources) == 0:
        return ["no sources in sources.json"]

    source_by_n = {}
    seen_urls = set()
    for entry in sources:
        if not isinstance(entry, dict):
            problems.append(f"source entry {entry!r} is not an object")
            continue

        n = entry.get("n")
        if not isinstance(n, int):
            problems.append(f"source n={n!r} is not an integer")
        elif n in source_by_n:
            problems.append(f"duplicate source number [{n}] in sources.json")
        else:
            source_by_n[n] = entry

        url = entry.get("url")
        if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            problems.append(f"source n={n!r} has invalid URL: {url!r}")
        elif url in seen_urls:
            problems.append(f"duplicate URL in sources.json: {url}")
        else:
            seen_urls.add(url)

    # 2. Split report_text at the heading "## References"
    matches = list(_REF_HEADING.finditer(report_text))
    if not matches:
        problems.append("missing '## References' heading")
        body = report_text
        ref_section = ""
    else:
        body = report_text[:matches[-1].start()]
        ref_section = report_text[matches[-1].end():]

    # 3. Extract citations [n] from BODY only (excluding code blocks and markdown links)
    cited = set()
    segments = _CODE.split(body)
    for i, segment in enumerate(segments):
        if i % 2:  # skip code segments
            continue
        for match in _GROUP.finditer(segment):
            for n in _group_numbers(match.group(1)):
                cited.add(n)

    # 4. Cross-check body citations with sources
    for c in sorted(cited):
        if c not in source_by_n:
            problems.append(f"[{c}] cited in body but missing from sources.json")

    for n in sorted(source_by_n.keys()):
        if n not in cited:
            problems.append(f"source [{n}] never cited in body")

    # 5. Check the References section
    if matches:
        ref_lines = {}
        for line in ref_section.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            line_match = re.match(r"^\[(\d+)\]\s*(.*)$", line_str)
            if not line_match:
                problems.append(f"unexpected line in References section: {line_str}")
                continue
            n = int(line_match.group(1))
            if n in ref_lines:
                problems.append(f"duplicate reference line for [{n}] in References")
            else:
                ref_lines[n] = line_str

            if n not in source_by_n:
                problems.append(f"reference [{n}] in References is not in sources.json")
            else:
                raw_urls = re.findall(r"https?://[^\s<>]+", line_str)
                urls = [u.rstrip(".,;:)]>") for u in raw_urls]
                if len(urls) == 0:
                    problems.append(f"reference line [{n}] has no URL")
                elif len(urls) > 1:
                    problems.append(f"reference line [{n}] bundles multiple URLs: {urls}")
                else:
                    expected_url = source_by_n[n].get("url")
                    if urls[0] != expected_url:
                        problems.append(
                            f"reference line [{n}] URL '{urls[0]}' does not match sources.json URL '{expected_url}'"
                        )

        for n in sorted(source_by_n.keys()):
            if n not in ref_lines:
                problems.append(f"source [{n}] missing reference line in References")

    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
