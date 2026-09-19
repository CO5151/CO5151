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
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from src.core.config import settings
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
        r"(?:^|\n)(Điều\s+(\d+)\.\s*([^\n]*))\n([\s\S]*?)(?=(?:\nĐiều\s+\d+\.|\Z))",
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

    return ParsedDocument(
        doc_id=doc_id,
        title=title,
        doc_type=doc_type,
        issuer=issuer,
        issue_date=issue_date,
        effective_date=effective_date,
        status="in_force",
        articles=parsed_articles,
    )


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
            articles=parsed_articles,
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


def llm_fallback_parse_document(
    text: str, default_metadata: dict[str, Any] | None = None
) -> ParsedDocument | None:
    """Uses LLM to parse non-standard, scanned, or complex legal documents when regex fails.

    Calls Gemini or local model with structured prompt. Degrades gracefully if unavailable.
    """
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No GEMINI_API_KEY found, skipping LLM fallback parsing")
        return None

    logger.info("Triggering LLM fallback parsing with Gemini...")
    prompt = f"""You are an expert legal document parser for Vietnamese Law.
Parse the following legal document into a strict JSON structure.
Format:
{{
  "doc_id": "document number e.g. 152/2020/ND-CP",
  "title": "document title",
  "doc_type": "Nghị định | Thông tư | Luật | Quyết định",
  "issuer": "Chính phủ | Bộ ...",
  "issue_date": "YYYY-MM-DD",
  "effective_date": "YYYY-MM-DD",
  "articles": [
    {{
      "article_number": "1",
      "title": "Tên điều",
      "content": "Toàn văn điều",
      "clauses": [
        {{"clause_number": "1", "content": "Nội dung khoản 1"}}
      ]
    }}
  ]
}}

Document text:
{text[:6000]}
"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.llm.cloud_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_json)

            articles = []
            doc_id = normalize_doc_id(parsed.get("doc_id", "UNKNOWN/DOC"))
            for art in parsed.get("articles", []):
                art_num = str(art.get("article_number", "1"))
                art_id = f"{doc_id}:Article_{art_num}"
                clauses = []
                for c in art.get("clauses", []):
                    c_num = str(c.get("clause_number", "1"))
                    clauses.append(
                        ParsedClause(
                            clause_id=f"{art_id}:Clause_{c_num}",
                            clause_number=c_num,
                            content=c.get("content", ""),
                        )
                    )
                articles.append(
                    ParsedArticle(
                        article_id=art_id,
                        article_number=art_num,
                        title=art.get("title", ""),
                        content=art.get("content", ""),
                        clauses=clauses,
                    )
                )

            return ParsedDocument(
                doc_id=doc_id,
                title=parsed.get("title", ""),
                doc_type=parsed.get("doc_type", "Nghị định"),
                issuer=parsed.get("issuer", "Chính phủ"),
                issue_date=parsed.get("issue_date", "2020-01-01"),
                effective_date=parsed.get("effective_date", "2020-01-01"),
                status="in_force",
                articles=articles,
            )
    except Exception as e:
        logger.warning("LLM fallback parsing encountered an error: %s", e)
        return None


def extract_cross_references(doc: ParsedDocument, full_text: str) -> list[LegalCrossReference]:
    """Extracts explicit legal cross-references from the document text.

    Detects:
    - AMENDS: 'Sửa đổi, bổ sung một số điều của Nghị định số...'
    - SUPERSEDES: 'Bãi bỏ Điều... của Nghị định số...'
    - GUIDES: 'Căn cứ Luật số...' / 'Quy định chi tiết...'
    """
    refs: list[LegalCrossReference] = []

    # 1. Detect AMENDS from Title & Body
    amend_pattern = re.compile(
        r"(?:Sửa đổi, bổ sung|SỬA ĐỔI, BỔ SUNG)\s+[^.\n]*?(?:Nghị định|Thông tư|Luật)\s+(?:số\s+)?([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)",
        re.IGNORECASE,
    )
    for match in amend_pattern.finditer(full_text):
        target_raw = match.group(1)
        target_doc = normalize_doc_id(target_raw)
        if target_doc != doc.doc_id:
            refs.append(
                LegalCrossReference(
                    source_doc_id=doc.doc_id,
                    target_doc_id=target_doc,
                    rel_type="AMENDS",
                    scope="Document level amendment",
                    effective_date=doc.effective_date,
                )
            )

    # 2. Detect Repeals (Bãi bỏ) -> SUPERSEDES
    repeal_pattern = re.compile(
        r"Bãi bỏ\s+(?:khoản\s+(\d+)\s+)?(?:Điều\s+(\d+))\s+của\s+(?:Nghị định|Thông tư|Luật)\s+(?:số\s+)?([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)",
        re.IGNORECASE,
    )
    for match in repeal_pattern.finditer(full_text):
        c_num, a_num, target_raw = match.groups()
        target_doc = normalize_doc_id(target_raw)
        target_art = f"{target_doc}:Article_{a_num}" if a_num else None
        refs.append(
            LegalCrossReference(
                source_doc_id=doc.doc_id,
                target_doc_id=target_doc,
                target_article_id=target_art,
                rel_type="SUPERSEDES",
                scope=(
                    f"Repeals Article {a_num} Clause {c_num}"
                    if c_num
                    else f"Repeals Article {a_num}"
                ),
                effective_date=doc.effective_date,
            )
        )

    # 3. Detect GUIDES / Căn cứ
    guides_pattern = re.compile(
        r"Căn cứ\s+((?:Bộ luật|Luật)\s+[^;\n]+)",
        re.IGNORECASE,
    )
    for match in guides_pattern.finditer(full_text):
        raw_law = match.group(1).strip()
        law_title = re.sub(r"\s+ngày\s+\d+.*", "", raw_law).strip()
        refs.append(
            LegalCrossReference(
                source_doc_id=doc.doc_id,
                target_doc_id=law_title,
                rel_type="GUIDES",
                scope=f"Guides {law_title}",
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

    for article in doc.articles:
        for clause in article.clauses:
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, clause.clause_id))
            context_header = f"[{doc.doc_type} {doc.doc_id} - {doc.title}] [Điều {article.article_number}: {article.title}]"
            full_chunk_text = f"{context_header} [Khoản {clause.clause_number}]: {clause.content}"

            # If embedding model is not called yet, generate deterministic dummy vector for ingestion testing
            vector = [0.0] * dummy_vector_dim if dummy_vector_dim else []

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

        # 1. Parse document hierarchy (HTML DOM vs Regex vs LLM)
        if path.suffix.lower() in (".html", ".htm"):
            parsed_doc, cross_refs = parse_html_document(text)
        else:
            parsed_doc = parse_legal_document(text)
            cross_refs = extract_cross_references(parsed_doc, text)

        # 2. Trigger LLM fallback if regex/HTML produced 0 articles
        if not parsed_doc.articles and enable_llm_fallback:
            logger.info("No articles parsed for %s, trying LLM fallback...", path.name)
            llm_doc = llm_fallback_parse_document(text)
            if llm_doc and llm_doc.articles:
                parsed_doc = llm_doc
                cross_refs = extract_cross_references(parsed_doc, text)

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
        """Upserts document, articles, clauses, and relationships into Neo4j."""
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
            if ref.rel_type in ("AMENDS", "SUPERSEDES", "GUIDES"):
                # Ensure target document node exists in graph before linking
                self.neo4j_client.execute_query(
                    "MERGE (d:Document {doc_id: $doc_id})",
                    {"doc_id": ref.target_doc_id},
                )
                self.neo4j_client.create_relationship(
                    from_label="Document",
                    from_key="doc_id",
                    from_val=ref.source_doc_id,
                    to_label="Document",
                    to_key="doc_id",
                    to_val=ref.target_doc_id,
                    rel_type=ref.rel_type,
                    properties={
                        "scope": ref.scope or "",
                        "effective_date": ref.effective_date or doc.effective_date,
                    },
                )

    def _ingest_to_qdrant(self, chunks: list[dict[str, Any]]) -> None:
        """Initializes collection if needed and upserts legal chunks."""
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
        """Ingests all .txt and .html legal documents found in directory."""
        dir_path = Path(raw_dir)
        results = []
        files = sorted(list(dir_path.glob("*.txt")) + list(dir_path.glob("*.html")))
        for file_path in files:
            res = self.ingest_file(
                file_path=file_path,
                sync_qdrant=sync_qdrant,
                sync_neo4j=sync_neo4j,
                enable_llm_fallback=enable_llm_fallback,
            )
            results.append(res)
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
        print(f"Successfully ingested {len(results)} documents from {args.dir}")
