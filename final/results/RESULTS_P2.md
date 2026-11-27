# Kết quả mới vượt paper cũ — bản dùng cho D3

Cập nhật: 26/11/2026 · Mọi số dưới đây **tính lại trực tiếp từ raw JSON**, không chép từ slide D2.

Nguồn raw:
- `data/benchmarks/eval_correctness_100.json` (cấu hình **v1**)
- `data/benchmarks/eval_correctness_100_v2.json` (cấu hình **v2**)
- `data/benchmarks/eval_correctness_100_p1.json` (cấu hình **p1**)
- `docs/RETRIEVAL_RESULTS.md` & `scripts/make_results_workbook.py` (commit `b40ace3`, đo retrieval trên đủ 100 câu với `dense_top_k=6`, Neo4j bật, Hybrid RRF + BM25 + `cap=2/văn bản`)
- `eval/raw/retrieval_100.json` (tạo bởi `scripts/eval_retrieval.py` ngày 27/11/2026 trên `src/agents/lawgraph.py` sau khi sửa khử trùng cấp Điều + Okapi BM25+IDF fallback, đủ 100 câu)
- Testset: `data/benchmarks/sbv_testset_tvpl.json` (100 câu, ground truth chuyên gia)

---

## 1. Kết quả chính: 96/100 so với 91/100 của paper

Cùng 100 câu, cùng định nghĩa 3 điều kiện (presence + validity + trúng căn cứ), **không dùng LLM judge**:

| Chỉ số | v1 | v2 | **p1 (chốt)** | Paper [1] |
|---|---:|---:|---:|---:|
| Abstain | 0,0% | 1,0% | **0,0%** | — |
| Citation presence | 100,0% | 99,0% | **100,0%** | — |
| Citation validity | 93,0% | 94,9% | **99,0%** | — |
| Trúng căn cứ (`gt_hit`) | 97,0% | 95,0% | **97,0%** | — |
| **Cả ba điều kiện cùng lúc** | 91,0% | 91,0% | **96,0% (96/100)** | **91,0% (91/100)** |
| Tổng thời gian 100 câu | 1856,7 s | 2056,4 s | **1182,6 s** | — |
| Giây/câu (wall-clock, cả batch) | 18,6 | 20,6 | **11,8** | — |
| Số lần retry | 29 | 37 | 30 | — |

**Chênh lệch: +5,0 điểm tuyệt đối (96 so với 91).**

### Phát biểu được phép dùng
> Trên proxy ba điều kiện đo được bằng code (không cần judge), cấu hình p1 đạt **96/100**, cao hơn 5 điểm so với 91/100 công bố trong SBV-LawGraph [1] trên cùng bộ 100 câu.

### Phát biểu **không** được dùng
> ~~"Hệ thống vượt paper về Answer Correctness"~~ — sai. Con số 91% của paper gồm **cả** điều kiện *semantic equivalence* do Gemini judge chấm; proxy 96% của nhóm **không** có điều kiện đó. Vì semantic equivalence chỉ có thể **làm giảm** điểm, Answer Correctness thật của nhóm là **≤ 96%**, chưa xác định. Đây là **cận trên**, không phải bằng chứng vượt.

Rubric A3/A5 phạt đúng kiểu overclaim này ("kết luận vượt xa dữ liệu", "claim khớp số liệu"). Ghi cận trên + cách kiểm chứng còn thiếu là **điểm cộng**, không phải điểm trừ.

---

## 2. Vì sao 96% không phải may mắn — cơ chế nhân quả

Bước nhảy 91% → 96% không đến từ đổi model hay tăng token, mà từ **một ràng buộc tất định ở đầu ra**:

**Đo được tiền đề:** trên 100 câu, hạng của điều khoản chuẩn trong kết quả truy xuất là
`rank ≤ 2: 77%` · `rank ≤ 3: 87%` · `rank ≤ 6: 90%`. Căn cứ đúng gần như **luôn** nằm trong top-3, nhưng chỉ 80% câu trả lời trích tới nó — model bỏ qua căn cứ tốt nhất và viết theo trí nhớ.

**Can thiệp:** thêm 3 quy tắc vào prompt drafter, trong đó quy tắc then chốt là *"bản nháp phải trích ít nhất một căn cứ trong top-3 đã truy xuất"*. Không đạt → viết lại (một lần). Điều kiện này **kiểm bằng `extract_citations` trong code**, không phụ thuộc model tự khai.

**Kết quả riêng của can thiệp:** `gt_hit` 80% → 93,3%, abstain 6,7% → 3,3% (đo trên 30 câu).
**Kết quả trên 100 câu (p1):** validity 94,9% → **99,0%** — do quy tắc "mỗi kết luận chỉ nêu MỘT điều khoản, không trích để trang trí". Trước đó model trích 5–12 điều/câu, chỉ cần một điều sai là cả câu tính invalid.

Đây là **ablation tách được cơ chế** mà RT3 yêu cầu: cùng model, cùng testset, cùng ngân sách token, chỉ khác ràng buộc đầu ra.

---

## 3. Truy xuất: đo lại đúng `k = 2` và nâng cấp (27/11/2026)

Tiến trình cải thiện tầng truy hồi qua ba mốc trên bộ 100 câu `sbv_testset_tvpl.json`:
1. **D2 (25/10/2026):** đo ở `k ≈ 3,25`, đạt `34,47%` — từng diễn đạt sai là "HOÀN TOÀN NHẤT QUÁN" với paper.
2. **Mốc `b40ace3` (09/11/2026):** thêm Hybrid RRF + BM25 + `cap=2/văn bản`, đo lại đúng `k = 2` (`dense_top_k=6`, Neo4j bật) đạt **`P@2 = 41,0%`**, `F2@2 = 0,638`, `R@6 = 89,2%`.
3. **Mốc `27/11/2026` (`scripts/eval_retrieval.py` → `eval/raw/retrieval_100.json`):** sửa lỗi trùng chunk cùng Điều trong `dense_retrieve()`, bổ sung Okapi BM25+IDF (unigram + bigram) làm nhánh lexical fallback trong `LawGraphAgent`, chặn `STATUTE_CATALOG` đè RRF, và truyền `raw_query` sạch cho bi-encoder. Kết quả chạy kiểm chứng đủ 100 câu (cấu hình mặc định `hybrid_rrf`, `top_k = 6`, Neo4j đang tắt nên nhánh lexical dùng chỉ mục BM25+IDF cục bộ):

| Chỉ số truy xuất | Paper [1] (1.703 VB) | G4 — `b40ace3` (09/11) | **G4 — `hybrid_rrf` (27/11, raw JSON)** | Kết luận |
|---|---:|---:|---:|---|
| Precision@2 | 37,0–39,0% | 41,0% (`0,410`) | **48,0% (`0,4800`)** | **Vượt +9 đến +11 điểm** (cùng `k = 2`) |
| F2@2 | 0,60–0,61 | 0,638 | **0,737 (`0,7366`)** | **Vượt** (cùng `k = 2`) |
| Recall | 76,0% (`@10`) | 89,2% (`@6`) | **96,0% (`@6`)** (`R@2=86,8%`) | **Vượt +20,0 điểm** ngay ở `k = 6` |
| Hit@2 | — | 77,0% | **89,0%** (`Hit@6 = 96,0%`) | 89/100 câu lọt top-2 |
| Độ nhiễu ngữ cảnh (`1 − P@2`) | > 60,0% | ~59,0% | **52,0%** | **Giảm > 8 điểm** (cùng định nghĩa) |
| Xử lý văn bản hết hiệu lực | 0,0% (gom NĐ 101/2012) | 100,0%\* | **100,0%\*** | **Vượt\*** (*phụ thuộc metadata đồ thị) |

*(Ghi chú ablation từ cùng raw `eval/raw/retrieval_100.json`: `dense_only` đạt `P@2 = 49,0% / R@6 = 96,0% / F2@2 = 0,7485`; `bm25_only` đạt `P@2 = 48,5% / R@6 = 90,5% / F2@2 = 0,7450`; `hybrid_rrf` đạt `P@2 = 48,0% / R@6 = 96,0% / F2@2 = 0,7366`.)*

**Bốn điểm trung thực bắt buộc phải giữ trong D3:**
1. **Chênh lệch quy mô kho dữ liệu (rất quan trọng):** SBV-LawGraph [1] truy xuất trên **1.703 văn bản**, còn chỉ mục vector/BM25 cục bộ hiện tại của G4 mới chứa **29 văn bản NHNN cốt lõi** (91 điều duy nhất / 103 chunk trong `qdrant_chunks_export.json`; đồ thị có ~34 văn bản gồm metadata) nhưng đã bao phủ 100% điều khoản ground truth của 100 câu test. Do đó, con số `P@2 = 48,0%` **chỉ đại diện trong phạm vi tập con 29 văn bản đã lập chỉ mục**, chưa tương đương truy xuất toàn kho 1.703 văn bản.
2. **Trần lý thuyết trên bộ 100 câu là `54,5%`:** có 91/100 câu chỉ có đúng 1 điều khoản ground truth (trung bình 1,13 điều/câu), nên `P@2 = 48,0%` đạt ~88% trần toán học của bộ test.
3. **Không trộn cấu hình:** mọi con số trên đo ở `dense_top_k = 6` (`b40ace3` đo lúc Neo4j bật; `27/11` đo với Neo4j tắt nên đi qua fallback `lexical_retrieve_export`). Đợt W1.5 sẽ chạy lại cả khi Neo4j bật để đối chứng.
4. **Cảnh báo metadata:** `data/processed/neo4j_graph_export.json` vẫn còn bản ghi `101/2012/ND-CP` gán nhầm `status: "in_force"`, nên chỉ số lọc hết hiệu lực 100% vẫn mang tính phụ thuộc dữ liệu đồ thị cục bộ.

---

## 4. Điểm tham chiếu D2 (để thấy tiến bộ trong kỳ)

| Mốc | Answer Correctness | Cách đo |
|---|---:|---|
| D2 (chốt interim) | **85,0%** | LLM-as-judge Gemini, 100 câu (`sbv_100_gemini_judge_summary.json`) |
| Paper [1] | 91,0% | Judge, gồm semantic equivalence |
| G4 p1 (nay) | **96,0%** | Proxy 3 điều kiện, **không** judge |

⚠️ **Ba con số này không cùng thang đo.** Không được xếp chung một bảng mà không ghi rõ cột "cách đo". Với D3 phải hoặc (a) chạy judge trên p1 để có số cùng thang, hoặc (b) trình bày proxy riêng và nói rõ.

---

## 5. Việc còn thiếu để A3 đạt mức 9–10

Kết quả trên là **1 run/cấu hình**. Yêu cầu cứng là **3 run/cấu hình** trên **100 câu**, tức:

```
C1 (p1)        : 100 câu × 3 run = 300 task-run
C2 (ablation)  : 100 câu × 3 run = 300 task-run
────────────────────────────────────────────────────
Tổng           : 600 task-run
```

Ước tính thời gian từ số đo thật: C1 ≈ 11,8 s/câu → ~59 phút; C2 (tắt selective traversal, ngắn hơn) ~9–10 s/câu → ~50 phút. **Tổng ~2 giờ máy**, chia 3 máy thì dưới 1 giờ.

Còn thiếu và phải bổ sung trong lần chạy này:
1. **Mỗi dòng raw** phải có: `run_id, config_id, seed, latency_ms (wall-clock từng câu), input_tokens, output_tokens, cost_usd, retries, error_class, trace_path`.
2. **Báo cáo mean + SD** qua 3 run, không chỉ 1 run.
3. **Cost/task** — hiện chưa có trong raw; phải tính từ token thật, ghi rõ đơn giá và ngày.
4. **Kiểm chứng nhiễu:** p1 96% có nằm ngoài 1 SD của 3 run không? Nếu SD > 3 điểm thì phải hạ giọng kết luận.
5. **Contamination:** bộ 100 câu lấy từ thuvienphapluat.vn, công khai, đã dùng trong paper [1]. Phải có đoạn thảo luận + 5 câu held-out tự soạn chấm tay.

---

## 6. Tham chiếu

[1] K. N. Phan, X.-B. Le, T. T. Quan, "SBV-LawGraph: A Hybrid RAG Approach Integrating Knowledge Graph for the State Bank of Vietnam Legal Documents," *ACIIDS*, Springer, 2026.
