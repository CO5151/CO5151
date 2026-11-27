# final/ — Bộ nộp D3 + D4 (G4 · CO5151 · HK261)

Hạn nộp: **23:59 CN 06/12/2026** · Bảo vệ: **T4 09/12, 19:30–19:50 + Q&A 19:50–20:00, B4-305 (có mặt 17:50)**

Thư mục này là **khung làm việc**, không phải bài nộp hoàn chỉnh. Mọi `[TODO: ...]` màu đỏ phải được xoá trước khi nộp.

## Vào từ đâu

| Nếu bạn là | Đọc file này trước |
|---|---|
| Bất kỳ ai | [`plan/WORK_ASSIGNMENT.md`](plan/WORK_ASSIGNMENT.md) — chia việc, lịch theo ngày, định nghĩa "xong" |
| Người viết báo cáo | [`report/main.tex`](report/main.tex) (bản Việt) & [`report/main_en.tex`](report/main_en.tex) (bản Anh) — khung 2 cột ACM; *khi nộp chọn đúng 1 ngôn ngữ nhất quán* |
| Người làm bảo mật | [`security/INJECTION_PLAN.md`](security/INJECTION_PLAN.md) & [`security/attacks/README.md`](security/attacks/README.md) — 20 ca, có phát hiện lỗ hổng trong code |
| Người làm slide | [`slides/main.tex`](slides/main.tex) — 19 frame, đã đánh dấu mốc phút |
| Người viết phần kết quả | [`results/RESULTS_P2.md`](results/RESULTS_P2.md) — số đã đối chiếu từ raw + `docs/RETRIEVAL_RESULTS.md` (gồm cả cận trên và lỗi dữ liệu) |

## Nội dung

```
final/
├── README.md                    ← file này
├── plan/
│   ├── STATUS.md                ← nhật ký tiến độ hàng ngày
│   └── WORK_ASSIGNMENT.md       ← chia việc + lịch 26/11–09/12 + rủi ro
├── report/
│   ├── main.tex                 ← D3 (VI), ACM sigconf 2 cột
│   ├── main_en.tex              ← D3 (EN), bản song song tiếng Anh
│   ├── refs.bib                 ← 8 entry đã kiểm từ D1/D2
│   ├── main.pdf                 ← bản build tiếng Việt
│   └── main_en.pdf              ← bản build tiếng Anh
├── slides/
│   ├── main.tex                 ← khung slide 16:9, 20 phút + 6 frame backup
│   └── main.pdf                 ← bản build hiện tại (19 frame)
├── results/
│   └── RESULTS_P2.md            ← kết quả mới: 96/100 vs paper 91/100
└── security/
    ├── INJECTION_PLAN.md        ← kế hoạch vá F1–F5 & lịch red-team
    └── attacks/                 ← 20 ca (cases.json), runner & results/
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
3. **Precision@2 hiện đạt 48,0% (và `F2@2 = 0,737`, `Recall@6 = 96,0%`, `Hit@2 = 89,0%`, nhiễu `52,0%`)** trên đủ 100 câu ở chế độ `hybrid_rrf` (`eval/raw/retrieval_100.json`, đo bằng `scripts/eval_retrieval.py` ngày 27/11 sau khi sửa lỗi khử trùng cấp Điều + Okapi BM25+IDF trong `LawGraphAgent`, tăng từ `34,47% @ k≈3,25` ở D2 → `41,0% @ 2` ở `b40ace3` → `48,0% @ 2`). **Bắt buộc ghi rõ giới hạn:** kết quả này đo trên **tập con chỉ mục cục bộ 29 văn bản / 103 chunk** (dù phủ 100% câu hỏi benchmark), chưa phải toàn kho 1.703 văn bản của paper [1], và vẫn còn lỗi metadata `101/2012/ND-CP`.

Rubric A3/A5 phạt nặng việc kết luận vượt xa dữ liệu. Ghi đúng cận trên + nói rõ phần chưa kiểm chứng là **điểm cộng**.

## Việc đang chặn tiến độ

- [ ] **Nguồn góp ý D2** — Phụ lục B (bảng phản hồi góp ý) bắt buộc phải có; trong tài liệu nhóm hiện chỉ có 3 góp ý D1. Cần hỏi GV (hạn 28/11).
- [ ] **Baseline ngoài chạy được** — số công bố của [1] không tái lập được tại máy; cần 1 baseline chạy được cùng corpus/model.
- [ ] **Switch ablation** — `enable_selective_traversal` hiện là config chết (chỉ khai báo, không nơi nào đọc) → phải sửa trước khi chạy C2.
- [ ] **Latency chưa được đo** — `src/evaluation/evaluator.py` tự khai "End-to-end latency is not measured in this run".

## Lưu ý kỹ thuật đã kiểm

- Report build bằng XeTeX/tectonic, font `texgyretermes` cho tiếng Việt — **giống toolchain D2**, nên artifact text-layer (dấu cách bị dính khi copy text, ví dụ "Hệđa") là **có từ D2**, không phải lỗi mới. Bản in/đọc vẫn đúng.
- Slide dùng `aspectratio=169`, theme tối giản, không phụ thuộc theme ngoài → build được offline sau lần tải bundle đầu.
