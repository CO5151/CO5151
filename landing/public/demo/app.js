/**
 * CO5151 Seminar S1-7: Agent Design Patterns Comparison
 * Streamlined, authentic interactive workbench for comparing 3 Agent architectures
 * Group G4 (LegalPilot-VN) - HCMUT-VNU
 */

const SCENARIOS = {
  fintech: {
    id: "fintech",
    title: "1. Cấp Phép Ví Điện Tử FDI (2024)",
    query: "Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024",
    enterprise: "Global PayTech Asia Ltd. (FDI)",
    trap: "NĐ 101/2012 bị bãi bỏ từ 01/07/2024; thay thế bằng NĐ 52/2024 (Vốn 50 tỷ VNĐ).",
    
    // Pattern 1: Deterministic Workflow
    p1: {
      tokens: 780,
      steps: [
        {
          name: "Bước 1: Router phân loại yêu cầu",
          tokens: 180,
          desc: "Nhận dạng từ khóa 'ví điện tử', 'FDI' -> Định tuyến sang nhóm thủ tục thanh toán không dùng tiền mặt.",
          action: "classify_intent(query)",
          obs: "category = 'fintech_payment_licensing'",
          context: "[Prompt Router cố định]:\nClassify intent: 'Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024'\nOutput: fintech_payment_licensing"
        },
        {
          name: "Bước 2: Truy vấn cơ sở dữ liệu tĩnh",
          tokens: 330,
          desc: "Lấy văn bản khớp cứng trong bảng tra cứu (chọn văn bản đầu tiên tìm thấy: NĐ 101/2012/NĐ-CP).",
          action: "db_lookup('fintech_payment_licensing')",
          obs: "matched_document = '101/2012/ND-CP' (Điều 15: Điều kiện cấp phép)",
          context: "[Prompt Retriever]:\nQuery: fintech_payment_licensing\nResult: 101/2012/ND-CP - Nghị định về thanh toán không dùng tiền mặt"
        },
        {
          name: "Bước 3: Định dạng kết quả tư vấn",
          tokens: 270,
          status: "failed",
          desc: "Soạn thảo văn bản viện dẫn trực tiếp NĐ 101/2012 mà không qua bước rà soát hiệu lực.",
          action: "format_response(matched_document)",
          obs: "THẤT BẠI: Trích dẫn văn bản đã hết hiệu lực từ 01/07/2024. Hồ sơ nộp lên NHNN sẽ bị từ chối.",
          context: "[Prompt Formatter]:\nInput: 101/2012/ND-CP\nOutput: 'Hồ sơ xin cấp phép áp dụng theo Nghị định 101/2012/NĐ-CP...' (SAI LUẬT)"
        }
      ],
      grounding: "0% (Dính luật hết hiệu lực)",
      outcomeClass: "result-danger"
    },

    // Pattern 2: Monolithic ReAct Agent
    p2: {
      tokens: 8950,
      steps: [
        {
          name: "Turn 1: Tool search_statute()",
          tokens: 950,
          desc: "LLM tự suy luận và gọi tool tìm kiếm văn bản pháp luật về cấp phép ví điện tử.",
          thought: "Người dùng cần biết điều kiện cấp phép ví điện tử cho nhà đầu tư nước ngoài. Tôi cần tìm văn bản quy định cấp phép.",
          action: "search_statute(query='quy định cấp phép dịch vụ ví điện tử')",
          obs: "Kết quả: Nghị định 101/2012/NĐ-CP (Điều 15 quy định điều kiện cấp phép cung ứng dịch vụ trung gian thanh toán).",
          context: "[System Prompt: 650 tokens (Luật, hướng dẫn, mô tả tools)]\n+ [User Query: 'Tư vấn điều kiện cấp phép ví điện tử cho nhà đầu tư ngoại năm 2024']\n--> Tổng Context Turn 1: 950 tokens"
        },
        {
          name: "Turn 2: Tool verify_validity()",
          tokens: 1750,
          desc: "LLM phát hiện cần kiểm tra hiệu lực NĐ 101/2012; context bắt đầu dồn lịch sử Turn 1.",
          thought: "Tôi cần kiểm tra xem Nghị định 101/2012/NĐ-CP còn hiệu lực thi hành hay không trước khi tư vấn.",
          action: "verify_validity(doc_id='101/2012/ND-CP')",
          obs: "CẢNH BÁO: Nghị định 101/2012/NĐ-CP ĐÃ BÃI BỎ từ 01/07/2024. Văn bản thay thế: Nghị định 52/2024/NĐ-CP.",
          context: "[System Prompt + User Query]\n+ [Turn 1 Thought + Action: search_statute + Observation: 101/2012]\n--> Toàn bộ lịch sử Turn 1 được nhồi vào prompt. Tổng Context Turn 2: 1.750 tokens"
        },
        {
          name: "Turn 3: Tool search_statute() [Context dài]",
          tokens: 2650,
          desc: "LLM tra cứu NĐ 52/2024 và điều kiện FDI. Context dài > 2.600 tokens làm tăng độ trễ.",
          thought: "NĐ 101 đã hết hiệu lực và được thay thế bởi NĐ 52/2024. Tôi cần tra cứu vốn điều lệ tối thiểu và tỷ lệ sở hữu nước ngoài trong NĐ 52/2024.",
          action: "search_statute(query='Nghị định 52/2024 vốn điều lệ tối thiểu và tỷ lệ sở hữu nước ngoài')",
          obs: "NĐ 52/2024/NĐ-CP: Điều 22 quy định vốn điều lệ tối thiểu 50 tỷ VNĐ; Điều 23 trần sở hữu nước ngoài tối đa 49%.",
          context: "[System Prompt + User Query]\n+ [Lịch sử Turn 1 + Obs 1] + [Lịch sử Turn 2 + Obs 2]\n--> Context phình to 2.650 tokens. Chú ý của LLM bị phân tán."
        },
        {
          name: "Turn 4: Tổng hợp kết quả [Context dồn dập]",
          tokens: 3600,
          status: "failed",
          desc: "Context dồn tích 3 turns trước (>3.600 tokens). LLM nhầm lẫn giữa điều kiện NĐ 101 và NĐ 52.",
          thought: "Đã có đủ dữ liệu. Tôi sẽ tổng hợp kết quả tư vấn cho Global PayTech Asia Ltd.",
          action: "finish_response()",
          obs: "KẾT QUẢ BỊ TRỘN LẪN: Nhận diện đúng NĐ 52/2024 nhưng lẫn lộn quy trình cấp phép cũ của NĐ 101 vào văn bản kết luận do prompt quá dài.",
          context: "[Toàn bộ hội thoại tích lũy qua 4 turns: > 3.600 tokens]\n--> Chi phí tích lũy 4 turns: 950 + 1750 + 2650 + 3600 = 8.950 tokens (Gấp 11.8 lần)"
        }
      ],
      grounding: "60% (Lẫn lộn luật cũ & mới do prompt dài)",
      outcomeClass: "result-warning"
    },

    // Pattern 3: Orchestrator-Workers (Google ADK)
    p3: {
      tokens: 2410,
      steps: [
        {
          name: "Bước 1: Lead Orchestrator phân rã Subgoals",
          tokens: 450,
          desc: "Phân tách truy vấn phức tạp thành 2 nhiệm vụ con độc lập: Subgoal A (Cấp phép) & Subgoal B (Vốn FDI).",
          thought: "Phân rã thành: Subgoal A = 'Điều kiện cấp phép ví điện tử'; Subgoal B = 'Kiểm tra trần sở hữu vốn ngoại 45% so với quy định'.",
          action: "plan_subgoals(query)",
          obs: "Đã khởi tạo kế hoạch: [Subgoal A: PENDING, Subgoal B: PENDING]",
          memory: [
            { type: "state", text: "State Schema: LegalAgentState (session_id: sess_01)" },
            { type: "plan", text: "Subgoal A: Cấp phép ví điện tử (PENDING)" },
            { type: "plan", text: "Subgoal B: Trần sở hữu ngoại FDI 45% (PENDING)" }
          ],
          context: "[Lead Prompt chuyên biệt]: Nhận diện và bẻ nhỏ subgoals. Context gọn nhẹ: 450 tokens."
        },
        {
          name: "Bước 2: Workers tra cứu độc lập (Context sạch)",
          tokens: 730,
          desc: "Worker 1 & Worker 2 chạy với context cách ly sạch (<400 tokens/worker), không dính lịch sử thừa.",
          thought: "Worker 1 tra cứu Subgoal A -> NĐ 101/2012. Worker 2 tra cứu Subgoal B -> Điều 23 trần ngoại 49%.",
          action: "Worker1: search(subgoal_a) | Worker2: search(subgoal_b)",
          obs: "Worker 1 trả về NĐ 101/2012. Worker 2 xác nhận FDI 45% <= trần 49% (ĐẠT).",
          memory: [
            { type: "keep", text: "● Subgoal B: FDI 45% ĐẠT (Trần 49%) - LƯU VÀO STATE MEMORY" },
            { type: "pending", text: "○ Subgoal A: Lấy văn bản NĐ 101/2012 - CHỜ KIỂM ĐỊNH" }
          ],
          context: "[Worker 1 Context: 380 tokens] | [Worker 2 Context: 350 tokens]\n--> Context mỗi worker hoàn toàn sạch, không bị tích lũy prompt."
        },
        {
          name: "Bước 3: ClaimAuditor kiểm định qua VBPL",
          tokens: 310,
          status: "failed",
          desc: "Auditor đối soát hiệu lực độc lập; phát hiện NĐ 101/2012 đã bị thay thế bởi NĐ 52/2024.",
          action: "verify_validity('101/2012/ND-CP')",
          obs: "CẢNH BÁO: NĐ 101/2012 đã hết hiệu lực từ 01/07/2024; quan hệ kế thừa: revoked_by = '52/2024/ND-CP'.",
          memory: [
            { type: "keep", text: "● Subgoal B: ĐÃ HỢP LỆ (Không bị ảnh hưởng)" },
            { type: "update", text: "⚠️ Subgoal A: NĐ 101/2012 HẾT HIỆU LỰC -> Cần điều hướng" }
          ],
          context: "[Auditor Context]: 310 tokens đối soát độc lập qua API cơ sở dữ liệu quốc gia VBPL."
        },
        {
          name: "Bước 4: Điều hướng thay thế & Bảo toàn State Memory",
          tokens: 620,
          status: "recovered",
          desc: "Truy vết sang NĐ 52/2024 theo quan hệ 'revoked_by'. Chỉ cập nhật Subgoal A, Subgoal B giữ nguyên trong memory.",
          thought: "Chỉ truy vấn lại văn bản thay thế 52/2024 cho Subgoal A. Subgoal B (FDI 45%) đã hợp lệ nên không chạy lại.",
          action: "reroute_successor('52/2024/ND-CP', subgoal_a)",
          obs: "Lấy NĐ 52/2024 Điều 22: Vốn tối thiểu 50 tỷ VNĐ (Doanh nghiệp 35 tỷ -> Thiếu 15 tỷ).",
          memory: [
            { type: "keep", text: "● Subgoal B (FDI 45%): ĐƯỢC BẢO TOÀN TRONG STATE MEMORY (Tiết kiệm 100% chi phí chạy lại)" },
            { type: "keep", text: "● Subgoal A: Đã cập nhật NĐ 52/2024 Điều 22 (Vốn 50 tỷ)" }
          ],
          context: "[Re-routing Prompt]: Chỉ điều phối lại Subgoal A. Giữ nguyên trạng thái Subgoal B."
        },
        {
          name: "Bước 5: Drafter tổng hợp từ State Memory",
          tokens: 650,
          desc: "Drafter nhận các điều khoản sạch từ bộ nhớ trạng thái để soạn thảo báo cáo tuân thủ chính xác 100%.",
          action: "draft_compliance_dossier(state_memory)",
          obs: "HOÀN TẤT: Căn cứ NĐ 52/2024: Vốn điều lệ 35 tỷ thiếu 15 tỷ so với mức tối thiểu 50 tỷ; Tỷ lệ FDI 45% đạt chuẩn.",
          memory: [
            { type: "keep", text: "💾 Ghi nhận checkpoint hoàn tất vào SQLite (enterprise_compliance.db)" }
          ],
          context: "[Drafter Context]: Nhận dữ liệu đã qua xác thực từ State Memory. Tổng token toàn bộ: 2.410 tkn (3.2x)."
        }
      ],
      grounding: "100% (Đã kiểm định qua VBPL)",
      outcomeClass: "result-success"
    }
  },

  traffic: {
    id: "traffic",
    title: "2. Xử Phạt Vượt Đèn Đỏ Xe Máy",
    query: "Mức xử phạt vượt đèn đỏ xe máy theo quy định mới nhất hiện hành",
    enterprise: "Logistics Express Vietnam JSC",
    trap: "NĐ 100/2019 (600k-1M) bị thay thế bởi NĐ 168/2024 (4M-6M, tước GPLX 1-3 tháng).",

    p1: {
      tokens: 760,
      steps: [
        {
          name: "Bước 1: Router định tuyến",
          tokens: 180,
          action: "classify_intent(query)",
          obs: "category = 'traffic_violation_penalty'",
          desc: "Định tuyến sang nhóm vi phạm trật tự an toàn giao thông đường bộ.",
          context: "Input: 'Mức xử phạt vượt đèn đỏ xe máy theo quy định mới nhất hiện hành'"
        },
        {
          name: "Bước 2: Tra cứu bảng tĩnh",
          tokens: 310,
          action: "db_lookup('traffic_violation_penalty')",
          obs: "matched_document = '100/2019/ND-CP' (Điều 6 Khoản 4)",
          desc: "Lấy NĐ 100/2019 quy định phạt 600.000 - 1.000.000 VNĐ.",
          context: "Query: traffic_violation_penalty -> Top match: 100/2019/ND-CP"
        },
        {
          name: "Bước 3: Định dạng kết quả",
          tokens: 270,
          status: "failed",
          action: "format_response(matched_document)",
          obs: "THẤT BẠI: Cung cấp mức phạt cũ 600k-1M; không có thông tin tước GPLX theo luật mới.",
          desc: "Không kiểm tra tính hiệu lực, tư vấn sai lệch mức phạt thực tế.",
          context: "Tư vấn phạt 600.000 - 1.000.000 VNĐ theo NĐ 100/2019 (ĐÃ BÃI BỎ)."
        }
      ],
      grounding: "0% (Văn bản đã bị bãi bỏ)",
      outcomeClass: "result-danger"
    },

    p2: {
      tokens: 8580,
      steps: [
        {
          name: "Turn 1: Tool search_statute()",
          tokens: 910,
          thought: "Cần tìm mức phạt tiền khi vượt đèn đỏ mô tô, xe gắn máy.",
          action: "search_statute(query='mức phạt vượt đèn đỏ xe máy')",
          obs: "Nghị định 100/2019/NĐ-CP Điều 6 Khoản 4: Phạt tiền từ 600.000 đến 1.000.000 đồng.",
          context: "System Prompt + User Query -> Context: 910 tokens"
        },
        {
          name: "Turn 2: Tool verify_validity()",
          tokens: 1680,
          thought: "Kiểm tra xem Nghị định 100/2019 còn hiệu lực không.",
          action: "verify_validity(doc_id='100/2019/ND-CP')",
          obs: "Nghị định 100/2019/NĐ-CP ĐÃ BÃI BỎ bởi Nghị định 168/2024/NĐ-CP.",
          context: "Prompt + Lịch sử Turn 1 (Thought, Action, Obs) -> Context: 1.680 tokens"
        },
        {
          name: "Turn 3: Tool search_statute() [Lịch sử dài]",
          tokens: 2540,
          thought: "NĐ 100 bị thay thế. Cần tìm mức phạt và hình thức tước GPLX trong NĐ 168/2024.",
          action: "search_statute(query='Nghị định 168/2024 mức phạt vượt đèn đỏ mô tô')",
          obs: "Nghị định 168/2024/NĐ-CP Điều 6 Khoản 4: Phạt từ 4.000.000 đến 6.000.000 VNĐ; tước GPLX 1-3 tháng.",
          context: "Prompt + Turn 1 + Turn 2 -> Context: 2.540 tokens"
        },
        {
          name: "Turn 4: Tổng hợp [Context dồn dập]",
          tokens: 3450,
          status: "failed",
          thought: "Tổng hợp các mức phạt đã tìm được trong toàn bộ lịch sử.",
          action: "finish_response()",
          obs: "LẪN LỘN: Báo mức phạt từ 600k đến 6 triệu đồng do context lưu cả kết quả NĐ 100 lẫn NĐ 168.",
          context: "Tích lũy trọn vẹn 4 turns: 910 + 1680 + 2540 + 3450 = 8.580 tokens (11.3x)"
        }
      ],
      grounding: "50% (Đưa cả mức phạt cũ và mới)",
      outcomeClass: "result-warning"
    },

    p3: {
      tokens: 2270,
      steps: [
        {
          name: "Bước 1: Lead Orchestrator phân rã",
          tokens: 420,
          thought: "Tách truy vấn thành: Subgoal A (Khung tiền phạt) và Subgoal B (Hình thức phạt bổ sung).",
          action: "plan_subgoals(query)",
          obs: "Khởi tạo: [Subgoal A: Khung tiền phạt, Subgoal B: Tước giấy phép]",
          memory: [
            { type: "plan", text: "Subgoal A: Khung tiền phạt vi phạm (PENDING)" },
            { type: "plan", text: "Subgoal B: Hình phạt bổ sung tước GPLX (PENDING)" }
          ],
          context: "Context Lead: 420 tokens phân rã."
        },
        {
          name: "Bước 2: Workers tra cứu độc lập",
          tokens: 650,
          action: "Worker1: search(subgoal_a) | Worker2: search(subgoal_b)",
          obs: "Worker 1 lấy NĐ 100/2019 Điều 6; Worker 2 xác định có áp dụng tước GPLX.",
          memory: [
            { type: "pending", text: "○ Subgoal A: NĐ 100/2019 (Chờ kiểm định)" },
            { type: "keep", text: "● Subgoal B: Có áp dụng hình thức tước GPLX (Đã xác định)" }
          ],
          context: "Worker 1: 360 tkn | Worker 2: 290 tkn (Context sạch, không dính lịch sử thừa)"
        },
        {
          name: "Bước 3: Auditor kiểm định hiệu lực",
          tokens: 290,
          status: "failed",
          action: "verify_validity('100/2019/ND-CP')",
          obs: "CẢNH BÁO: NĐ 100/2019 đã hết hiệu lực; thay thế bởi NĐ 168/2024/NĐ-CP.",
          memory: [
            { type: "update", text: "⚠️ Subgoal A: NĐ 100 hết hiệu lực -> Kế thừa sang NĐ 168/2024" },
            { type: "keep", text: "● Subgoal B: Giữ nguyên trong memory" }
          ],
          context: "Auditor Context: 290 tokens đối soát độc lập."
        },
        {
          name: "Bước 4: Điều hướng thay thế NĐ 168/2024",
          tokens: 590,
          status: "recovered",
          action: "reroute_successor('168/2024/ND-CP', subgoal_a)",
          obs: "Lấy NĐ 168/2024 Điều 6 Khoản 4: Phạt 4.000.000 - 6.000.000 VNĐ.",
          memory: [
            { type: "keep", text: "● Subgoal A: Đã cập nhật NĐ 168/2024 (Phạt 4 - 6 triệu VNĐ)" },
            { type: "keep", text: "● Subgoal B: Tước GPLX 1-3 tháng (Bảo toàn trong State Memory)" }
          ],
          context: "Chỉ cập nhật Subgoal A. Tổng token tiết kiệm đáng kể."
        },
        {
          name: "Bước 5: Drafter hoàn thiện báo cáo",
          tokens: 320,
          action: "draft_compliance_dossier(state_memory)",
          obs: "HOÀN TẤT: Phạt tiền 4.000.000 - 6.000.000 VNĐ, tước GPLX 01 - 03 tháng (NĐ 168/2024).",
          memory: [
            { type: "keep", text: "💾 Ghi vết kiểm định vào SQLite (session_id: traffic_01)" }
          ],
          context: "Tổng token: 2.270 tkn. Căn cứ chính xác 100%."
        }
      ],
      grounding: "100% (Chuẩn Nghị định 168/2024)",
      outcomeClass: "result-success"
    }
  },

  labor: {
    id: "labor",
    title: "3. Giấy Phép Lao Động Chuyên Gia Ngoại",
    query: "Điều kiện cấp giấy phép lao động cho chuyên gia nước ngoài",
    enterprise: "TechVentures VN LLC",
    trap: "NĐ 152/2020 (bằng đúng ngành) được sửa đổi bởi NĐ 70/2023 (nới lỏng sang bằng ĐH + 3 năm kinh nghiệm).",

    p1: {
      tokens: 780,
      steps: [
        {
          name: "Bước 1: Router phân loại",
          tokens: 180,
          action: "classify_intent(query)",
          obs: "category = 'foreign_labor_permit'",
          desc: "Định tuyến sang nghiệp vụ quản lý lao động nước ngoài.",
          context: "Input: 'Điều kiện cấp giấy phép lao động cho chuyên gia nước ngoài'"
        },
        {
          name: "Bước 2: Tra cứu NĐ 152/2020",
          tokens: 330,
          action: "db_lookup('foreign_labor_permit')",
          obs: "matched_document = '152/2020/ND-CP' (Điều 3 Khoản 3)",
          desc: "Lấy quy định cũ: Bắt buộc bằng đại học phải trùng tên chuyên ngành đào tạo.",
          context: "Query: foreign_labor_permit -> 152/2020/ND-CP Điều 3"
        },
        {
          name: "Bước 3: Định dạng kết quả",
          tokens: 270,
          status: "failed",
          action: "format_response(matched_document)",
          obs: "THẤT BẠI: Hướng dẫn doanh nghiệp từ chối chuyên gia nếu bằng cấp lệch ngành (Bỏ sót NĐ 70/2023).",
          desc: "Áp dụng luật cũ gây khó khăn, đình trệ tuyển dụng chuyên gia.",
          context: "Tư vấn theo NĐ 152/2020 (Bỏ sót văn bản sửa đổi NĐ 70/2023)."
        }
      ],
      grounding: "0% (Bỏ sót Nghị định 70/2023 sửa đổi)",
      outcomeClass: "result-danger"
    },

    p2: {
      tokens: 8770,
      steps: [
        {
          name: "Turn 1: Tool search_statute()",
          tokens: 940,
          thought: "Tìm điều kiện cấp giấy phép cho chuyên gia nước ngoài.",
          action: "search_statute(query='điều kiện chuyên gia giấy phép lao động')",
          obs: "NĐ 152/2020/NĐ-CP Điều 3: Yêu cầu có bằng đại học đúng chuyên ngành và 3 năm kinh nghiệm.",
          context: "Context Turn 1: 940 tokens"
        },
        {
          name: "Turn 2: Tool verify_validity()",
          tokens: 1720,
          thought: "Kiểm tra xem Điều 3 NĐ 152 có sửa đổi bổ sung không.",
          action: "verify_validity(doc_id='152/2020/ND-CP')",
          obs: "Điều 3 Khoản 3 đã được SỬA ĐỔI, BỔ SUNG bởi Nghị định 70/2023/NĐ-CP Điều 1 Khoản 5.",
          context: "Lịch sử Turn 1 + Turn 2 -> Context: 1.720 tokens"
        },
        {
          name: "Turn 3: Tool search_statute() [Lịch sử dồn]",
          tokens: 2600,
          thought: "Tìm nội dung sửa đổi tại Điều 1 Khoản 5 NĐ 70/2023.",
          action: "search_statute(query='Nghị định 70/2023 tiêu chuẩn chuyên gia')",
          obs: "NĐ 70/2023/NĐ-CP: Có bằng đại học trở lên hoặc tương đương và 3 năm kinh nghiệm phù hợp vị trí.",
          context: "Context phình lên 2.600 tokens."
        },
        {
          name: "Turn 4: Tổng hợp [Context dồn dập]",
          tokens: 3510,
          status: "failed",
          thought: "Tổng hợp kết quả tư vấn cho doanh nghiệp TechVentures.",
          action: "finish_response()",
          obs: "MƠ HỒ: Trích dẫn NĐ 70/2023 nhưng vẫn lưu ý điều kiện khắt khe của NĐ 152 do prompt dồn cả 2 văn bản.",
          context: "Tổng token tiêu tốn: 940 + 1720 + 2600 + 3510 = 8.770 tokens (11.2x)"
        }
      ],
      grounding: "70% (Lẫn lộn quy định cũ và mới)",
      outcomeClass: "result-warning"
    },

    p3: {
      tokens: 2340,
      steps: [
        {
          name: "Bước 1: Lead Orchestrator phân rã",
          tokens: 440,
          thought: "Tách thành: Subgoal A (Tiêu chuẩn văn bằng & kinh nghiệm) và Subgoal B (Hồ sơ giải trình).",
          action: "plan_subgoals(query)",
          obs: "Khởi tạo: [Subgoal A: Tiêu chuẩn chuyên gia, Subgoal B: Nhu cầu sử dụng lao động]",
          memory: [
            { type: "plan", text: "Subgoal A: Tiêu chuẩn văn bằng & kinh nghiệm (PENDING)" },
            { type: "plan", text: "Subgoal B: Giải trình nhu cầu sử dụng lao động (PENDING)" }
          ],
          context: "Context Lead: 440 tokens phân rã."
        },
        {
          name: "Bước 2: Workers tra cứu độc lập",
          tokens: 670,
          action: "Worker1: search(subgoal_a) | Worker2: search(subgoal_b)",
          obs: "Worker 1 lấy Điều 3 NĐ 152; Worker 2 xác nhận quy trình giải trình nhu cầu lao động.",
          memory: [
            { type: "pending", text: "○ Subgoal A: NĐ 152/2020 Điều 3 (Chờ kiểm định)" },
            { type: "keep", text: "● Subgoal B: Quy trình giải trình nhu cầu lao động (Đã xác thực)" }
          ],
          context: "Worker 1: 370 tkn | Worker 2: 300 tkn (Context sạch)"
        },
        {
          name: "Bước 3: Auditor kiểm định hiệu lực",
          tokens: 300,
          status: "failed",
          action: "verify_validity('152/2020/ND-CP')",
          obs: "CẢNH BÁO: Điều 3 Khoản 3 đã được SỬA ĐỔI bởi Nghị định 70/2023/NĐ-CP (quan hệ: amends).",
          memory: [
            { type: "update", text: "⚠️ Subgoal A: NĐ 152 đã sửa đổi -> Duyệt quan hệ 'amends' tới NĐ 70/2023" },
            { type: "keep", text: "● Subgoal B: Giữ nguyên trong memory" }
          ],
          context: "Auditor Context: 300 tokens kiểm định độc lập."
        },
        {
          name: "Bước 4: Điều hướng thay thế NĐ 70/2023",
          tokens: 600,
          status: "recovered",
          action: "reroute_successor('70/2023/ND-CP', subgoal_a)",
          obs: "Lấy NĐ 70/2023 Điều 1 Khoản 5: Bằng đại học bất kỳ + 3 năm kinh nghiệm phù hợp vị trí công việc.",
          memory: [
            { type: "keep", text: "● Subgoal A: Đã cập nhật NĐ 70/2023 (Nới lỏng điều kiện bằng cấp)" },
            { type: "keep", text: "● Subgoal B: Giải trình nhu cầu (Bảo toàn trong State Memory)" }
          ],
          context: "Chỉ cập nhật Subgoal A. Subgoal B giữ nguyên."
        },
        {
          name: "Bước 5: Drafter soạn thảo hướng dẫn",
          tokens: 330,
          action: "draft_compliance_dossier(state_memory)",
          obs: "HOÀN TẤT: Hướng dẫn tuyển dụng chuyên gia: Có bằng ĐH bất kỳ và 03 năm kinh nghiệm phù hợp (NĐ 70/2023).",
          memory: [
            { type: "keep", text: "💾 Ghi vết kiểm định vào SQLite (session_id: labor_01)" }
          ],
          context: "Tổng token: 2.340 tkn. Căn cứ chính xác 100%."
        }
      ],
      grounding: "100% (Áp dụng đúng NĐ 70/2023)",
      outcomeClass: "result-success"
    }
  }
};

class StreamlinedDemoApp {
  constructor() {
    this.currentScenarioKey = "fintech";
    this.currentStepIndex = -1; // -1: not started
    this.maxSteps = 5;
    this.isPlaying = false;
    this.speed = 1000;
    this.playTimer = null;

    this.initDOMElements();
    this.bindEvents();
    this.renderScenarioHeader();
    this.resetSimulation();
  }

  initDOMElements() {
    this.btnStep = document.getElementById("btnStep");
    this.btnPlay = document.getElementById("btnPlay");
    this.btnReset = document.getElementById("btnReset");

    this.scenTrap = document.getElementById("scenTrap");
    this.scenEnterprise = document.getElementById("scenEnterprise");
    this.scenQuery = document.getElementById("scenQuery");

    this.p1Logs = document.getElementById("p1Logs");
    this.p2Logs = document.getElementById("p2Logs");
    this.p3Logs = document.getElementById("p3Logs");

    this.p1Tokens = document.getElementById("p1Tokens");
    this.p2Tokens = document.getElementById("p2Tokens");
    this.p3Tokens = document.getElementById("p3Tokens");

    this.p1Status = document.getElementById("p1Status");
    this.p2Status = document.getElementById("p2Status");
    this.p3Status = document.getElementById("p3Status");

    this.pills = document.querySelectorAll(".scenario-pill");
    this.speedBtns = document.querySelectorAll(".speed-btn");
  }

  bindEvents() {
    this.pills.forEach(pill => {
      pill.addEventListener("click", () => {
        this.pills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        this.currentScenarioKey = pill.dataset.scenario;
        this.renderScenarioHeader();
        this.resetSimulation();
      });
    });

    this.speedBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        this.speedBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.speed = parseInt(btn.dataset.speed, 10);
        if (this.isPlaying) {
          this.pauseSimulation();
          this.playSimulation();
        }
      });
    });

    this.btnStep.addEventListener("click", () => {
      this.pauseSimulation();
      this.stepForward();
    });

    this.btnPlay.addEventListener("click", () => {
      if (this.isPlaying) {
        this.pauseSimulation();
      } else {
        this.playSimulation();
      }
    });

    this.btnReset.addEventListener("click", () => {
      this.resetSimulation();
    });
  }

  renderScenarioHeader() {
    const sc = SCENARIOS[this.currentScenarioKey];
    this.scenTrap.textContent = `Bẫy pháp lý: ${sc.trap}`;
    this.scenEnterprise.textContent = sc.enterprise;
    this.scenQuery.textContent = `"${sc.query}"`;
  }

  resetSimulation() {
    this.pauseSimulation();
    this.currentStepIndex = -1;
    this.renderStepState();
  }

  stepForward() {
    if (this.currentStepIndex < this.maxSteps - 1) {
      this.currentStepIndex++;
      this.renderStepState();
    } else {
      this.pauseSimulation();
    }
  }

  playSimulation() {
    if (this.currentStepIndex >= this.maxSteps - 1) {
      this.currentStepIndex = -1;
    }
    this.isPlaying = true;
    this.btnPlay.innerHTML = "<span>⏸ Tạm Dừng</span>";
    this.btnPlay.classList.add("btn-secondary");
    this.btnPlay.classList.remove("btn-primary");

    this.playTimer = setInterval(() => {
      if (this.currentStepIndex < this.maxSteps - 1) {
        this.currentStepIndex++;
        this.renderStepState();
      } else {
        this.pauseSimulation();
      }
    }, this.speed);
  }

  pauseSimulation() {
    this.isPlaying = false;
    if (this.playTimer) {
      clearInterval(this.playTimer);
      this.playTimer = null;
    }
    this.btnPlay.innerHTML = "<span>▶ Chạy Mô Phỏng</span>";
    this.btnPlay.classList.add("btn-primary");
    this.btnPlay.classList.remove("btn-secondary");
  }

  renderStepState() {
    const sc = SCENARIOS[this.currentScenarioKey];
    const idx = this.currentStepIndex;

    this.renderCardSteps(this.p1Logs, sc.p1.steps, idx, this.p1Tokens, this.p1Status, sc.p1);
    this.renderCardSteps(this.p2Logs, sc.p2.steps, idx, this.p2Tokens, this.p2Status, sc.p2);
    this.renderCardSteps(this.p3Logs, sc.p3.steps, idx, this.p3Tokens, this.p3Status, sc.p3);
  }

  renderCardSteps(container, steps, currentIdx, tokenEl, statusEl, patternObj) {
    container.innerHTML = "";
    let consumedTokens = 0;

    steps.forEach((st, i) => {
      const item = document.createElement("div");
      item.className = "log-step-item";

      const isExecuted = i <= currentIdx;
      if (isExecuted) {
        item.classList.add("active");
        consumedTokens += st.tokens;

        if (i === currentIdx) item.classList.add("current");
        if (st.status === "failed") item.classList.add("failed");
        if (st.status === "recovered") item.classList.add("recovered");
      }

      let extraBlocks = "";
      if (isExecuted) {
        if (st.thought) {
          extraBlocks += `
            <div class="step-block step-thought">
              <span class="block-tag">💭 Thought:</span> ${st.thought}
            </div>
          `;
        }
        if (st.action) {
          extraBlocks += `
            <div class="step-block step-action">
              <span class="block-tag">🛠️ Action (Tool):</span> <code>${st.action}</code>
            </div>
          `;
        }
        if (st.obs) {
          extraBlocks += `
            <div class="step-block step-obs">
              <span class="block-tag">👁️ Observation:</span> ${st.obs}
            </div>
          `;
        }
        if (st.memory && st.memory.length > 0) {
          const memItems = st.memory.map(m => `<div class="memory-item ${m.type}">${m.text}</div>`).join("");
          extraBlocks += `
            <div class="step-memory">
              <div class="memory-header">💾 State Memory:</div>
              ${memItems}
            </div>
          `;
        }
        if (st.context) {
          extraBlocks += `
            <div class="step-context">
              <div class="context-header">
                <span>📦 Context Window (Prompt gửi vào model)</span>
                <span class="context-size">${st.tokens} tokens</span>
              </div>
              <pre class="context-content">${st.context}</pre>
            </div>
          `;
        }
      }

      item.innerHTML = `
        <div class="step-meta">
          <span class="step-name">${st.name}</span>
          <span>${st.tokens} tokens</span>
        </div>
        <div class="step-desc">${st.desc}</div>
        ${extraBlocks}
      `;

      container.appendChild(item);
    });

    tokenEl.textContent = `${consumedTokens.toLocaleString()} tkn`;

    if (currentIdx >= steps.length - 1) {
      statusEl.textContent = patternObj.grounding;
      statusEl.className = `result-badge ${patternObj.outcomeClass}`;
    } else {
      statusEl.textContent = currentIdx === -1 ? "CHƯA BẮT ĐẦU" : `Đang chạy (Bước ${currentIdx + 1}/${steps.length})`;
      statusEl.className = "result-badge";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  new StreamlinedDemoApp();
});
