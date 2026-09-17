"""
Keyword search over the curated knowledge base (knowledge/*.md).

Why keyword scoring instead of embeddings/a vector DB: the corpus is 8 short,
hand-written docs. At this size a vector index adds a dependency and a moving
part without improving recall — every doc is short enough that simple term
overlap against its title/tags/body finds the right one. See
docs/DECISION_LOG.md for what would change this (larger, less curated corpora,
or docs that don't share vocabulary with how customers phrase questions).
"""

import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"

_docs_cache = None


def _parse_doc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    # Minimal frontmatter parser — good enough for our own hand-written docs.
    doc_id, title, tags = path.stem, path.stem, []
    if text.startswith("---"):
        end = text.index("---", 3)
        frontmatter, body = text[3:end].strip(), text[end + 3:].strip()
        for line in frontmatter.splitlines():
            if line.startswith("id:"):
                doc_id = line.split(":", 1)[1].strip()
            elif line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("tags:"):
                tags = [t.strip() for t in line.split(":", 1)[1].strip(" []").split(",") if t.strip()]
    else:
        body = text
    return {"id": doc_id, "title": title, "tags": tags, "body": body}


def load_docs() -> list[dict]:
    global _docs_cache
    if _docs_cache is None:
        _docs_cache = [_parse_doc(p) for p in sorted(KNOWLEDGE_DIR.glob("*.md"))]
    return _docs_cache


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def search_docs(query: str, top_k: int = 3) -> dict:
    """Score each doc by term overlap between the query and its title/tags/body.

    Title and tag matches are weighted higher than body matches — a query term
    that appears in the doc's title is a much stronger signal of relevance
    than the same term appearing once in a long body paragraph.
    """
    query_terms = set(_tokenize(query))
    if not query_terms:
        return {"results": []}

    scored = []
    for doc in load_docs():
        title_terms = set(_tokenize(doc["title"]))
        tag_terms = set(_tokenize(" ".join(doc["tags"])))
        body_terms = _tokenize(doc["body"])
        body_counts = {t: body_terms.count(t) for t in query_terms if t in body_terms}

        score = (
            3 * len(query_terms & title_terms)
            + 2 * len(query_terms & tag_terms)
            + sum(body_counts.values())
        )
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:top_k]
    if not top:
        return {"results": [], "message": "No matching documentation found."}

    return {
        "results": [
            {
                "id": doc["id"],
                "title": doc["title"],
                # First ~600 chars is enough context for the model to cite and
                # paraphrase without pulling the whole doc into every turn.
                "excerpt": doc["body"][:600].strip(),
            }
            for _, doc in top
        ]
    }
