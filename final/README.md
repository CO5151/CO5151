# final/ — Bộ nộp D3 + D4 (G4 · CO5151 · HK261)

Hạn nộp: **23:59 CN 06/12/2026** · Bảo vệ: **T4 09/12, 19:30–19:50 + Q&A 19:50–20:00, B4-305 (có mặt 17:50)**

Thư mục này là **khung làm việc**, không phải bài nộp hoàn chỉnh. Mọi `[TODO: ...]` màu đỏ phải được xoá trước khi nộp.

## Vào từ đâu

| Nếu bạn là | Đọc file này trước |
|---|---|
| Bất kỳ ai | [`plan/WORK_ASSIGNMENT.md`](plan/WORK_ASSIGNMENT.md) — chia việc, lịch theo ngày, định nghĩa "xong" |
| Người viết báo cáo | [`report/main.tex`](report/main.tex) — khung 2 cột ACM, mỗi mục có ghi chú "viết gì, lấy bằng chứng ở đâu" |
| Người làm bảo mật | [`security/INJECTION_PLAN.md`](security/INJECTION_PLAN.md) — 14 ca, chia cho 3 người, có phát hiện lỗ hổng trong code |
| Người làm slide | [`slides/main.tex`](slides/main.tex) — 18 frame, đã đánh dấu mốc phút |
| Người viết phần kết quả | [`results/RESULTS_P2.md`](results/RESULTS_P2.md) — số đã tính lại từ raw, gồm cả chỗ **thua** paper |

## Nội dung

```
final/
├── README.md                    ← file này
├── plan/
│   └── WORK_ASSIGNMENT.md       ← chia việc + lịch 26/11–09/12 + rủi ro
├── report/
│   ├── main.tex                 ← khung D3, ACM sigconf 2 cột, tiếng Việt
│   ├── refs.bib                 ← 5 entry đã kiểm + chỗ cần bổ sung
│   └── main.pdf                 ← bản build hiện tại (3 trang khung)
├── slides/
│   ├── main.tex                 ← khung slide 16:9, 20 phút + 5 frame backup
│   └── main.pdf                 ← bản build hiện tại (18 frame)
├── results/
│   └── RESULTS_P2.md            ← kết quả mới: 96/100 vs paper 91/100
└── security/
    └── INJECTION_PLAN.md        ← A4: 14 ca direct + indirect
```

## Build

```bash
# Cần tectonic (đã cài sẵn trên máy này: /opt/homebrew/bin/tectonic)
cd final/report && tectonic main.tex     # → main.pdf
cd final/slides && tectonic main.tex     # → main.pdf
```

Nếu tectonic lỗi quyền ghi cache (sandbox), trỏ cache vào chỗ ghi được:

```bash
TECTONIC_CACHE_DIR=/tmp/tectonic-cache tectonic main.tex
```

## Ba con số phải thuộc (dùng đúng, đừng nói quá)

1. **96/100** — kết quả cấu hình p1 trên 100 câu, proxy 3 điều kiện, **không** dùng LLM judge. Paper [1] công bố **91/100**.
2. **96% là cận trên**, không phải bằng chứng vượt: paper có thêm điều kiện *semantic equivalence*, nhóm chưa đo.
3. **Precision@2 của nhóm thấp hơn paper** (34,47% vs 37–39%) và khác `k` → **chưa so sánh được**. Báo cáo D2 đã ghi "nhất quán" cho chỉ số này; D3 phải sửa lại.

Rubric A3/A5 phạt nặng việc kết luận vượt xa dữ liệu. Ghi đúng cận trên + nói rõ phần chưa kiểm chứng là **điểm cộng**.

## Việc đang chặn tiến độ

- [ ] **Nguồn góp ý D2** — Phụ lục B (bảng phản hồi góp ý) bắt buộc phải có; trong tài liệu nhóm hiện chỉ có 3 góp ý D1. Cần hỏi GV (hạn 28/11).
- [ ] **Baseline ngoài chạy được** — số công bố của [1] không tái lập được tại máy; cần 1 baseline chạy được cùng corpus/model.
- [ ] **Switch ablation** — `enable_selective_traversal` hiện là config chết (chỉ khai báo, không nơi nào đọc) → phải sửa trước khi chạy C2.
- [ ] **Latency chưa được đo** — `src/evaluation/evaluator.py` tự khai "End-to-end latency is not measured in this run".

## Lưu ý kỹ thuật đã kiểm

- Report build bằng XeTeX/tectonic, font `texgyretermes` cho tiếng Việt — **giống toolchain D2**, nên artifact text-layer (dấu cách bị dính khi copy text, ví dụ "Hệđa") là **có từ D2**, không phải lỗi mới. Bản in/đọc vẫn đúng.
- Slide dùng `aspectratio=169`, theme tối giản, không phụ thuộc theme ngoài → build được offline sau lần tải bundle đầu.
