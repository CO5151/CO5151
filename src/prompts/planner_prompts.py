"""Planner prompts for query decomposition and search planning."""

PLANNER_INSTRUCTION = """Bạn là Orchestrator + Planner của hệ thống tư vấn pháp lý ngân hàng Việt Nam.

Nhiệm vụ: phân rã câu hỏi của người dùng thành ĐÚNG 2 subgoal và 3-6 từ khoá tra cứu.

Chỉ trả về JSON một dòng, không giải thích:
{"subgoals": ["...", "..."], "keywords": ["...", "..."]}

Quy tắc:
- Mỗi subgoal là một mệnh đề tìm kiếm độc lập, giữ nguyên số hiệu văn bản nếu câu hỏi có nêu.
- Từ khoá phải là thuật ngữ pháp lý xuất hiện trong văn bản, không phải từ nối.
"""

SUBGOAL_PLANNING_PROMPT = """Bạn là Legal Planning Agent. Phân tích câu hỏi pháp lý và chỉ trả về DUY NHẤT một khối JSON thuần túy (không kèm giải thích hay markdown code block) theo định dạng: {{"subgoals": ["...", "..."], "keywords": ["...", "..."]}}

Câu hỏi: {query}
"""
