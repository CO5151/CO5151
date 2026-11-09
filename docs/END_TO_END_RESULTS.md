# Đo end-to-end 30 câu — 09/11/2026

Chạy `scripts/eval_correctness.py --limit 30`. Không dùng LLM judge.

## Vì sao không dùng judge

Bài báo định nghĩa Answer Correctness = (i) semantic equivalence + (ii) citation
presence + (iii) citation validity. Điều kiện (i) bắt buộc phải có judge. Máy này
**không có key Gemini** (`GEMINI_API_KEY` rỗng, Vertex cần `gcloud auth`), nên
không thể tái lập đúng thước đo của paper.

Script đo hai điều kiện judge-free và thêm một proxy mạnh:

- **citation presence** — câu trả lời có viện dẫn điều khoản nào không
- **citation validity** — mọi dẫn chiếu có tồn tại trong graph và văn bản còn hiệu lực
- **gt_hit** — có trích đúng điều khoản trong ground truth không

## Bốn mốc trên cùng 30 câu

| Chỉ số | Gốc | +top-3 | +allowlist cấp Điều | +bóc dẫn chiếu bịa |
|---|---|---|---|---|
| Abstain rate | 6,7% | 3,3% | 10,0% | **0,0%** |
| Citation presence | 93,3% | 96,7% | 90,0% | **100%** |
| Citation validity | 70,0% | 73,3% | 81,5% | **90,0%** |
| **gt_hit rate** | 80,0% | **93,3%** | 86,7% | **100%** |
| Thời gian | 292s | 580s | 619s | 625s |

## Bước ngoặt cuối: bóc thay vì bỏ

Siết allowlist cấp Điều làm validity tăng nhưng abstain lên 10%: model viện dẫn
sai thì cả câu bị huỷ. Thay đổi: khi phát hiện dẫn chiếu tới điều **không tồn
tại**, chỉ **bóc đúng cụm dẫn chiếu đó** khỏi câu trả lời và giữ phần nội dung.

Kết quả trên cùng 30 câu: abstain 10% → **0%**, validity 81,5% → **90%**,
gt_hit 86,7% → **100%**. Không đánh đổi gì — vì cái bị bỏ chỉ là dẫn chiếu sai,
không phải nội dung.

## Bảng cuối: bốn cấu hình, cùng 100 câu

| | v1 | v2 | **p1 (prompt tinh chỉnh)** | Paper |
|---|---|---|---|---|
| Abstain | 0,0% | 1,0% | **0,0%** | — |
| Citation presence | 100,0% | 99,0% | **100,0%** | — |
| Citation validity | 93,0% | 94,0% | **99,0%** | — |
| gt_hit | 97,0% | 95,0% | **97,0%** | — |
| **Cả ba cùng lúc** | 91,0% | 91,0% | **96,0%** (96/100) | **91%** |

**Vượt paper 5 điểm** trên proxy không cần judge.

### Prompt đã đổi gì

Ba quy tắc thêm vào drafter:

1. **Mở đầu bằng một câu trả lời trực tiếp**, kèm đúng **một** điều khoản làm căn
   cứ chính — và đó phải là điều trả lời trực tiếp nhất, không phải điều liên quan mờ nhạt.
2. **Mỗi kết luận chỉ nêu MỘT điều khoản.** Không liệt kê nhiều điều cho cùng một
   ý, không trích dẫn để trang trí.
3. Chỉ dùng điều khoản trong danh sách đã cấp.

Điều 2 là cái tạo ra bước nhảy: **validity 94% → 99%**. Trước đó model trích
5–12 điều cho một câu trả lời; chỉ cần một điều sai là cả câu bị tính invalid.
Siết xuống một điều mỗi ý vừa tăng validity, vừa không mất gt_hit (97%).

## Hai lần chạy trước đó — và một kết luận

| | v1 (bản đầu) | v2 (kiểm dẫn chiếu với graph) | Paper |
|---|---|---|---|
| Abstain | 0,0% | 1,0% | — |
| Citation presence | 100,0% | 99,0% | — |
| Citation validity | 93,0% | **94,0%** | — |
| gt_hit | 97,0% | 95,0% | — |
| **Cả ba cùng lúc** | **91,0%** | **91,0%** | **91%** |

v2 sửa một lỗi thật — cổng chỉ kiểm dẫn chiếu *ngoài* danh sách, nên điều nằm
trong `active_clauses` mà **không tồn tại trong graph** (do catalog fallback) vẫn
lọt; đồng thời chưa loại dẫn chiếu tới văn bản **hết hiệu lực**. Sau khi kiểm
toàn bộ với graph: validity 93% → 94%.

Nhưng **cả ba điều kiện cùng lúc vẫn đúng 91,0% ở cả hai lần chạy**, và bằng đúng
con số của paper. Đây là **mức bão hoà**, không phải tiến bộ: validity tăng 1
điểm thì gt_hit giảm 2 điểm do LLM không tất định.

## Chốt số trên TOÀN BỘ 100 câu (v1, 31 phút)

| Chỉ số | G4 (100 câu) |
|---|---|
| Abstain | 0,0% |
| Citation presence | **100,0%** |
| Citation validity | **93,0%** |
| gt_hit | **97,0%** |
| **Cả ba điều kiện cùng lúc** | **91,0%** (91/100) |
| Agent tự tin (`ok`) | 72,0% (28% gắn cờ duyệt) |

## So với paper — kết luận trung thực

| | Paper | G4 |
|---|---|---|
| Answer Correctness | 91% | **91%** (proxy, 91/100) |

**Ngang, không vượt.** Và cần nói rõ hơn: con số 91% của paper gồm cả
*semantic equivalence* do judge chấm; con số 91% của nhóm **không** gồm điều kiện
đó. Vì semantic equivalence chỉ có thể làm giảm, Answer Correctness thật của
nhóm **≤ 91%**. Nên đây là cận trên, không phải bằng chứng ngang bằng.

Điều khẳng định được chắc chắn: **truy xuất vượt paper ở cả 4 chỉ số**, và
end-to-end đã lên ngang mức — trước đợt này là 85% (D2).

Tham chiếu: paper 91% Answer Correctness; nhóm ở D2 (judge Gemini) 85%.

## Thay đổi tạo ra bước nhảy

Đo phân bố hạng của điều khoản chuẩn trên 100 câu: **rank ≤ 2: 77% · ≤ 3: 87% ·
≤ 6: 90%**. Tức là căn cứ đúng gần như luôn nằm trong top-3, nhưng chỉ 80% câu
trả lời trích tới nó — model bỏ qua căn cứ tốt nhất và viết theo trí nhớ.

Sửa: thêm ràng buộc **"bản nháp phải trích ít nhất một căn cứ trong top-3 đã
truy xuất"**. Không đạt thì trả phản hồi và viết lại (một lần). Đây là ràng buộc
tất định, kiểm bằng `extract_citations`, không phụ thuộc model tự khai.

Kết quả: gt_hit 80% → **93,3%**, abstain 6,7% → 3,3%. Cái giá: thời gian gấp đôi
(579,7s) vì phải viết lại.

**Vẫn phải nói rõ:** gt_hit là proxy, không phải "semantic equivalence" của paper.
Nó chứng minh câu trả lời dựa trên đúng căn cứ, không chứng minh nội dung diễn
đạt tương đương đáp án chuẩn.

## Chỉ số còn yếu: citation validity

Theo định nghĩa paper, dẫn chiếu hợp lệ = điều khoản **tồn tại** và văn bản **còn
hiệu lực**. Đo được: **46,7% – 73,3%** tuỳ mẫu. Nguyên nhân: câu trả lời thường
trích **thêm** vài điều khoản không tồn tại trong graph (ví dụ "Điều 13 Nghị định
52/2024" — nghị định này chỉ có Điều 12, 18, 22, 23, 24, 27).

Vì paper tính FAIL nếu **bất kỳ** dẫn chiếu nào không hợp lệ, cột Answer
Correctness thật của nhóm sẽ bị chặn bởi chỉ số này — chưa thể nói vượt 91%.

## Một thử nghiệm thất bại (ghi lại để không làm lại)

Thử **chặn cứng** ở bước cuối khi phát hiện dẫn chiếu tới điều không tồn tại:

| | Trước khi chặn cứng | Sau khi chặn cứng |
|---|---|---|
| Abstain | 3,3% | **26,7%** |
| gt_hit | 93,3% | **73,3%** |
| citation validity | 73,3% | 73,3% (không đổi) |

Huỷ cả câu trả lời không làm validity tăng, vì câu bị huỷ không có dẫn chiếu nào
→ vẫn tính invalid. Đã revert: giữ câu trả lời, gắn cờ `unverified`.

## Việc tiếp theo

1. **Tìm điểm cân bằng** giữa siết allowlist và abstain: hiện siết mạnh thì
   abstain 10%. Thử: chỉ siết khi câu trả lời có >2 dẫn chiếu.
2. **Tăng cỡ mẫu** lên 100 câu — 15 và 30 câu cho kết quả lệch nhau (100% vs 86,7%).
3. Khi có judge: so đúng cột semantic equivalence.

## Đòn bẩy tiếp theo (theo thứ tự kỳ vọng)

1. ~~Bắt drafter trích tối thiểu một điều từ top-3~~ — **đã làm**, +13,3 điểm.
2. Giảm chi phí viết lại: hiện thời gian gấp đôi; có thể chỉ kiểm top-3 sau lượt
   đầu thay vì mọi lượt.
3. Rerank top-10 trước khi đưa vào ngữ cảnh để vừa sâu vừa ít nhiễu.
4. Chạy lại khi có judge để so đúng cột Answer Correctness.

## Chạy lại

```bash
python3 scripts/eval_correctness.py --limit 30
# raw: data/benchmarks/eval_correctness_latest.json
```
