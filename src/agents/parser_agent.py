"""Legal Parser Agent: Structure extraction for Vietnamese legal documents.

Uses Google ADK (Agent Development Kit) to parse non-standard, scanned,
or unstructured legal text into hierarchical ParsedDocument/ParsedArticle/ParsedClause representations.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from src.agents.base import ADKAgent, get_default_model, invoke_adk_agent
from src.core.config import settings
from src.core.logger import logger
from src.knowledge.ingestion import (
    ParsedArticle,
    ParsedClause,
    ParsedDocument,
    normalize_doc_id,
)


class ClauseExtract(BaseModel):
    """Pydantic model representing a single statutory clause."""

    clause_number: str = Field(default="1", description="Số thứ tự khoản (ví dụ '1', '2')")
    content: str = Field(description="Nội dung điều khoản")


class ArticleExtract(BaseModel):
    """Pydantic model representing a statutory article."""

    article_number: str = Field(description="Số điều (ví dụ '1', '2')")
    title: str = Field(default="", description="Tiêu đề của điều")
    content: str = Field(description="Toàn bộ nội dung điều")
    clauses: list[ClauseExtract] = Field(default_factory=list, description="Danh sách các khoản")


class DocumentExtract(BaseModel):
    """Pydantic model representing a parsed legal document hierarchy."""

    doc_id: str = Field(description="Số hiệu văn bản (ví dụ '152/2020/ND-CP')")
    title: str = Field(description="Tên hoặc trích yếu nội dung văn bản")
    doc_type: str = Field(default="Nghị định", description="Loại văn bản")
    issuer: str = Field(default="Chính phủ", description="Cơ quan ban hành")
    issue_date: str = Field(default="2020-01-01", description="Ngày ban hành (YYYY-MM-DD)")
    effective_date: str = Field(default="2020-01-01", description="Ngày có hiệu lực (YYYY-MM-DD)")
    articles: list[ArticleExtract] = Field(default_factory=list, description="Danh sách các điều")


class LegalParserAgent(ADKAgent):
    """Official Google ADK Agent for parsing complex Vietnamese legal texts."""

    def __init__(self, model: str | None = None) -> None:
        instruction = (
            "Bạn là Chuyên gia Bóc tách Văn bản Pháp luật Việt Nam (Legal Document Parser Agent) "
            "theo chuẩn Google ADK. Nhiệm vụ của bạn là phân tích cấu trúc các văn bản quy phạm "
            "pháp luật (Luật, Nghị định, Thông tư, Quyết định), trích xuất metadata và toàn bộ "
            "các Điều, Khoản thành cấu trúc dữ liệu JSON chặt chẽ."
        )
        super().__init__(
            name="LegalParserAgent",
            description="Bóc tách tài liệu pháp lý phức tạp hoặc phi chuẩn sang cấu trúc phân cấp Document-Article-Clause theo chuẩn Google ADK.",
            role="parser",
            tools=[],
            instruction=instruction,
            model=model or get_default_model(),
        )

    def _run(self, input_data: Any, context: dict[str, Any]) -> ParsedDocument | None:
        """Executes parsing via standard ADK interface."""
        if isinstance(input_data, str):
            text = input_data
            meta = context.get("default_metadata")
        elif isinstance(input_data, dict):
            text = input_data.get("text", "")
            meta = input_data.get("default_metadata") or context.get("default_metadata")
        else:
            return None
        return self.parse(text, default_metadata=meta)

    def parse(
        self,
        text: str,
        default_metadata: dict[str, Any] | None = None,
    ) -> ParsedDocument | None:
        """Parses legal text into a structured ParsedDocument using Google ADK."""
        meta = default_metadata or {}
        if not text or not text.strip():
            return None

        # Build structured parsing prompt
        prompt = f"""You are an expert legal document parser for Vietnamese Law.
Parse the following legal document into a strict JSON structure matching the schema:
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

Return ONLY valid JSON matching this schema, without markdown backticks or commentary.

Document text:
{text[:6000]}
"""
        raw_output = ""
        # 1. Try Google ADK Agent invocation
        if self.adk_agent:
            try:
                raw_output = invoke_adk_agent(self.adk_agent, prompt).strip()
            except Exception as e:
                logger.warning("Google ADK Agent invocation failed for LegalParserAgent: %s", e)

        # 2. Fallback to direct LLM instance if ADK runner produced no output
        if not raw_output and self.llm:
            try:
                from langchain_core.messages import HumanMessage

                res = self.llm.invoke([HumanMessage(content=prompt)])
                raw_output = getattr(res, "content", "").strip()
            except Exception as e:
                logger.warning("Direct LLM fallback invocation failed for LegalParserAgent: %s", e)

        # 3. Fallback to Gemini REST if GEMINI_API_KEY is configured
        if not raw_output:
            api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
            if (
                api_key
                and not api_key.startswith("paste_")
                and not api_key.startswith("sk-local-dummy")
            ):
                try:
                    import httpx

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
                        raw_output = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                except Exception as e:
                    logger.warning("Gemini REST fallback failed for LegalParserAgent: %s", e)

        if not raw_output:
            logger.info("LegalParserAgent produced no output (LLM unavailable or offline)")
            return None

        # Clean JSON markdown fences if present
        clean_json = raw_output
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_output)
        if fence_match:
            clean_json = fence_match.group(1).strip()

        try:
            doc_data = DocumentExtract.model_validate_json(clean_json)
        except Exception as e:
            try:
                # Lenient json loads fallback
                parsed_dict = json.loads(clean_json)
                doc_data = DocumentExtract.model_validate(parsed_dict)
            except Exception as e2:
                logger.warning(
                    "Failed to validate parsed legal document against schema: %s / %s", e, e2
                )
                return None

        # Construct validated domain model
        doc_id = normalize_doc_id(doc_data.doc_id or meta.get("doc_id", "UNKNOWN/DOC"))
        articles: list[ParsedArticle] = []

        for art in doc_data.articles:
            art_num = str(art.article_number or "1")
            art_id = f"{doc_id}:Article_{art_num}"
            clauses: list[ParsedClause] = []

            for c in art.clauses:
                c_num = str(c.clause_number or "1")
                clause_id = f"{art_id}:Clause_{c_num}"
                clauses.append(
                    ParsedClause(
                        clause_id=clause_id,
                        clause_number=c_num,
                        content=c.content,
                    )
                )

            if not clauses:
                clauses.append(
                    ParsedClause(
                        clause_id=f"{art_id}:Clause_1",
                        clause_number="1",
                        content=art.content,
                    )
                )

            articles.append(
                ParsedArticle(
                    article_id=art_id,
                    article_number=art_num,
                    title=art.title,
                    content=art.content,
                    clauses=clauses,
                )
            )

        return ParsedDocument(
            doc_id=doc_id,
            title=doc_data.title or meta.get("title", f"Văn bản {doc_id}"),
            doc_type=doc_data.doc_type or meta.get("doc_type", "Nghị định"),
            issuer=doc_data.issuer or meta.get("issuer", "Chính phủ"),
            issue_date=doc_data.issue_date or meta.get("issue_date", "2020-01-01"),
            effective_date=doc_data.effective_date or meta.get("effective_date", "2020-01-01"),
            status="in_force",
            articles=articles,
        )
