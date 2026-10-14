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
      tokens: 969,
      latency: "4,570 ms",
      steps: [
        {
          name: "Bước 1: Router phân loại yêu cầu",
          tokens: 180,
          desc: "Nhận dạng từ khóa 'ví điện tử', 'FDI' -> Định tuyến sang nhóm thủ tục thanh toán không dùng tiền mặt.",
          action: "classify_intent(query)",
          obs: "category = 'fintech_payment_licensing'",
          context: "[Prompt Router (DeepSeek)]:\nClassify intent: 'Doanh nghiệp muốn xin cấp phép ví điện tử thì vốn tối thiểu cần bao nhiêu tiền...'\nOutput: fintech_payment_licensing (180 tokens)"
        },
        {
          name: "Bước 2: Vector Search 1-Shot (Không có vòng lặp)",
          tokens: 340,
          desc: "Tìm kiếm ngữ nghĩa 1 lần: Chỉ bốc trúng Điều 18 Thông tư 40/2024/TT-NHNN (hồ sơ mở ví), trượt mất Điều 22 NĐ 52/2024.",
          action: "dense_hybrid_search(query, top_k=2)",
          obs: "matched_document = '40/2024/TT-NHNN:Article_18' (Quy định về hồ sơ, thỏa thuận mở ví điện tử)",
          context: "[Prompt Retriever]:\nQuery: 'cấp phép ví điện tử vốn tối thiểu'\nResult: [40/2024/TT-NHNN] Điều 18: Hồ sơ mở ví điện tử..."
        },
        {
          name: "Bước 3: Tổng hợp kết quả (Thất bại trước bẫy pháp lý)",
          tokens: 449,
          status: "failed",
          desc: "LLM sinh câu trả lời dựa trên context thiếu sót, không có cơ chế rà soát lại để tìm văn bản quy định về vốn.",
          action: "synthesize_response(matched_document)",
          obs: "THẤT BẠI: Kết luận 'Không có quy định nào đề cập đến vốn điều lệ tối thiểu' do thiếu Điều 22 NĐ 52/2024.",
          context: "[DeepSeek Output (Live Run)]:\n'Dựa trên căn cứ pháp lý cung cấp (Thông tư 40/2024/TT-NHNN, Điều 18), không có quy định nào đề cập đến vốn điều lệ tối thiểu... Không thể trả lời doanh nghiệp cần bao nhiêu vốn.' (SAI NGHIỆP VỤ)"
        }
      ],
      grounding: "0% (Bỏ sót quy định vốn tối thiểu)",
      outcomeClass: "result-danger"
    },

    // Pattern 2: Monolithic ReAct Agent
    p2: {
      tokens: 6351,
      latency: "7,096 ms",
      steps: [
        {
          name: "Turn 1: Tool search_statutes()",
          tokens: 1150,
          desc: "DeepSeek tự gọi công cụ tra cứu ngữ nghĩa vector dense embedding trong 103 chunks.",
          thought: "Người dùng cần biết mức vốn điều lệ tối thiểu và căn cứ pháp lý hiện hành để xin cấp phép ví điện tử. Tôi cần tra cứu quy định cấp phép.",
          action: "search_statutes(query='vốn điều lệ tối thiểu cấp phép cung ứng dịch vụ ví điện tử')",
          obs: "Tìm thấy: Nghị định 52/2024/NĐ-CP (Điều 22: Vốn tối thiểu 50 tỷ đồng) và Thông tư 40/2024/TT-NHNN (Điều 27).",
          context: "[System Prompt: 650 tokens (Luật, tools, hướng dẫn)]\n+ [User Query]\n--> Tổng Context Turn 1: 1.150 tokens"
        },
        {
          name: "Turn 2: Tool verify_statute_validity() [Đồ thị Neo4j]",
          tokens: 2480,
          desc: "DeepSeek nhận diện cần kiểm tra hiệu lực NĐ 52/2024 và TT 40/2024 qua đồ thị Neo4j; context bắt đầu dồn lịch sử Turn 1.",
          thought: "Đã có NĐ 52/2024 và TT 40/2024. Để tránh tư vấn sai luật, tôi cần kiểm tra tính hiệu lực pháp lý của hai văn bản này qua đồ thị quan hệ Neo4j.",
          action: "verify_statute_validity('52/2024/ND-CP') | verify_statute_validity('40/2024/TT-NHNN')",
          obs: "Neo4j Graph xác nhận: Cả 2 văn bản đều IN_FORCE (Còn hiệu lực). NĐ 52/2024 bãi bỏ/thay thế NĐ 101/2012/NĐ-CP.",
          context: "[System Prompt + User Query]\n+ [Turn 1 Thought + Action: search_statutes + Observation: 52/2024 & 40/2024]\n--> Toàn bộ lịch sử Turn 1 được nhồi vào prompt. Context Turn 2: 2.480 tokens."
        },
        {
          name: "Turn 3: Tổng hợp kết luận [Context dồn dập 6.351 tokens]",
          tokens: 2721,
          desc: "Toàn bộ hội thoại và kết quả tool dồn tích vào prompt (>2.700 tokens cho 1 lượt). Đưa ra kết luận đúng nhưng tốn chi phí gấp 6.5x.",
          thought: "Đã có đầy đủ căn cứ từ Qdrant và Neo4j. Tôi sẽ tổng hợp kết luận tư vấn pháp lý hoàn chỉnh.",
          action: "finish_response()",
          obs: "KẾT QUẢ ĐẠT: Vốn tối thiểu 50 tỷ VNĐ theo Điều 22 NĐ 52/2024. Cảnh báo NĐ 101/2012 cũ đã bị bãi bỏ.",
          context: "[Toàn bộ hội thoại tích lũy qua các turns: > 2.700 tokens]\n--> Tổng token thực tế đo đạc: 1.150 + 2.480 + 2.721 = 6.351 tokens (Gấp 6.5 lần)"
        }
      ],
      grounding: "100% (Tìm đúng luật nhưng tốn 6.351 tokens)",
      outcomeClass: "result-warning"
    },

    // Pattern 3: Orchestrator-Workers (Google ADK & LangGraph)
    p3: {
      tokens: 2580,
      latency: "8,856 ms",
      steps: [
        {
          name: "Bước 1: Lead Orchestrator phân rã Subgoals",
          tokens: 180,
          desc: "Orchestrator phân rã câu hỏi thành 2 subgoals độc lập (Vốn tối thiểu & Điều kiện FDI) mà không mang vác context nặng.",
          thought: "Phân rã thành: Subgoal 1 = 'Điều kiện vốn pháp định tối thiểu 50 tỷ đồng'; Subgoal 2 = 'Thủ tục và điều kiện FDI theo NĐ 52/2024'.",
          action: "plan_subgoals(query)",
          obs: "Đã khởi tạo kế hoạch: [Subgoal 1: PENDING, Subgoal 2: PENDING]",
          memory: [
            { type: "state", text: "State Schema: LegalAgentState (session_id: sess_d994bf5e)" },
            { type: "plan", text: "Subgoal 1: Vốn tối thiểu 50 tỷ đồng (PENDING)" },
            { type: "plan", text: "Subgoal 2: Điều kiện nhà đầu tư FDI (PENDING)" }
          ],
          context: "[Lead Prompt (Google ADK)]: Chỉ phân tích và sinh subgoals. Context gọn nhẹ: 180 tokens."
        },
        {
          name: "Bước 2: LawGraph Worker tra cứu độc lập",
          tokens: 0,
          desc: "Worker duyệt đồ thị quan hệ Neo4j và Qdrant dense chunks bằng thuật toán graph traversal (0 token LLM).",
          thought: "Tra cứu đồ thị quan hệ cho 2 subgoals, phát hiện NĐ 101/2012 có liên kết REVOKED_BY sang NĐ 52/2024.",
          action: "LawGraphAgent.retrieve_provisions(subgoals)",
          obs: "Thu thập 4 điều khoản (Điều 22 & 23 NĐ 52/2024, Điều 18 & 23 TT 40/2024).",
          memory: [
            { type: "keep", text: "● Đồ thị Neo4j: Cung cấp Điều 22 & 23 NĐ 52/2024 (Vốn 50 tỷ, FDI trần 49%)" },
            { type: "pending", text: "○ Chuyển giao danh sách điều khoản sang Claim Auditor để chốt chặn hiệu lực" }
          ],
          context: "[Code Traversal thuần túy]: Chạy ngầm trong worker, 0 token LLM tiêu hao."
        },
        {
          name: "Bước 3: Claim Auditor chốt chặn hiệu lực qua VBPL",
          tokens: 0,
          status: "recovered",
          desc: "Auditor đối soát hiệu lực độc lập qua cơ sở dữ liệu quốc gia VBPL và đồ thị bãi bỏ. Bắt buộc 100% căn cứ phải còn hiệu lực.",
          action: "ClaimAuditorAgent.audit_provisions(clauses)",
          obs: "XÁC THỰC 100%: NĐ 52/2024 và TT 40/2024 hợp lệ hoàn toàn; chặn đứng hoàn toàn NĐ 101/2012 cũ.",
          memory: [
            { type: "keep", text: "● Grounding Rate: 100.0% Grounded" },
            { type: "update", text: "✅ Toàn bộ căn cứ pháp lý đã qua kiểm định hợp lệ (is_fully_verified = True)" }
          ],
          context: "[Auditor Logic]: Kiểm tra logic Python đối chiếu DB, 0 token LLM tiêu hao."
        },
        {
          name: "Bước 4: Compliance Drafter tổng hợp hồ sơ",
          tokens: 2400,
          desc: "Drafter chỉ nhận các điều khoản sạch đã được Auditor phê duyệt để soạn thảo bản tư vấn chuyên nghiệp kèm lộ trình.",
          action: "DrafterAgent.synthesize_dossier(verified_clauses, audit_report)",
          obs: "HOÀN TẤT: Căn cứ Điều 22 NĐ 52/2024: Vốn tối thiểu 50 tỷ VNĐ (Doanh nghiệp 35 tỷ -> Thiếu 15 tỷ); Tỷ lệ FDI 49% theo Điều 23; kèm 5 bước khuyến nghị thực thi.",
          memory: [
            { type: "keep", text: "💾 Ghi nhận checkpoint hoàn tất vào SQLite (enterprise_compliance.db) - Session ID: sess_d994bf5e" }
          ],
          context: "[Drafter Prompt (Google ADK)]: Chỉ nhận điều khoản sạch còn hiệu lực. Tổng token toàn bộ: 2.580 tkn (Tiết kiệm 59.4% so với ReAct)."
        }
      ],
      grounding: "100% Grounded (Xác thực tuyệt đối qua VBPL & Neo4j)",
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
    this.renderP1Diagram();
    this.renderP2Diagram();
    this.renderP3Diagram();
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

    this.p1Svg = document.getElementById("p1Svg");
    this.p2Svg = document.getElementById("p2Svg");
    this.p3Svg = document.getElementById("p3Svg");

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
      <text x="180" y="116" text-anchor="middle" fill="#f87171" font-size="8" font-family="monospace">🚫 BỘ NHỚ: Stateless (0 Memory) · Không lưu checkpoint</text>
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

      <!-- In-Memory Context Bloat Callout Banner -->
      <rect x="18" y="100" width="324" height="24" rx="4" fill="rgba(245, 158, 11, 0.08)" stroke="rgba(245, 158, 11, 0.3)" />
      <text x="180" y="116" text-anchor="middle" fill="#fbbf24" font-size="8" font-family="monospace">⚠️ BỘ NHỚ: In-Memory (Context dồn tích qua các turn)</text>
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

      <!-- Re-route Arc from Oracle back to Lead Orch -->
      <path id="p3_e_rollback" d="M 158 72 C 140 86, 110 86, 94 68" stroke="#a855f7" stroke-dasharray="3 2" stroke-width="1.5" fill="none" marker-end="url(#p3-arr-purple)" />
      <text x="126" y="88" text-anchor="middle" fill="#c084fc" font-size="7">↺ Re-route</text>

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
      <text x="180" y="119" text-anchor="middle" fill="#34d399" font-size="8" font-family="monospace">🛡️ KIỂM ĐỊNH VBPL & ĐIỀU HƯỚNG THAY THẾ (Google ADK)</text>
    `;
  }

  highlightParadigmDiagrams(idx) {
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

    if (idx === 0) {
      const r = document.getElementById("p1_n_router");
      if (r) r.setAttribute("stroke-width", "3");

      const l = document.getElementById("p2_n_llm");
      if (l) l.setAttribute("stroke-width", "3.2");

      const o = document.getElementById("p3_n_orch");
      if (o) o.setAttribute("stroke-width", "3.2");
    } else if (idx === 1) {
      const l1 = document.getElementById("p1_n_llm1");
      if (l1) l1.setAttribute("stroke-width", "3");

      const e = document.getElementById("p2_n_env");
      if (e) e.setAttribute("stroke-width", "3");

      const w1 = document.getElementById("p3_n_w1");
      if (w1) w1.setAttribute("stroke-width", "3");
    } else if (idx === 2) {
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
    } else if (idx === 3) {
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
    } else if (idx >= 4) {
      const d = document.getElementById("p3_n_drafter");
      if (d) d.setAttribute("stroke-width", "3.2");
    }
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

    this.highlightParadigmDiagrams(idx);
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
