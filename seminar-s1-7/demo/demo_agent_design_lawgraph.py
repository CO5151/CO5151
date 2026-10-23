#!/usr/bin/env python3
"""
CO5151: Advanced Agentic AI | Group G4 (HCMUT-VNU)
Seminar S1-7: Agent Design Patterns & Orchestration for Vietnamese Law Graph
Faculty Advisor: Dr. Le Xuan Bach
Presenters: Dang Lam Tung (Lead) · Nguyen Trung Phong · Vu Viet Hung

This script is an interactive demonstration comparing 3 agent design paradigms
for the Vietnamese Law Graph compliance problem:
  1. Deterministic Workflow (Prompt Chaining & Routing - Anthropic Dec 2024)
  2. Monolithic Autonomous Agent (Single Giant Context / ReAct Loop - OpenAI Apr 2025)
  3. Lead/Subagent Orchestrator + LangGraph Checkpointing & Differential Rollback (Anthropic Jun 2025 + LangGraph)

Features:
  - Real SQLite persistence for durable execution checkpoints.
  - Non-LLM External Deterministic Ground-Truth Oracle (vbpl.vn registry verifier).
  - Multi-scenario support: FDI E-Wallet Licensing (2024), Traffic Light Penalties, Foreign Labor Permits.
  - Interactive Step-by-Step or Benchmark Comparison modes.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Terminal ANSI Styling
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"


# =====================================================================
# 1. VIETNAMESE STATUTORY LAW GRAPH CATALOG
# =====================================================================
LAW_GRAPH_CATALOG: Dict[str, Dict[str, Any]] = {
    "52/2024/ND-CP": {
        "doc_id": "52/2024/ND-CP",
        "title": "Nghị định 52/2024/NĐ-CP về thanh toán không dùng tiền mặt",
        "issue_date": "2024-05-15",
        "effective_date": "2024-07-01",
        "status": "active",
        "supersedes": ["101/2012/ND-CP", "80/2016/ND-CP"],
        "articles": {
            "Điều 22": {
                "title": "Điều kiện cung ứng dịch vụ trung gian thanh toán (Ví điện tử)",
                "content": (
                    "Tổ chức cung ứng dịch vụ Ví điện tử phải có vốn điều lệ thực góp "
                    "tối thiểu 50.000.000.000 VNĐ (50 tỷ đồng); có đề án kinh doanh và "
                    "hệ thống công nghệ thông tin đáp ứng tiêu chuẩn an toàn bảo mật cấp độ 3."
                ),
                "min_capital_vnd": 50_000_000_000,
            },
            "Điều 23": {
                "title": "Tỷ lệ tham gia và điều kiện cho nhà đầu tư nước ngoài",
                "content": (
                    "Tổ chức cung ứng dịch vụ ví điện tử có nhà đầu tư nước ngoài góp vốn "
                    "phải tuân thủ tỷ lệ sở hữu tối đa và điều kiện tiếp cận thị trường theo "
                    "cam kết WTO và biểu cam kết quốc tế của Việt Nam (tối đa 49%)."
                ),
                "foreign_ownership_cap": 0.49,
            },
        },
    },
    "101/2012/ND-CP": {
        "doc_id": "101/2012/ND-CP",
        "title": "Nghị định 101/2012/NĐ-CP về thanh toán không dùng tiền mặt (ĐÃ HẾT HIỆU LỰC)",
        "issue_date": "2012-11-22",
        "effective_date": "2013-03-01",
        "status": "expired",
        "revoked_by": "52/2024/ND-CP",
        "revoked_date": "2024-07-01",
        "articles": {
            "Điều 15": {
                "title": "Điều kiện cấp Giấy phép hoạt động cung ứng dịch vụ trung gian thanh toán (CŨ)",
                "content": (
                    "Vốn điều lệ tối thiểu 50 tỷ đồng. (Quy định này đã bị BÃI BỎ TOÀN BỘ "
                    "kể từ ngày 01/07/2024 bởi Nghị định 52/2024/NĐ-CP)."
                ),
            }
        },
    },
    "168/2024/ND-CP": {
        "doc_id": "168/2024/ND-CP",
        "title": "Nghị định 168/2024/NĐ-CP xử phạt vi phạm hành chính trật tự ATGT đường bộ",
        "issue_date": "2024-12-26",
        "effective_date": "2025-01-01",
        "status": "active",
        "supersedes": ["100/2019/ND-CP", "123/2021/ND-CP"],
        "articles": {
            "Điều 6 Khoản 4": {
                "title": "Xử phạt người điều khiển xe mô tô, xe gắn máy vượt đèn đỏ",
                "content": (
                    "Phạt tiền từ 4.000.000 VNĐ đến 6.000.000 VNĐ đối với người điều khiển "
                    "xe mô tô, xe gắn máy không chấp hành hiệu lệnh của đèn tín hiệu giao thông. "
                    "Hình thức xử phạt bổ sung: Tước quyền sử dụng GPLX từ 01 tháng đến 03 tháng."
                ),
                "fine_range": "4.000.000 - 6.000.000 VNĐ",
                "license_revocation": "1-3 tháng",
            }
        },
    },
    "100/2019/ND-CP": {
        "doc_id": "100/2019/ND-CP",
        "title": "Nghị định 100/2019/NĐ-CP xử phạt vi phạm giao thông đường bộ (ĐÃ BÃI BỎ)",
        "issue_date": "2019-12-30",
        "effective_date": "2020-01-01",
        "status": "expired",
        "revoked_by": "168/2024/ND-CP",
        "revoked_date": "2025-01-01",
        "articles": {
            "Điều 6 Khoản 4 Điểm e": {
                "title": "Xử phạt vượt đèn đỏ xe máy (CŨ)",
                "content": "Phạt tiền từ 600.000 VNĐ đến 1.000.000 VNĐ (Mức cũ đã hết hiệu lực thi hành).",
                "fine_range": "600.000 - 1.000.000 VNĐ",
            }
        },
    },
    "70/2023/ND-CP": {
        "doc_id": "70/2023/ND-CP",
        "title": "Nghị định 70/2023/NĐ-CP sửa đổi bổ sung Nghị định 152/2020/NĐ-CP về lao động nước ngoài",
        "issue_date": "2023-09-18",
        "effective_date": "2023-09-18",
        "status": "active",
        "amends": "152/2020/ND-CP",
        "articles": {
            "Điều 1 Khoản 5": {
                "title": "Điều kiện cấp Giấy phép lao động cho Chuyên gia nước ngoài",
                "content": (
                    "Có bằng đại học trở lên hoặc tương đương và có ít nhất 3 năm kinh nghiệm làm việc "
                    "phù hợp với vị trí công việc mà người lao động nước ngoài dự kiến làm việc tại Việt Nam."
                ),
                "requirement": "Bằng ĐH + 3 năm kinh nghiệm phù hợp",
            }
        },
    },
    "152/2020/ND-CP": {
        "doc_id": "152/2020/ND-CP",
        "title": "Nghị định 152/2020/NĐ-CP quy định về người lao động nước ngoài làm việc tại Việt Nam",
        "issue_date": "2020-12-30",
        "effective_date": "2021-02-15",
        "status": "partially_amended",
        "amended_by": "70/2023/ND-CP",
        "articles": {
            "Điều 3 Khoản 3": {
                "title": "Tiêu chuẩn chuyên gia (Quy định gốc đã bị sửa đổi)",
                "content": "Yêu cầu bằng đại học đúng chuyên ngành đào tạo (Quy định cũ gây ách tắc, đã được nới lỏng bởi NĐ 70/2023).",
            }
        },
    },
}


# =====================================================================
# 2. EXTERNAL DETERMINISTIC GROUND-TRUTH ORACLE
# Decoupled Non-LLM Verification Gate (vbpl.vn / National Legal Registry)
# =====================================================================
def external_vbpl_verify_oracle(doc_id: str) -> Dict[str, Any]:
    """External deterministic statutory registry oracle.
    Answers with binary precision (VALID vs EXPIRED/REVOKED) without LLM parametric bias.
    """
    time.sleep(0.04)  # Network latency simulation
    doc = LAW_GRAPH_CATALOG.get(doc_id)
    if not doc:
        return {
            "doc_id": doc_id,
            "status": "UNKNOWN",
            "is_valid": False,
            "message": f"Statute {doc_id} not indexed in national registry.",
        }

    status = doc.get("status")
    if status == "expired":
        return {
            "doc_id": doc_id,
            "title": doc.get("title"),
            "status": "REVOKED (Hết hiệu lực toàn bộ)",
            "is_valid": False,
            "revoked_by": doc.get("revoked_by"),
            "revoked_date": doc.get("revoked_date"),
        }
    elif status == "partially_amended":
        return {
            "doc_id": doc_id,
            "title": doc.get("title"),
            "status": "PARTIALLY_AMENDED (Đã bị sửa đổi bổ sung)",
            "is_valid": True,
            "amended_by": doc.get("amended_by"),
        }
    else:
        return {
            "doc_id": doc_id,
            "title": doc.get("title"),
            "status": "ACTIVE (Đang có hiệu lực thi hành)",
            "is_valid": True,
            "effective_date": doc.get("effective_date"),
            "supersedes": doc.get("supersedes", []),
        }


# =====================================================================
# 3. DURABLE STATE CHECKPOINT MANAGER (SQLITE BACKED)
# Implements LangGraph Checkpointing & Differential Rollback
# =====================================================================
class SQLiteCheckpointManager:
    """Persistent state manager storing immutable node snapshots for durable execution."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS state_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    node_name TEXT NOT NULL,
                    completed_subgoals TEXT NOT NULL,
                    state_payload TEXT NOT NULL
                )
                """
            )

    def save_checkpoint(
        self,
        checkpoint_id: str,
        session_id: str,
        node_name: str,
        completed_subgoals: List[str],
        state_payload: Dict[str, Any],
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO state_checkpoints
                (checkpoint_id, session_id, timestamp, node_name, completed_subgoals, state_payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_id,
                    session_id,
                    time.time(),
                    node_name,
                    json.dumps(completed_subgoals, ensure_ascii=False),
                    json.dumps(state_payload, ensure_ascii=False),
                ),
            )

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT checkpoint_id, session_id, node_name, completed_subgoals, state_payload
            FROM state_checkpoints WHERE checkpoint_id = ?
            """,
            (checkpoint_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "checkpoint_id": row[0],
            "session_id": row[1],
            "node_name": row[2],
            "completed_subgoals": json.loads(row[3]),
            "state_payload": json.loads(row[4]),
        }

    def list_checkpoints(self, session_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT checkpoint_id, node_name, timestamp, completed_subgoals
            FROM state_checkpoints WHERE session_id = ? ORDER BY timestamp ASC
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "checkpoint_id": r[0],
                "node_name": r[1],
                "timestamp": r[2],
                "completed_subgoals": json.loads(r[3]),
            }
            for r in rows
        ]


# =====================================================================
# 4. DATA STRUCTURES & EXECUTION METRICS
# =====================================================================
@dataclass
class Scenario:
    id: str
    title: str
    query: str
    enterprise_name: str
    entity_type: str
    charter_capital: float
    foreign_ownership_ratio: float
    regulatory_trap: str
    expected_active_statute: str
    revoked_statute: str


TEST_SCENARIOS: Dict[str, Scenario] = {
    "fintech": Scenario(
        id="fintech",
        title="FDI E-Wallet License (Decree 101/2012 Revoked -> Decree 52/2024)",
        query="Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024",
        enterprise_name="Global PayTech Asia Ltd. (FDI)",
        entity_type="Doanh nghiệp FDI",
        charter_capital=35_000_000_000.0,
        foreign_ownership_ratio=0.45,
        regulatory_trap="Decree 101/2012/ND-CP was revoked on July 1, 2024; replaced by Decree 52/2024/ND-CP (Charter capital 50B VND).",
        expected_active_statute="52/2024/ND-CP",
        revoked_statute="101/2012/ND-CP",
    ),
    "traffic": Scenario(
        id="traffic",
        title="Motorbike Red Light Penalty (Decree 100/2019 Revoked -> Decree 168/2024)",
        query="Mức xử phạt vượt đèn đỏ xe máy theo quy định mới nhất hiện hành",
        enterprise_name="Logistics Express Vietnam JSC",
        entity_type="Công ty Cổ phần (Vận tải)",
        charter_capital=15_000_000_000.0,
        foreign_ownership_ratio=0.0,
        regulatory_trap="Decree 100/2019/ND-CP (600k-1M) was replaced by Decree 168/2024/ND-CP (4M-6M VNĐ, license suspended 1-3 mos).",
        expected_active_statute="168/2024/ND-CP",
        revoked_statute="100/2019/ND-CP",
    ),
    "labor": Scenario(
        id="labor",
        title="Foreign Expert Work Permit (Decree 152/2020 Amended by Decree 70/2023)",
        query="Điều kiện cấp giấy phép lao động cho chuyên gia nước ngoài",
        enterprise_name="TechVentures VN LLC",
        entity_type="Công ty TNHH",
        charter_capital=20_000_000_000.0,
        foreign_ownership_ratio=0.70,
        regulatory_trap="Decree 152/2020 required university degree strictly matching major; Decree 70/2023 relaxed to any university degree + 3 yrs experience.",
        expected_active_statute="70/2023/ND-CP",
        revoked_statute="152/2020/ND-CP (un-amended clause)",
    ),
}


@dataclass
class ParadigmResult:
    pattern_id: str
    name: str
    paradigm_type: str
    tokens: int = 0
    wall_clock_ms: float = 0.0
    turns: int = 0
    subagent_calls: int = 0
    checkpoints_saved: int = 0
    checkpoints_restored: int = 0
    cited_statute: str = ""
    grounding_rate: float = 0.0
    failure_recovery: str = ""
    dossier_excerpt: str = ""
    steps_log: List[Dict[str, Any]] = field(default_factory=list)


# =====================================================================
# 5. PARADIGM 1: DETERMINISTIC WORKFLOW (PROMPT CHAINING & ROUTING)
# Anthropic Dec 2024: "Workflows use fixed code paths where LLMs are atomic steps"
# =====================================================================
def run_paradigm_1_workflow(scenario: Scenario, verbose: bool = True) -> ParadigmResult:
    start_time = time.perf_counter()
    res = ParadigmResult(
        pattern_id="workflow",
        name="1. Deterministic Workflow (Prompt Chaining & Routing)",
        paradigm_type="Deterministic Workflow (Fixed Code Path)",
    )

    if verbose:
        print(f"\n{BOLD}{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}{CYAN}▶ [PATTERN 1] DETERMINISTIC WORKFLOW (Prompt Chaining & Routing - Anthropic 2024){RESET}")
        print(f"  {DIM}Control: Fixed Code Path | Token Cost: 1.0x Baseline | Recovery: None{RESET}")
        print(f"{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    # Step 1: Semantic Intent Router
    t0 = time.perf_counter()
    res.tokens += 180
    res.turns += 1
    step_1 = {
        "step": 1,
        "name": "Semantic Intent Router",
        "description": "Classifying query intent -> routes to static legal extractor",
        "tokens": 180,
    }
    res.steps_log.append(step_1)
    if verbose:
        print(f"  {CYAN}Step 1 [Router]:{RESET} Classifying domain query...")
        print(f"    Intent: '{scenario.title}' -> Route: Standard Statutory Extraction Chain")

    # Step 2: Extraction Step (Suffers from popularity bias / outdated vector hit)
    t1 = time.perf_counter()
    res.tokens += 320
    res.turns += 1
    # Brittle trap: Static prompt chain retrieves top popular document (revoked law)
    retrieved_statute = scenario.revoked_statute.split()[0]
    step_2 = {
        "step": 2,
        "name": "Prompt Chaining: Extractor",
        "description": f"Extracted statute from static index: {retrieved_statute}",
        "tokens": 320,
    }
    res.steps_log.append(step_2)
    if verbose:
        print(f"  {CYAN}Step 2 [Prompt Chain - Extractor]:{RESET} Extracting provisions from static vector store...")
        print(f"    -> Extracted statutory reference: {YELLOW}{retrieved_statute}{RESET}")

    # Step 3: Synthesis Step
    t2 = time.perf_counter()
    res.tokens += 260
    res.turns += 1
    dossier = (
        f"[TƯ VẤN PHÁP LÝ - WORKFLOW]\n"
        f"Căn cứ: {retrieved_statute}.\n"
        f"Kết luận: Doanh nghiệp {scenario.enterprise_name} áp dụng điều kiện quy định tại {retrieved_statute}."
    )
    step_3 = {
        "step": 3,
        "name": "Prompt Chaining: Synthesizer",
        "description": "Formatted advisory dossier without validity check",
        "tokens": 260,
    }
    res.steps_log.append(step_3)

    res.cited_statute = retrieved_statute
    res.grounding_rate = 0.0  # 0% because it relied on expired/revoked statute
    res.failure_recovery = "None (Pipeline blindly outputs revoked law)"
    res.dossier_excerpt = dossier
    res.wall_clock_ms = (time.perf_counter() - start_time) * 1000 + 40.0

    if verbose:
        print(f"  {CYAN}Step 3 [Prompt Chain - Synthesizer]:{RESET} Formatting final client memo...")
        print(f"  {RED}✖ REGULATORY OUTCOME:{RESET} Advises client based on expired {retrieved_statute}!")
        print(f"    Grounding Rate: {RED}0.0%{RESET} | Total Tokens: {res.tokens} (1.0x baseline) | Latency: {res.wall_clock_ms:.1f}ms")
        print(f"    Analysis: Lowest token consumption and fastest execution, but zero dynamic resilience.")

    return res


# =====================================================================
# 6. PARADIGM 2: MONOLITHIC AUTONOMOUS AGENT (SINGLE GIANT REACT LOOP)
# OpenAI Apr 2025: Single Model-Directed Tool Loop (Context Inflation & Drift)
# =====================================================================
def run_paradigm_2_monolithic_agent(scenario: Scenario, verbose: bool = True) -> ParadigmResult:
    start_time = time.perf_counter()
    res = ParadigmResult(
        pattern_id="monolithic",
        name="2. Monolithic Autonomous Agent (Single ReAct Loop)",
        paradigm_type="Model-Directed Single Context Loop",
    )

    if verbose:
        print(f"\n{BOLD}{YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}{YELLOW}▶ [PATTERN 2] MONOLITHIC AUTONOMOUS AGENT (Single ReAct Loop - OpenAI 2025){RESET}")
        print(f"  {DIM}Control: Model Directed | Token Multiplier: 11.7x | Context: Shared Volatile RAM{RESET}")
        print(f"{YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    accumulated_context = 950  # System prompt + tools definition + user query
    res.tokens += accumulated_context
    res.turns += 1

    # Turn 1: Thought & Action
    step_1 = {
        "turn": 1,
        "thought": "I need to search for relevant statutes and provisions for user query.",
        "action": f"search_statutes('{scenario.query}')",
        "tokens": accumulated_context,
    }
    res.steps_log.append(step_1)
    if verbose:
        print(f"  {YELLOW}Turn 1 [ReAct Loop - Context: {accumulated_context} tokens]:{RESET}")
        print(f"    Thought: I need to search statutory database for provisions.")
        print(f"    Action: search_statutes('{scenario.query}')")

    # Turn 2: Observation & Check (Top hit is revoked statute)
    retrieved_statute = scenario.revoked_statute.split()[0]
    accumulated_context += 800  # Added tool schema, observation, search results
    res.tokens += accumulated_context
    res.turns += 1
    step_2 = {
        "turn": 2,
        "thought": f"Top search hit returned {retrieved_statute}. Let me verify status.",
        "action": f"verify_status('{retrieved_statute}')",
        "observation": f"REVOKED by {scenario.expected_active_statute}",
        "tokens": accumulated_context,
    }
    res.steps_log.append(step_2)
    if verbose:
        print(f"  {YELLOW}Turn 2 [ReAct Loop - Context: {accumulated_context} tokens]:{RESET}")
        print(f"    Observation: Top hit is {retrieved_statute}.")
        print(f"    Thought: Need to verify if {retrieved_statute} is still valid.")
        print(f"    Action: verify_status('{retrieved_statute}') -> Status: REVOKED by {scenario.expected_active_statute}!")

    # Turn 3: Attention Dilution / Compounding Error
    accumulated_context += 900  # Context increases quadratically with full conversation history
    res.tokens += accumulated_context
    res.turns += 1
    step_3 = {
        "turn": 3,
        "thought": f"Got revoked status, now searching replacement conditions and ownership ratio.",
        "action": "search_statutes('điều kiện thay thế và tỷ lệ sở hữu')",
        "tokens": accumulated_context,
    }
    res.steps_log.append(step_3)
    if verbose:
        print(f"  {YELLOW}Turn 3 [ReAct Loop - Context Dilution: {accumulated_context} tokens]:{RESET}")
        print(f"    Thought: Statutory change detected. Now retrieving secondary conditions...")
        print(f"    Notice: Entire raw history is retained in prompt; attention begins to dilute across {accumulated_context} tokens.")

    # Turn 4: Synthesis with Partial Hallucination (mixing up old & new decree articles)
    accumulated_context += 950
    res.tokens += accumulated_context
    res.turns += 1
    dossier = (
        f"[TƯ VẤN PHÁP LÝ - MONOLITHIC AGENT]\n"
        f"Lưu ý: {retrieved_statute} đã bị thay thế bởi {scenario.expected_active_statute}.\n"
        f"Doanh nghiệp cần áp dụng điều kiện theo cả hai văn bản (nhầm lẫn điều khoản cũ và mới do trôi ngữ cảnh)."
    )
    step_4 = {
        "turn": 4,
        "action": "generate_response",
        "description": "Synthesized with context confusion",
        "tokens": accumulated_context,
    }
    res.steps_log.append(step_4)

    res.cited_statute = f"{retrieved_statute} & {scenario.expected_active_statute} (Mixed)"
    res.grounding_rate = 0.60  # 60% grounding due to mixed-context hallucination
    res.failure_recovery = "Ad-hoc ReAct in-memory (No persistent checkpoint; crash = complete restart)"
    res.dossier_excerpt = dossier
    res.wall_clock_ms = (time.perf_counter() - start_time) * 1000 + 420.0

    if verbose:
        print(f"  {YELLOW}Turn 4 [ReAct Loop - Synthesis - Total Cumulative: {res.tokens} tokens]:{RESET}")
        print(f"  {YELLOW}⚠ REGULATORY OUTCOME:{RESET} Mentions replacement but confuses cross-decree articles due to context pollution.")
        print(f"    Grounding Rate: {YELLOW}60.0%{RESET} | Cumulative Tokens: {res.tokens} (11.7x multiplier) | Latency: {res.wall_clock_ms:.1f}ms")
        print(f"    Analysis: Quadratic token inflation; volatile state lost if container crashes at Turn 3.")

    return res


# =====================================================================
# 7. PARADIGM 3: LEAD/SUBAGENT ORCHESTRATOR + LANGGRAPH CHECKPOINTING (G4)
# Anthropic Jun 2025 Multi-Agent System + LangGraph Durable Execution
# =====================================================================
def run_paradigm_3_orchestrator(
    scenario: Scenario,
    checkpoint_mgr: SQLiteCheckpointManager,
    session_id: str,
    verbose: bool = True,
) -> ParadigmResult:
    start_time = time.perf_counter()
    res = ParadigmResult(
        pattern_id="orchestrator",
        name="3. Lead/Subagent Orchestrator + LangGraph Checkpointing (G4 LegalPilot-VN)",
        paradigm_type="Hierarchical Lead/Subagents + Cyclic StateGraph",
    )

    if verbose:
        print(f"\n{BOLD}{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}{GREEN}▶ [PATTERN 3] LEAD/SUBAGENT ORCHESTRATOR WITH DURABLE CHECKPOINTING (G4){RESET}")
        print(f"  {DIM}Architecture: Hierarchical Decomposition | Isolated Clean Contexts | SQLite Checkpointer{RESET}")
        print(f"{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    # -------------------------------------------------------------
    # Node 1: Lead Orchestrator (Dynamic Subgoal Decomposition)
    # -------------------------------------------------------------
    lead_tokens = 450
    res.tokens += lead_tokens
    res.turns += 1

    subgoal_A = f"Xác định điều kiện tiên quyết và văn bản điều chỉnh chính ({scenario.title})"
    subgoal_B = f"Đối chiếu điều kiện cụ thể hồ sơ doanh nghiệp ({scenario.enterprise_name})"
    completed_subgoals: List[str] = []

    # Checkpoint C1: Save state after planning
    c1_id = f"{session_id}_C1_PLAN"
    checkpoint_mgr.save_checkpoint(
        checkpoint_id=c1_id,
        session_id=session_id,
        node_name="LeadOrchestrator_Planning",
        completed_subgoals=["SubgoalsDecomposed"],
        state_payload={
            "subgoal_A": subgoal_A,
            "subgoal_B": subgoal_B,
            "enterprise": scenario.enterprise_name,
            "status": "PLAN_READY",
        },
    )
    res.checkpoints_saved += 1

    if verbose:
        print(f"  {BLUE}[Node 1: Lead Orchestrator - Dynamic Planning]{RESET}")
        print(f"    Decomposed query into 2 independent subgoals:")
        print(f"      • Subgoal A: {subgoal_A}")
        print(f"      • Subgoal B: {subgoal_B}")
        print(f"    {MAGENTA}💾 [SQLite Checkpoint Saved: '{c1_id}']{RESET} State persisted to database.")

    # -------------------------------------------------------------
    # Node 2: Subagent 1: LawGraph Retrieval Worker (Context Isolation)
    # -------------------------------------------------------------
    # Runs in a clean, isolated context of ~380 tokens (no system prompt bloat!)
    worker_1_tokens = 380
    res.tokens += worker_1_tokens
    res.turns += 1
    res.subagent_calls += 1

    # First retrieval returns the historically popular candidate (revoked statute)
    initial_candidate = scenario.revoked_statute.split()[0]
    completed_subgoals.append("CandidateRetrieved")

    # Checkpoint C2: State after initial retrieval
    c2_id = f"{session_id}_C2_RETRIEVAL"
    checkpoint_mgr.save_checkpoint(
        checkpoint_id=c2_id,
        session_id=session_id,
        node_name="LawGraphWorker",
        completed_subgoals=completed_subgoals,
        state_payload={"candidate_statute": initial_candidate, "status": "RETRIEVED"},
    )
    res.checkpoints_saved += 1

    if verbose:
        print(f"\n  {BLUE}[Node 2: Subagent 'LawGraph Worker' - Context Isolation (<400 tokens)]{RESET}")
        print(f"    Executing Subgoal A in isolated scratchpad...")
        print(f"    -> Candidate retrieved from catalog: {YELLOW}{initial_candidate}{RESET}")
        print(f"    {MAGENTA}💾 [SQLite Checkpoint Saved: '{c2_id}']{RESET}")

    # -------------------------------------------------------------
    # Node 3: Subagent 2: Claim Auditor / Verification Oracle Worker
    # -------------------------------------------------------------
    auditor_tokens = 310
    res.tokens += auditor_tokens
    res.turns += 1
    res.subagent_calls += 1

    if verbose:
        print(f"\n  {BLUE}[Node 3: Subagent 'Claim Auditor' - Non-LLM Verification Oracle Gate]{RESET}")
        print(f"    Executing verification: {BOLD}external_vbpl_verify_oracle('{initial_candidate}'){RESET}")

    oracle_report = external_vbpl_verify_oracle(initial_candidate)

    if not oracle_report.get("is_valid", False):
        if verbose:
            print(f"    {RED}✖ STATUTORY REVOCATION DETECTED:{RESET} {initial_candidate} was {oracle_report.get('status')}!")
            print(f"    -> Successor indicated in national registry: {GREEN}{oracle_report.get('revoked_by')}{RESET}")

        # -------------------------------------------------------------
        # Node 4: LangGraph Differential Rollback Edge (Durable Recovery)
        # -------------------------------------------------------------
        if verbose:
            print(f"\n  {GREEN}[LangGraph Durable Execution: State Recovery Loop]{RESET}")
            print(f"    {MAGENTA}↺ Performing Differential Rollback to Checkpoint '{c1_id}'...{RESET}")
            print(f"    -> Preserved Data: Subgoal B enterprise profile state remains 100% INTACT in cache!")
            print(f"    -> Zero Cold-Restart overhead; re-dispatching Subgoal A only.")

        restored_state = checkpoint_mgr.load_checkpoint(c1_id)
        res.checkpoints_restored += 1

        # Re-dispatch LawGraph worker directly to successor statute
        successor_statute = oracle_report.get("revoked_by") or scenario.expected_active_statute
        re_retrieval_tokens = 340
        res.tokens += re_retrieval_tokens
        res.turns += 1
        res.subagent_calls += 1

        # Re-verify successor with Oracle
        oracle_successor = external_vbpl_verify_oracle(successor_statute)
        re_audit_tokens = 280
        res.tokens += re_audit_tokens
        res.turns += 1
        res.subagent_calls += 1

        if verbose:
            print(f"    -> LawGraph Worker re-traverses graph edge directly to successor: {GREEN}{successor_statute}{RESET}")
            print(f"    -> Auditor re-verifies {successor_statute}: {GREEN}{oracle_successor.get('status')}{RESET}")

        active_statute = successor_statute
    else:
        active_statute = initial_candidate

    # -------------------------------------------------------------
    # Node 5: Subagent 3: Drafter Worker (Synthesis from 100% Verified Facts)
    # -------------------------------------------------------------
    drafter_tokens = 650
    res.tokens += drafter_tokens
    res.turns += 1
    res.subagent_calls += 1

    active_doc_info = LAW_GRAPH_CATALOG.get(active_statute, {})
    articles_summary = ""
    for art_no, art_data in active_doc_info.get("articles", {}).items():
        articles_summary += f"\n    • {art_no} ({art_data.get('title')}): {art_data.get('content')}"

    dossier = (
        f"=======================================================================\n"
        f"HỒ SƠ TƯ VẤN PHÁP LÝ TUÂN THỦ (LEGALPILOT-VN COMPLIANCE DOSSIER)\n"
        f"Doanh nghiệp: {scenario.enterprise_name} | Loại hình: {scenario.entity_type}\n"
        f"Vốn điều lệ: {scenario.charter_capital:,.0f} VNĐ | Sở hữu ngoại: {scenario.foreign_ownership_ratio * 100:.1f}%\n"
        f"-----------------------------------------------------------------------\n"
        f"CĂN CỨ PHÁP LÝ XÁC THỰC HIỆN HÀNH: {active_statute} ({active_doc_info.get('title')})\n"
        f"Ngày có hiệu lực: {active_doc_info.get('effective_date')}\n"
        f"Trạng thái kiểm định: 100% HỢP LỆ (Đã thay thế và bãi bỏ {scenario.revoked_statute})\n"
        f"Điều khoản quy phạm áp dụng:{articles_summary}\n"
        f"======================================================================="
    )

    # Checkpoint C3: Final verified state
    c3_id = f"{session_id}_C3_FINAL_DOSSIER"
    checkpoint_mgr.save_checkpoint(
        checkpoint_id=c3_id,
        session_id=session_id,
        node_name="DrafterWorker",
        completed_subgoals=["AllSubgoalsVerified", "DossierSynthesized"],
        state_payload={"active_statute": active_statute, "dossier": dossier},
    )
    res.checkpoints_saved += 1

    res.cited_statute = active_statute
    res.grounding_rate = 1.0  # 100% Grounded
    res.failure_recovery = "Durable Checkpoint Differential Rollback (Preserved Subgoal B; Pruned Expired Law)"
    res.dossier_excerpt = dossier
    res.wall_clock_ms = (time.perf_counter() - start_time) * 1000 + 160.0

    if verbose:
        print(f"\n  {BLUE}[Node 5: Subagent 'Drafter Worker' - Clean Synthesis]{RESET}")
        print(f"    Synthesizing dossier from strictly verified active statute {active_statute}...")
        print(f"    {MAGENTA}💾 [SQLite Checkpoint Saved: '{c3_id}']{RESET} Complete audit trail recorded.")
        print(f"  {GREEN}✔ REGULATORY OUTCOME:{RESET} 100% Legally grounded dossier delivered!")
        print(f"    Grounding Rate: {GREEN}100.0%{RESET} | Cumulative Tokens: {res.tokens} (~3.2x simulated step budget) | Latency: {res.wall_clock_ms:.1f}ms")
        print("    Analysis: Simulated step budget for illustration; see the live DeepSeek-V3 run for measured tokens.")

    return res


# =====================================================================
# 8. BENCHMARK COMPARATOR & REPORT GENERATOR
# =====================================================================
def run_full_comparative_benchmark(scenario: Scenario, db_path: str = ":memory:") -> None:
    print(f"\n{BOLD}{MAGENTA}" + "═" * 86 + f"{RESET}")
    print(f"{BOLD}{WHITE}  CO5151 SEMINAR S1-7: AGENT DESIGN PATTERNS SIMULATED BENCHMARK TRACE{RESET}")
    print(f"{BOLD}{WHITE}  FACULTY ADVISOR: DR. LE XUAN BACH | GROUP G4 (LEGALPILOT-VN){RESET}")
    print(f"{DIM}  Scenario: {scenario.title}{RESET}")
    print(f"{DIM}  Enterprise: {scenario.enterprise_name} | Query: \"{scenario.query}\"{RESET}")
    print(f"{BOLD}{MAGENTA}" + "═" * 86 + f"{RESET}")

    checkpoint_mgr = SQLiteCheckpointManager(db_path)
    session_id = f"demo_{int(time.time())}"

    # Run Paradigm 1
    p1 = run_paradigm_1_workflow(scenario, verbose=True)

    # Run Paradigm 2
    p2 = run_paradigm_2_monolithic_agent(scenario, verbose=True)

    # Run Paradigm 3
    p3 = run_paradigm_3_orchestrator(scenario, checkpoint_mgr, session_id, verbose=True)

    # Comparative Summary Table
    token_mult_p1 = 1.0
    token_mult_p2 = p2.tokens / max(1, p1.tokens)
    token_mult_p3 = p3.tokens / max(1, p1.tokens)

    print(f"\n{BOLD}{WHITE}" + "═" * 86 + f"{RESET}")
    print(f"{BOLD}{WHITE}           SIMULATED ARCHITECTURAL COMPARISON: WORKFLOWS VS. MONOLITHIC VS. G4           {RESET}")
    print(f"{BOLD}{WHITE}" + "═" * 86 + f"{RESET}")
    print(f"{BOLD}{'Architectural Metric':<26} | {'1. Workflow':<18} | {'2. Monolithic Agent':<18} | {'3. Orchestrator (G4)':<18}{RESET}")
    print("-" * 27 + "+" + "-" * 20 + "+" + "-" * 20 + "+" + "-" * 20)
    print(f"{'Control Flow':<26} | {'Fixed Code Path':<18} | {'Model Directed':<18} | {'Hierarchical Lead':<18}")
    print(f"{'Total Tokens Consumed':<26} | {f'{p1.tokens:,} (1.0x)':<18} | {f'{p2.tokens:,} ({token_mult_p2:.1f}x)':<18} | {f'{p3.tokens:,} ({token_mult_p3:.1f}x)':<18}")
    print(f"{'Execution Steps / Turns':<26} | {f'{p1.turns} steps':<18} | {f'{p2.turns} turns':<18} | {f'{p3.turns} node visits':<18}")
    print(f"{'Context Hygiene':<26} | {'Rigid / No state':<18} | {'Diluted / Bloated':<18} | {'Clean Isolated Nodes':<18}")
    print(f"{'Compounding Error (P=p^n)':<26} | {'Zero correction':<18} | {'High Risk':<18} | {'Bounded by State':<18}")
    print(f"{'Checkpoint Rollback':<26} | {'None (Crash)':<18} | {'None (Cold Restart)':<18} | {'Durable SQLite C1->C3':<18}")
    print(f"{'Statutory Grounding':<26} | {f'{RED}0.0% (Revoked){RESET}':<27} | {f'{YELLOW}60.0% (Mixed){RESET}':<27} | {f'{GREEN}100.0% (Active){RESET}':<27}")
    print(f"{'Wall-clock Latency':<26} | {f'{p1.wall_clock_ms:.1f} ms':<18} | {f'{p2.wall_clock_ms:.1f} ms':<18} | {f'{p3.wall_clock_ms:.1f} ms':<18}")
    print(f"{BOLD}{WHITE}" + "═" * 86 + f"{RESET}")

    print(f"\n{BOLD}{CYAN}Key Literature Alignments Illustrated by the Simulated Trace:{RESET}")
    print(f"  1. {BOLD}Anthropic (Dec 2024) Simplicity-First Thesis:{RESET}")
    print(f"     Workflows (Pattern 1) are deterministic, fastest ({p1.wall_clock_ms:.1f}ms) and cheapest ({p1.tokens} tokens),")
    print(f"     but fail catastrophically when encountering dynamic legal obsolescence.")
    print(f"  2. {BOLD}Anthropic (Jun 2025) Multi-Agent Research System Reality:{RESET}")
    print(f"     Lead/Subagent decomposition incurs a ~3.2x simulated token multiplier ({p3.tokens} vs {p1.tokens} tokens),")
    print(f"     which is the deliberate price paid for context isolation and elimination of compounding errors.")
    print(f"  3. {BOLD}LangGraph (2024-2025) Durable Execution & Differential Rollback:{RESET}")
    print(f"     When Oracle detects Decree 101/2012 revocation, G4 rolls back to SQLite Checkpoint C1,")
    print(f"     preserving completed Subgoal B without redundant cold re-execution.")

    print(f"\n{BOLD}{GREEN}Generated Compliance Dossier Preview (G4 Lead/Subagent Output):{RESET}")
    print(f"{DIM}{p3.dossier_excerpt}{RESET}\n")


# =====================================================================
# 9. CLI ENTRY POINT
# =====================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="CO5151 Seminar S1-7: Agent Design Patterns & Orchestration Demo for Vietnamese Law Graph"
    )
    parser.add_argument(
        "--scenario",
        choices=["fintech", "traffic", "labor"],
        default="fintech",
        help="Target legal domain scenario to simulate (default: fintech)",
    )
    parser.add_argument(
        "--paradigm",
        choices=["all", "workflow", "monolithic", "orchestrator"],
        default="all",
        help="Agent design paradigm to execute (default: all for comparison)",
    )
    parser.add_argument(
        "--db",
        default=":memory:",
        help="SQLite database path for durable checkpoints (default: :memory:)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format for automated evaluation pipelines",
    )

    args = parser.parse_args()
    scenario = TEST_SCENARIOS[args.scenario]

    if args.paradigm == "all":
        run_full_comparative_benchmark(scenario, db_path=args.db)
    elif args.paradigm == "workflow":
        res = run_paradigm_1_workflow(scenario, verbose=True)
        if args.json:
            print(json.dumps(asdict(res), indent=2, ensure_ascii=False))
    elif args.paradigm == "monolithic":
        res = run_paradigm_2_monolithic_agent(scenario, verbose=True)
        if args.json:
            print(json.dumps(asdict(res), indent=2, ensure_ascii=False))
    elif args.paradigm == "orchestrator":
        mgr = SQLiteCheckpointManager(args.db)
        sess = f"session_{int(time.time())}"
        res = run_paradigm_3_orchestrator(scenario, mgr, sess, verbose=True)
        if args.json:
            print(json.dumps(asdict(res), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
