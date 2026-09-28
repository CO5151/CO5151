"""Official Google ADK Agent Application for LegalPilot-VN (Theme 9).

Integrates the multi-agent legal compliance system into the Google ADK ecosystem.
Launch with:
    adk web adk_agents
"""

from typing import Any, Dict, List, Optional
from google.adk import Agent
from src.tools.statutory_retriever import retrieve_statutory_provisions
from src.tools.validity_checker import check_statute_validity
from src.agents.orchestrator import LegalOrchestrator
from src.memory.state_models import EnterpriseProfile


def lookup_legal_statutes(keywords: List[str]) -> List[Dict[str, Any]]:
    """Tra cứu các điều khoản quy phạm pháp luật Việt Nam (Luật, Nghị định, Thông tư) theo từ khoá.

    Args:
        keywords: Danh sách từ khoá tìm kiếm (ví dụ: ['ví điện tử', 'điều kiện cấp phép']).

    Returns:
        Danh sách điều khoản quy phạm kèm số hiệu văn bản, ngày ban hành và trạng thái hiệu lực.
    """
    return retrieve_statutory_provisions(keywords)


def verify_statute_validity(doc_id: str) -> Dict[str, Any]:
    """Kiểm tra trạng thái hiệu lực pháp lý của văn bản quy phạm pháp luật (còn hiệu lực hay đã hết hiệu lực/bị bãi bỏ).

    Args:
        doc_id: Số hiệu văn bản cần thẩm định (ví dụ: '101/2012/ND-CP', '52/2024/ND-CP').

    Returns:
        Thông tin hiệu lực, văn bản thay thế/bãi bỏ (revoked_by), và các văn bản bị thay thế.
    """
    return check_statute_validity(doc_id)


def execute_compliance_audit_pipeline(query: str, company_name: str = "Doanh nghiệp Mẫu", charter_capital: float = 30_000_000_000.0) -> str:
    """Thực thi toàn bộ quy trình điều phối đa tác tử kiểm định và lập hồ sơ tuân thủ pháp lý.

    Thực hiện:
    1. Phân rã mục tiêu truy vấn (Planning).
    2. Tra cứu văn bản pháp luật (LawGraph).
    3. Thẩm định hiệu lực thời gian & phát hiện văn bản bãi bỏ (Claim Auditor).
    4. Tự động chuyển hướng và loại bỏ căn cứ hết hiệu lực (Re-route).
    5. Soạn thảo hồ sơ tuân thủ kèm miễn trừ trách nhiệm (Drafter).

    Args:
        query: Câu hỏi hoặc tình huống pháp lý cần tư vấn.
        company_name: Tên doanh nghiệp yêu cầu tư vấn.
        charter_capital: Vốn điều lệ hiện có của doanh nghiệp (VNĐ).

    Returns:
        Báo cáo tư vấn tuân thủ pháp lý hoàn chỉnh (Compliance Dossier).
    """
    orchestrator = LegalOrchestrator()
    profile = EnterpriseProfile(
        company_name=company_name,
        entity_type="Doanh nghiệp FDI",
        charter_capital=charter_capital,
        sector_code="6419",
        headcount=40,
        foreign_ownership_ratio=0.49,
    )
    state = orchestrator.run(query=query, enterprise_profile=profile)
    return state.final_compliance_dossier or "Không thể hoàn thành hồ sơ tuân thủ."


root_agent = Agent(
    name="legalpilot",
    model="gemini-2.5-flash",
    description="Hệ thống đa tác tử tư vấn tuân thủ pháp luật Việt Nam (Google ADK Multi-Agent Compliance System).",
    instruction=(
        "Bạn là Trợ lý Pháp lý Cao cấp LegalPilot-VN (Theme 9). "
        "Nhiệm vụ của bạn là hỗ trợ doanh nghiệp tra cứu và tuân thủ các quy định pháp luật Việt Nam. "
        "QUY TẮC BẮT BUỘC:\n"
        "1. Luôn sử dụng công cụ verify_statute_validity hoặc execute_compliance_audit_pipeline để đảm bảo căn cứ pháp lý còn hiệu lực.\n"
        "2. TUYỆT ĐỐI KHÔNG viện dẫn văn bản đã hết hiệu lực (ví dụ Nghị định 101/2012/NĐ-CP đã bị bãi bỏ bởi Nghị định 52/2024/NĐ-CP).\n"
        "3. Khi người dùng yêu cầu tư vấn tình huống phức tạp, ưu tiên gọi execute_compliance_audit_pipeline.\n"
        "4. Mọi báo cáo phải giữ nguyên lời cảnh báo miễn trừ trách nhiệm pháp lý."
    ),
    tools=[
        lookup_legal_statutes,
        verify_statute_validity,
        execute_compliance_audit_pipeline,
    ],
)
