"""research.py - STUDENT IMPLEMENTS.  The main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import sys
import time  # noqa: F401
from collections import Counter  # noqa: F401
from pathlib import Path

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent  # noqa: F401
from model import make_model  # noqa: F401
from sandbox import download, open_sandbox, upload  # noqa: F401

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator
SANITIZER_SOURCE = ROOT / "sanitize_citations.py"
SANITIZER_PATH = f"{WORKDIR}/research/sanitize_citations.py"


def slugify(topic):
    """Turn a topic into a safe file name: lower case, runs of non-word characters become one "-", max 60 chars,
    never empty (fall back to "topic"). The topic is user input: "../../x" must not escape reports/."""
    if not topic or not str(topic).strip():
        return "topic"
    clean = str(topic).strip().lower()
    clean = re.sub(r"[^\w]+", "-", clean)
    clean = clean.strip("-")
    if not clean:
        return "topic"
    clean = clean[:60].rstrip("-")
    return clean or "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return (
        f"Please conduct a comprehensive deep literature survey on the topic: '{topic.strip()}'.\n\n"
        "MANDATORY MULTI-SOURCE RESEARCH WORKFLOW:\n"
        "1. Plan with write_todos and decompose the topic into at least 3 distinct sub-questions.\n"
        "2. Delegate research to researcher subagents using the task tool in parallel:\n"
        "   - Task 1: Search arXiv using arxiv_search, label entries as source: 'arxiv', save to /tmp/work/research/notes/01-arxiv.md.\n"
        "   - Task 2: Search trending papers using hf_daily_papers, label entries as source: 'hf-daily', save to /tmp/work/research/notes/02-hf-daily.md.\n"
        "   - Task 3: Search topic papers using hf_search_papers, label entries as source: 'hf-search', save to /tmp/work/research/notes/03-hf-search.md.\n"
        "3. Review notes and confirm all 3 families (arxiv, hf-daily, and hf-search) exist.\n"
        "4. Compile /tmp/work/research/sources.json with papers from ALL 3 families (arxiv, hf-daily, hf-search), numbered sequentially 1..K.\n"
        "5. Write the body of /tmp/work/report/report.md following REPORT_TEMPLATE.md (do NOT write ## References).\n"
        "   CRITICAL: You MUST cite at least one arxiv paper, at least one hf-daily paper, and at least one hf-search paper in the text!\n"
        "   ONLY cite numbers 1..K that actually exist in sources.json.\n"
        "6. Execute /tmp/work/research/finalize_citations.py until it outputs FINALIZED.\n"
        "7. Execute /tmp/work/research/check_citations.py until it outputs OK.\n"
        "8. Spot-check citations with citation-checker."
    )


def summarize(messages, elapsed, model_name):
    """Return {"model", "elapsed_s", "subagent_calls", "tool_calls": {name: count}, "tokens": {"input", "output"}}."""
    tool_counts = Counter()
    input_tokens = 0
    output_tokens = 0

    for msg in messages:
        # 1. Count tool calls on lead messages
        tool_calls = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_calls = msg.tool_calls
        elif isinstance(msg, dict) and "tool_calls" in msg:
            tool_calls = msg.get("tool_calls") or []

        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                tool_counts[name] += 1

        # 2. Count tokens from usage_metadata or response_metadata
        usage = None
        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            usage = msg.usage_metadata
        elif isinstance(msg, dict) and "usage_metadata" in msg:
            usage = msg.get("usage_metadata")

        if usage:
            input_tokens += int(usage.get("input_tokens", 0) if isinstance(usage, dict) else getattr(usage, "input_tokens", 0))
            output_tokens += int(usage.get("output_tokens", 0) if isinstance(usage, dict) else getattr(usage, "output_tokens", 0))
        elif hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
            tu = msg.response_metadata.get("token_usage")
            if isinstance(tu, dict):
                input_tokens += int(tu.get("prompt_tokens", 0))
                output_tokens += int(tu.get("completion_tokens", 0))

    return {
        "model": str(model_name),
        "elapsed_s": round(float(elapsed), 1),
        "subagent_calls": int(tool_counts.get("task", 0)),
        "tool_calls": dict(tool_counts),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
        },
    }


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path."""
    from check_citations import check

    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report_bytes = files.get(REPORT_PATH)
    sources_bytes = files.get(SOURCES_PATH)

    if not report_bytes or not report_bytes.strip():
        raise RuntimeError("Report is missing or empty in sandbox")
    if not sources_bytes or not sources_bytes.strip():
        raise RuntimeError("sources.json is missing or empty in sandbox")

    try:
        sources = json.loads(sources_bytes.decode("utf-8"))
        if not isinstance(sources, list) or len(sources) == 0:
            raise ValueError("sources.json must be a non-empty list")
    except Exception as exc:
        raise RuntimeError(f"sources.json is invalid JSON: {exc}") from exc

    report_text = report_bytes.decode("utf-8")
    problems = check(report_text, sources)
    if problems:
        raise RuntimeError(f"Citation verification failed on downloaded report: {problems}")

    meta = summarize(messages, elapsed, model_name)
    if meta["subagent_calls"] < 3:
        raise RuntimeError(f"Run produced only {meta['subagent_calls']} subagent calls (need >= 3)")

    families = sorted({
        s.get("source") for s in sources if isinstance(s, dict) and s.get("source")
    })
    valid_families = set(families) & {"arxiv", "hf-daily", "hf-search", "web"}
    if len(valid_families) < 3:
        raise RuntimeError(f"Run produced only {families} source families (need >= 3)")

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(topic)

    meta["topic"] = topic.strip()
    meta["n_sources"] = len(sources)
    meta["source_families"] = families

    report_path = reports_dir / f"{slug}.md"
    sources_path = reports_dir / f"{slug}.sources.json"
    meta_path = reports_dir / f"{slug}.meta.json"

    report_path.write_bytes(report_bytes)
    sources_path.write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    return report_path


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic)."""
    if not topic or not str(topic).strip():
        print("Usage: python research.py \"<topic>\"", file=sys.stderr)
        return 2

    topic_str = str(topic).strip()
    try:
        model = make_model()
    except Exception as exc:
        print(f"FAILED: cannot initialize model: {exc}", file=sys.stderr)
        return 1

    model_name = getattr(model, "model_name", None) or getattr(model, "model", None) or str(model)
    start = time.monotonic()

    try:
        with open_sandbox() as backend:
            backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
            upload(
                backend,
                {
                    VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(),
                    FINALIZER_PATH: FINALIZER_SOURCE.read_bytes(),
                    SANITIZER_PATH: SANITIZER_SOURCE.read_bytes(),
                },
            )
            agent = build_lead_agent(backend, model)
            result = agent.invoke(
                {"messages": [{"role": "user", "content": build_prompt(topic_str)}]},
                config={"recursion_limit": 1000},
            )
            messages = result.get("messages", []) if isinstance(result, dict) else []
            elapsed = time.monotonic() - start

            # In-sandbox finalization & validation verification (RUBRIC 2.6)
            backend.execute(f"python3 {SANITIZER_PATH}")
            fin_res = backend.execute(f"python3 {FINALIZER_PATH}")
            if getattr(fin_res, "output", None):
                print(f"[Sandbox Finalizer] {fin_res.output.strip()}")
            chk_res = backend.execute(f"python3 {VALIDATOR_PATH}")
            if getattr(chk_res, "output", None):
                print(f"[Sandbox Validator] {chk_res.output.strip()}")

            report_path = save_outputs(backend, topic_str, messages, elapsed, model_name)
            print(f"SUCCESS: Report saved to {report_path}")
            return 0
    except RuntimeError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAILED: unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
