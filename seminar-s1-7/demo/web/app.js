/**
 * CO5151 Seminar S1-7: Agent Design Patterns & Orchestration
 * Vietnamese Law Graph Compliance Interactive Workbench
 * Group G4: Dang Lam Tung · Nguyen Trung Phong · Vu Viet Hung
 * Faculty Advisor: Dr. Le Xuan Bach
 */

// ============================================================================
// 1. STATUTORY LAW GRAPH & SCENARIOS DATABASE
// ============================================================================
const SCENARIOS = {
  fintech: {
    id: "fintech",
    title: "1. Cấp phép Ví điện tử FDI (NĐ 101/2012 hết hiệu lực → NĐ 52/2024)",
    query: "Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024",
    enterprise: "Global PayTech Asia Ltd. (FDI)",
    entityType: "Doanh nghiệp FDI",
    capital: "35.000.000.000 VNĐ",
    foreignRatio: "45.0%",
    regulatoryTrap: "Bẫy pháp lý: NĐ 101/2012 bị bãi bỏ từ 01/07/2024; thay thế bằng NĐ 52/2024 (Vốn ĐL tối thiểu 50 tỷ VNĐ).",
    initialDoc: "101/2012/ND-CP",
    successorDoc: "52/2024/ND-CP",
    subgoalA: "Xác định điều kiện cấp phép ví điện tử và mức vốn điều lệ tối thiểu",
    subgoalB: "Đối chiếu trần sở hữu nước ngoài (Room ngoại tối đa 49%)",
    initialClause: {
      docId: "101/2012/ND-CP",
      article: "Điều 15",
      title: "Điều kiện cấp phép (ĐÃ HẾT HIỆU LỰC)",
      content: "Vốn điều lệ tối thiểu 50 tỷ đồng (Văn bản đã bị bãi bỏ toàn bộ từ ngày 01/07/2024 bởi NĐ 52/2024).",
      status: "expired"
    },
    successorClause: {
      docId: "52/2024/ND-CP",
      article: "Điều 22 & 23",
      title: "Điều kiện cung ứng Ví điện tử & Tỷ lệ sở hữu nước ngoài",
      content: "Vốn điều lệ tối thiểu 50.000.000.000 VNĐ; tỷ lệ nhà đầu tư nước ngoài tuân thủ cam kết WTO (tối đa 49%).",
      status: "active"
    },
    diffText: `● [PRESERVED IN CACHE] enterprise_profile (Vốn: 35 tỷ, FDI: 45%) - KHÔNG TÍNH LẠI
● [PRESERVED IN CACHE] Subgoal B (Tỷ lệ sở hữu nước ngoài đạt chuẩn Điều 23)
- [PRUNED FROM MEMORY] 101/2012/ND-CP:Điều 15 (Bãi bỏ bởi vbpl_verify_oracle)
+ [INSERTED TO MEMORY] 52/2024/ND-CP:Điều 22 & 23 (Hiệu lực từ 01/07/2024)`,
    p1: {
      steps: [
        { name: "Router Phân Loại Ý Định", desc: "Phân loại câu hỏi sang luồng cấp phép Ví điện tử", tokens: 180, status: "active" },
        { name: "Prompt Chain: Trích Xuất Căn Cứ", desc: "Vector search trả về NĐ 101/2012 (độ phổ biến cao nhất)", tokens: 320, status: "failed" },
        { name: "Prompt Chain: Tổng Hợp Văn Bản", desc: "Soạn thảo thư tư vấn căn cứ theo NĐ 101/2012", tokens: 260, status: "failed" }
      ],
      tokens: 760,
      latency: 42,
      grounding: "0% (Trích dẫn luật hết hiệu lực)",
      recovery: "Không thể phục hồi (Workflow mù hiệu lực)",
      outcomeClass: "result-danger",
      dossier: "[CẢNH BÁO TƯ VẤN SAI LỆCH - WORKFLOW]\nCăn cứ: Nghị định 101/2012/NĐ-CP (ĐÃ BÃI BỎ).\nHồ sơ nộp lên NHNN sẽ BỊ BÁC BỎ NGAY LẬP TỨC do viện dẫn sai văn bản quy phạm pháp luật!"
    },
    p2: {
      steps: [
        { name: "Turn 1 [ReAct Loop - Thought/Action]", desc: "Search: 'quy định cấp phép ví điện tử' (System prompt + History)", tokens: 950, status: "active" },
        { name: "Turn 2 [ReAct Loop - Observation]", desc: "Top hit NĐ 101/2012 -> Verify status: REVOKED by 52/2024!", tokens: 1750, status: "active" },
        { name: "Turn 3 [ReAct Loop - Context Drift]", desc: "Search thêm tỷ lệ sở hữu ngoại; attention bị loãng qua 2.650 tokens", tokens: 2650, status: "active" },
        { name: "Turn 4 [ReAct Loop - Tổng Hợp]", desc: "Tổng hợp toàn bộ lịch sử; nhầm lẫn điều khoản giữa NĐ 101 và 52", tokens: 3600, status: "failed" }
      ],
      tokens: 8950,
      latency: 420,
      grounding: "60% (Trôi dạt ngữ cảnh / Ảo giác)",
      recovery: "ReAct tùy tiện trong RAM (Sập tiến trình = Mất trắng)",
      outcomeClass: "result-warning",
      dossier: "[TƯ VẤN BỊ XÁO TRỘN NGỮ CẢNH - MONOLITHIC AGENT]\nNhận diện được NĐ 52/2024 nhưng trộn lẫn điều kiện cũ từ NĐ 101/2012 vào quy trình thẩm định. Tiêu tốn 8.950 tokens (11.8x)."
    },
    p3: {
      steps: [
        { name: "Node 1: Lead Orchestrator - Phân Rã", desc: "Decompose thành Subgoal A (Điều kiện cấp phép) & Subgoal B (Room ngoại FDI)", tokens: 450, status: "active", chk: "C1_PLAN" },
        { name: "Node 2: LawGraph Worker (Cô Lập)", desc: "Tra cứu Subgoal A trong context sạch < 400 tokens -> Trả về NĐ 101/2012", tokens: 380, status: "active", chk: "C2_RETRIEVAL" },
        { name: "Node 3: Auditor Oracle (Kiểm Định)", desc: "Gọi vbpl_verify_oracle('101/2012') -> CẢNH BÁO: Hết hiệu lực thi hành!", tokens: 310, status: "failed" },
        { name: "Node 4: LangGraph Rollback Vi Sai", desc: "Rollback về C1_PLAN (Subgoal B được bảo toàn!); Chuyển tiếp NĐ 52/2024", tokens: 620, status: "recovered", chk: "C1_RESTORE" },
        { name: "Node 5: Drafter Worker (Tổng Hợp)", desc: "Soạn thảo hồ sơ tuân thủ 100% từ NĐ 52/2024 (Điều 22 & 23)", tokens: 650, status: "active", chk: "C3_FINAL" }
      ],
      tokens: 2410,
      latency: 245,
      grounding: "100% (Xác thực pháp lý tuyệt đối)",
      recovery: "Durable SQLite Rollback (Phục hồi vi sai)",
      outcomeClass: "result-success",
      dossier: "HỒ SƠ TƯ VẤN PHÁP LÝ TUÂN THỦ (LEGALPILOT-VN)\n• Doanh nghiệp: Global PayTech Asia Ltd. (FDI) | Vốn: 35 tỷ VNĐ\n• Căn cứ pháp lý: Nghị định 52/2024/NĐ-CP (Có hiệu lực từ 01/07/2024)\n• Cảnh báo tuân thủ: Vốn điều lệ hiện tại (35 tỷ) THIẾU 15 TỶ so với mức tối thiểu 50 tỷ quy định tại Điều 22 Khoản 1!\n• Tỷ lệ sở hữu ngoại: 45% ĐẠT điều kiện (dưới trần 49% theo Điều 23)."
    }
  },
  traffic: {
    id: "traffic",
    title: "2. Xử phạt Vượt đèn đỏ Mô tô (NĐ 100/2019 bãi bỏ → NĐ 168/2024)",
    query: "Mức xử phạt vượt đèn đỏ xe máy theo quy định mới nhất hiện hành",
    enterprise: "Logistics Express Vietnam JSC",
    entityType: "Công ty Cổ phần",
    capital: "15.000.000.000 VNĐ",
    foreignRatio: "0.0%",
    regulatoryTrap: "Bẫy pháp lý: NĐ 100/2019 (600k-1M) đã bị thay thế bởi NĐ 168/2024 (Phạt 4M-6M, tước GPLX 1-3 tháng).",
    initialDoc: "100/2019/ND-CP",
    successorDoc: "168/2024/ND-CP",
    subgoalA: "Xác định khung tiền phạt đối với hành vi vượt đèn đỏ mô tô",
    subgoalB: "Xác định hình thức xử phạt bổ sung (tước giấy phép lái xe)",
    initialClause: {
      docId: "100/2019/ND-CP",
      article: "Điều 6 Khoản 4",
      title: "Xử phạt vượt đèn đỏ xe máy (CŨ)",
      content: "Phạt tiền từ 600.000 VNĐ đến 1.000.000 VNĐ (Quy định cũ đã bị bãi bỏ bởi NĐ 168/2024).",
      status: "expired"
    },
    successorClause: {
      docId: "168/2024/ND-CP",
      article: "Điều 6 Khoản 4",
      title: "Xử phạt vượt đèn đỏ xe máy (MỚI)",
      content: "Phạt tiền từ 4.000.000 VNĐ đến 6.000.000 VNĐ; tước quyền sử dụng GPLX từ 01 tháng đến 03 tháng.",
      status: "active"
    },
    diffText: `● [PRESERVED IN CACHE] enterprise_profile (Logistics Express JSC) - KHÔNG TÍNH LẠI
● [PRESERVED IN CACHE] Subgoal B (Xác minh hình thức xử phạt bổ sung)
- [PRUNED FROM MEMORY] 100/2019/ND-CP (Bãi bỏ bởi vbpl_verify_oracle)
+ [INSERTED TO MEMORY] 168/2024/ND-CP (Áp dụng mức phạt mới 4M-6M VNĐ)`,
    p1: {
      steps: [
        { name: "Router Phân Loại Ý Định", desc: "Phân loại câu hỏi sang luồng xử phạt giao thông đường bộ", tokens: 170, status: "active" },
        { name: "Prompt Chain: Extractor", desc: "Trích xuất NĐ 100/2019 Điều 6 Khoản 4 Điểm e (Mức phạt 600k-1 triệu)", tokens: 310, status: "failed" },
        { name: "Prompt Chain: Synthesizer", desc: "Xuất thông báo tư vấn phạt 600k-1M (Sai luật hoàn toàn)", tokens: 250, status: "failed" }
      ],
      tokens: 730,
      latency: 38,
      grounding: "0% (Luật cũ đã bãi bỏ)",
      recovery: "Không có",
      outcomeClass: "result-danger",
      dossier: "[TƯ VẤN SAI LỆCH - WORKFLOW]\nThông báo lái xe mức phạt 600.000 - 1.000.000 VNĐ theo Nghị định 100/2019. Lái xe sẽ bị phạt 4-6 triệu theo luật mới!"
    },
    p2: {
      steps: [
        { name: "Turn 1 [ReAct Loop]", desc: "Search: 'mức phạt vượt đèn đỏ xe máy' -> Trả về NĐ 100/2019", tokens: 910, status: "active" },
        { name: "Turn 2 [ReAct Loop]", desc: "Verify status: NĐ 100 bị bãi bỏ bởi NĐ 168/2024", tokens: 1680, status: "active" },
        { name: "Turn 3 [ReAct Loop]", desc: "Search hình thức tước bằng lái; lịch sử dài phình to", tokens: 2540, status: "active" },
        { name: "Turn 4 [ReAct Loop]", desc: "Tổng hợp; đưa ra mức phạt lẫn lộn từ 600k đến 6 triệu", tokens: 3450, status: "failed" }
      ],
      tokens: 8580,
      latency: 410,
      grounding: "50% (Đưa ra cả mức phạt cũ và mới)",
      recovery: "ReAct không lưu checkpoint",
      outcomeClass: "result-warning",
      dossier: "[TƯ VẤN LẪN LỘN - MONOLITHIC AGENT]\nTrích dẫn mâu thuẫn: Phạt từ 600.000 đến 6.000.000 đồng và có thể bị tước GPLX."
    },
    p3: {
      steps: [
        { name: "Node 1: Lead Orchestrator", desc: "Phân rã: Subgoal A (Khung phạt tiền) & Subgoal B (Hình thức phạt bổ sung)", tokens: 420, status: "active", chk: "C1_PLAN" },
        { name: "Node 2: LawGraph Worker", desc: "Tra cứu Subgoal A trong context sạch -> Lấy NĐ 100/2019", tokens: 360, status: "active", chk: "C2_RETRIEVAL" },
        { name: "Node 3: Auditor Oracle Gate", desc: "Kiểm tra vbpl_verify_oracle('100/2019') -> BÃI BỎ bởi NĐ 168/2024!", tokens: 290, status: "failed" },
        { name: "Node 4: Rollback & Re-route", desc: "Rollback về C1_PLAN, chuyển hướng tra cứu NĐ 168/2024 Điều 6 Khoản 4", tokens: 590, status: "recovered", chk: "C1_RESTORE" },
        { name: "Node 5: Drafter Worker", desc: "Tổng hợp kết quả xác thực 100% từ NĐ 168/2024", tokens: 610, status: "active", chk: "C3_FINAL" }
      ],
      tokens: 2270,
      latency: 230,
      grounding: "100% (Chuẩn Nghị định 168/2024)",
      recovery: "Durable SQLite Rollback",
      outcomeClass: "result-success",
      dossier: "KẾT QUẢ TƯ VẤN PHÁP LUẬT CHÍNH XÁC (NĐ 168/2024/NĐ-CP):\n• Hành vi: Người điều khiển xe mô tô, xe gắn máy vượt đèn đỏ.\n• Mức phạt tiền: 4.000.000 VNĐ - 6.000.000 VNĐ (Điều 6 Khoản 4).\n• Xử phạt bổ sung: Tước quyền sử dụng GPLX từ 01 đến 03 tháng."
    }
  },
  labor: {
    id: "labor",
    title: "3. Giấy phép Chuyên gia Ngoại (NĐ 152/2020 sửa đổi bởi NĐ 70/2023)",
    query: "Điều kiện cấp giấy phép lao động cho chuyên gia nước ngoài",
    enterprise: "TechVentures VN LLC",
    entityType: "Công ty TNHH",
    capital: "20.000.000.000 VNĐ",
    foreignRatio: "70.0%",
    regulatoryTrap: "Bẫy pháp lý: NĐ 152/2020 yêu cầu bằng ĐH đúng ngành; NĐ 70/2023 đã nới lỏng sang bằng ĐH bất kỳ + 3 năm kinh nghiệm phù hợp.",
    initialDoc: "152/2020/ND-CP",
    successorDoc: "70/2023/ND-CP",
    subgoalA: "Xác định tiêu chuẩn văn bằng chuyên môn của chuyên gia nước ngoài",
    subgoalB: "Xác định số năm kinh nghiệm làm việc thực tế phù hợp",
    initialClause: {
      docId: "152/2020/ND-CP",
      article: "Điều 3 Khoản 3",
      title: "Tiêu chuẩn chuyên gia (QUY ĐỊNH CŨ KHẮT KHE)",
      content: "Yêu cầu có bằng đại học đúng chuyên ngành đào tạo (Quy định cũ gây tắc nghẽn tuyển dụng).",
      status: "expired"
    },
    successorClause: {
      docId: "70/2023/ND-CP",
      article: "Điều 1 Khoản 5",
      title: "Tiêu chuẩn chuyên gia (QUY ĐỊNH MỚI NỚI LỎNG)",
      content: "Có bằng đại học trở lên hoặc tương đương và có ít nhất 03 năm kinh nghiệm làm việc phù hợp với vị trí.",
      status: "active"
    },
    diffText: `● [PRESERVED IN CACHE] enterprise_profile (TechVentures LLC) - KHÔNG TÍNH LẠI
● [PRESERVED IN CACHE] Subgoal B (Kinh nghiệm 3 năm thực tế)
- [PRUNED FROM MEMORY] 152/2020/ND-CP:Điều 3 (Yêu cầu bằng đúng ngành)
+ [INSERTED TO MEMORY] 70/2023/ND-CP:Điều 1 Khoản 5 (Nới lỏng điều kiện bằng cấp)`,
    p1: {
      steps: [
        { name: "Router Phân Loại Ý Định", desc: "Định tuyến sang nghiệp vụ Giấy phép lao động nước ngoài", tokens: 180, status: "active" },
        { name: "Prompt Chain: Extractor", desc: "Lấy NĐ 152/2020 Điều 3 Khoản 3 (Yêu cầu bằng đúng ngành)", tokens: 330, status: "failed" },
        { name: "Prompt Chain: Synthesizer", desc: "Tư vấn doanh nghiệp từ chối chuyên gia nếu bằng cấp lệch ngành", tokens: 270, status: "failed" }
      ],
      tokens: 780,
      latency: 40,
      grounding: "0% (Bỏ sót Nghị định 70/2023 sửa đổi)",
      recovery: "Không có",
      outcomeClass: "result-danger",
      dossier: "[TƯ VẤN SAI QUY CHUẨN - WORKFLOW]\nYêu cầu chuyên gia phải có bằng đại học đúng chuyên ngành đào tạo theo NĐ 152/2020 (Gây đình trệ tuyển dụng chuyên gia giỏi)."
    },
    p2: {
      steps: [
        { name: "Turn 1 [ReAct Loop]", desc: "Search: 'điều kiện chuyên gia giấy phép lao động' -> NĐ 152/2020", tokens: 940, status: "active" },
        { name: "Turn 2 [ReAct Loop]", desc: "Verify status: NĐ 152 được sửa đổi bởi NĐ 70/2023", tokens: 1720, status: "active" },
        { name: "Turn 3 [ReAct Loop]", desc: "Search điều khoản sửa đổi Điều 1 Khoản 5; ngữ cảnh dồn ốc", tokens: 2600, status: "active" },
        { name: "Turn 4 [ReAct Loop]", desc: "Synthesizer bối rối giữa điều kiện 152 và 70", tokens: 3510, status: "failed" }
      ],
      tokens: 8770,
      latency: 415,
      grounding: "70% (Lẫn lộn quy định cũ và mới)",
      recovery: "Không có checkpoint",
      outcomeClass: "result-warning",
      dossier: "[TƯ VẤN BỊ MƠ HỒ - MONOLITHIC AGENT]\nNêu quy định NĐ 70/2023 nhưng vẫn lưu ý doanh nghiệp về quy định khắt khe của NĐ 152/2020 do prompt bị nhiễu."
    },
    p3: {
      steps: [
        { name: "Node 1: Lead Orchestrator", desc: "Phân rã: Subgoal A (Tiêu chuẩn văn bằng & kinh nghiệm) & Subgoal B (Hồ sơ)", tokens: 440, status: "active", chk: "C1_PLAN" },
        { name: "Node 2: LawGraph Worker", desc: "Tra cứu Subgoal A trong context độc lập", tokens: 370, status: "active", chk: "C2_RETRIEVAL" },
        { name: "Node 3: Auditor Oracle Gate", desc: "Oracle cảnh báo Điều 3 Khoản 3 NĐ 152 đã được sửa đổi bởi NĐ 70/2023!", tokens: 300, status: "failed" },
        { name: "Node 4: Rollback & Re-route", desc: "Rollback về C1_PLAN; duyệt cạnh 'amends' tới NĐ 70/2023 Điều 1 Khoản 5", tokens: 600, status: "recovered", chk: "C1_RESTORE" },
        { name: "Node 5: Drafter Worker", desc: "Soạn thảo hướng dẫn chính xác 100% theo Nghị định 70/2023", tokens: 630, status: "active", chk: "C3_FINAL" }
      ],
      tokens: 2340,
      latency: 240,
      grounding: "100% (Áp dụng đúng NĐ 70/2023)",
      recovery: "Durable SQLite Rollback",
      outcomeClass: "result-success",
      dossier: "HƯỚNG DẪN TUÂN THỦ CHUẨN XÁC THEO NĐ 70/2023/NĐ-CP (Điều 1 Khoản 5):\n• Tiêu chuẩn chuyên gia: Có bằng đại học trở lên HOẶC tương đương;\n• Kinh nghiệm: Có ít nhất 03 năm kinh nghiệm làm việc phù hợp với vị trí dự kiến làm việc tại Việt Nam.\n(Không bắt buộc bằng đại học phải trùng tên chuyên ngành như NĐ 152 cũ)."
    }
  }
};

// ============================================================================
// 2. WORKFLOW DAG DATA (LANGGRAPH STATEGRAPH)
// ============================================================================
const WORKFLOW_NODES = [
  { id: "wf_start", label: "__start__", sub: "User Query & Profile", x: 70, y: 160, type: "entry", color: "#3b82f6", class: "BaseModel: LegalAgentState", tokens: "Input" },
  { id: "wf_planner", label: "LegalOrchestrator", sub: "Dynamic Subgoal Planner", x: 230, y: 160, type: "lead", color: "#10b981", class: "src.agents.orchestrator.LegalOrchestrator", tokens: "450 tkn" },
  { id: "wf_lawgraph", label: "LawGraphAgent", sub: "Statutory Retrieval Worker", x: 440, y: 100, type: "worker", color: "#06b6d4", class: "src.agents.lawgraph.LawGraphAgent", tokens: "380 tkn (Isolated)" },
  { id: "wf_auditor", label: "ClaimAuditorAgent", sub: "Deterministic Oracle Gate", x: 650, y: 100, type: "oracle", color: "#f59e0b", class: "src.agents.claim_auditor.ClaimAuditorAgent", tokens: "310 tkn (Oracle)" },
  { id: "wf_decision", label: "[is_valid?]", sub: "Conditional Route Gate", x: 840, y: 100, type: "gate", color: "#f43f5e", class: "LangGraph Conditional Edge", tokens: "Zero LLM" },
  { id: "wf_rollback", label: "Differential Rollback", sub: "Restore C1 (Sub B Intact)", x: 530, y: 220, type: "rollback", color: "#a855f7", class: "Durable SQLite Rollback", tokens: "Zero Restart Cost" },
  { id: "wf_drafter", label: "DrafterAgent", sub: "Compliance Synthesizer", x: 840, y: 220, type: "drafter", color: "#10b981", class: "src.agents.drafter.DrafterAgent", tokens: "650 tkn" },
  { id: "wf_sqlite", label: "SQLiteCheckpointer", sub: "Audit Log & Checkpointer", x: 1010, y: 220, type: "sqlite", color: "#a855f7", class: "src.memory.sqlite_manager.SQLiteMemoryManager", tokens: "Persistence" },
  { id: "wf_end", label: "__end__", sub: "Verified Compliance Dossier", x: 1160, y: 220, type: "exit", color: "#10b981", class: "Final LegalAgentState", tokens: "Output" }
];

const WORKFLOW_EDGES = [
  { from: "wf_start", to: "wf_planner", label: "dispatch" },
  { from: "wf_planner", to: "wf_lawgraph", label: "Subgoal A (Clean Scope)" },
  { from: "wf_lawgraph", to: "wf_auditor", label: "candidate clauses" },
  { from: "wf_auditor", to: "wf_decision", label: "audit report" },
  { from: "wf_decision", to: "wf_rollback", label: "REVOKED / EXPIRED", type: "rollback" },
  { from: "wf_rollback", to: "wf_planner", label: "Restore Checkpoint C1", type: "rollback" },
  { from: "wf_decision", to: "wf_drafter", label: "ACTIVE (100% Valid)", type: "valid" },
  { from: "wf_planner", to: "wf_drafter", label: "Subgoal B (Cached Profile)", type: "cache" },
  { from: "wf_drafter", to: "wf_sqlite", label: "persist audit log" },
  { from: "wf_sqlite", to: "wf_end", label: "return completed state" }
];

// ============================================================================
// 3. STATUTORY LAW GRAPH DATA (FOR TAB 4)
// ============================================================================
const GRAPH_DATA = {
  nodes: [
    { id: "query", label: "User Query", sub: "Yêu cầu tư vấn", x: 80, y: 240, type: "query", color: "#3b82f6" },
    { id: "lead", label: "Lead Orchestrator", sub: "Phân rã Subgoals", x: 260, y: 240, type: "agent", color: "#10b981" },
    { id: "sub_a", label: "Subgoal A (Worker)", sub: "Điều kiện chính", x: 440, y: 150, type: "subgoal", color: "#06b6d4" },
    { id: "sub_b", label: "Subgoal B (Worker)", sub: "Điều kiện bổ trợ", x: 440, y: 330, type: "subgoal", color: "#06b6d4" },
    { id: "doc_old", label: "NĐ 101/2012", sub: "Văn bản cũ (HẾT HL)", x: 640, y: 150, type: "expired", color: "#f43f5e" },
    { id: "oracle", label: "Oracle Verifier", sub: "vbpl_verify_oracle", x: 840, y: 150, type: "oracle", color: "#f59e0b" },
    { id: "doc_new", label: "NĐ 52/2024", sub: "Văn bản thay thế", x: 640, y: 380, type: "active", color: "#10b981" },
    { id: "drafter", label: "Drafter Worker", sub: "Tổng hợp Dossier", x: 860, y: 380, type: "drafter", color: "#a855f7" }
  ],
  edges: [
    { from: "query", to: "lead", label: "dispatches" },
    { from: "lead", to: "sub_a", label: "subtask 1" },
    { from: "lead", to: "sub_b", label: "subtask 2" },
    { from: "sub_a", to: "doc_old", label: "retrieves" },
    { from: "doc_old", to: "oracle", label: "audits status" },
    { from: "oracle", to: "lead", label: "ROLLBACK C1", type: "rollback" },
    { from: "lead", to: "doc_new", label: "re-routes (successor)", type: "reroute" },
    { from: "doc_new", to: "drafter", label: "verified clauses" },
    { from: "sub_b", to: "drafter", label: "cached profile" }
  ]
};

// ============================================================================
// 4. APPLICATION STATE & CONTROLLER
// ============================================================================
class DemoApp {
  constructor() {
    this.currentScenarioKey = "fintech";
    this.currentStepIndex = -1; // -1: not started
    this.maxSteps = 5;
    this.isPlaying = false;
    this.speed = 1000;
    this.timer = null;

    this.initDOM();
    this.initEvents();
    this.renderScenarioInfo();
    this.renderParadigmDiagrams();
    this.renderWorkflowGraph();
    this.renderStatutoryGraph();
    this.resetSimulation();
  }

  initDOM() {
    this.scenarioPills = document.querySelectorAll(".scenario-pill");
    this.tabButtons = document.querySelectorAll(".tab-btn");
    this.tabPanels = document.querySelectorAll(".tab-panel");
    this.playBtn = document.getElementById("btnPlay");
    this.stepBtn = document.getElementById("btnStep");
    this.resetBtn = document.getElementById("btnReset");
    this.speedBtns = document.querySelectorAll(".speed-btn");

    this.p1Logs = document.getElementById("p1Logs");
    this.p2Logs = document.getElementById("p2Logs");
    this.p3Logs = document.getElementById("p3Logs");

    this.p1Tokens = document.getElementById("p1Tokens");
    this.p2Tokens = document.getElementById("p2Tokens");
    this.p3Tokens = document.getElementById("p3Tokens");

    this.p1Status = document.getElementById("p1Status");
    this.p2Status = document.getElementById("p2Status");
    this.p3Status = document.getElementById("p3Status");

    // 3 Side-by-Side Embedded Architecture SVGs
    this.p1Svg = document.getElementById("p1Svg");
    this.p2Svg = document.getElementById("p2Svg");
    this.p3Svg = document.getElementById("p3Svg");

    this.wfSvg = document.getElementById("workflowSvg");
    this.lawSvg = document.getElementById("lawGraphSvg");
    this.dossierText = document.getElementById("dossierText");

    // Memory Inspector DOM Elements
    this.memCompany = document.getElementById("memCompany");
    this.memType = document.getElementById("memType");
    this.memCapital = document.getElementById("memCapital");
    this.memForeign = document.getElementById("memForeign");
    this.memStepCount = document.getElementById("memStepCount");
    this.memSubgoalsList = document.getElementById("memSubgoalsList");
    this.memClauseCount = document.getElementById("memClauseCount");
    this.memClausesDeck = document.getElementById("memClausesDeck");
    this.memAuditBadge = document.getElementById("memAuditBadge");
    this.memGroundingRate = document.getElementById("memGroundingRate");
    this.memClaimsRatio = document.getElementById("memClaimsRatio");
    this.memAuditFeedback = document.getElementById("memAuditFeedback");
    this.memDiffBox = document.getElementById("memDiffBox");
    this.memSqliteTableBody = document.getElementById("memSqliteTableBody");

    // Workflow Inspector DOM Elements
    this.wfCurrentNodeBadge = document.getElementById("wfCurrentNodeBadge");
    this.wfNodeName = document.getElementById("wfNodeName");
    this.wfNodeClass = document.getElementById("wfNodeClass");
    this.wfNodeTokens = document.getElementById("wfNodeTokens");
    this.wfNodeTransition = document.getElementById("wfNodeTransition");
  }

  initEvents() {
    this.scenarioPills.forEach(pill => {
      pill.addEventListener("click", () => {
        this.scenarioPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        this.currentScenarioKey = pill.dataset.scenario;
        this.renderScenarioInfo();
        this.resetSimulation();
      });
    });

    this.tabButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        this.tabButtons.forEach(b => b.classList.remove("active"));
        this.tabPanels.forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        const panelId = btn.dataset.tab;
        const panel = document.getElementById(panelId);
        if (panel) panel.classList.add("active");
        if (panelId === "tabWorkflow") {
          setTimeout(() => this.renderWorkflowGraph(), 50);
        } else if (panelId === "tabGraph") {
          setTimeout(() => this.renderStatutoryGraph(), 50);
        }
      });
    });

    if (this.playBtn) {
      this.playBtn.addEventListener("click", () => this.togglePlay());
    }
    if (this.stepBtn) {
      this.stepBtn.addEventListener("click", () => this.stepForward());
    }
    if (this.resetBtn) {
      this.resetBtn.addEventListener("click", () => this.resetSimulation());
    }
    if (this.speedBtns) {
      this.speedBtns.forEach(btn => {
        btn.addEventListener("click", () => {
          this.speedBtns.forEach(b => b.classList.remove("active"));
          btn.classList.add("active");
          this.speed = parseInt(btn.dataset.speed, 10) || 1000;
          if (this.isPlaying) {
            this.pause();
            this.play();
          }
        });
      });
    }
  }

  renderScenarioInfo() {
    const sc = SCENARIOS[this.currentScenarioKey];
    if (!sc) return;
    const bannerTitle = document.getElementById("scenarioBannerTitle");
    const bannerDesc = document.getElementById("scenarioBannerDesc");
    const bannerRisk = document.getElementById("scenarioBannerRisk");
    if (bannerTitle) bannerTitle.textContent = `${sc.icon} ${sc.title} — ${sc.enterprise}`;
    if (bannerDesc) bannerDesc.textContent = sc.description;
    if (bannerRisk) bannerRisk.textContent = `Rủi ro: ${sc.trap}`;

    if (this.memCompany) this.memCompany.textContent = sc.enterprise;
    if (this.memType) this.memType.textContent = sc.type;
    if (this.memCapital) this.memCapital.textContent = sc.charterCapital;
    if (this.memForeign) this.memForeign.textContent = sc.foreignOwnership;
  }

  togglePlay() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  play() {
    if (this.currentStepIndex >= this.maxSteps - 1) {
      this.resetSimulation();
    }
    this.isPlaying = true;
    if (this.playBtn) {
      this.playBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> Tạm Dừng`;
      this.playBtn.classList.add("playing");
    }
    this.timer = setInterval(() => {
      this.stepForward();
    }, this.speed);
  }

  pause() {
    this.isPlaying = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.playBtn) {
      this.playBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> Chạy Mô Phỏng (Race)`;
      this.playBtn.classList.remove("playing");
    }
  }

  stepForward() {
    if (this.currentStepIndex < this.maxSteps - 1) {
      this.currentStepIndex++;
      this.renderStepState();
    } else {
      this.pause();
    }
  }

  resetSimulation() {
    this.pause();
    this.currentStepIndex = -1;
    this.renderStepState();
  }

  renderStepState() {
    const sc = SCENARIOS[this.currentScenarioKey];
    const idx = this.currentStepIndex;

    // Render 3 Paradigms Side-by-Side Step Logs
    this.renderCardSteps(this.p1Logs, sc.p1.steps, idx, sc.p1.tokens, this.p1Tokens, this.p1Status, sc.p1);
    this.renderCardSteps(this.p2Logs, sc.p2.steps, idx, sc.p2.tokens, this.p2Tokens, this.p2Status, sc.p2);
    this.renderCardSteps(this.p3Logs, sc.p3.steps, idx, sc.p3.tokens, this.p3Tokens, this.p3Status, sc.p3);

    // Highlight the 3 Side-by-Side Architecture SVGs!
    this.highlightParadigmDiagrams(idx);

    // Update Dossier tab text
    if (idx >= 4) {
      this.dossierText.textContent = sc.p3.dossier;
    } else {
      this.dossierText.textContent = `[Hồ sơ đang được xử lý qua đồ thị StateGraph... Bước hiện tại: ${idx + 1}/5]`;
    }

    // Render Live Memory Inspector & Memory Bus HUD
    this.renderLiveMemory(idx, sc);

    // Highlight active nodes in Workflow & Law Graphs
    this.highlightWorkflowStep(idx);
    this.highlightStatutoryGraphStep(idx);
  }

  renderCardSteps(container, steps, currentIdx, maxTokens, tokenEl, statusEl, patternObj) {
    container.innerHTML = "";
    let consumedTokens = 0;

    steps.forEach((st, i) => {
      const item = document.createElement("div");
      item.className = "log-step-item";

      if (i <= currentIdx) {
        item.classList.add("active");
        consumedTokens += st.tokens;

        if (i === currentIdx) {
          item.classList.add("current");
        }
        if (st.status === "failed") {
          item.classList.add("failed");
        } else if (st.status === "recovered") {
          item.classList.add("recovered");
        }
      }

      item.innerHTML = `
        <div class="step-meta">
          <span class="step-name">${st.name}</span>
          <span>${st.tokens} tokens</span>
        </div>
        <div class="step-desc">${st.desc}</div>
      `;
      container.appendChild(item);
    });

    tokenEl.textContent = `${consumedTokens.toLocaleString()} tkn`;

    if (currentIdx >= steps.length - 1) {
      statusEl.textContent = patternObj.grounding;
      statusEl.className = `result-badge ${patternObj.outcomeClass}`;
    } else {
      statusEl.textContent = currentIdx === -1 ? "CHƯA BẮT ĐẦU" : `Đang chạy (Bước ${currentIdx + 1})`;
      statusEl.className = "result-badge";
    }
  }

  // ==========================================================================
  // 3 SIDE-BY-SIDE ARCHITECTURE DIAGRAMS RENDERER
  // ==========================================================================
  renderParadigmDiagrams() {
    this.renderP1Diagram();
    this.renderP2Diagram();
    this.renderP3Diagram();
  }

  renderP1Diagram() {
    if (!this.p1Svg) return;
    this.p1Svg.innerHTML = `
      <defs>
        <marker id="p1-arr" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717a" />
        </marker>
        <marker id="p1-arr-green" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
        </marker>
        <marker id="p1-arr-red" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#f43f5e" />
        </marker>
      </defs>

      <!-- In Circle -->
      <circle cx="26" cy="46" r="14" fill="#10b981" />
      <text x="26" y="50" text-anchor="middle" fill="#000" font-size="10.5" font-weight="700">In</text>

      <!-- In -> Router -->
      <line x1="40" y1="46" x2="68" y2="46" stroke="#71717a" stroke-width="1.5" marker-end="url(#p1-arr)" />

      <!-- Router Node -->
      <rect id="p1_n_router" x="68" y="28" width="62" height="36" rx="6" fill="#14141e" stroke="#3b82f6" stroke-width="1.5" />
      <text x="99" y="44" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">Router</text>
      <text x="99" y="56" text-anchor="middle" fill="#93c5fd" font-size="7.5">Phân loại</text>

      <!-- Router -> LLM 1 (Extractor) -->
      <line x1="130" y1="46" x2="152" y2="46" stroke="#71717a" stroke-width="1.5" marker-end="url(#p1-arr)" />

      <!-- LLM 1 Node -->
      <rect id="p1_n_llm1" x="152" y="28" width="66" height="36" rx="6" fill="#14141e" stroke="#71717a" stroke-width="1.5" />
      <text x="185" y="44" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">LLM 1</text>
      <text x="185" y="56" text-anchor="middle" fill="#a1a1aa" font-size="7.5">Trích xuất</text>

      <!-- LLM 1 -> Gate -->
      <line x1="218" y1="46" x2="236" y2="46" stroke="#71717a" stroke-width="1.5" marker-end="url(#p1-arr)" />

      <!-- Gate Diamond -->
      <polygon id="p1_n_gate" points="248,34 260,46 248,58 236,46" fill="#f59e0b" stroke="#d97706" stroke-width="1.2" />
      <text x="248" y="48.5" text-anchor="middle" fill="#000" font-size="7" font-weight="800">Gate</text>

      <!-- Gate Pass -> LLM 2 -->
      <path d="M 260 40 L 278 28" stroke="#10b981" stroke-width="1.5" marker-end="url(#p1-arr-green)" />
      <text x="270" y="32" fill="#10b981" font-size="7" font-weight="700">Pass</text>

      <!-- LLM 2 Node -->
      <rect id="p1_n_llm2" x="278" y="14" width="46" height="26" rx="5" fill="#14141e" stroke="#71717a" stroke-width="1.5" />
      <text x="301" y="30" text-anchor="middle" fill="#fff" font-size="8.5" font-weight="700">LLM 2</text>

      <!-- Out Circle -->
      <circle cx="340" cy="27" r="12" fill="#f97316" />
      <text x="340" y="31" text-anchor="middle" fill="#fff" font-size="8.5" font-weight="700">Out</text>

      <!-- Gate Fail -> Exit -->
      <path d="M 254 56 L 270 72" stroke="#f43f5e" stroke-width="1.5" marker-end="url(#p1-arr-red)" />
      <text x="268" y="66" fill="#f43f5e" font-size="7" font-weight="700">Fail</text>
      <circle id="p1_n_exit" cx="288" cy="78" r="11" fill="#f43f5e" />
      <text x="288" y="81" text-anchor="middle" fill="#fff" font-size="8" font-weight="700">Exit</text>

      <!-- Stateless / No Memory Callout Banner -->
      <rect x="18" y="100" width="324" height="24" rx="4" fill="rgba(244, 63, 94, 0.08)" stroke="rgba(244, 63, 94, 0.25)" />
      <text x="180" y="116" text-anchor="middle" fill="#f87171" font-size="8" font-family="monospace">🚫 BỘ NHỚ: Stateless (0 Memory) · Sập là phải chạy lại từ đầu</text>
    `;
  }

  renderP2Diagram() {
    if (!this.p2Svg) return;
    this.p2Svg.innerHTML = `
      <defs>
        <marker id="p2-arr" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717a" />
        </marker>
        <marker id="p2-arr-cyan" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#06b6d4" />
        </marker>
      </defs>

      <!-- In Circle -->
      <circle cx="26" cy="46" r="14" fill="#10b981" />
      <text x="26" y="50" text-anchor="middle" fill="#000" font-size="10.5" font-weight="700">In</text>

      <line x1="40" y1="46" x2="68" y2="46" stroke="#71717a" stroke-dasharray="3 3" stroke-width="1.5" />

      <!-- LLM ReAct Node -->
      <rect id="p2_n_llm" x="68" y="24" width="90" height="44" rx="8" fill="#14141e" stroke="#f59e0b" stroke-width="1.8" />
      <text x="113" y="42" text-anchor="middle" fill="#fff" font-size="9.5" font-weight="700">🤖 LLM ReAct</text>
      <text x="113" y="56" text-anchor="middle" fill="#fbbf24" font-size="7.5">Thought & Plan</text>

      <!-- Bi-directional Loop to Environment/Tools -->
      <path id="p2_e_action" d="M 158 36 C 180 20, 200 20, 218 36" stroke="#06b6d4" stroke-width="1.8" fill="none" marker-end="url(#p2-arr-cyan)" />
      <text x="188" y="22" text-anchor="middle" fill="#06b6d4" font-size="7.5" font-weight="700">Action ➔</text>

      <!-- Environment / Tools Node -->
      <rect id="p2_n_env" x="218" y="24" width="85" height="44" rx="8" fill="#14141e" stroke="#06b6d4" stroke-width="1.8" />
      <text x="260" y="42" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">Environment</text>
      <text x="260" y="56" text-anchor="middle" fill="#a1a1aa" font-size="7.5">Tools & APIs</text>

      <path id="p2_e_obs" d="M 218 54 C 200 68, 180 68, 158 54" stroke="#a1a1aa" stroke-width="1.8" fill="none" />
      <text x="188" y="73" text-anchor="middle" fill="#a1a1aa" font-size="7.5">⮜ Observation</text>

      <line x1="303" y1="46" x2="324" y2="46" stroke="#71717a" stroke-dasharray="3 3" stroke-width="1.5" />
      <circle cx="338" cy="46" r="13" fill="#f97316" />
      <text x="338" y="50" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">Out</text>

      <!-- Volatile Context Bloat Memory Callout -->
      <rect x="18" y="100" width="324" height="24" rx="4" fill="rgba(245, 158, 11, 0.08)" stroke="rgba(245, 158, 11, 0.3)" />
      <text x="180" y="116" text-anchor="middle" fill="#fbbf24" font-size="8" font-family="monospace">⚠️ BỘ NHỚ: RAM Tạm (O(N²) quadratic bloat, trôi dạt ngữ cảnh)</text>
    `;
  }

  renderP3Diagram() {
    if (!this.p3Svg) return;
    this.p3Svg.innerHTML = `
      <defs>
        <marker id="p3-arr" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717a" />
        </marker>
        <marker id="p3-arr-green" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
        </marker>
        <marker id="p3-arr-purple" viewBox="0 0 10 10" refX="20" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#a855f7" />
        </marker>
      </defs>

      <!-- In Circle -->
      <circle cx="24" cy="46" r="13" fill="#10b981" />
      <text x="24" y="50" text-anchor="middle" fill="#000" font-size="10" font-weight="700">In</text>

      <line x1="37" y1="46" x2="56" y2="46" stroke="#10b981" stroke-width="1.5" marker-end="url(#p3-arr-green)" />

      <!-- Orchestrator Box -->
      <rect id="p3_n_orch" x="56" y="24" width="76" height="44" rx="6" fill="#14141e" stroke="#10b981" stroke-width="1.8" />
      <text x="94" y="42" text-anchor="middle" fill="#fff" font-size="9" font-weight="700">Lead Orch</text>
      <text x="94" y="56" text-anchor="middle" fill="#6ee7b7" font-size="7.5">Phân rã Subgoals</text>

      <!-- Dispatches to Workers -->
      <path d="M 132 36 L 158 24" stroke="#06b6d4" stroke-width="1.4" marker-end="url(#p3-arr)" />
      <rect id="p3_n_w1" x="158" y="12" width="80" height="26" rx="4" fill="#14141e" stroke="#06b6d4" stroke-width="1.4" />
      <text x="198" y="28" text-anchor="middle" fill="#67e8f9" font-size="8">LawGraph Worker</text>

      <path d="M 132 56 L 158 66" stroke="#f59e0b" stroke-width="1.4" marker-end="url(#p3-arr)" />
      <rect id="p3_n_oracle" x="158" y="54" width="80" height="26" rx="4" fill="#14141e" stroke="#f59e0b" stroke-width="1.4" />
      <text x="198" y="70" text-anchor="middle" fill="#fcd34d" font-size="8">Auditor Oracle</text>

      <!-- Rollback Arc from Oracle back to Lead Orch -->
      <path id="p3_e_rollback" d="M 158 72 C 140 86, 110 86, 94 68" stroke="#a855f7" stroke-dasharray="3 2" stroke-width="1.5" fill="none" marker-end="url(#p3-arr-purple)" />
      <text x="126" y="88" text-anchor="middle" fill="#c084fc" font-size="7">↺ Rollback C1</text>

      <!-- Synthesizer Box -->
      <rect id="p3_n_drafter" x="262" y="28" width="62" height="36" rx="5" fill="#14141e" stroke="#10b981" stroke-width="1.5" />
      <text x="293" y="45" text-anchor="middle" fill="#fff" font-size="8.5" font-weight="700">Synthesizer</text>
      <text x="293" y="56" text-anchor="middle" fill="#a1a1aa" font-size="7">Drafter</text>

      <path d="M 238 25 L 262 38" stroke="#10b981" stroke-width="1.2" />
      <path d="M 238 67 L 262 54" stroke="#10b981" stroke-width="1.2" />

      <line x1="324" y1="46" x2="336" y2="46" stroke="#10b981" stroke-width="1.5" />
      <circle cx="344" cy="46" r="11" fill="#f97316" />
      <text x="344" y="50" text-anchor="middle" fill="#fff" font-size="8" font-weight="700">Out</text>

      <!-- Bottom summary banner -->
      <rect x="18" y="104" width="324" height="22" rx="4" fill="rgba(16, 185, 129, 0.08)" stroke="rgba(16, 185, 129, 0.25)" />
      <text x="180" y="119" text-anchor="middle" fill="#34d399" font-size="8" font-family="monospace">🛡️ KIỂM ĐỊNH ORACLE & KHÔI PHỤC VI SAI (Độc lập phân rã)</text>
    `;
  }

  highlightParadigmDiagrams(idx) {
    // Reset all nodes
    const p1Nodes = ["p1_n_router", "p1_n_llm1", "p1_n_gate", "p1_n_llm2", "p1_n_exit"];
    p1Nodes.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.setAttribute("stroke-width", "1.5");
    });

    const p2Nodes = ["p2_n_llm", "p2_n_env"];
    p2Nodes.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.setAttribute("stroke-width", "1.8");
    });

    const p3Nodes = ["p3_n_orch", "p3_n_w1", "p3_n_oracle", "p3_n_drafter"];
    p3Nodes.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.setAttribute("stroke-width", "1.5");
    });
    const rb = document.getElementById("p3_e_rollback");
    if (rb) rb.setAttribute("stroke-width", "1.5");

    if (idx === -1) return;

    // Step 0: Planning & Dispatch
    if (idx === 0) {
      const r = document.getElementById("p1_n_router");
      if (r) r.setAttribute("stroke-width", "3");

      const l = document.getElementById("p2_n_llm");
      if (l) l.setAttribute("stroke-width", "3.2");

      const o = document.getElementById("p3_n_orch");
      if (o) o.setAttribute("stroke-width", "3.2");
    }

    // Step 1: Retrieval
    else if (idx === 1) {
      const l1 = document.getElementById("p1_n_llm1");
      if (l1) l1.setAttribute("stroke-width", "3");

      const e = document.getElementById("p2_n_env");
      if (e) e.setAttribute("stroke-width", "3");

      const w1 = document.getElementById("p3_n_w1");
      if (w1) w1.setAttribute("stroke-width", "3");
    }

    // Step 2: Oracle Audit
    else if (idx === 2) {
      const g = document.getElementById("p1_n_gate");
      if (g) g.setAttribute("stroke-width", "2.8");

      const l = document.getElementById("p2_n_llm");
      if (l) {
        l.setAttribute("stroke", "#f43f5e");
        l.setAttribute("stroke-width", "3.2");
      }

      const ora = document.getElementById("p3_n_oracle");
      if (ora) {
        ora.setAttribute("stroke", "#f43f5e");
        ora.setAttribute("stroke-width", "3");
      }
    }

    // Step 3: Rollback vs Failure
    else if (idx === 3) {
      const ex = document.getElementById("p1_n_exit");
      if (ex) ex.setAttribute("stroke-width", "3");

      const l = document.getElementById("p2_n_llm");
      if (l) {
        l.setAttribute("stroke", "#f59e0b");
        l.setAttribute("stroke-width", "3.5");
      }

      const r = document.getElementById("p3_e_rollback");
      if (r) {
        r.setAttribute("stroke-width", "3");
        r.setAttribute("stroke", "#c084fc");
      }
      const o = document.getElementById("p3_n_orch");
      if (o) o.setAttribute("stroke-width", "3");
    }

    // Step 4: Final Synthesis & Persistence
    else if (idx >= 4) {
      const d = document.getElementById("p3_n_drafter");
      if (d) d.setAttribute("stroke-width", "3.2");
    }
  }

  // ==========================================================================
  // LIVE MEMORY & STATE INSPECTOR RENDERER (TAB 3)
  // ==========================================================================
  renderLiveMemory(idx, sc) {
    if (!this.memSubgoalsList) return;

    this.memStepCount.textContent = `Bước: ${Math.max(0, idx + 1)} / 5`;

    if (idx === -1) {
      this.memSubgoalsList.innerHTML = `
        <div class="subgoal-item">
          <span>Subgoal A: ${sc.subgoalA}</span>
          <span class="subgoal-status-badge" style="background: rgba(255,255,255,0.08); color: #a1a1aa;">CHỜ THỰC THI</span>
        </div>
        <div class="subgoal-item">
          <span>Subgoal B: ${sc.subgoalB}</span>
          <span class="subgoal-status-badge" style="background: rgba(255,255,255,0.08); color: #a1a1aa;">CHỜ THỰC THI</span>
        </div>
      `;
      this.memClauseCount.textContent = "0 điều khoản";
      this.memClausesDeck.innerHTML = `<div style="font-size: 0.75rem; color: var(--text-muted); font-style: italic;">Chưa có văn bản nào được nạp vào working memory.</div>`;
      this.memAuditBadge.textContent = "CHƯA KIỂM ĐỊNH";
      this.memAuditBadge.style.color = "#a1a1aa";
      this.memGroundingRate.textContent = "0.0%";
      this.memClaimsRatio.textContent = "0 / 0";
      this.memAuditFeedback.textContent = "Cổng kiểm định Oracle tiền định chưa được kích hoạt.";
      return;
    }

    // Step 0: Plan Created
    if (idx === 0) {
      this.memSubgoalsList.innerHTML = `
        <div class="subgoal-item done">
          <span>Subgoal A: ${sc.subgoalA}</span>
          <span class="subgoal-status-badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981;">PLAN READY</span>
        </div>
        <div class="subgoal-item cached">
          <span>Subgoal B: ${sc.subgoalB}</span>
          <span class="subgoal-status-badge" style="background: rgba(168, 85, 247, 0.15); color: #c084fc;">PRESERVED IN CACHE</span>
        </div>
      `;
      this.memClauseCount.textContent = "0 điều khoản (Đang dispatch worker)";
      this.memClausesDeck.innerHTML = `<div style="font-size: 0.75rem; color: #60a5fa;">Đã phân rã subgoals vào Pydantic LegalAgentState. Đang gọi LawGraphAgent...</div>`;
      this.memAuditBadge.textContent = "PLAN_READY";
      this.memAuditFeedback.textContent = "Kế hoạch đã sẵn sàng. Chờ LawGraphAgent truy xuất văn bản.";
    }

    // Step 1: Candidate Retrieved
    else if (idx === 1) {
      this.memClauseCount.textContent = `1 điều khoản (Cần kiểm định)`;
      this.memClausesDeck.innerHTML = `
        <div class="clause-item">
          <div style="display:flex; justify-content:space-between; font-weight:700;">
            <span style="color:#f59e0b;">${sc.initialClause.docId} (${sc.initialClause.article})</span>
            <span class="badge-tag" style="background:rgba(245, 158, 11, 0.15); color:#f59e0b;">UNVERIFIED</span>
          </div>
          <div style="font-size:0.72rem; color:#a1a1aa;">${sc.initialClause.title}</div>
          <div style="font-size:0.7rem; color:#71717a;">${sc.initialClause.content}</div>
        </div>
      `;
      this.memAuditBadge.textContent = "CHỜ ORACLE";
      this.memGroundingRate.textContent = "0.0%";
      this.memClaimsRatio.textContent = "0 / 1";
      this.memAuditFeedback.textContent = `Đã nạp ${sc.initialClause.docId} vào scratchpad. Chuẩn bị gọi vbpl_verify_oracle().`;
    }

    // Step 2: Oracle Detects Revocation
    else if (idx === 2) {
      this.memClauseCount.textContent = `1 điều khoản (PHÁT HIỆN HẾT HIỆU LỰC)`;
      this.memClausesDeck.innerHTML = `
        <div class="clause-item expired-law">
          <div style="display:flex; justify-content:space-between; font-weight:700;">
            <span style="color:#f43f5e; text-decoration:line-through;">${sc.initialClause.docId} (${sc.initialClause.article})</span>
            <span class="badge-tag" style="background:rgba(244, 63, 94, 0.15); color:#f43f5e;">REVOKED / BÃI BỎ</span>
          </div>
          <div style="font-size:0.72rem; color:#f87171;">Bị bãi bỏ bởi ${sc.successorDoc} từ 01/07/2024!</div>
          <div style="font-size:0.7rem; color:#71717a;">vbpl_verify_oracle trả về is_active = false. Kích hoạt ngắt mạch cứng!</div>
        </div>
      `;
      this.memAuditBadge.textContent = "FAIL (REVOKED)";
      this.memAuditBadge.className = "badge-tag result-danger";
      this.memGroundingRate.textContent = "0.0%";
      this.memClaimsRatio.textContent = "0 / 1 (Vi phạm hiệu lực)";
      this.memAuditFeedback.textContent = `CẢNH BÁO: ${sc.initialClause.docId} đã hết hiệu lực. Kích hoạt conditional rollback edge về Checkpoint C1_PLAN!`;
    }

    // Step 3: Rollback & Re-route (Differential recovery)
    else if (idx === 3) {
      this.memSubgoalsList.innerHTML = `
        <div class="subgoal-item done">
          <span>Subgoal A: Chuyển tiếp tra cứu kế thừa ${sc.successorDoc}</span>
          <span class="subgoal-status-badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981;">RE-ROUTED</span>
        </div>
        <div class="subgoal-item cached">
          <span>Subgoal B: ${sc.subgoalB}</span>
          <span class="subgoal-status-badge" style="background: rgba(168, 85, 247, 0.15); color: #c084fc;">PRESERVED IN CACHE</span>
        </div>
      `;
      this.memClauseCount.textContent = `1 điều khoản (Đã thay thế)`;
      this.memClausesDeck.innerHTML = `
        <div class="clause-item active-law">
          <div style="display:flex; justify-content:space-between; font-weight:700;">
            <span style="color:#10b981;">${sc.successorClause.docId} (${sc.successorClause.article})</span>
            <span class="badge-tag" style="background:rgba(16, 185, 129, 0.15); color:#10b981;">ACTIVE / VERIFIED</span>
          </div>
          <div style="font-size:0.72rem; color:#34d399;">${sc.successorClause.title}</div>
          <div style="font-size:0.7rem; color:#a1a1aa;">${sc.successorClause.content}</div>
        </div>
      `;
      this.memAuditBadge.textContent = "RE-AUDIT PASS";
      this.memAuditBadge.className = "badge-tag result-success";
      this.memGroundingRate.textContent = "100.0%";
      this.memClaimsRatio.textContent = "2 / 2";
      this.memAuditFeedback.textContent = `Khôi phục vi sai thành công từ C1_PLAN. Subgoal B giữ nguyên trong memory. Oracle xác nhận ${sc.successorDoc} đang có hiệu lực.`;
    }

    // Step 4: Final Dossier Synthesized
    else if (idx >= 4) {
      this.memClauseCount.textContent = `2 điều khoản (100% Căn cứ hợp lệ)`;
      this.memClausesDeck.innerHTML = `
        <div class="clause-item active-law">
          <div style="display:flex; justify-content:space-between; font-weight:700;">
            <span style="color:#10b981;">${sc.successorClause.docId} (${sc.successorClause.article})</span>
            <span class="badge-tag" style="background:rgba(16, 185, 129, 0.15); color:#10b981;">100% GROUNDED</span>
          </div>
          <div style="font-size:0.72rem; color:#34d399;">${sc.successorClause.title}</div>
          <div style="font-size:0.7rem; color:#a1a1aa;">${sc.successorClause.content}</div>
        </div>
      `;
      this.memAuditBadge.textContent = "FULLY VERIFIED";
      this.memAuditBadge.className = "badge-tag result-success";
      this.memGroundingRate.textContent = "100.0%";
      this.memClaimsRatio.textContent = "2 / 2 (Chuẩn xác)";
      this.memAuditFeedback.textContent = `Hồ sơ tuân thủ đã hoàn tất và ghi vào SQLite. Không còn bất kỳ căn cứ pháp lý hết hiệu lực nào.`;
    }
  }

  // ==========================================================================
  // WORKFLOW STATEGRAPH SVG RENDERER (TAB 2)
  // ==========================================================================
  renderWorkflowGraph() {
    if (!this.wfSvg) return;
    this.wfSvg.innerHTML = "";

    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
      <marker id="wf-arrow" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717a" />
      </marker>
      <marker id="wf-arrow-green" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
      </marker>
      <marker id="wf-arrow-purple" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#a855f7" />
      </marker>
    `;
    this.wfSvg.appendChild(defs);

    // Draw Workflow Edges
    WORKFLOW_EDGES.forEach(edge => {
      const fromNode = WORKFLOW_NODES.find(n => n.id === edge.from);
      const toNode = WORKFLOW_NODES.find(n => n.id === edge.to);
      if (!fromNode || !toNode) return;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("id", `wf_edge_${edge.from}_${edge.to}`);
      path.setAttribute("class", `workflow-edge ${edge.type === "rollback" ? "rollback-edge" : ""}`);

      const dx = toNode.x - fromNode.x;
      const dy = toNode.y - fromNode.y;
      let d = "";

      if (edge.type === "rollback") {
        d = `M ${fromNode.x} ${fromNode.y} C ${fromNode.x - 80} ${fromNode.y + 60}, ${toNode.x + 80} ${toNode.y + 60}, ${toNode.x} ${toNode.y}`;
      } else if (edge.type === "cache") {
        d = `M ${fromNode.x} ${fromNode.y} C ${fromNode.x + 120} ${fromNode.y + 100}, ${toNode.x - 120} ${toNode.y}, ${toNode.x} ${toNode.y}`;
      } else {
        const cx1 = fromNode.x + dx * 0.5;
        const cy1 = fromNode.y;
        const cx2 = fromNode.x + dx * 0.5;
        const cy2 = toNode.y;
        d = `M ${fromNode.x} ${fromNode.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${toNode.x} ${toNode.y}`;
      }

      path.setAttribute("d", d);
      path.setAttribute("stroke", edge.type === "rollback" ? "#a855f7" : edge.type === "valid" ? "#10b981" : "#3f3f46");
      path.setAttribute("stroke-width", edge.type === "rollback" || edge.type === "valid" ? "2.0" : "1.5");
      path.setAttribute("fill", "none");
      path.setAttribute("marker-end", edge.type === "rollback" ? "url(#wf-arrow-purple)" : edge.type === "valid" ? "url(#wf-arrow-green)" : "url(#wf-arrow)");
      this.wfSvg.appendChild(path);
    });

    // Draw Workflow Nodes (Cards / Rects)
    WORKFLOW_NODES.forEach(node => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", "workflow-node");
      g.setAttribute("id", `node_${node.id}`);

      const w = 120;
      const h = 54;
      const rx = 8;

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", node.x - w / 2);
      rect.setAttribute("y", node.y - h / 2);
      rect.setAttribute("width", w);
      rect.setAttribute("height", h);
      rect.setAttribute("rx", rx);
      rect.setAttribute("fill", "#111116");
      rect.setAttribute("stroke", node.color);
      rect.setAttribute("stroke-width", "1.5");

      const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
      title.setAttribute("x", node.x);
      title.setAttribute("y", node.y - 6);
      title.setAttribute("text-anchor", "middle");
      title.setAttribute("fill", "#fff");
      title.setAttribute("font-size", "10px");
      title.setAttribute("font-weight", "700");
      title.textContent = node.label;

      const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
      sub.setAttribute("x", node.x);
      sub.setAttribute("y", node.y + 12);
      sub.setAttribute("text-anchor", "middle");
      sub.setAttribute("fill", "#a1a1aa");
      sub.setAttribute("font-size", "8.5px");
      sub.textContent = node.sub;

      g.appendChild(rect);
      g.appendChild(title);
      g.appendChild(sub);

      g.addEventListener("click", () => {
        this.inspectWorkflowNode(node);
      });

      this.wfSvg.appendChild(g);
    });
  }

  inspectWorkflowNode(node) {
    if (this.wfNodeName) this.wfNodeName.textContent = node.label;
    if (this.wfNodeClass) this.wfNodeClass.textContent = node.class || "StateGraph Node";
    if (this.wfNodeTokens) this.wfNodeTokens.textContent = node.tokens || "< 450 tokens";
    if (this.wfCurrentNodeBadge) {
      this.wfCurrentNodeBadge.textContent = "INSPECTED";
      this.wfCurrentNodeBadge.className = "badge-tag";
    }
  }

  highlightWorkflowStep(idx) {
    document.querySelectorAll(".workflow-node").forEach(n => {
      n.classList.remove("active", "failed", "rollback");
    });
    document.querySelectorAll(".workflow-edge").forEach(e => e.classList.remove("active"));

    if (idx === -1) {
      this.updateWorkflowInspector(WORKFLOW_NODES[0], "C0_INIT (Chờ thực thi)", "IDLE");
      return;
    }

    if (idx === 0) {
      const n = document.getElementById("node_wf_planner");
      if (n) n.classList.add("active");
      this.updateWorkflowInspector(WORKFLOW_NODES[1], "C0_INIT ➔ C1_PLAN", "ACTIVE");
    } else if (idx === 1) {
      const n = document.getElementById("node_wf_lawgraph");
      if (n) n.classList.add("active");
      this.updateWorkflowInspector(WORKFLOW_NODES[2], "C1_PLAN ➔ C2_RETRIEVAL", "RUNNING");
    } else if (idx === 2) {
      const n = document.getElementById("node_wf_auditor");
      const g = document.getElementById("node_wf_decision");
      if (n) n.classList.add("failed");
      if (g) g.classList.add("failed");
      this.updateWorkflowInspector(WORKFLOW_NODES[3], "C2_RETRIEVAL ➔ ORACLE_FAILURE", "REVOKED");
    } else if (idx === 3) {
      const n = document.getElementById("node_wf_rollback");
      const p = document.getElementById("node_wf_planner");
      if (n) n.classList.add("rollback");
      if (p) p.classList.add("active");
      this.updateWorkflowInspector(WORKFLOW_NODES[5], "DIFF_ROLLBACK ➔ C1_PLAN (Sub B Cached)", "RECOVERED");
    } else if (idx >= 4) {
      const d = document.getElementById("node_wf_drafter");
      const s = document.getElementById("node_wf_sqlite");
      const e = document.getElementById("node_wf_end");
      if (d) d.classList.add("active");
      if (s) s.classList.add("active");
      if (e) e.classList.add("active");
      this.updateWorkflowInspector(WORKFLOW_NODES[7], "C1_PLAN ➔ C3_FINAL_DOSSIER", "COMPLETED");
    }
  }

  updateWorkflowInspector(node, transition, badge) {
    if (this.wfNodeName) this.wfNodeName.textContent = node.label;
    if (this.wfNodeClass) this.wfNodeClass.textContent = node.class || "StateGraph Node";
    if (this.wfNodeTokens) this.wfNodeTokens.textContent = node.tokens || "< 450 tokens";
    if (this.wfNodeTransition) this.wfNodeTransition.textContent = transition;
    if (this.wfCurrentNodeBadge) {
      this.wfCurrentNodeBadge.textContent = badge;
      this.wfCurrentNodeBadge.className = `badge-tag ${badge === "REVOKED" ? "result-danger" : badge === "RECOVERED" ? "result-warning" : "result-success"}`;
    }
  }

  // ==========================================================================
  // STATUTORY KNOWLEDGE GRAPH SVG RENDERER (TAB 4)
  // ==========================================================================
  renderStatutoryGraph() {
    if (!this.lawSvg) return;
    this.lawSvg.innerHTML = "";

    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
      <marker id="arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#71717a" />
      </marker>
      <marker id="arrow-green" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
      </marker>
      <marker id="arrow-purple" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#a855f7" />
      </marker>
    `;
    this.lawSvg.appendChild(defs);

    GRAPH_DATA.edges.forEach(edge => {
      const fromNode = GRAPH_DATA.nodes.find(n => n.id === edge.from);
      const toNode = GRAPH_DATA.nodes.find(n => n.id === edge.to);
      if (!fromNode || !toNode) return;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("id", `edge_${edge.from}_${edge.to}`);
      path.setAttribute("class", "graph-edge");

      const dx = toNode.x - fromNode.x;
      const dy = toNode.y - fromNode.y;
      const cx1 = fromNode.x + dx * 0.5;
      const cy1 = fromNode.y;
      const cx2 = fromNode.x + dx * 0.5;
      const cy2 = toNode.y;

      let d = `M ${fromNode.x} ${fromNode.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${toNode.x} ${toNode.y}`;
      if (edge.type === "rollback") {
        d = `M ${fromNode.x} ${fromNode.y} C ${fromNode.x - 100} ${fromNode.y - 80}, ${toNode.x + 100} ${toNode.y - 80}, ${toNode.x} ${toNode.y}`;
      }

      path.setAttribute("d", d);
      path.setAttribute("stroke", edge.type === "rollback" ? "#a855f7" : edge.type === "reroute" ? "#10b981" : "#3f3f46");
      path.setAttribute("stroke-width", edge.type === "rollback" ? "2.5" : "1.5");
      path.setAttribute("fill", "none");
      path.setAttribute("marker-end", edge.type === "rollback" ? "url(#arrow-purple)" : edge.type === "reroute" ? "url(#arrow-green)" : "url(#arrow)");
      this.lawSvg.appendChild(path);
    });

    GRAPH_DATA.nodes.forEach(node => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("class", "graph-node");
      g.setAttribute("id", `node_${node.id}`);

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", node.x);
      circle.setAttribute("cy", node.y);
      circle.setAttribute("r", "20");
      circle.setAttribute("fill", "#181820");
      circle.setAttribute("stroke", node.color);
      circle.setAttribute("stroke-width", "2");

      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", node.x);
      text.setAttribute("y", node.y + 32);
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("fill", "#f4f4f5");
      text.setAttribute("font-size", "11px");
      text.setAttribute("font-weight", "600");
      text.textContent = node.label;

      const subText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      subText.setAttribute("x", node.x);
      subText.setAttribute("y", node.y + 45);
      subText.setAttribute("text-anchor", "middle");
      subText.setAttribute("fill", "#71717a");
      subText.setAttribute("font-size", "9px");
      subText.textContent = node.sub;

      g.appendChild(circle);
      g.appendChild(text);
      g.appendChild(subText);

      this.lawSvg.appendChild(g);
    });
  }

  highlightStatutoryGraphStep(idx) {
    document.querySelectorAll("#lawGraphSvg .graph-node circle").forEach(c => {
      c.setAttribute("r", "20");
      c.setAttribute("stroke-width", "2");
    });

    if (idx === 0) {
      this.pulseLawNode("lead");
    } else if (idx === 1) {
      this.pulseLawNode("sub_a");
      this.pulseLawNode("doc_old");
    } else if (idx === 2) {
      this.pulseLawNode("oracle");
      this.pulseLawNode("doc_old");
    } else if (idx === 3) {
      this.pulseLawNode("lead");
      this.pulseLawNode("doc_new");
    } else if (idx === 4) {
      this.pulseLawNode("drafter");
      this.pulseLawNode("doc_new");
    }
  }

  pulseLawNode(id) {
    const el = document.querySelector(`#lawGraphSvg #node_${id} circle`);
    if (el) {
      el.setAttribute("r", "25");
      el.setAttribute("stroke-width", "3.5");
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.demoApp = new DemoApp();
});
