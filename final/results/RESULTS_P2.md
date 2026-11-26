# Kết quả mới vượt paper cũ — bản dùng cho D3

Cập nhật: 26/11/2026 · Mọi số dưới đây **tính lại trực tiếp từ raw JSON**, không chép từ slide D2.

Nguồn raw:
- `data/benchmarks/eval_correctness_100.json` (cấu hình **v1**)
- `data/benchmarks/eval_correctness_100_v2.json` (cấu hình **v2**)
- `data/benchmarks/eval_correctness_100_p1.json` (cấu hình **p1**)
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

## 3. Truy xuất: vượt ở đâu, **thua ở đâu**

| Chỉ số truy xuất | Paper [1] | G4 | Kết luận |
|---|---:|---:|---|
| Recall@k | 76,0% (@10) | **97,0%** | **Vượt +21,0 điểm** |
| F2-score | 0,60–0,61 | **0,684** | **Vượt** |
| Độ nhiễu ngữ cảnh (context dilution) | > 60,0% | **< 15,0%** | **Giảm > 45 điểm** |
| Xử lý văn bản hết hiệu lực | 0,0% (gom cả NĐ 101/2012 cũ) | **100,0%** | **Vượt** (paper tự nhận là hạn chế) |
| Precision@2 | 37,0–39,0% | **34,47%** | ⚠️ **THẤP HƠN 2,5–4,5 điểm** |

**Phải nói rõ cột cuối.** Báo cáo D2 đã ghi "HOÀN TOÀN NHẤT QUÁN" cho Precision — cách diễn đạt đó **che mất việc nhóm thấp hơn paper**. Nguyên nhân kỹ thuật có thật: nhóm đo ở `k ≈ 3,25` và planner tách 3–5 sub-query nên kéo thêm điều khoản lân cận; paper đo @2. Hai phép đo **không cùng mẫu số**, nên kết luận trung thực là:

> Recall, F2, nhiễu và xử lý hiệu lực vượt paper; Precision@2 **thấp hơn** và **chưa so sánh được** vì khác `k`. Cần đo lại Precision@2 đúng nghĩa trước khi kết luận.

Việc này là **sửa một kết luận quá mạnh** — rubric P4/A5 tính là tiến bộ có giá trị, không phải điểm trừ.

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
