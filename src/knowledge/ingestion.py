"""Vietnamese Legal Document Ingestion Pipeline for LegalPilot-VN.

Performs hierarchical parsing (Document -> Article -> Clause), legal chunking with
contextual metadata, cross-reference relationship extraction (AMENDS, GUIDES, SUPERSEDES),
and simultaneous ingestion into Neo4j Knowledge Graph and Qdrant Vector Store.

Supports:
1. Regex & Heuristic Parsing for standardized legal drafting text (.txt).
2. HTML DOM Parsing for scraped pages from vbpl.vn or thuvienphapluat (.html).
3. LLM-assisted Fallback Parsing for complex, non-standard, or scanned documents.
4. CLI execution for one-click batch ingestion.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.exceptions import KnowledgeBaseError
from src.core.logger import get_logger
from src.knowledge.neo4j_client import Neo4jClient
from src.knowledge.qdrant_client import QdrantClientManager

logger = get_logger(__name__)


@dataclass
class ParsedClause:
    """Represents a single clause (Khoản) or sub-clause within an Article."""

    clause_id: str
    clause_number: str
    content: str


@dataclass
class ParsedArticle:
    """Represents a legal article (Điều) containing clauses."""

    article_id: str
    article_number: str
    title: str
    content: str
    clauses: list[ParsedClause] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Represents a complete Vietnamese legal document with metadata and hierarchy."""

    doc_id: str
    title: str
    doc_type: str
    issuer: str
    issue_date: str
    effective_date: str
    expiration_date: str | None = None
    status: str = "in_force"
    articles: list[ParsedArticle] = field(default_factory=list)
    # Provenance from an authoritative record (moj_id, eff_status_code, source_url...).
    metadata: dict[str, Any] = field(default_factory=dict)


# Alias for backward compatibility / semantic naming
HTMLParsed = ParsedDocument


@dataclass
class LegalCrossReference:
    """Represents a directional relationship between legal entities."""

    source_doc_id: str
    target_doc_id: str
    rel_type: str  # AMENDS, GUIDES, SUPERSEDES, REFERS_TO
    source_article_id: str | None = None
    target_article_id: str | None = None
    scope: str | None = None
    effective_date: str | None = None


def normalize_doc_id(doc_id_raw: str) -> str:
    """Normalizes raw document numbers into standard uppercase identifier.

    Example: '152/2020/NĐ-CP' -> '152/2020/ND-CP'
    """
    cleaned = doc_id_raw.strip().replace(" ", "")
    # Normalize Vietnamese accented characters in official document symbols
    replacements = {
        "Đ": "D",
        "đ": "d",
        "\u2013": "-",
        "\u2014": "-",
    }
    for k, v in replacements.items():
        cleaned = cleaned.replace(k, v)
    return cleaned.upper()


def parse_legal_document(
    text: str, default_metadata: dict[str, Any] | None = None
) -> ParsedDocument:
    """Parses raw text of a Vietnamese legal document into a structured hierarchy."""
    meta = default_metadata or {}

    # 1. Extract Document Identifier (Số hiệu)
    doc_id_match = re.search(r"Số:\s*([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)", text, re.IGNORECASE)
    doc_id = (
        normalize_doc_id(doc_id_match.group(1))
        if doc_id_match
        else meta.get("doc_id", "UNKNOWN/DOC")
    )

    # 2. Extract Issuer (Cơ quan ban hành)
    issuer_match = re.search(
        r"^(CHÍNH PHỦ|BỘ [^\n]+|THỦ TƯỚNG CHÍNH PHỦ|QUỐC HỘI)",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    issuer = (
        issuer_match.group(1).strip().title() if issuer_match else meta.get("issuer", "Chính phủ")
    )

    # 3. Extract Document Type
    type_match = re.search(
        r"\n(NGHỊ ĐỊNH|THÔNG TƯ|LUẬT|QUYẾT ĐỊNH|NGHỊ QUYẾT)\n", text, re.IGNORECASE
    )
    doc_type = (
        type_match.group(1).strip().title() if type_match else meta.get("doc_type", "Nghị định")
    )

    # 4. Extract Issue Date (Ngày ký / ban hành)
    date_match = re.search(
        r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text, re.IGNORECASE
    )
    if date_match:
        d, m, y = date_match.groups()
        issue_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    else:
        issue_date = meta.get("issue_date", "2020-01-01")

    # 5. Extract Effective Date (Ngày có hiệu lực)
    eff_match = re.search(
        r"(?:có hiệu lực(?:\s+thi hành)?\s+(?:từ|kể từ)\s+ngày)\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if eff_match:
        d, m, y = eff_match.groups()
        effective_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    else:
        effective_date = meta.get("effective_date", issue_date)

    # 6. Extract Document Title
    title = meta.get("title")
    if not title:
        # Paragraph immediately following doc_type is typically the title
        title_match = re.search(
            rf"{doc_type}\s*\n+([^\n]+(?:\n[^\nCăn cứ]+)*)",
            text,
            re.IGNORECASE,
        )
        if title_match:
            title = re.sub(r"\s+", " ", title_match.group(1).strip())
        else:
            title = f"{doc_type} số {doc_id}"

    # 7. Extract Articles (Điều)
    article_pattern = re.compile(
        r"(?:^|\n)(Điều\s+(\d+)\.\s*([^\n]*))\n?([\s\S]*?)(?=^Điều\s+\d+\.|\Z)",
        re.MULTILINE,
    )

    parsed_articles: list[ParsedArticle] = []
    for match in article_pattern.finditer(text):
        _full_header = match.group(1).strip()
        art_num = match.group(2).strip()
        art_title = match.group(3).strip()
        art_content = match.group(4).strip()

        article_id = f"{doc_id}:Article_{art_num}"

        # 8. Extract Clauses (Khoản) within Article
        clause_pattern = re.compile(r"(?:^|\n)(\d+)\.\s*([\s\S]*?)(?=(?:\n\d+\.|\Z))", re.MULTILINE)
        parsed_clauses: list[ParsedClause] = []

        clause_matches = list(clause_pattern.finditer(art_content))
        if clause_matches:
            for c_match in clause_matches:
                c_num = c_match.group(1).strip()
                c_text = c_match.group(2).strip()
                clause_id = f"{article_id}:Clause_{c_num}"
                parsed_clauses.append(
                    ParsedClause(clause_id=clause_id, clause_number=c_num, content=c_text)
                )
        else:
            # Single clause article
            clause_id = f"{article_id}:Clause_1"
            parsed_clauses.append(
                ParsedClause(clause_id=clause_id, clause_number="1", content=art_content)
            )

        parsed_articles.append(
            ParsedArticle(
                article_id=article_id,
                article_number=art_num,
                title=art_title,
                content=art_content,
                clauses=parsed_clauses,
            )
        )

    if not parsed_articles:
        parsed_articles = split_roman_sections(doc_id, text)

    return ParsedDocument(
        doc_id=doc_id,
        title=title,
        doc_type=doc_type,
        issuer=issuer,
        issue_date=issue_date,
        effective_date=effective_date,
        status="in_force",
        articles=disambiguate_ids(parsed_articles),
    )


_ROMAN_HEADING = re.compile(r"^([IVXL]{1,6})\s*[./]\s*(.*)$")
_TOP_LEVEL_ITEM = re.compile(r"(?:^|\n)(\d+)[./](?!\d)\s*([\s\S]*?)(?=\n\d+[./](?!\d)|\Z)")
_FIRST_ITEM = re.compile(r"^1[./](?!\d)\s*\S", re.MULTILINE)

#: Article number used when a document has numbered items but no sections at all.
WHOLE_TEXT_ARTICLE = "0"


def split_roman_sections(doc_id: str, text: str) -> list[ParsedArticle]:
    """Splits pre-2010 SBV circulars that use Roman sections (I., II/) instead of Điều.

    Each section becomes an article numbered by its numeral; top-level items
    (``1.``, ``2/``, but not ``1.1.``) become clauses. Short circulars with only
    numbered items become a single article ``0`` so they still yield chunks.
    """
    lines = [raw.strip() for raw in text.split("\n") if raw.strip()]
    sections: list[tuple[str, str, list[str]]] = []
    for line in lines:
        match = _ROMAN_HEADING.match(line)
        if match:
            sections.append((match.group(1), match.group(2).strip(), []))
        elif sections:
            if not sections[-1][1]:
                # Heading text wrapped onto the line after the bare numeral.
                numeral, _, body = sections[-1]
                sections[-1] = (numeral, line, body)
            else:
                sections[-1][2].append(line)
    if not sections or sections[0][0] != "I":
        body_text = "\n".join(lines)
        first = _FIRST_ITEM.search(body_text)
        if not first:
            return []
        sections = [(WHOLE_TEXT_ARTICLE, "", body_text[first.start() :].split("\n"))]

    articles: list[ParsedArticle] = []
    for numeral, heading, body in sections:
        article_id = f"{doc_id}:Article_{numeral}"
        content = "\n".join(body).strip()
        items = list(_TOP_LEVEL_ITEM.finditer(content))
        clauses = [
            ParsedClause(
                clause_id=f"{article_id}:Clause_{m.group(1)}",
                clause_number=m.group(1),
                content=m.group(2).strip(),
            )
            for m in items
        ] or [ParsedClause(clause_id=f"{article_id}:Clause_1", clause_number="1", content=content)]
        articles.append(
            ParsedArticle(
                article_id=article_id,
                article_number=numeral,
                title=heading,
                content=content,
                clauses=clauses,
            )
        )
    return articles


def disambiguate_ids(articles: list[ParsedArticle]) -> list[ParsedArticle]:
    """Makes repeated Article / Clause numbers unique within one document.

    A Decision that promulgates a Regulation restarts at Điều 1, and nested lists
    restart clause numbering. Identical ids would be MERGEd into one node in Neo4j
    and silently overwrite each other, so the k-th repeat gets an ``_k`` suffix.
    """
    seen_articles: collections.Counter[str] = collections.Counter()
    for art in articles:
        seen_articles[art.article_id] += 1
        if seen_articles[art.article_id] > 1:
            old_id = art.article_id
            art.article_id = f"{old_id}_{seen_articles[old_id]}"
            for clause in art.clauses:
                clause.clause_id = _rekey(clause.clause_id, old_id, art.article_id) or ""
        seen_clauses: collections.Counter[str] = collections.Counter()
        for clause in art.clauses:
            seen_clauses[clause.clause_id] += 1
            if seen_clauses[clause.clause_id] > 1:
                clause.clause_id = f"{clause.clause_id}_{seen_clauses[clause.clause_id]}"
    return articles


def parse_html_document(
    html_content: str, default_metadata: dict[str, Any] | None = None
) -> tuple[ParsedDocument, list[LegalCrossReference]]:
    """Parses raw HTML from VBPL or similar legal portals using BeautifulSoup.

    Extracts:
    1. Metadata from header tags / text.
    2. Articles and Clauses from semantic tags (p, div, h3, h4).
    3. Cross-references from hyperlinks (a tags linking to other legal documents).
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")
    meta = default_metadata or {}

    # Strip script and style tags
    for s in soup(["script", "style", "noscript"]):
        s.decompose()

    raw_text = soup.get_text("\n")

    # 1. Metadata extraction
    doc_id_match = re.search(r"Số:\s*([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)", raw_text, re.IGNORECASE)
    doc_id = (
        normalize_doc_id(doc_id_match.group(1))
        if doc_id_match
        else meta.get("doc_id", "UNKNOWN/DOC")
    )

    issuer_match = re.search(
        r"^(CHÍNH PHỦ|BỘ [^\n]+|THỦ TƯỚNG CHÍNH PHỦ|QUỐC HỘI)",
        raw_text,
        re.MULTILINE | re.IGNORECASE,
    )
    issuer = (
        issuer_match.group(1).strip().title() if issuer_match else meta.get("issuer", "Chính phủ")
    )

    type_match = re.search(
        r"\n(NGHỊ ĐỊNH|THÔNG TƯ|LUẬT|QUYẾT ĐỊNH|NGHỊ QUYẾT)\n", raw_text, re.IGNORECASE
    )
    doc_type = (
        type_match.group(1).strip().title() if type_match else meta.get("doc_type", "Nghị định")
    )

    date_match = re.search(
        r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", raw_text, re.IGNORECASE
    )
    if date_match:
        d, m, y = date_match.groups()
        issue_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    else:
        issue_date = meta.get("issue_date", "2020-01-01")

    eff_match = re.search(
        r"(?:có hiệu lực(?:\s+thi hành)?\s+(?:từ|kể từ)\s+ngày)\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        raw_text,
        re.IGNORECASE,
    )
    if eff_match:
        d, m, y = eff_match.groups()
        effective_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    else:
        effective_date = meta.get("effective_date", issue_date)

    title_elem = soup.find(["h1", "h2", "div"], class_=re.compile(r"title|vbTitle|header", re.I))
    if title_elem and title_elem.get_text().strip():
        title = re.sub(r"\s+", " ", title_elem.get_text().strip())
    else:
        title_match = re.search(
            rf"{doc_type}\s*\n+([^\n]+(?:\n[^\nCăn cứ]+)*)",
            raw_text,
            re.IGNORECASE,
        )
        title = (
            re.sub(r"\s+", " ", title_match.group(1).strip())
            if title_match
            else f"{doc_type} số {doc_id}"
        )

    # 2. Extract Articles from HTML paragraphs
    parsed_articles: list[ParsedArticle] = []
    paragraphs = soup.find_all(["p", "div", "h3", "h4"])
    current_art_num: str | None = None
    current_art_title = ""
    current_art_content_parts: list[str] = []

    def commit_article() -> None:
        if current_art_num is not None:
            art_id = f"{doc_id}:Article_{current_art_num}"
            full_content = "\n".join(current_art_content_parts).strip()

            clause_pattern = re.compile(
                r"(?:^|\n)(\d+)\.\s*([\s\S]*?)(?=(?:\n\d+\.|\Z))", re.MULTILINE
            )
            c_matches = list(clause_pattern.finditer(full_content))
            clauses = []
            if c_matches:
                for cm in c_matches:
                    c_num = cm.group(1).strip()
                    c_text = cm.group(2).strip()
                    clauses.append(
                        ParsedClause(
                            clause_id=f"{art_id}:Clause_{c_num}",
                            clause_number=c_num,
                            content=c_text,
                        )
                    )
            else:
                clauses.append(
                    ParsedClause(
                        clause_id=f"{art_id}:Clause_1",
                        clause_number="1",
                        content=full_content,
                    )
                )

            parsed_articles.append(
                ParsedArticle(
                    article_id=art_id,
                    article_number=current_art_num,
                    title=current_art_title,
                    content=full_content,
                    clauses=clauses,
                )
            )

    for p in paragraphs:
        p_text = p.get_text().strip()
        art_match = re.match(r"^Điều\s+(\d+)[\.:]\s*(.*)$", p_text, re.IGNORECASE)
        if art_match:
            commit_article()
            current_art_num = art_match.group(1).strip()
            current_art_title = art_match.group(2).strip()
            current_art_content_parts = []
        elif current_art_num is not None and p_text:
            current_art_content_parts.append(p_text)

    commit_article()

    # Fallback to text parsing if HTML structure didn't find articles
    if not parsed_articles:
        parsed_doc = parse_legal_document(raw_text, default_metadata=meta)
    else:
        parsed_doc = ParsedDocument(
            doc_id=doc_id,
            title=title,
            doc_type=doc_type,
            issuer=issuer,
            issue_date=issue_date,
            effective_date=effective_date,
            status="in_force",
            articles=disambiguate_ids(parsed_articles),
        )

    # 3. Extract Hyperlinks for Cross-References
    link_refs: list[LegalCrossReference] = []
    for a in soup.find_all("a"):
        link_text = a.get_text().strip()
        link_match = re.search(r"([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)", link_text)
        if link_match:
            target_id = normalize_doc_id(link_match.group(1))
            if target_id != doc_id:
                link_refs.append(
                    LegalCrossReference(
                        source_doc_id=doc_id,
                        target_doc_id=target_id,
                        rel_type="REFERS_TO",
                        scope="Extracted from hyperlink anchor",
                        effective_date=effective_date,
                    )
                )

    text_refs = extract_cross_references(parsed_doc, raw_text)
    all_refs = text_refs + [
        r for r in link_refs if not any(tr.target_doc_id == r.target_doc_id for tr in text_refs)
    ]

    return parsed_doc, all_refs


#: Sidecar keys that map onto ParsedDocument attributes; the rest become provenance.
_AUTHORITATIVE_FIELDS = (
    "title",
    "doc_type",
    "issuer",
    "issue_date",
    "effective_date",
    "expiration_date",
    "status",
)


def load_sidecar_metadata(path: Path) -> dict[str, Any] | None:
    """Returns the ``<stem>.meta.json`` record stored next to a raw document, if any."""
    sidecar = path.with_name(f"{path.stem}.meta.json")
    if not sidecar.exists():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise KnowledgeBaseError(f"Invalid metadata sidecar {sidecar}: {e}") from e
    return data if isinstance(data, dict) else None


def _rekey(value: str | None, old_id: str, new_id: str) -> str | None:
    if value is None:
        return None
    if value == old_id:
        return new_id
    if value.startswith(f"{old_id}:"):
        return new_id + value[len(old_id) :]
    return value


def apply_authoritative_metadata(
    doc: ParsedDocument,
    cross_refs: list[LegalCrossReference],
    meta: dict[str, Any],
) -> tuple[ParsedDocument, list[LegalCrossReference]]:
    """Overrides regex-derived metadata with an authoritative record (e.g. MoJ gateway).

    Text heuristics cannot read legacy numbers without a year (``22/QĐ-NH1``) and
    fall back to ``UNKNOWN/DOC``, which would make Article/Clause ids collide across
    documents. When the record carries a ``doc_id``, every id derived from the
    parsed one is re-keyed so the hierarchy stays unique.
    """
    old_id, new_id = doc.doc_id, meta.get("doc_id") or doc.doc_id
    if new_id != old_id:
        doc.doc_id = new_id
        for art in doc.articles:
            art.article_id = _rekey(art.article_id, old_id, new_id) or art.article_id
            for clause in art.clauses:
                clause.clause_id = _rekey(clause.clause_id, old_id, new_id) or clause.clause_id
        for ref in cross_refs:
            ref.source_doc_id = _rekey(ref.source_doc_id, old_id, new_id) or ref.source_doc_id
            ref.source_article_id = _rekey(ref.source_article_id, old_id, new_id)
            ref.target_doc_id = _rekey(ref.target_doc_id, old_id, new_id) or ref.target_doc_id
            ref.target_article_id = _rekey(ref.target_article_id, old_id, new_id)

    for key in _AUTHORITATIVE_FIELDS:
        if key == "expiration_date" and key in meta:
            doc.expiration_date = meta[key]
        elif meta.get(key):
            setattr(doc, key, meta[key])
    doc.metadata = {
        k: v
        for k, v in meta.items()
        if k not in (*_AUTHORITATIVE_FIELDS, "doc_id", "inbound_relations") and v is not None
    }
    # A document never refers to itself at document level.
    cross_refs = [
        r for r in cross_refs if not (r.target_doc_id == doc.doc_id and not r.target_article_id)
    ]
    # Relations recorded on *this* document by the authority (e.g. "Bị thay thế bởi X")
    # point inwards: X -> doc. The repealing text may sit outside the corpus.
    for rel in meta.get("inbound_relations") or []:
        source = rel.get("source_doc_id")
        if source and source != doc.doc_id:
            cross_refs.append(
                LegalCrossReference(
                    source_doc_id=source,
                    target_doc_id=doc.doc_id,
                    rel_type=rel.get("rel_type", "SUPERSEDES"),
                    scope=rel.get("scope"),
                    effective_date=meta.get("revoked_date") or meta.get("expiration_date"),
                )
            )
    return doc, cross_refs


def llm_fallback_parse_document(
    text: str, default_metadata: dict[str, Any] | None = None
) -> ParsedDocument | None:
    """Uses Google ADK LegalParserAgent to parse non-standard, scanned, or complex legal documents when regex fails.

    Wraps the official Google ADK Agent pipeline with schema validation and fallback handling.
    """
    from src.agents.parser_agent import LegalParserAgent

    agent = LegalParserAgent()
    return agent.parse(text, default_metadata=default_metadata)


def apply_revocation_status(documents: dict[str, Any]) -> int:
    """Propagate revocation metadata onto repealed documents.

    Scans every ``SUPERSEDES`` cross-reference and marks the target document as
    ``expired`` with a ``revoked_by`` pointer to the repealing instrument. Without
    this step, offline exports record every parsed instrument as ``in_force``,
    producing a graph that cannot represent the amendment chain the retrieval layer
    depends on.

    Args:
        documents: Mapping of ``doc_id`` to document payload, mutated in place.

    Returns:
        Number of documents whose status was updated.
    """
    updates = 0
    for doc in documents.values():
        for ref in doc.get("cross_references") or []:
            if ref.get("rel_type") != "SUPERSEDES":
                continue
            if ref.get("target_article_id"):
                # Article-level repeal; does not expire the whole instrument
                continue
            target_id = str(ref.get("target_doc_id", ""))
            if not target_id:
                continue
            target = documents.get(target_id) or next(
                (d for did, d in documents.items() if did.upper() == target_id.upper()),
                None,
            )
            if not target:
                # Target instrument has not been ingested; nothing to update yet.
                continue
            source_id = str(ref.get("source_doc_id", ""))
            if target.get("status") != "expired" or target.get("revoked_by") != source_id:
                target["status"] = "expired"
                target["revoked_by"] = source_id
                target["revoked_date"] = ref.get("effective_date")
                updates += 1
    return updates


def extract_cross_references(doc: ParsedDocument, full_text: str) -> list[LegalCrossReference]:
    """Extracts explicit legal cross-references from the document text.

    Detects:
    - Document-level AMENDS: 'Sửa đổi, bổ sung một số điều của Nghị định số...'
    - Article-level AMENDS: 'Sửa đổi, bổ sung Điều X (khoản Y) của Nghị định số...'
    - Document-level SUPERSEDES: 'Bãi bỏ toàn bộ Nghị định số...'
    - Article-level SUPERSEDES: 'Bãi bỏ Điều X (khoản Y) của Nghị định số...'
    - GUIDES: 'Căn cứ Luật số...' / 'Quy định chi tiết...'
    - Article-level CITES: 'theo quy định tại Điều X Nghị định Y', intra-statute citations, etc.
    """
    refs: list[LegalCrossReference] = []

    def has_ref(
        rel_type: str,
        target_doc: str,
        target_art: str | None = None,
        src_art: str | None = None,
    ) -> bool:
        return any(
            r.rel_type == rel_type
            and r.target_doc_id == target_doc
            and r.target_article_id == target_art
            and r.source_article_id == src_art
            for r in refs
        )

    # 1. Detect AMENDS from Title & Body
    amend_doc_targets: list[str] = []
    amend_pattern = re.compile(
        r"(?:Sửa đổi, bổ sung|SỬA ĐỔI, BỔ SUNG)\s+[^.\n]*?(?:Nghị định|Thông tư|Luật)\s+(?:số\s+)?([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)",
        re.IGNORECASE,
    )
    for match in amend_pattern.finditer(full_text):
        target_raw = match.group(1)
        target_doc = normalize_doc_id(target_raw)
        if target_doc != doc.doc_id:
            if target_doc not in amend_doc_targets:
                amend_doc_targets.append(target_doc)
            if not has_ref("AMENDS", target_doc):
                refs.append(
                    LegalCrossReference(
                        source_doc_id=doc.doc_id,
                        target_doc_id=target_doc,
                        rel_type="AMENDS",
                        scope="Document level amendment",
                        effective_date=doc.effective_date,
                    )
                )

    # 2. Detect Article-level AMENDS
    # When this document is an amending instrument (e.g. Decree 70/2023 amending Decree 152/2020),
    # individual articles/clauses specify which target articles they amend.
    art_amend_pattern = re.compile(
        r"Sửa đổi, bổ sung\s+(?:(?:khoản|điểm)\s+[^,\n]+?\s+)?(?:Điều\s+(\d+))",
        re.IGNORECASE,
    )
    for art in doc.articles:
        art_target_doc = None
        art_target_match = amend_pattern.search(art.title) or amend_pattern.search(
            art.content[:200]
        )
        if art_target_match:
            art_target_doc = normalize_doc_id(art_target_match.group(1))
        elif amend_doc_targets:
            art_target_doc = amend_doc_targets[0]

        if art_target_doc and art_target_doc != doc.doc_id:
            for m in art_amend_pattern.finditer(art.content):
                target_art_num = m.group(1)
                target_art_id = f"{art_target_doc}:Article_{target_art_num}"
                if not has_ref("AMENDS", art_target_doc, target_art_id, art.article_id):
                    refs.append(
                        LegalCrossReference(
                            source_doc_id=doc.doc_id,
                            target_doc_id=art_target_doc,
                            source_article_id=art.article_id,
                            target_article_id=target_art_id,
                            rel_type="AMENDS",
                            scope=m.group(0).strip(),
                            effective_date=doc.effective_date,
                        )
                    )

    # 3. Detect Repeals (Bãi bỏ) -> SUPERSEDES
    repeal_pattern = re.compile(
        r"Bãi bỏ\s+(?:(?:khoản|điểm)\s+([^,\n]+?)\s+)?(?:Điều\s+(\d+))\s+của\s+(?:Nghị định|Thông tư|Luật|Quyết định)?\s*(?:số\s+)?([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)",
        re.IGNORECASE,
    )
    for art in doc.articles:
        for match in repeal_pattern.finditer(art.content):
            c_info, a_num, target_raw = match.groups()
            target_doc = normalize_doc_id(target_raw)
            target_art = f"{target_doc}:Article_{a_num}" if a_num else None
            scope_desc = (
                f"Bãi bỏ khoản {c_info.strip()} Điều {a_num}" if c_info else f"Bãi bỏ Điều {a_num}"
            )
            if not has_ref("SUPERSEDES", target_doc, target_art, art.article_id):
                refs.append(
                    LegalCrossReference(
                        source_doc_id=doc.doc_id,
                        target_doc_id=target_doc,
                        source_article_id=art.article_id,
                        target_article_id=target_art,
                        rel_type="SUPERSEDES",
                        scope=scope_desc,
                        effective_date=doc.effective_date,
                    )
                )

    # Global text search for repeals not inside parsed articles
    for match in repeal_pattern.finditer(full_text):
        c_info, a_num, target_raw = match.groups()
        target_doc = normalize_doc_id(target_raw)
        target_art = f"{target_doc}:Article_{a_num}" if a_num else None
        scope_desc = (
            f"Bãi bỏ khoản {c_info.strip()} Điều {a_num}" if c_info else f"Bãi bỏ Điều {a_num}"
        )
        if not any(
            r.rel_type == "SUPERSEDES"
            and r.target_doc_id == target_doc
            and r.target_article_id == target_art
            for r in refs
        ):
            refs.append(
                LegalCrossReference(
                    source_doc_id=doc.doc_id,
                    target_doc_id=target_doc,
                    target_article_id=target_art,
                    rel_type="SUPERSEDES",
                    scope=scope_desc,
                    effective_date=doc.effective_date,
                )
            )

    # Detect whole-document repeals / replacements
    whole_doc_pattern = re.compile(
        r"(?:Bãi bỏ|Thay thế)\s+(?:toàn bộ\s+)?(?:Nghị định|Thông tư|Luật|Bộ luật)\s+"
        r"(?:số\s+)?([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)",
        re.IGNORECASE,
    )
    for match in whole_doc_pattern.finditer(full_text):
        target_doc = normalize_doc_id(match.group(1))
        if target_doc == doc.doc_id:
            continue
        if not any(
            r.rel_type == "SUPERSEDES"
            and r.target_doc_id == target_doc
            and r.target_article_id is None
            for r in refs
        ):
            verb = match.group(0).strip().split()[0]
            refs.append(
                LegalCrossReference(
                    source_doc_id=doc.doc_id,
                    target_doc_id=target_doc,
                    rel_type="SUPERSEDES",
                    scope=f"Repeals the whole instrument ({verb})",
                    effective_date=doc.effective_date,
                )
            )

    # 4. Detect GUIDES / Căn cứ
    guides_pattern = re.compile(
        r"Căn cứ\s+((?:Bộ luật|Luật)\s+[^;\n]+)",
        re.IGNORECASE,
    )
    for match in guides_pattern.finditer(full_text):
        raw_law = match.group(1).strip()
        law_title = re.sub(r"\s+ngày\s+\d+.*", "", raw_law).strip()
        if not has_ref("GUIDES", law_title):
            refs.append(
                LegalCrossReference(
                    source_doc_id=doc.doc_id,
                    target_doc_id=law_title,
                    rel_type="GUIDES",
                    scope=f"Guides {law_title}",
                    effective_date=doc.effective_date,
                )
            )

    # 5. Detect Article-level CITES (Statutory Citations / Viện dẫn quy định)
    cite_art_pattern = re.compile(
        r"(?:theo quy định tại|căn cứ tại|căn cứ theo|quy định tại|áp dụng theo|hướng dẫn tại|đối chiếu với quy định tại|nêu tại)\s+"
        r"(?:(?:khoản|điểm)\s+[^,\n]+?\s+)?"
        r"(?:Điều\s+(\d+))\s+"
        r"(?:của\s+)?(?:Nghị định|Thông tư|Luật|Bộ luật|Quyết định)?\s*"
        r"(?:số\s+)?([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)",
        re.IGNORECASE,
    )
    intra_cite_pattern = re.compile(
        r"(?:theo quy định tại|căn cứ tại|căn cứ theo|quy định tại|áp dụng theo|hướng dẫn tại|nêu tại)\s+"
        r"(?:(?:khoản|điểm)\s+[^,\n]+?\s+)?"
        r"(?:Điều\s+(\d+))\s+"
        r"(?:của\s+)?(?:Nghị định này|Thông tư này|Luật này|Bộ luật này|Quyết định này|Văn bản này)",
        re.IGNORECASE,
    )
    cite_doc_pattern = re.compile(
        r"(?:theo quy định tại|căn cứ vào|hướng dẫn tại|áp dụng quy định của|thực hiện theo)\s+"
        r"(?:Nghị định|Thông tư|Quyết định|Luật|Bộ luật)\s+"
        r"(?:số\s+)?([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)",
        re.IGNORECASE,
    )

    for art in doc.articles:
        # Cross-statute Article citation
        for m in cite_art_pattern.finditer(art.content):
            art_num = m.group(1)
            target_doc = normalize_doc_id(m.group(2))
            target_art = f"{target_doc}:Article_{art_num}"
            if not has_ref("CITES", target_doc, target_art, art.article_id):
                refs.append(
                    LegalCrossReference(
                        source_doc_id=doc.doc_id,
                        target_doc_id=target_doc,
                        source_article_id=art.article_id,
                        target_article_id=target_art,
                        rel_type="CITES",
                        scope=m.group(0).strip(),
                        effective_date=doc.effective_date,
                    )
                )

        # Intra-statute Article citation
        for m in intra_cite_pattern.finditer(art.content):
            art_num = m.group(1)
            target_doc = doc.doc_id
            target_art = f"{target_doc}:Article_{art_num}"
            if target_art != art.article_id and not has_ref(
                "CITES", target_doc, target_art, art.article_id
            ):
                refs.append(
                    LegalCrossReference(
                        source_doc_id=doc.doc_id,
                        target_doc_id=target_doc,
                        source_article_id=art.article_id,
                        target_article_id=target_art,
                        rel_type="CITES",
                        scope=m.group(0).strip(),
                        effective_date=doc.effective_date,
                    )
                )

        # Cross-statute Document citation
        for m in cite_doc_pattern.finditer(art.content):
            target_doc = normalize_doc_id(m.group(1))
            if target_doc != doc.doc_id and not any(
                r.rel_type == "CITES"
                and r.target_doc_id == target_doc
                and r.source_article_id == art.article_id
                for r in refs
            ):
                refs.append(
                    LegalCrossReference(
                        source_doc_id=doc.doc_id,
                        target_doc_id=target_doc,
                        source_article_id=art.article_id,
                        target_article_id=None,
                        rel_type="CITES",
                        scope=m.group(0).strip(),
                        effective_date=doc.effective_date,
                    )
                )

    return refs


def generate_legal_chunks(
    doc: ParsedDocument,
    dummy_vector_dim: int | None = 768,
) -> list[dict[str, Any]]:
    """Generates vectorized legal chunks formatted for Qdrant payload indexing.

    Each chunk contains prepended statutory context:
    '[Document Type Doc_ID - Title] [Article num: Title] [Clause num]: Content'
    """
    chunks: list[dict[str, Any]] = []
    pairs = [(article, clause) for article in doc.articles for clause in article.clauses]
    texts = [
        f"[{doc.doc_type} {doc.doc_id} - {doc.title}] [Điều {article.article_number}: {article.title}]"
        f" [Khoản {clause.clause_number}]: {clause.content}"
        for article, clause in pairs
    ]

    # If a custom test dimension is explicitly provided (not default 768), generate dummy vectors
    vectors: list[list[float]]
    if dummy_vector_dim is not None and dummy_vector_dim != 768:
        vectors = [[0.0] * dummy_vector_dim for _ in texts]
    elif not texts:
        vectors = []
    else:
        # Compute real dense embeddings with the Vietnamese bi-encoder, one batch per document
        try:
            from sentence_transformers import SentenceTransformer

            _global_embedder = getattr(generate_legal_chunks, "_embedder", None)
            if _global_embedder is None:
                _global_embedder = SentenceTransformer(
                    "bkai-foundation-models/vietnamese-bi-encoder"
                )
                generate_legal_chunks._embedder = _global_embedder  # type: ignore[attr-defined]
            encoded = _global_embedder.encode(texts, batch_size=32, normalize_embeddings=True)
            vectors = [[float(x) for x in row] for row in encoded]
        except Exception as e:
            logger.warning("Embedding failed for %s, using zero vectors: %s", doc.doc_id, e)
            vectors = [[0.0] * 768 for _ in texts]

    for (article, clause), full_chunk_text, vector in zip(pairs, texts, vectors, strict=True):
        chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, clause.clause_id))
        chunks.append(
            {
                "id": chunk_id,
                "vector": vector,
                "text": full_chunk_text,
                "payload": {
                    "doc_id": doc.doc_id,
                    "article_id": article.article_id,
                    "clause_id": clause.clause_id,
                    "article_number": article.article_number,
                    "clause_number": clause.clause_number,
                    "doc_type": doc.doc_type,
                    "issuer": doc.issuer,
                    "title": doc.title,
                    "status": doc.status,
                    "effective_date": doc.effective_date,
                    "expiration_date": doc.expiration_date,
                    "text": full_chunk_text,
                    "raw_clause": clause.content,
                },
            }
        )

    return chunks


class LegalIngestionPipeline:
    """Orchestrates end-to-end legal document parsing and storage ingestion."""

    def __init__(
        self,
        neo4j_client: Neo4jClient | None = None,
        qdrant_manager: QdrantClientManager | None = None,
    ):
        """Initializes storage clients for graph and vector indexing."""
        self.neo4j_client = neo4j_client or Neo4jClient()
        self.qdrant_manager = qdrant_manager or QdrantClientManager()

    def ingest_file(
        self,
        file_path: str | Path,
        sync_qdrant: bool = True,
        sync_neo4j: bool = True,
        vector_dim: int = 768,
        enable_llm_fallback: bool = True,
    ) -> dict[str, Any]:
        """Reads, parses, and ingests a single legal document file into Neo4j and Qdrant."""
        path = Path(file_path)
        if not path.exists():
            raise KnowledgeBaseError(f"Legal file not found: {path}")

        logger.info("Starting ingestion of: %s", path.name)
        text = path.read_text(encoding="utf-8")
        sidecar = load_sidecar_metadata(path)

        # 1. Parse document hierarchy (HTML DOM vs Regex vs LLM)
        if path.suffix.lower() in (".html", ".htm"):
            parsed_doc, cross_refs = parse_html_document(text, default_metadata=sidecar)
        else:
            parsed_doc = parse_legal_document(text, default_metadata=sidecar)
            cross_refs = extract_cross_references(parsed_doc, text)

        # 2. Trigger LLM fallback if regex/HTML produced 0 articles
        if not parsed_doc.articles and enable_llm_fallback:
            logger.info("No articles parsed for %s, trying LLM fallback...", path.name)
            llm_doc = llm_fallback_parse_document(text)
            if llm_doc and llm_doc.articles:
                parsed_doc = llm_doc
                cross_refs = extract_cross_references(parsed_doc, text)

        if sidecar:
            parsed_doc, cross_refs = apply_authoritative_metadata(parsed_doc, cross_refs, sidecar)

        logger.info(
            "Parsed %s: %d articles found, %d cross-references",
            parsed_doc.doc_id,
            len(parsed_doc.articles),
            len(cross_refs),
        )

        # 3. Ingest into Neo4j
        if sync_neo4j:
            self._ingest_to_neo4j(parsed_doc, cross_refs)

        # 4. Ingest into Qdrant
        chunks = generate_legal_chunks(parsed_doc, dummy_vector_dim=vector_dim)
        if sync_qdrant:
            self._ingest_to_qdrant(chunks)

        return {
            "doc_id": parsed_doc.doc_id,
            "title": parsed_doc.title,
            "articles_count": len(parsed_doc.articles),
            "chunks_count": len(chunks),
            "cross_refs_count": len(cross_refs),
        }

    def _ingest_to_neo4j(self, doc: ParsedDocument, cross_refs: list[LegalCrossReference]) -> None:
        """Upserts document, articles, clauses, and relationships into Neo4j (or exports if offline)."""
        if not self.neo4j_client.verify_connectivity():
            logger.warning(
                "Neo4j instance at %s is unreachable. Exporting parsed graph nodes & relations to data/processed/neo4j_graph_export.json for offline fallback.",
                self.neo4j_client.uri,
            )
            export_file = Path("data/processed/neo4j_graph_export.json")
            export_file.parent.mkdir(parents=True, exist_ok=True)
            current_data: dict[str, Any] = {}
            if export_file.exists():
                try:
                    current_data = json.loads(export_file.read_text(encoding="utf-8"))
                except Exception:
                    current_data = {}

            current_data[doc.doc_id] = {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "issuer": doc.issuer,
                "issue_date": doc.issue_date,
                "effective_date": doc.effective_date,
                "status": doc.status,
                **doc.metadata,
                "articles": [
                    {
                        "article": f"Điều {art.article_number}",
                        "title": art.title,
                        "content": art.content,
                        "clauses": [
                            {"clause_number": c.clause_number, "content": c.content}
                            for c in art.clauses
                        ],
                    }
                    for art in doc.articles
                ],
                "cross_references": [
                    {
                        "source_doc_id": ref.source_doc_id,
                        "target_doc_id": ref.target_doc_id,
                        "source_article_id": ref.source_article_id,
                        "target_article_id": ref.target_article_id,
                        "rel_type": ref.rel_type,
                        "scope": ref.scope,
                        "effective_date": ref.effective_date,
                    }
                    for ref in cross_refs
                ],
            }
            # Propagate repeal metadata so the exported graph carries the amendment
            # chain instead of recording every instrument as in_force.
            updated = apply_revocation_status(current_data)
            if updated:
                logger.info(
                    "Revocation inference updated %d document status(es) in the graph export.",
                    updated,
                )
            export_file.write_text(
                json.dumps(current_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return

        self.neo4j_client.init_schema()

        # Upsert Document
        self.neo4j_client.upsert_document(
            doc_id=doc.doc_id,
            title=doc.title,
            doc_type=doc.doc_type,
            issuer=doc.issuer,
            issue_date=doc.issue_date,
            effective_date=doc.effective_date,
            expiration_date=doc.expiration_date,
            status=doc.status,
            source_url=doc.metadata.get("source_url"),
        )
        if doc.metadata:
            self.neo4j_client.execute_query(
                "MATCH (d:Document {doc_id: $doc_id}) SET d += $props",
                {"doc_id": doc.doc_id, "props": doc.metadata},
            )

        # Upsert Articles and Clauses
        for art in doc.articles:
            self.neo4j_client.upsert_article(
                article_id=art.article_id,
                doc_id=doc.doc_id,
                article_number=art.article_number,
                title=art.title,
                content=art.content,
            )
            for clause in art.clauses:
                self.neo4j_client.upsert_clause(
                    clause_id=clause.clause_id,
                    article_id=art.article_id,
                    clause_number=clause.clause_number,
                    content=clause.content,
                )

        # Upsert Cross-References
        for ref in cross_refs:
            if ref.rel_type in ("AMENDS", "SUPERSEDES", "GUIDES", "CITES", "REFERS_TO"):
                props = {
                    "scope": ref.scope or "",
                    "effective_date": ref.effective_date or doc.effective_date,
                }
                # Case 1: Article-to-Article relationship
                if ref.source_article_id and ref.target_article_id:
                    self.neo4j_client.upsert_relationship(
                        from_label="Article",
                        from_key="article_id",
                        from_val=ref.source_article_id,
                        to_label="Article",
                        to_key="article_id",
                        to_val=ref.target_article_id,
                        rel_type=ref.rel_type,
                        properties=props,
                    )
                    # Ensure target article is connected to target document if known
                    if ref.target_doc_id:
                        self.neo4j_client.execute_query(
                            """
                            MERGE (d:Document {doc_id: $doc_id})
                            MERGE (a:Article {article_id: $art_id})
                            MERGE (d)-[:CONTAINS]->(a)
                            """,
                            {"doc_id": ref.target_doc_id, "art_id": ref.target_article_id},
                        )

                # Case 2: Article-to-Document citation
                elif ref.source_article_id and not ref.target_article_id:
                    self.neo4j_client.upsert_relationship(
                        from_label="Article",
                        from_key="article_id",
                        from_val=ref.source_article_id,
                        to_label="Document",
                        to_key="doc_id",
                        to_val=ref.target_doc_id,
                        rel_type=ref.rel_type,
                        properties=props,
                    )

                # Case 3: Document-to-Document relationship
                else:
                    self.neo4j_client.upsert_relationship(
                        from_label="Document",
                        from_key="doc_id",
                        from_val=ref.source_doc_id,
                        to_label="Document",
                        to_key="doc_id",
                        to_val=ref.target_doc_id,
                        rel_type=ref.rel_type,
                        properties=props,
                    )

                # Propagate validity: a repealed instrument must not remain 'in_force'
                # in the graph, otherwise temporal pruning has nothing to act on.
                if ref.rel_type == "SUPERSEDES":
                    if ref.target_article_id:
                        # Article-level repeal
                        self.neo4j_client.execute_query(
                            "MATCH (a:Article {article_id: $target_art}) "
                            "SET a.status = 'expired', "
                            "    a.revoked_by = $source, "
                            "    a.revoked_date = $date",
                            {
                                "target_art": ref.target_article_id,
                                "source": ref.source_doc_id,
                                "date": ref.effective_date or doc.effective_date,
                            },
                        )
                    else:
                        # Whole-document repeal. Inferred from text, so it never
                        # overrides a status that came from an authoritative record.
                        self.neo4j_client.execute_query(
                            "MATCH (d:Document {doc_id: $target}) "
                            "WHERE d.status_source IS NULL "
                            "SET d.status = 'expired', "
                            "    d.revoked_by = $source, "
                            "    d.revoked_date = $date",
                            {
                                "target": ref.target_doc_id,
                                "source": ref.source_doc_id,
                                "date": ref.effective_date or doc.effective_date,
                            },
                        )

    def _ingest_to_qdrant(self, chunks: list[dict[str, Any]]) -> None:
        """Initializes collection if needed and upserts legal chunks (or exports if offline)."""
        if not self.qdrant_manager.health_check():
            logger.warning(
                "Qdrant instance at %s:%s is unreachable. Exporting vector chunks to data/processed/qdrant_chunks_export.json for offline fallback.",
                self.qdrant_manager.host,
                self.qdrant_manager.port,
            )
            export_file = Path("data/processed/qdrant_chunks_export.json")
            export_file.parent.mkdir(parents=True, exist_ok=True)
            existing_chunks: list[dict[str, Any]] = []
            if export_file.exists():
                try:
                    existing_chunks = json.loads(export_file.read_text(encoding="utf-8"))
                except Exception:
                    existing_chunks = []
            # De-duplicate by chunk id so that re-ingesting is idempotent. Previously
            # this appended unconditionally, so every re-run duplicated the corpus.
            by_id: dict[str, dict[str, Any]] = {
                str(entry.get("id")): entry for entry in existing_chunks
            }
            for entry in chunks:
                by_id[str(entry.get("id"))] = entry
            merged = [by_id[key] for key in sorted(by_id)]
            export_file.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return

        self.qdrant_manager.init_collection(
            vector_size=len(chunks[0]["vector"]) if chunks else 768,
            recreate=False,
        )
        self.qdrant_manager.upsert_legal_chunks(chunks)

    def ingest_directory(
        self,
        raw_dir: str | Path = "data/raw",
        sync_qdrant: bool = True,
        sync_neo4j: bool = True,
        enable_llm_fallback: bool = True,
    ) -> list[dict[str, Any]]:
        """Ingests all .txt and .html legal documents found in directory.

        A failing file is logged and reported with an ``error`` key instead of
        aborting the batch, so one malformed document cannot stop a corpus load.
        """
        dir_path = Path(raw_dir)
        results: list[dict[str, Any]] = []
        files = sorted(list(dir_path.glob("*.txt")) + list(dir_path.glob("*.html")))
        for i, file_path in enumerate(files, 1):
            try:
                res = self.ingest_file(
                    file_path=file_path,
                    sync_qdrant=sync_qdrant,
                    sync_neo4j=sync_neo4j,
                    enable_llm_fallback=enable_llm_fallback,
                )
            except Exception as e:
                logger.error("Ingestion failed for %s: %s", file_path.name, e)
                res = {"file": file_path.name, "error": f"{type(e).__name__}: {e}"}
            results.append(res)
            logger.info("Ingested %d/%d files", i, len(files))
        return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegalPilot-VN Document Ingestion Pipeline")
    parser.add_argument(
        "--file",
        type=str,
        help="Path to a single .txt or .html legal document to ingest",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="data/raw",
        help="Directory containing legal documents (default: data/raw)",
    )
    parser.add_argument(
        "--no-qdrant",
        action="store_true",
        help="Skip syncing to Qdrant vector store",
    )
    parser.add_argument(
        "--no-neo4j",
        action="store_true",
        help="Skip syncing to Neo4j knowledge graph",
    )
    parser.add_argument(
        "--vector-dim",
        type=int,
        default=768,
        help="Vector dimension for Qdrant (default: 768)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM fallback parsing",
    )

    args = parser.parse_args()

    pipeline = LegalIngestionPipeline()
    if args.file:
        res = pipeline.ingest_file(
            file_path=args.file,
            sync_qdrant=not args.no_qdrant,
            sync_neo4j=not args.no_neo4j,
            vector_dim=args.vector_dim,
            enable_llm_fallback=not args.no_llm,
        )
        print(f"Successfully ingested: {res}")
    else:
        results = pipeline.ingest_directory(
            raw_dir=args.dir,
            sync_qdrant=not args.no_qdrant,
            sync_neo4j=not args.no_neo4j,
            enable_llm_fallback=not args.no_llm,
        )
        failed = [r for r in results if "error" in r]
        print(f"Successfully ingested {len(results) - len(failed)} documents from {args.dir}")
        for r in failed:
            print(f"  FAILED {r['file']}: {r['error']}")
