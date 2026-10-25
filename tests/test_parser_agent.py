"""Unit tests for LegalParserAgent (Google ADK agentic parser)."""

import json
from unittest.mock import patch

from src.agents.parser_agent import (
    DocumentExtract,
    LegalParserAgent,
)
from src.knowledge.ingestion import ParsedDocument

SAMPLE_LLM_JSON = json.dumps(
    {
        "doc_id": "777/2025/NĐ-CP",
        "title": "Nghị định quy định về giao dịch điện tử",
        "doc_type": "Nghị định",
        "issuer": "Chính phủ",
        "issue_date": "2025-05-10",
        "effective_date": "2025-07-01",
        "articles": [
            {
                "article_number": "1",
                "title": "Phạm vi điều chỉnh",
                "content": "Điều 1. Phạm vi điều chỉnh. Nghị định này quy định về giao dịch điện tử trong cơ quan nhà nước.",
                "clauses": [
                    {
                        "clause_number": "1",
                        "content": "Nghị định này quy định về giao dịch điện tử trong cơ quan nhà nước.",
                    }
                ],
            },
            {
                "article_number": "2",
                "title": "Đối tượng áp dụng",
                "content": "Điều 2. Đối tượng áp dụng. Áp dụng đối với cơ quan, tổ chức, cá nhân.",
                "clauses": [
                    {
                        "clause_number": "1",
                        "content": "Áp dụng đối với cơ quan, tổ chức, cá nhân tham gia giao dịch.",
                    }
                ],
            },
        ],
    }
)


def test_parser_agent_initialization():
    """Tests LegalParserAgent conforms to Google ADK standards."""
    agent = LegalParserAgent()
    assert agent.name == "LegalParserAgent"
    assert agent.role == "parser"
    assert "Google ADK" in agent.instruction
    assert agent.adk_agent is not None or agent.llm is None


def test_parser_pydantic_schema_validation():
    """Tests Pydantic validation of DocumentExtract, ArticleExtract, and ClauseExtract."""
    doc_data = DocumentExtract.model_validate_json(SAMPLE_LLM_JSON)
    assert doc_data.doc_id == "777/2025/NĐ-CP"
    assert len(doc_data.articles) == 2
    assert doc_data.articles[0].article_number == "1"
    assert len(doc_data.articles[0].clauses) == 1
    assert doc_data.articles[0].clauses[0].clause_number == "1"


def test_parser_agent_parse_with_mocked_llm(monkeypatch):
    """Tests successful document parsing with simulated LLM output."""
    agent = LegalParserAgent()

    # Mock invoke_adk_agent to return valid JSON
    with patch("src.agents.parser_agent.invoke_adk_agent", return_value=SAMPLE_LLM_JSON):
        doc = agent.parse("Văn bản scan không chuẩn...")

    assert isinstance(doc, ParsedDocument)
    assert doc.doc_id == "777/2025/ND-CP"
    assert doc.title == "Nghị định quy định về giao dịch điện tử"
    assert doc.effective_date == "2025-07-01"
    assert len(doc.articles) == 2
    assert doc.articles[0].article_id == "777/2025/ND-CP:Article_1"
    assert len(doc.articles[0].clauses) == 1
    assert doc.articles[0].clauses[0].clause_id == "777/2025/ND-CP:Article_1:Clause_1"


def test_parser_agent_handles_markdown_fences():
    """Tests parsing when LLM wraps output in ```json markdown fences."""
    agent = LegalParserAgent()
    fenced_output = f"```json\n{SAMPLE_LLM_JSON}\n```"

    with patch("src.agents.parser_agent.invoke_adk_agent", return_value=fenced_output):
        doc = agent.parse("Some raw text")

    assert doc is not None
    assert doc.doc_id == "777/2025/ND-CP"


def test_parser_agent_handles_empty_or_invalid_text():
    """Tests parser agent degrades gracefully on empty input or invalid output."""
    agent = LegalParserAgent()
    assert agent.parse("") is None
    assert agent.parse("   ") is None

    # Invalid JSON output from LLM
    with patch("src.agents.parser_agent.invoke_adk_agent", return_value="This is not JSON"):
        assert agent.parse("Valid text but LLM failed") is None


def test_parser_agent_execute_adk_lifecycle():
    """Tests executing parser agent through ADKAgent.execute interface."""
    agent = LegalParserAgent()

    with patch("src.agents.parser_agent.invoke_adk_agent", return_value=SAMPLE_LLM_JSON):
        result = agent.execute({"text": "sample text", "default_metadata": {}})

    assert result.success is True
    assert result.agent_name == "LegalParserAgent"
    assert isinstance(result.data, ParsedDocument)
    assert result.execution_time_ms >= 0.0
