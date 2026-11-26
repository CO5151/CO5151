# Chia việc G4 — D3 + D4 (26/11 → 09/12/2026)

Hạn nộp: **23:59 CN 06/12**. Bảo vệ: **T4 09/12, 19:30–19:50 + Q&A, B4-305, có mặt 17:50**.

## 0. Quyết định đã chốt (không bàn lại)

| Hạng mục | Chốt |
|---|---|
| Hướng | **Research** (RT1–RT4), baseline ngoài = SBV-LawGraph ACIIDS 2026 |
| Task set | **100 câu** SBV (toàn bộ `sbv_testset_tvpl.json`), không lọc |
| Cấu hình | **C1 = full** · **C2 = full − Selective Traversal** |
| Số run | **3 run/cấu hình** → **600 task-run** |
| Thời gian máy | ~2 giờ tuần tự (C1 ≈ 11,8 s/câu, C2 ~10 s/câu); chia 3 máy < 1 giờ |
| Định dạng báo cáo | ACM `sigconf`, 2 cột, tiếng Việt, thân bài 6–8 trang |
| Demo | Chạy trên tag `final`; có 1 ca tấn công + 1 hành động được bảo vệ |

## 1. Ba nguyên tắc làm việc

1. **Không số tay.** Mọi số trong báo cáo/slide sinh từ `eval/summary.csv` bằng `make tables`. Nếu chưa có số, ghi `\TODO{}` — không điền ước lượng.
2. **Không mô tả như đã làm.** Việc gì chưa xong thì ghi "chưa cài đặt" (rubric A2 trừ nặng nếu ngược lại).
3. **Mỗi việc phải có đường dẫn bằng chứng**: commit hash / trang báo cáo / dòng log. Ai làm gì thì ghi vào bảng §3 cuối ngày.

## 2. Việc theo workstream

### W1 · Harness đánh giá + 600 task-run — **Tùng** (Hưng hỗ trợ)
| # | Việc | Deliverable | Hạn | Xong khi |
|---|---|---|---|---|
| W1.1 | Sửa `enable_selective_traversal` thành switch thật (đang là config chết — grep chỉ thấy khai báo) | commit | **28/11** | `--ablate traversal` chạy khác kết quả C1 |
| W1.2 | Mở rộng `scripts/eval_correctness.py`: `--config C1\|C2`, `--run-id`, `--seed` | commit | **28/11** | chạy được `--limit 2 --config C2` |
| W1.3 | Thêm log từng câu: `latency_ms` (wall-clock), `cost_usd`, `trace_path`, `error_class` | commit | **28/11** | 1 dòng JSONL có đủ 4 field |
| W1.4 | Xoá dòng tự khai "latency not measured" trong `evaluator.py` | commit | 28/11 | grep không còn |
| W1.5 | Chạy **600 task-run** (3 máy song song) | `eval/raw/*.jsonl` | **01/12** | 600 dòng, đủ 3 run × 2 config × 100 câu |
| W1.6 | `scripts/make_final_tables.py`: raw → `eval/summary.csv` + bảng markdown | commit | **01/12** | chạy lại ra đúng số trong báo cáo |
| W1.7 | Mean ± SD qua 3 run + kiểm tra chênh lệch ngoài 1 SD | `eval/summary.csv` | 01/12 | có cột SD |
| W1.8 | Cost report: token thật × đơn giá, ghi model + ngày | `docs/COST_REPORT.md` | 02/12 | tổng USD khớp raw |

### W2 · Red team 14 ca — **Hưng** (Tùng, Phong mỗi người 4–5 ca)
Chi tiết đầy đủ ở [`final/security/INJECTION_PLAN.md`](../security/INJECTION_PLAN.md).
| # | Việc | Deliverable | Hạn | Xong khi |
|---|---|---|---|---|
| W2.1 | Khung `scripts/redteam_injection.py` + schema JSONL | commit | **27/11** | chạy `--phase before --dry-run` |
| W2.2 | 14 payload + `target_behavior` kiểm tự động được | `eval/redteam/cases.json` | **28/11** | 14 case, 6 direct + 8 indirect |
| W2.3 | **Pha A** — chạy trên code hiện tại | `injection_before.jsonl` | **28/11** | 14 dòng, dự đoán 13 fail |
| W2.4 | Vá FIX-1..FIX-8 (xem INJECTION_PLAN §4) | commit | **01/12** | mỗi FIX có commit riêng |
| W2.5 | **Pha B** — chạy lại | `injection_after.jsonl` | **03/12** | có bảng before/after |
| W2.6 | Audit trail ca A05 (nộp hồ sơ → token → audit) | log + ảnh | **02/12** | có 1 dòng audit thật |
| W2.7 | `threat_model_rules.yaml` v0 → v1 | commit | 04/12 | 10 vector khớp code thật |

### W3 · Báo cáo D3 — **Tùng chủ trì**, ai viết mục nấy
Khung: [`final/report/main.tex`](../report/main.tex). Sửa trực tiếp trong file, **không** tạo file mới.
| Mục | Nội dung | Người viết | Hạn |
|---|---|---|---|
| Abstract | 150 từ, có số | Tùng | 04/12 |
| §1 Giới thiệu + giả thuyết | người dùng, đóng góp, giả thuyết bác bỏ được | Tùng | 02/12 |
| §2 Related work | khoảng trống so với [1] | Tùng | 02/12 |
| §3 Thiết kế (R1–R4) | sơ đồ thật, tools, memory, 3 trục | **Tùng** R1/R2 · **Phong** R3 · **Hưng** R4 | 02/12 |
| §4 Triển khai | stack, trace thật, thay đổi từ D2 | Phong | 03/12 |
| §5 Đánh giá | task set, configs, kết quả, ablation, cost, lỗi | Tùng (khung) + Hưng (error analysis) | 03/12 |
| §6 Bảo mật | threat model, bảng 14 ca, residual risk | Hưng | 04/12 |
| §7 Giới hạn | tách giới hạn thiết kế vs phép đo | Tùng | 04/12 |
| §8 Đạo đức | nguồn dữ liệu, riêng tư, trách nhiệm | Phong | 04/12 |
| §9 Kết luận | trả lời giả thuyết bằng số | Tùng | 04/12 |
| Phụ lục A tái lập | lệnh, deps, hardware, seeds | Phong | 05/12 |
| Phụ lục B phản hồi góp ý | **cần dữ liệu góp ý D2** ⚠️ | Tùng | 04/12 |
| Phụ lục C đóng góp + AI-use | % + commit | cả 3 xác nhận | 05/12 |
| Phụ lục D đối chiếu R1–R4/RT1–RT4 | mã ↔ vị trí ↔ log | Tùng | 05/12 |

### W4 · Đóng gói D4 — **Phong**
| # | Việc | Deliverable | Hạn | Xong khi |
|---|---|---|---|---|
| W4.1 | Pin deps (đang dùng `>=`) | `requirements.lock.txt` | **02/12** | `pip install -r` chạy sạch |
| W4.2 | Rà `.env.example`: chỉ tên biến, không giá trị thật | file | 02/12 | grep không thấy key |
| W4.3 | README: thêm mục "tái lập trong 5 lệnh" | `README.md` | 03/12 | người ngoài làm theo được |
| W4.4 | `make demo` + `make eval-main` + `make tables` | `Makefile` | 03/12 | 3 target chạy được |
| W4.5 | Trace đại diện + raw results vào `eval/` | thư mục | 03/12 | có ≥3 trace |
| W4.6 | Test **checkout sạch** ở thư mục mới | biên bản ngắn | **04/12** | 5 lệnh chạy hết, ghi lỗi gặp |
| W4.7 | Cấp quyền repo + data cho GV, test bằng tài khoản khác | xác nhận | 05/12 | mở được không cần login owner |

### W5 · Slide, demo, video — **Tùng** (cả nhóm tập)
Khung: [`final/slides/main.tex`](../slides/main.tex), đã chia mốc phút.
| # | Việc | Hạn | Xong khi |
|---|---|---|---|
| W5.1 | Điền hết `\TODO` trong slide | **04/12** | 0 chữ đỏ |
| W5.2 | Demo script: 1 task + trace + 1 ca attack + 1 hành động token | 04/12 | chạy 3 lần liên tiếp không lỗi |
| W5.3 | Video dự phòng ~10' quay trên tag `final` | 05/12 | mở được, có tiếng |
| W5.4 | Tổng duyệt #1 bấm giờ | 05/12 | ≤ 20:00 |
| W5.5 | Tổng duyệt #2 + Q&A giả lập (mỗi người bị hỏi 5 câu) | 06/12 | không ai trả lời hộ |

### W6 · Hành chính — **Tùng**
| # | Việc | Hạn |
|---|---|---|
| W6.1 | Lấy góp ý D2 từ GV (chặn Phụ lục B) | **28/11** |
| W6.2 | Tag `final` + commit hash đầy đủ; ghi vào báo cáo + email | **05/12** |
| W6.3 | Email nộp: `[CO5151][G4] Final report + presentation`, CC cả nhóm, 4 PDF + link | **06/12 trước 23:59** |
| W6.4 | Nhắc từng người gửi **peer evaluation riêng**, không CC nhóm | 05/12 |
| W6.5 | Chuẩn bị "phiếu phản biện" nếu được phân nhóm phản biện | 06/12 |

## 3. Lịch theo ngày (ai làm gì)

| Ngày | Tùng | Phong | Hưng |
|---|---|---|---|
| **T5 26/11** | chốt phạm vi, dựng khung report/slide, commit | đọc INJECTION_PLAN, nhận 5 ca | khung redteam + schema log |
| **T6 27/11** | W1.1 switch ablation · W6.1 hỏi góp ý D2 | payload A01/A03/A08 | payload A04/A06 + 14 case JSON |
| **T7 28/11** | W1.2–W1.4 harness log cost/latency | payload A10/A14 | **Pha A** chạy 14 ca |
| **CN 29/11** | FIX-2 cổng nội dung không tin cậy | FIX-4 export path | FIX-1 nối sanitizer |
| **T2 30/11** | FIX-3 delimiter provenance | FIX-5 memory policy | bắt đầu chạy 600 run (máy 1) |
| **T3 01/12** | chạy 600 run (máy 2) · W1.6 tables | FIX-6 · W4.1–W4.2 pin deps | kết thúc 600 run · error analysis |
| **T4 02/12** | §1 §2 §3.1–3.2 · W1.8 cost report | §3.3 §4 §8 · W4.3–W4.5 | FIX-8 audit + ca A05 |
| **T5 03/12** | §3.4 §5 khung | W4.6 checkout sạch | **Pha B** · bảng before/after |
| **T6 04/12** | §7 §9 Phụ lục B/D · điền slide | Phụ lục A · rà báo cáo | §6 · threat model v1 |
| **T7 05/12** | tag `final` · Phụ lục C · tổng duyệt #1 | W4.7 quyền truy cập | video + backup slide |
| **CN 06/12** | **NỘP trước 23:59** · nhắc peer eval | tổng duyệt #2 | Q&A prep |
| **T7 09/12** | demo chính | share màn hình / dự phòng | trả lời phần security |

## 4. Định nghĩa "xong" (DoD) cho mọi việc

Một việc chỉ được đánh dấu xong khi có **đủ 3**:
1. **Sản phẩm** — file/commit cụ thể, không phải "đã làm trên máy tôi".
2. **Bằng chứng** — đường dẫn: commit hash, số trang báo cáo, hoặc dòng log.
3. **Người kiểm** — một người khác đã mở và xác nhận (ghi tên vào bảng dưới).

Điền vào bảng này cuối mỗi ngày, trong `final/plan/STATUS.md`:

```
| Ngày | Việc | Người | Bằng chứng | Người kiểm | Trạng thái |
```

## 5. Rủi ro và cách chặn

| Rủi ro | Xảy ra thì sao | Chặn trước |
|---|---|---|
| **Không có góp ý D2 bằng văn bản** | Phụ lục B trống → P4 mất 4% | Hỏi GV ngay 27/11; nếu không có, dùng tiêu chí "cần cải thiện" trong rubric + ghi rõ nguồn |
| **600 run trượt hạn** | A3 xuống mức 5–7 | Chạy 3 máy từ 30/11, không đợi vá xong FIX mới chạy C1 |
| **Vá FIX-2 làm giảm success** | Mất 96% đã có | Chạy C1 **trước** khi vá, lưu raw; báo cáo cả 2 mốc |
| **p1 96% là nhiễu** | Kết luận sai | Bắt buộc 3 run + SD; nếu SD > 3 điểm thì hạ giọng |
| **Không kịp 6–8 trang** | A5 mất điểm | Cắt §2 xuống 1 đoạn, đẩy chi tiết vào phụ lục — **không** cắt §5 |
| **Demo lỗi API lúc bảo vệ** | P2 giảm | Video dự phòng trên đúng tag + nói rõ là bản ghi |

## 6. Cắt gì nếu thiếu thời gian (thứ tự)

Cắt từ dưới lên: (7) backup slide → (6) trục nâng cao thứ 4 → (5) phân tích lỗi sâu → (4) video dài → (3) phiếu phản biện.
**Không cắt**: 600 task-run · 14 ca injection · tag `final` · Phụ lục B/C · slide đúng 20 phút.
Lý do: A3+A4+B2 = **42% final**; thiếu một ngưỡng tối thiểu là nguyên tiêu chí rơi từ 9–10 xuống 5–7.
