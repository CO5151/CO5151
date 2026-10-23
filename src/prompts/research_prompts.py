"""Research prompts for LawGraph retrieval analysis and Live Gazette web verification."""

LAWGRAPH_RESEARCH_PROMPT = """Bạn là LawGraph Research Agent chuyên về đồ thị pháp lý.
Nhiệm vụ: Tóm tắt ngắn gọn trong 1 câu cơ sở pháp lý và sự phù hợp của các điều khoản đối với câu hỏi.

Câu hỏi: {query}
Mục tiêu: {subgoals}
Điều khoản: {context}
"""

LIVE_GAZETTE_PROMPT = """Bạn là Live Gazette / Web Finding Agent.
Nhiệm vụ: Đánh giá tính xác thực của thông tin từ cổng công báo/cơ quan nhà nước chính thức trong 1 câu.

Câu hỏi: {query}
Thông tin tìm kiếm: {text}
"""
