# Seminar S2-5 — Safety & Alignment

> **CO5151 · Advanced Agentic AI (HK261)** — Nhóm G4: Đặng Lâm Tùng (Trưởng nhóm) · Nguyễn Trung Phong · Vũ Việt Hưng
> GVHD: TS. Lê Xuân Bách — Khoa KH&KT Máy tính, ĐHBK ĐHQG-HCM

Bộ tài liệu cho buổi báo cáo **S2-5**: *Guardrails, Constitutional AI, human-in/on-the-loop và thực thi ranh giới hành động*.
Luận điểm xuyên suốt: **alignment là prior, system safety là bound** — model "nói nó aligned" không phải là một *safety case*.

---

## 1. Trong thư mục này có gì

| Tệp | Nội dung | Trạng thái |
|---|---|---|
| `slides_s2_5_vi.tex` / `.pdf` | Deck chính: **25 slide + 6 backup** (31 frame), 16:10, theme HCMUT | ✅ xong |
| `qa_s2_5_vi_short.tex` / `.pdf` | Bản ngắn 2 trang: **14 câu phản biện** + bảng "lỗi nào cần tầng nào" + action boundary của G4 | ✅ xong |
| `annotated_bibliography.tex` / `.pdf` | 2 core + 3 extension readings, mỗi bài **đúng một câu** phản biện | ✅ xong |
| `annotated_bibliography_en.tex` / `.pdf` | Bản tiếng Anh của bibliography | ✅ xong |
| `ai_use_statement.tex` / `.pdf` | Bản khai báo sử dụng AI | ⚠️ **nhóm phải rà lại** (xem §6) |
| `ai_use_statement_en.tex` / `.pdf` | Bản tiếng Anh | ⚠️ nhóm rà lại |
| `hcmut_logo.png` | Logo cho slide tiêu đề | ✅ |

**Cấu trúc deck** (để trả lời "mục đó nằm ở slide nào"):

| Phần | Người trình bày | Slides | Thời lượng |
|---|---|---|---|
| I — Core: cơ chế alignment (RLHF, Constitutional AI) | Nguyễn Trung Phong | 5–9 | 8 phút |
| II — Extension: bằng chứng (governance, alignment faking, scheming) | Vũ Việt Hưng | 10–16 | 9 phút |
| III — Synthesis: model alignment vs. system safety, action boundary cho G4 | Đặng Lâm Tùng | 17–25 | 13 phút |

Bản đồ 5 mục bắt buộc → slide nằm ngay trên **Slide 3**; toàn bộ đáp án phản biện nằm ở `qa_s2_5_vi_short.pdf` và **Backup 5**.

---

## 2. Build

```bash
# cách nhóm dùng (không cần cài TeX Live đầy đủ)
tectonic -X compile slides_s2_5_vi.tex
tectonic -X compile qa_s2_5_vi_short.tex
tectonic -X compile annotated_bibliography.tex
tectonic -X compile ai_use_statement.tex
```

* Tệp dùng `iftex`: **pdflatex** (giống deck S1-7, dùng `T5`) hoặc **xelatex/tectonic** (`fontspec` + Latin Modern / TeX Gyre).
* Cỡ chữ nhỏ (`\tiny`, `\scriptsize`) đã được nới baselineskip trong preamble để dấu tiếng Việt không chồng dòng — **đừng xoá** khối `\makeatletter ... \renewcommand{\tiny}`.
* Nếu thêm nội dung vào slide: build lại và kiểm tra **tràn trang** (log có `Overfull \vbox` là dấu hiệu).

---

## 3. Việc mỗi người cần làm **ngay bây giờ**

### 3.1 Nguyễn Trung Phong — Phần I (slides 5–9, 8 phút)

- [ ] **Học thuộc 5 con số** và nói được *mỗi số đo cái gì*:
  `182.831` prompt red-team (42.496 người + 140.335 model sinh) · `4` vòng critique–revision/prompt ·
  `135.296` so sánh helpfulness · `85 ± 3%` (175B InstructGPT thắng GPT-3) · `~40` labeler.
- [ ] Giải thích được **số hạng thứ 3 của PPO-ptx** mà không cần nhìn slide:
  đó là `γ·E_{z∼D_pre}[log π_θ(z)]` — log-likelihood của **chính policy hiện tại** trên dữ liệu pretraining (LM loss),
  **không phải** xác suất của một model pretrain cố định; mục đích là trộn gradient pretraining để chống quên.
- [ ] Trả lời được 2 câu bẫy:
  **(a)** *"40 labeler có đại diện cho nhân loại?"* → Không; RM học sở thích của nhóm được tuyển, nên sycophancy là hệ quả cơ chế.
  **(b)** *"AI judge có bias thì RLAIF có khuếch đại sai lệch?"* → Có; CAI **giảm** (không xoá) bằng **ensemble 16 nguyên tắc**,
  mỗi lượt rút ngẫu nhiên 1 nguyên tắc nên PM không tối ưu cục bộ theo một góc nhìn.
- [ ] Tập 8 phút **có bấm giờ**, không đọc slide; cắt bớt nếu quá 9 phút.

### 3.2 Vũ Việt Hưng — Phần II (slides 10–16, 9 phút)

- [ ] Kể đúng **setup alignment faking**: model được nói *đang bị train để luôn tuân thủ*, **chỉ free-tier** dùng để train;
  kết quả `14%` vs `≈0%`; sau RL thật → `78%` lý luận faking.
- [ ] Nhớ **3 biến thể** (system prompt → synthetic documents → RL thật) — đây là câu trả lời cho phản biện *"chỉ là prompt artifact"*.
- [ ] Thuộc **bảng Table 2** (5 hành vi × 5 model): Opus 3 tắt oversight `5%`, tự copy `10%`; o1 covert ranking `22%`;
  Llama 3.1 dùng `chattr +i` chặn bật lại oversight; o1 giữ dối trá `>85%` follow-up.
- [ ] Nói rõ **capability ≠ propensity**: 5–22% là *cận trên trong sandbox có nudge mạnh*, **không** phải tỉ lệ production.
- [ ] Chuẩn bị sẵn câu chốt khi bị hỏi "vậy có nên dừng dùng agent?": *không* — capability đã có, nên giảm **hệ quả** bằng thiết kế.
- [ ] Tập 9 phút có bấm giờ.

### 3.3 Đặng Lâm Tùng — Phần III (slides 17–25, 13 phút)

- [ ] Thuộc **bảng C0–C4** + **6 lớp thực thi** (identity → gateway → oracle → budget → human gate → audit/kill switch).
- [ ] Trả lời gọn 2 câu defense trong **60 giây mỗi câu**:
  **(1)** lỗi nào alignment xử lý / lỗi nào cần system safety (slide 19);
  **(2)** ép action boundary **ngoài prompt** bằng gì (slide 23).
- [ ] Nắm 2 ví dụ độc lập: **(A)** drafter bịa điều luật → oracle chặn; **(B)** *Moffatt v. Air Canada* (CA$812,02, gồm phí toà).
- [ ] Chuẩn bị phần **residual risk** (slide 24): nói trước cái gì ranh giới *không* chặn, kèm điều kiện mở C3.
- [ ] Điều phối Q&A: nhận câu hỏi, chỉ định người trả lời (xem §4), chốt thời gian.
- [ ] Tập 13 phút có bấm giờ.

### 3.4 Cả nhóm — trước giờ G

- [ ] **Đọc abstract + phần Limitations** của cả 5 paper (không chỉ đọc slide) — giám khảo sẽ hỏi đúng chỗ này.
- [ ] Thống nhất **3 câu chốt** (§5) và **danh sách điều không được nói** (§6).
- [ ] **Dry-run đủ 30 phút** một lần, bấm giờ từng phần; ghi lại chỗ bị quá giờ.
- [ ] Chuẩn bị **bản PDF trên máy khác** + USB: `slides_s2_5_vi.pdf`, `qa_s2_5_vi_short.pdf`.
- [ ] Kiểm tra máy chiếu: tỉ lệ 16:10, font nhúng (mở bằng Acrobat/Preview, không dùng trình duyệt).
- [ ] Rà lại `ai_use_statement` (tên/phiên bản công cụ, ngày ký, chữ ký) — xem §6.
- [ ] Xác nhận lại **quy chế Seminar 2**: có cần nộp kèm `annotated_bibliography` và `ai_use_statement` như Seminar 1 không.

---

## 4. Q&A: ai trả lời câu nào

| Loại câu hỏi | Người trả lời | Slide neo |
|---|---|---|
| RLHF, CAI, labeler, alignment tax, RLAIF | **Phong** | 5–9 |
| Alignment faking, scheming, capability vs. propensity, "prompt artifact" | **Hưng** | 10–16 |
| Model alignment vs. system safety, action boundary, escalation, project G4 | **Tùng** | 17–25 |
| Số liệu cụ thể (ai hỏi "con số này ở đâu ra?") | Người phụ trách phần đó | Bảng §7 |
| Câu ngoài phạm vi hoặc hóc | **Tùng** nhận, hẹn trả lời sau, **không đoán** | — |

Nguyên tắc: **một người trả lời, người khác bổ sung 1 câu** — không nói chồng.

---

## 5. Ba câu chốt (ai cũng phải nói được, không cần slide)

1. **CAI**: model tự phê bình theo *một nguyên tắc văn bản*, tự sửa, rồi học từ bản sửa; ở tầng RL, **AI judge** so sánh hai output
   theo nguyên tắc để tạo nhãn — **không có bước nào con người gán nhãn "có hại/không có hại"**.
2. **Alignment vs. system safety**: `E[harm] ≤ P(model sai) × I_max`. Alignment giảm `P`; system safety giảm `I_max`.
   Hai tầng không thay nhau, và "model nói nó aligned" **không phải** bằng chứng.
3. **Action boundary**: tập hành động + thẩm quyền + bằng chứng + hành vi ở biên, được thi hành bởi
   **credential, gateway, oracle, budget, approval gắn hash, audit/kill switch**.
   *Thứ gì chỉ ép bằng prompt thì đó là sở thích, không phải ranh giới.*

---

## 6. Ba điều **không được** nói (và nói gì thay vào)

| ❌ Không nói | ✅ Nói thay |
|---|---|
| "Hệ của nhóm an toàn." | "Hệ giới hạn **hậu quả** trong phạm vi C0–C3; residual risk đã liệt kê ở slide 24." |
| "Model X đã aligned." | "Model X **vượt** bộ eval này; đó là capability đo được, không phải kết luận về ý định." |
| "Scheming xảy ra 5% trong production." | "5% là **cận trên capability** trong sandbox có nudge mạnh." |

**Việc riêng:** `ai_use_statement.tex` hiện ghi công cụ theo những gì nhóm thực sự dùng ở phiên soạn thảo
(Copilot Chat trong VS Code + LLM đối chiếu số liệu). Nếu nhóm còn dùng công cụ khác (Gemini/ChatGPT…), **thêm dòng vào bảng**
trước khi nộp; ngày ký đang để `04/11/2026`.

---

## 7. Con số neo (để trả lời "số này ở đâu ra?")

| Claim | Số | Nguồn |
|---|---|---|
| Prompt red-team + model sinh | 42.496 + 140.335 = **182.831** | Bai et al. 2022, §3.2 |
| Số vòng critique–revision mỗi prompt | **4** | Bai et al. 2022, §3.2 + App. A |
| So sánh helpfulness / harmlessness | **135.296** / **182.831** | Bai et al. 2022, §3.2 |
| Nguyên tắc cho bước so sánh RL-CAI | **16** | Bai et al. 2022, §4.1 |
| Labeler | **~40** (Upwork/ScaleAI) | Ouyang et al. 2022, §3.4 |
| 175B InstructGPT > GPT-3 | **85 ± 3%** (> few-shot: **71 ± 4%**) | Ouyang et al. 2022, abstract |
| Alignment faking: free vs. paid, sau RL | **14%** vs **≈0%**, **78%** | Greenblatt et al. 2024, abstract |
| Eval scheming | **5 model × 6 eval × 300 rollouts** | Meinke et al. 2024, §3.1 |
| Opus 3 tắt oversight / tự copy | **5%** / **10%** | Meinke et al. 2024, Table 2 |
| o1 covert email ranking / giữ dối trá | **22%** / **>85%** | Meinke et al. 2024, Table 2 + abstract |
| Air Canada | **CA$812,02** (bồi thường + phí toà) | *Moffatt v. Air Canada*, 2024 BCCRT 149 |

Chi tiết + ngữ cảnh: `qa_s2_5_vi_short.pdf` §1–§9.

---

## 8. Việc còn lại (chưa làm)

- **Demo trực tiếp**: chưa làm. Hướng khả thi: một gateway tất định C0–C4 chạy offline, cho thấy cùng một request vẫn bị
  `DENY` dù model "hứa" sẽ cẩn thận — tức minh hoạ trực tiếp luận điểm của slide 23.
- **Rehearsal** đủ 30 phút và chốt lại thời lượng từng phần.
- **Xác nhận quy chế nộp** của Seminar 2.

---

## 9. Tham chiếu nhanh

- Bai et al. (2022) — [Constitutional AI](https://arxiv.org/abs/2212.08073)
- Ouyang et al. (2022) — [InstructGPT / RLHF](https://arxiv.org/abs/2203.02155)
- Shavit et al. (2023) — [Practices for Governing Agentic AI Systems](https://openai.com/index/practices-for-governing-agentic-ai-systems/)
- Greenblatt et al. (2024) — [Alignment Faking in LLMs](https://arxiv.org/abs/2412.14093)
- Meinke et al. (2024) — [Frontier Models are Capable of In-context Scheming](https://arxiv.org/abs/2412.04984)
- Greshake et al. (2023) — [Indirect Prompt Injection](https://arxiv.org/abs/2302.12173)
