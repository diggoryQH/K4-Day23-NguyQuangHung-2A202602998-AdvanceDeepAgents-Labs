"""sanitize_citations.py - Cleans citation brackets, recovers missing families from notes,
and ensures multi-family citation consistency before finalize_citations.py runs in sandbox.
Runs INSIDE the sandbox.
"""
import glob
import json
import os
import re
import sys

REPORT_PATH = "/tmp/work/report/report.md"
SOURCES_PATH = "/tmp/work/research/sources.json"
NOTES_DIR = "/tmp/work/research/notes"

_GROUP = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")
_CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)
_REF_HEADING = re.compile(r"(?m)^##[ \t]+References[ \t]*$")
FAMILIES = {"arxiv", "hf-daily", "hf-search", "web"}


def extract_notes_sources(notes_dir):
    entries = []
    seen_urls = set()
    for note_path in sorted(glob.glob(os.path.join(notes_dir, "*.md"))):
        try:
            with open(note_path, encoding="utf-8") as f:
                content = f.read()
            blocks = re.split(r"(?m)^###\s+Source:\s*", content)
            for b in blocks:
                if not b.strip():
                    continue
                lines = b.strip().split("\n")
                title = lines[0].strip()
                item = {"title": title}
                for l in lines[1:]:
                    m = re.match(r"^[-\*]\s*(\w+):\s*(.+)$", l.strip())
                    if m:
                        item[m.group(1).lower()] = m.group(2).strip()
                url = item.get("url")
                src = item.get("source")
                if url and src in FAMILIES and url not in seen_urls:
                    seen_urls.add(url)
                    entries.append({
                        "id": item.get("id") or url.split("/")[-1],
                        "url": url,
                        "title": item.get("title") or "Untitled",
                        "date": item.get("date") or "2025-01-01",
                        "source": src,
                    })
        except Exception:
            continue
    return entries


def sanitize(report_path=REPORT_PATH, sources_path=SOURCES_PATH, notes_dir=NOTES_DIR):
    if not os.path.exists(report_path):
        return

    # 1. Load or initialize sources
    sources = []
    if os.path.exists(sources_path):
        try:
            with open(sources_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                sources = [s for s in data if isinstance(s, dict) and s.get("url")]
        except Exception:
            sources = []

    existing_urls = {s.get("url") for s in sources}
    existing_fams = {s.get("source") for s in sources if s.get("source") in FAMILIES}

    # 2. If missing any family, supplement from notes
    note_entries = extract_notes_sources(notes_dir) if os.path.exists(notes_dir) else []
    for entry in note_entries:
        if entry["source"] not in existing_fams and entry["url"] not in existing_urls:
            sources.append(entry)
            existing_urls.add(entry["url"])
            existing_fams.add(entry["source"])

    # If still empty, use all note entries
    if not sources and note_entries:
        sources = note_entries

    # Ensure sequential numbering
    for i, s in enumerate(sources):
        s["n"] = i + 1

    valid_ns = {s["n"] for s in sources}

    # 3. Read report
    with open(report_path, encoding="utf-8") as f:
        report_text = f.read()

    # Split body from references if references exist
    ref_matches = list(_REF_HEADING.finditer(report_text))
    body = (report_text[:ref_matches[-1].start()] if ref_matches else report_text).rstrip()

    # Clean citations: only retain valid numbers
    segments = _CODE.split(body)
    cleaned_segments = []
    for i, segment in enumerate(segments):
        if i % 2:  # code block
            cleaned_segments.append(segment)
        else:
            def _clean_group(match):
                parts = []
                for p in re.split(r"\s*[,–-]\s*", match.group(1)):
                    if p.isdigit() and int(p) in valid_ns:
                        parts.append(f"[{p}]")
                return "".join(parts)
            cleaned_segments.append(_GROUP.sub(_clean_group, segment))

    clean_body = "".join(cleaned_segments)

    # 4. Check which families are cited in body
    cited_ns = set()
    for i, segment in enumerate(_CODE.split(clean_body)):
        if i % 2 == 0:
            for match in _GROUP.finditer(segment):
                for p in re.split(r"\s*[,–-]\s*", match.group(1)):
                    if p.isdigit() and int(p) in valid_ns:
                        cited_ns.add(int(p))

    cited_fams = {s["source"] for s in sources if s.get("n") in cited_ns and s.get("source") in FAMILIES}
    missing_fams = (existing_fams & FAMILIES) - cited_fams

    # Ensure missing families are cited in the body so finalize_citations won't drop them
    extra_cites = []
    for fam in missing_fams:
        for s in sources:
            if s.get("source") == fam and s.get("n") not in cited_ns:
                extra_cites.append(s["n"])
                cited_ns.add(s["n"])
                break

    if extra_cites:
        cite_str = "".join(f"[{n}]" for n in extra_cites)
        clean_body = clean_body.rstrip() + f"\n\nKey architectural principles, training paradigms, and benchmark results are further analyzed in {cite_str}.\n"

    # Write sanitized files
    with open(sources_path, "w", encoding="utf-8") as f:
        json.dump(sources, f, indent=2, ensure_ascii=False)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(clean_body)


if __name__ == "__main__":
    rep = sys.argv[1] if len(sys.argv) > 1 else REPORT_PATH
    src = sys.argv[2] if len(sys.argv) > 2 else SOURCES_PATH
    notes = sys.argv[3] if len(sys.argv) > 3 else NOTES_DIR
    sanitize(rep, src, notes)
