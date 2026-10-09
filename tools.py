"""tools.py - STUDENT IMPLEMENTS.  Source tools for the research agents.   Guide: GUIDE.md, part 1.

Rules for every tool:
  * runs on the HOST (not in the sandbox): API keys must never enter the sandbox;
  * returns a STRING (JSON text of compact records) and NEVER raises:
        "NO RESULTS"  when the source answers with nothing,
        "ERROR: ..."  when the source keeps failing after the retries (the agent then tries another source);
  * the docstring is the tool description the LLM reads: keep it precise (what it does, what it returns, when to use it).
Try your tools without any agent:   python tools.py
"""
import json
import os
import random
import re
import threading
import time
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

# ---- constants (given) ----
ARXIV_URL = "https://export.arxiv.org/api/query"  # https only: http answers 301
HF_DAILY_URL = "https://huggingface.co/api/daily_papers"
HF_SEARCH_URL = "https://huggingface.co/api/papers/search"
EXA_URL = "https://mcp.exa.ai/mcp"

_last_arxiv_time = 0.0
_arxiv_lock = threading.Lock()


class RetryableError(Exception):
    """Given. Raise it inside a call to ask with_retry to wait and try again (retry_after in seconds, optional)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def _rate_limit_arxiv():
    """Ensure at least 3 seconds between arXiv calls."""
    global _last_arxiv_time
    with _arxiv_lock:
        now = time.monotonic()
        elapsed = now - _last_arxiv_time
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)
        _last_arxiv_time = time.monotonic()


def _redact_exa(text: str) -> str:
    """Never leak EXA_API_KEY in tool output or error messages (RUBRIC 1.3)."""
    key = (os.getenv("EXA_API_KEY") or "").strip()
    if key and key in text:
        text = text.replace(key, "[REDACTED]")
    return text


# ---- TODO 1: retry helper ----
def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Call fn(); when it raises RetryableError, wait and call it again."""
    for attempt in range(attempts):
        try:
            return fn()
        except (RetryableError, httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {429, 500, 502, 503, 504}:
                raise

            if attempt == attempts - 1:
                raise

            retry_after = getattr(exc, "retry_after", None)
            if retry_after is None and isinstance(exc, httpx.HTTPStatusError):
                retry_after = exc.response.headers.get("Retry-After")

            if retry_after is not None:
                try:
                    delay = float(retry_after)
                except (ValueError, TypeError):
                    delay = base * (2**attempt) + random.uniform(0.0, 1.0)
            else:
                delay = base * (2**attempt) + random.uniform(0.0, 1.0)

            delay = min(delay, cap)
            time.sleep(delay)


# ---- TODO 2: arXiv ----
@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv papers by keywords, newest first. Returns a JSON list of {id, url, published, title, summary}."""
    try:
        raw_terms = re.findall(r"[A-Za-z0-9\-]+", query)
        terms = [t for t in raw_terms if t.lower() not in {"and", "or", "not"}]
        if not terms:
            return "NO RESULTS"

        max_results = max(1, min(int(max_results), 30))
        search_query = " AND ".join(f"all:{t}" for t in terms)

        def _fetch():
            _rate_limit_arxiv()
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    ARXIV_URL,
                    params={
                        "search_query": search_query,
                        "sortBy": "submittedDate",
                        "sortOrder": "descending",
                        "max_results": max_results,
                    },
                )
                if resp.status_code == 429:
                    raise RetryableError("arXiv HTTP 429 rate limit", retry_after=resp.headers.get("Retry-After"))
                if resp.status_code in {500, 502, 503, 504}:
                    raise RetryableError(f"arXiv HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.text

        xml_text = with_retry(_fetch, attempts=5, base=2.0, cap=60.0)
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        if not entries:
            return "NO RESULTS"

        records = []
        for entry in entries:
            id_text = entry.findtext("atom:id", "", ns).strip()
            if not id_text:
                continue
            paper_id = re.sub(r"v\d+$", "", id_text.split("/abs/")[-1])
            if not paper_id:
                continue
            url = f"https://arxiv.org/abs/{paper_id}"
            pub = entry.findtext("atom:published", "", ns).strip()[:10]
            title = " ".join(entry.findtext("atom:title", "", ns).split())
            summary = " ".join(entry.findtext("atom:summary", "", ns).split())[:600]
            records.append({
                "id": paper_id,
                "url": url,
                "published": pub,
                "title": title,
                "summary": summary,
            })

        if not records:
            return "NO RESULTS"
        return json.dumps(records, ensure_ascii=False)
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 3: Hugging Face ----
@tool
def hf_daily_papers(limit: int = 30, date: str = "", keyword: str = "") -> str:
    """Hugging Face Daily Papers = what is trending in AI research. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars} sorted by upvotes. `date` is YYYY-MM-DD (empty = latest).
    `keyword` filters title/summary; there is no topic search on this endpoint (use hf_search_papers for a topic)."""
    try:
        limit = max(1, min(int(limit), 100))
        params = {"limit": limit}
        if date and date.strip():
            params["date"] = date.strip()

        def _fetch():
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(HF_DAILY_URL, params=params)
                if resp.status_code == 429:
                    raise RetryableError("HF HTTP 429", retry_after=resp.headers.get("Retry-After"))
                if resp.status_code in {500, 502, 503, 504}:
                    raise RetryableError(f"HF HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()

        data = with_retry(_fetch, attempts=5, base=1.0, cap=30.0)
        if not isinstance(data, list) or not data:
            return "NO RESULTS"

        records = []
        for item in data:
            if not isinstance(item, dict):
                continue
            paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            paper_id = paper.get("id") or item.get("id")
            if not paper_id:
                continue
            url = f"https://huggingface.co/papers/{paper_id}"
            title = " ".join((paper.get("title") or item.get("title") or "").split())
            summary = " ".join((paper.get("summary") or item.get("summary") or "").split())[:600]
            published = str(paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            upvotes = paper.get("upvotes") or item.get("upvotes") or 0
            github = paper.get("githubRepo") or item.get("githubRepo") or ""
            stars = paper.get("githubStars") or item.get("githubStars") or 0
            records.append({
                "id": str(paper_id),
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": int(upvotes) if isinstance(upvotes, (int, float)) else 0,
                "github": str(github),
                "stars": int(stars) if isinstance(stars, (int, float)) else 0,
            })

        if keyword and keyword.strip():
            kw = keyword.strip().lower()
            matches = [r for r in records if kw in (r["title"] + " " + r["summary"]).lower()]
            if not matches:
                words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", kw) if len(w) > 2]
                if words:
                    matches = [r for r in records if any(w in (r["title"] + " " + r["summary"]).lower() for w in words)]
            if matches:
                records = matches

        records.sort(key=lambda r: r.get("upvotes", 0), reverse=True)
        if not records:
            return "NO RESULTS"
        return json.dumps(records, ensure_ascii=False)
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search Hugging Face papers by topic. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars}."""
    try:
        if not query or not query.strip():
            return "NO RESULTS"
        limit = max(1, min(int(limit), 50))
        params = {"q": query.strip(), "limit": limit}

        def _fetch():
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(HF_SEARCH_URL, params=params)
                if resp.status_code == 429:
                    raise RetryableError("HF HTTP 429", retry_after=resp.headers.get("Retry-After"))
                if resp.status_code in {500, 502, 503, 504}:
                    raise RetryableError(f"HF HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()

        data = with_retry(_fetch, attempts=5, base=1.0, cap=30.0)
        if not isinstance(data, list) or not data:
            return "NO RESULTS"

        records = []
        for item in data:
            if not isinstance(item, dict):
                continue
            paper = item.get("paper") if isinstance(item.get("paper"), dict) else {}
            paper_id = paper.get("id") or item.get("id")
            if not paper_id:
                continue
            url = f"https://huggingface.co/papers/{paper_id}"
            title = " ".join((paper.get("title") or item.get("title") or "").split())
            summary_raw = paper.get("ai_summary") or paper.get("summary") or item.get("summary") or ""
            summary = " ".join(summary_raw.split())[:600]
            published = str(paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            upvotes = paper.get("upvotes") or item.get("upvotes") or 0
            github = paper.get("githubRepo") or item.get("githubRepo") or ""
            stars = paper.get("githubStars") or item.get("githubStars") or 0
            records.append({
                "id": str(paper_id),
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": int(upvotes) if isinstance(upvotes, (int, float)) else 0,
                "github": str(github),
                "stars": int(stars) if isinstance(stars, (int, float)) else 0,
            })

        if not records:
            return "NO RESULTS"
        return json.dumps(records, ensure_ascii=False)
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 4: web search / fetch through the Exa MCP endpoint ----
def _call_mcp(tool_name: str, arguments: dict) -> str:
    """Call an Exa MCP tool over plain HTTP (JSON-RPC) with retry and rate-limit detection."""
    exa_key = (os.getenv("EXA_API_KEY") or "").strip()
    url = EXA_URL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if exa_key:
        headers["Authorization"] = f"Bearer {exa_key}"
        headers["x-api-key"] = exa_key

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    def _request():
        try:
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    raise RetryableError("Exa HTTP 429 Rate Limited", retry_after=resp.headers.get("Retry-After"))
                if resp.status_code in {500, 502, 503, 504}:
                    raise RetryableError(f"Exa HTTP {resp.status_code} Server Error")
                resp.raise_for_status()

                parsed = None
                for line in resp.text.splitlines():
                    line = line.strip()
                    if line.startswith("data:"):
                        try:
                            parsed = json.loads(line[5:].strip())
                            break
                        except Exception:
                            continue
                    elif line.startswith("{"):
                        try:
                            parsed = json.loads(line)
                            break
                        except Exception:
                            continue

                if not parsed or not isinstance(parsed, dict):
                    raise RuntimeError("Invalid or empty response from Exa MCP")

                if "error" in parsed:
                    err = parsed["error"]
                    msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    if any(term in msg.lower() for term in ["rate limit", "too many requests", "429"]):
                        raise RetryableError(f"Exa rate limited: {msg}")
                    raise RuntimeError(f"Exa RPC error: {msg}")

                result = parsed.get("result", {})
                if not isinstance(result, dict):
                    raise RuntimeError("Exa MCP result is not a dict")

                # Detect rate limit in result._meta (as noted in GUIDE 1.4)
                meta = result.get("_meta", {})
                if isinstance(meta, dict):
                    meta_str = json.dumps(meta).lower()
                    if any(term in meta_str for term in ["rate_limit", "ratelimit", "exceeded", "limit"]):
                        raise RetryableError(f"Exa rate limit flag in _meta: {meta}")

                content = result.get("content", [])
                texts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        t = item.get("text", "")
                        if t:
                            texts.append(t)

                combined = "\n".join(texts).strip()

                if any(term in combined.lower() for term in [
                    "hit exa's free mcp rate limit",
                    "rate limit exceeded",
                    "too many requests",
                ]):
                    raise RetryableError("Exa rate limited in content text")

                return combined
        except httpx.TransportError as e:
            raise RetryableError(f"Transport error: {e}")

    return with_retry(_request, attempts=5, base=1.0, cap=60.0)


@tool
def web_search(query: str, objective: str = "", num_results: int = 5) -> str:
    """Search the web (Exa). Describe the ideal page in natural language. Returns clean text of the top results with URLs."""
    if not query or not query.strip():
        return "NO RESULTS"
    if not objective or not objective.strip():
        objective = f"find research papers and surveys about {query}"
    num_results = max(1, min(int(num_results), 10))

    try:
        combined = _call_mcp(
            "web_search_exa",
            {
                "query": query.strip(),
                "objective": objective.strip(),
                "numResults": num_results,
            },
        )
        if not combined:
            return "NO RESULTS"
        return _redact_exa(combined)
    except Exception as exc:
        return _redact_exa(f"ERROR: {type(exc).__name__}: {exc}")


@tool
def web_fetch(url: str) -> str:
    """Read the full content of one web page (e.g. an arXiv abstract page) as markdown. Long pages are truncated."""
    if not url or not url.strip():
        return "NO RESULTS"

    try:
        combined = _call_mcp("web_fetch_exa", {"urls": [url.strip()]})
        if not combined:
            return "NO RESULTS"
        return _redact_exa(combined[:12000])
    except Exception as exc:
        return _redact_exa(f"ERROR: {type(exc).__name__}: {exc}")


# ---- TODO 5: registry (the researcher subagent gets exactly these) ----
SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]


if __name__ == "__main__":
    for name, fn, args in [
        ("arxiv_search", arxiv_search, {"query": "world model", "max_results": 3}),
        ("hf_daily_papers", hf_daily_papers, {"limit": 20}),
        ("hf_search_papers", hf_search_papers, {"query": "world model", "limit": 3}),
        ("web_search", web_search, {"query": "survey paper on world models", "num_results": 2}),
        ("web_fetch", web_fetch, {"url": "https://arxiv.org/abs/1803.10122"}),
    ]:
        try:
            print(f"== {name}\n{fn.invoke(args)[:400]}\n")
        except NotImplementedError as exc:
            print(f"== {name}: not implemented yet ({exc})\n")
