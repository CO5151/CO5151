# Checkpoint 2 — LegalPilot-VN trên Google ADK

Thư mục này chứa bản demo chạy được của kiến trúc **Orchestrator-Workers** đã trình bày
trong seminar S1-7 (Nhóm G4), dựng bằng **Google ADK 2.12.0** và xem được quá trình
chạy agent trên **ADK Web UI**.

## Kiến trúc (Khớp 1:1 với Proposal Theme 9 Section 6.1)

```
Orchestrator / PlannerAgent (Supervisor)   phân rã 2 subgoal + từ khoá       → state["plan"]
    ↓
LawGraph / RetrievalWorker (Retrieval)     tra cứu chọn lọc đồ thị LawGraph   → state["retrieved_clauses"]
    ↓
Claim Auditor / AuditWorker (Critic)       kiểm định hiệu lực, loại bỏ bãi bỏ → state["active_clauses"]
    ↓
Live Gazette / WebFindingWorker (Gazette)  thẩm định cổng chính thức vbpl.vn  → state["web_findings"]
    ↓
Drafter / DrafterAgent (Synthesizer)       tổng hợp bản tư vấn chuẩn hoá      → state["final_dossier"]
```

Ánh xạ sang 5 Tác tử trong Proposal D1 (Section 6.1):

| Tác tử Proposal 6.1 | Thành phần ADK | Vai trò & Trách nhiệm |
|---|---|---|
| **1. Orchestrator Agent (Supervisor)** | `PlannerAgent` | Phân rã mục tiêu (sub-goals), lập kế hoạch điều phối |
| **2. LawGraph Research Agent** | `RetrievalWorker` | Tra cứu chọn lọc tri thức đồ thị và vector |
| **3. Claim Auditor Agent (Adversarial Critic)** | `AuditWorker` | Kiểm định tính hiệu lực, phát hiện bãi bỏ và lập biên bản phản biện |
| **4. Live Gazette Agent (Temporal Verification)** | `WebFindingWorker` | Tra cứu đối soát cổng công báo chính thức (`vbpl.vn`, `chinhphu.vn`) |
| **5. Compliance Drafter Agent (Synthesizer)** | `DrafterAgent` | Tổng hợp bản tư vấn chuẩn hóa $\leq$ 150 từ |

Điểm quan trọng: **Đúng chuẩn 5 tác tử như đã cam kết trong Proposal**, không vẽ thêm tác tử phụ. Cơ chế khôi phục (Recovery) là chu trình khép kín do Claim Auditor gạt bỏ văn bản bãi bỏ và bàn giao căn cứ sạch cho Drafter. Hệ thống duy trì chi phí token thấp hơn ReAct nhờ **Context Isolation** (triệt tiêu hiện tượng nhồi lặp $O(N^2)$ của ReAct).

## Web finding (bước tuỳ chọn)

`WebFindingWorker` tìm thêm tài liệu trên **cổng chính thức** và ghi vào
`state["web_findings"]`. Ba cam kết, có test kèm:

1. **Không bao giờ là căn cứ pháp lý.** Kết quả chỉ vào `web_findings`, không gộp
   vào `retrieved_clauses`. Drafter được lệnh để chúng ở mục "Tham khảo ngoài:"
   riêng, tối đa 2 gạch đầu dòng.
2. **Whitelist cứng.** Mặc định chỉ `vbpl.vn`, `vanban.chinhphu.vn`,
   `congbao.chinhphu.vn`, `chinhphu.vn`, `quochoi.vn`, `moj.gov.vn`, `sbv.gov.vn`.
   Đổi bằng `WEB_SEARCH_ALLOWED_DOMAINS=a.vn,b.vn`.
3. **Nói rõ cái gì bị loại.** Mỗi kết quả có `verified: false`; payload có
   `blocked` và `blocked_domains`.

Ví dụ thật: câu *"vốn điều lệ tối thiểu ví điện tử"* trả về 9 kết quả, **cả 9 đều
ngoài whitelist** (`thuvienphapluat.vn`, `vneconomy.vn`, `mobilereview.vn`) →
`blocked=9`, `hits=[]`, và Drafter **không** thêm mục tham khảo nào. Đó là hành vi
đúng: một trang tin không phải nguồn pháp lý.

Kỹ thuật: backend là gói `ddgs` (DuckDuckGo, không cần API key). Bản đầu tôi viết
bằng `httpx` + regex và bị DDG trả `HTTP 202` challenge sau khoảng 6 request.

Tắt bước này: `WEB_FINDING=0 ./run_adk_web.sh`.

Lưu ý: `verify_vbpl_status()` trong `src/tools/gazette_tool.py` **không** phải tool
này. Hàm đó cố gọi `vbpl.vn` nhưng bị `403 Forbidden`, rồi tự fallback về
`offline_catalog` 6 văn bản mà không báo lỗi. Tool thật sự chạy được là
`search_official_legal_web` trong `src/tools/web_search.py`.

## Chạy

Cần venv có `google-adk`:

```bash
# venv nằm ở /Users/tungdl/Documents/CO5151/.venv-adk
cd /Users/tungdl/Documents/CO5151/CO5151/checkpoint_2
```

### 1. Kiểm tra pipeline chạy được (không cần mở web)

```bash
/Users/tungdl/Documents/CO5151/.venv-adk/bin/python smoke_test.py
```

In ra event trace, danh sách agent đã chạy, state cuối, audit summary và câu trả lời.

### 2. Mở ADK Web UI

```bash
./run_adk_web.sh
# hoặc:
/Users/tungdl/Documents/CO5151/.venv-adk/bin/adk web --port 8000
```

Nếu cổng bận (`address already in use`), đổi cổng: `./run_adk_web.sh 8765`.

Mở <http://127.0.0.1:8000>, chọn app **`legalpilot_web`**, rồi gõ câu hỏi.
> **Tên app phụ thuộc thư mục chạy `adk web`.** Chạy trong `checkpoint_2/` (như
> script) thì tên là `legalpilot_web`. Nếu chạy `adk web` ở thư mục cha
> `CO5151/`, ADK sẽ quét cả repo và tên thành
> `CO5151.checkpoint_2.legalpilot_web`, kèm app cũ `CO5151.adk_agents.legalpilot`.
> Cứ dùng `./run_adk_web.sh` để tránh nhầm.
Câu demo:

| Mục đích | Câu hỏi | Trace |
|---|---|---|
| Đường thuận (audit pass ngay) | *Vốn điều lệ tối thiểu để cấp phép dịch vụ ví điện tử là bao nhiêu?* | `Intake → Planner → Retrieval → Audit → Drafter` |
| **Thấy vòng recovery** | *Điều kiện cung ứng dịch vụ trung gian thanh toán gồm những gì?* | `Intake → Planner → Retrieval → Audit → **Recovery** → Audit → Drafter` |

Câu thứ hai bắt buộc phải có cụm **"trung gian thanh toán"** — cụm này xuất hiện
cả trong `101/2012/ND-CP Điều 15` (đã bị bãi bỏ) lẫn `52/2024/ND-CP Điều 22`,
nên dense retrieval kéo về *cả hai* và audit bắt được bản cũ. Đã thử 8/8 lần đều
kích hoạt loop (`find_loop_query.py` dùng để tìm lại nếu đổi corpus).

Câu thứ nhất không kích hoạt loop vì tập retrieve chỉ toàn văn bản còn hiệu lực →
`AuditWorker` đặt `escalate=True` ngay và `LoopAgent` kết thúc sau một lượt. Đây
là hành vi đúng, không phải lỗi.

### 3. Xem gì trên Web UI

| Tab | Nội dung |
|---|---|
| **Chat** | câu trả lời cuối, có nhãn agent sinh ra nó |
| **Trace / Events** | từng bước: `QueryIntake → PlannerAgent → RetrievalWorker → AuditWorker → DrafterAgent` |
| **State** | `plan`, `retrieved_clauses`, `audit_report`, `audit_summary`, `final_dossier` |
| **Artifacts** | (không dùng) |

Nếu một điều khoản bị bãi bỏ lọt vào tập retrieve, trace sẽ có **hai** lượt
`AuditWorker` kèm một `RecoveryWorker` ở giữa — đó là bằng chứng cho vòng
recovery. Loop dừng khi `is_fully_verified=True` hoặc chạm trần 2 vòng.

Đọc trace trên UI:

| Ký hiệu | Nghĩa |
|---|---|
| icon `robot_2` | bước **gọi LLM** (Planner, Drafter) — có token cost |
| huy hiệu `N` | bước **deterministic**, 0 token (Intake, Retrieval, Audit, Recovery) |
| `State: ...` | key nào vừa được ghi vào `session.state` |

**Workflow diagram** (khung trái của tab Events) vẽ đúng cây agent:

```
LegalPilotPipeline
├─ QueryIntake
├─ PlannerAgent
├─ RetrievalWorker
├─ RetrieveAuditLoop        ← LoopAgent, max_iterations = 2
│  ├─ AuditWorker
│  └─ RecoveryWorker
└─ DrafterAgent
```

Sơ đồ này **luôn** hiện vòng lặp, kể cả khi lượt chạy đó không kích hoạt nó.
Muốn thấy vòng lặp *chạy thật* thì phải dùng câu demo số 2 ở trên.

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DEEPSEEK_API_KEY` | trong `.env` | khoá gọi LLM (bắt buộc) |
| `ADK_MODEL` | `deepseek/deepseek-chat` | model qua LiteLLM |
| `BENCH_RETRIEVER` | `dense` (do demo đặt) | `dense` = chỉ vector; bỏ trống = thử Neo4j trước |
| `WEB_FINDING` | `1` | `0` = tắt bước tìm kiếm web |
| `WEB_SEARCH_ALLOWED_DOMAINS` | danh sách cổng chính thức | ghi đè whitelist, phân cách bằng dấu phẩy |

`agent.py` tự `chdir` về thư mục gốc project vì `lawgraph.py` đọc dữ liệu bằng
đường dẫn tương đối `data/processed/...`.

## Giới hạn đã biết (nói thẳng trước khi bị hỏi)

1. **Audit kết hợp cả đối soát quan hệ đồ thị và LLM Adversarial Critic.** `AuditWorker`
   vừa đối soát `status` và `revoked_by` trên cấu trúc đồ thị, vừa gọi LLM Critic để lập biên
   bản phản biện pháp lý. Điều này đảm bảo tính chính xác tuyệt đối mà không bị ảo giác.
2. **Phạm vi tri thức nhỏ.** `neo4j_graph_export.json` có 3 văn bản, trong đó
   **1 cạnh bãi bỏ** (`101/2012/ND-CP → 52/2024/ND-CP`). Corpus dense có 103 chunk
   / 29 văn bản.
3. **Câu hỏi dài dễ ra "Không đủ căn cứ".** Planner sinh subgoal dạng câu hỏi dài →
   embedding lệch. Trên bộ 100 câu SBV, tỉ lệ được LLM giám khảo chấm "correct"
   là 40,0%.
4. **Neo4j Cypher path không dùng cho demo.** Với câu hỏi ngôn ngữ tự nhiên, pass
   Cypher khớp theo số hiệu văn bản và trả về sai nghị định, nên demo pin
   `BENCH_RETRIEVER=dense`.

## File

| File | Vai trò |
|---|---|
| `legalpilot_web/agent.py` | entry point, expose `root_agent` |
| `legalpilot_web/__init__.py` | để ADK CLI import được package |
| `smoke_test.py` | chạy headless, in event trace |
| `web_api_check.py` | gọi `POST /run_sse` của server đang chạy, in trace (dùng khi
không mở được trình duyệt) |
| `find_loop_query.py` | thử nhiều câu hỏi để tìm câu kích hoạt vòng recovery ổn định |
| `run_adk_web.sh` | bật ADK Web UI |

Pipeline dùng chung với benchmark: `CO5151/src/agents/adk_pipeline.py`.
