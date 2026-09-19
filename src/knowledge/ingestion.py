"""Vietnamese Legal Document Ingestion Pipeline for LegalPilot-VN.

Performs hierarchical parsing (Document -> Article -> Clause), legal chunking with
contextual metadata, cross-reference relationship extraction (AMENDS, GUIDES, SUPERSEDES),
and simultaneous ingestion into Neo4j Knowledge Graph and Qdrant Vector Store.
"""

from __future__ import annotations

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


def parse_legal_document(text: str, default_metadata: dict[str, Any] | None = None) -> ParsedDocument:
    """Parses raw text of a Vietnamese legal document into a structured hierarchy."""
    meta = default_metadata or {}

    # 1. Extract Document Identifier (Số hiệu)
    doc_id_match = re.search(r"Số:\s*([0-9]+/[0-9]{4}/[A-Za-z0-9Đđ/-]+)", text, re.IGNORECASE)
    doc_id = normalize_doc_id(doc_id_match.group(1)) if doc_id_match else meta.get("doc_id", "UNKNOWN/DOC")

    # 2. Extract Issuer (Cơ quan ban hành)
    issuer_match = re.search(r"^(CHÍNH PHỦ|BỘ [^\n]+|THỦ TƯỚNG CHÍNH PHỦ|QUỐC HỘI)", text, re.MULTILINE | re.IGNORECASE)
    issuer = issuer_match.group(1).strip().title() if issuer_match else meta.get("issuer", "Chính phủ")

    # 3. Extract Document Type
    type_match = re.search(r"\n(NGHỊ ĐỊNH|THÔNG TƯ|LUẬT|QUYẾT ĐỊNH|NGHỊ QUYẾT)\n", text, re.IGNORECASE)
    doc_type = type_match.group(1).strip().title() if type_match else meta.get("doc_type", "Nghị định")

    # 4. Extract Issue Date (Ngày ký / ban hành)
    date_match = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text, re.IGNORECASE)
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
                parsed_clauses.append(ParsedClause(clause_id=clause_id, clause_number=c_num, content=c_text))
        else:
            # Single clause article
            clause_id = f"{article_id}:Clause_1"
            parsed_clauses.append(ParsedClause(clause_id=clause_id, clause_number="1", content=art_content))

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
                scope=f"Repeals Article {a_num} Clause {c_num}" if c_num else f"Repeals Article {a_num}",
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
    ) -> dict[str, Any]:
        """Reads, parses, and ingests a single legal document file into Neo4j and Qdrant."""
        path = Path(file_path)
        if not path.exists():
            raise KnowledgeBaseError(f"Legal file not found: {path}")

        logger.info("Starting ingestion of: %s", path.name)
        text = path.read_text(encoding="utf-8")

        # 1. Parse document hierarchy
        parsed_doc = parse_legal_document(text)
        logger.info("Parsed %s: %d articles found", parsed_doc.doc_id, len(parsed_doc.articles))

        # 2. Extract Cross-References
        cross_refs = extract_cross_references(parsed_doc, text)
        logger.info("Extracted %d cross-references for %s", len(cross_refs), parsed_doc.doc_id)

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

    def _ingest_to_neo4j(
        self, doc: ParsedDocument, cross_refs: list[LegalCrossReference]
    ) -> None:
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
    ) -> list[dict[str, Any]]:
        """Ingests all .txt legal documents found in directory."""
        dir_path = Path(raw_dir)
        results = []
        for file_path in sorted(dir_path.glob("*.txt")):
            res = self.ingest_file(
                file_path=file_path,
                sync_qdrant=sync_qdrant,
                sync_neo4j=sync_neo4j,
            )
            results.append(res)
        return results
