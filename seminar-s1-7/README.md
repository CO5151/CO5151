# CO5151 — Seminar S1-7: Agent Design Patterns & Orchestration
## Nhóm G4 (HK261, ĐHBK ĐHQG-HCM)
**Giảng viên hướng dẫn:** TS. Lê Xuân Bách  
**Nhóm thực hiện:** Đặng Lâm Tùng (Trưởng nhóm) · Nguyễn Trung Phong · Vũ Việt Hưng  
**Ngày báo cáo:** Thứ Tư 21/10/2026 (Hạn nộp bài qua Email: 23:59 Chủ Nhật 18/10/2026)

---

## 1. Cấu Trúc Thư Mục Project TeX

```
seminar-s1-7/
├── slides_s1_7.tex               # Slide Beamer 22 trang chuẩn nhận diện HCMUT & 5 phần bắt buộc
├── annotated_bibliography.tex   # Danh mục tài liệu tham khảo ĐÚNG 1 TRANG (mỗi bài 1 câu phản biện)
├── ai_use_statement.tex          # Tuyên bố sử dụng AI minh bạch theo chuẩn liêm chính học thuật
├── demo_orchestration_trace.py   # Script Python mô phỏng Execution Trace 3 Patterns (chạy trực tiếp)
└── README.md                     # Hướng dẫn biên dịch, phân chia bài báo & kế hoạch demo
```

---

## 2. Phân Chia Bài Báo Cho Từng Thành Viên Nhóm

Theo yêu cầu của Thầy, nhóm cần nghiên cứu sâu cả **Core Papers** lẫn **Extension Papers** và viết **ĐÚNG MỘT CÂU PHẢN BIỆN** (Critical Reflection) cho mỗi bài:

| Thành viên | Bài báo phân công | Hướng phản biện trọng tâm | Slide phụ trách |
| :--- | :--- | :--- | :--- |
| **Đặng Lâm Tùng**<br>*(Trưởng nhóm -- Kiến trúc \& Phân tích Phản biện)* | 1. **Anthropic (2024):** *Building Effective Agents*<br>2. **Chen et al. (2024):** *Scaling Agentic Workflows (arXiv:2403.02419)* | • Đánh giá chi phí token scaling và bóc mẽ ảo tưởng "tính trồi" (emergence) của đa tác tử.<br>• Phân tích rủi ro khi các mắt xích công cụ bị đứt gãy âm thầm (silent failure). | Slide 1–3 (Bối cảnh, Đặt bài toán)<br>Slide 12 (Bảng so sánh)<br>Slide 13–15 (Phản biện cốt lõi & What we don't believe) |
| **Nguyễn Trung Phong**<br>*(Thực nghiệm \& Khảo sát Patterns)* | 3. **Wu et al. (2023):** *AutoGen (arXiv:2308.08155)*<br>4. **Shinn et al. (2023):** *Reflexion (NeurIPS 2023)*<br>5. **Madaan et al. (2023):** *Self-Refine (NeurIPS 2023)* | • Phân tích bẫy tự xác nhận (Self-Confirmation bias) trong vòng lặp Evaluator-Optimizer.<br>• Chỉ ra hội chứng nịnh bợ (Sycophancy) và buồng vang trong chat tự do giữa các agent. | Slide 4–9 (Khảo sát các Pattern 1–5)<br>Slide 16–17 (So sánh thực nghiệm chi phí vs độ trễ) |
| **Vũ Việt Hưng**<br>*(Điều phối trạng thái \& Trace Demo)* | 6. **Hong et al. (2024):** *MetaGPT (ICLR 2024)*<br>7. **Gou et al. (2024):** *CRITIC (ICLR 2024)*<br>8. **LangChain (2024):** *LangGraph Documentation* | • Phân tích sự cứng nhắc của SOP tĩnh trong MetaGPT.<br>• Phân tích kiến trúc máy trạng thái (FSM) và giao thức Model Context Protocol (MCP). | Slide 10–11 (Quản lý State, Memory, MCP)<br>Slide 18–22 (Demo Trace, Liên hệ Đề tài Legal RAG & Hướng mở) |

---

## 3. Thiết Kế Bản Demo (Execution Trace Benchmark)

### Ý tưởng cốt lõi của Demo
Không làm demo đồ chơi (như nhờ 2 agent viết thơ). Demo phải phơi bày **ANATOMY OF ORCHESTRATION WITH EXECUTION TRACE**, cho thấy một hệ thống tác tử đối mặt với lỗi ngữ nghĩa, bắt lỗi qua tool ngoài và tự phục hồi như thế nào.

### Kịch bản thử nghiệm
- **Tình huống:** Doanh nghiệp có vốn đầu tư nước ngoài nộp hồ sơ xin cấp phép Ví điện tử (Tháng 10/2024).
- **Cạm bẫy:** Nghị định 101/2012/NĐ-CP (quy định vốn 50 tỷ) đã bị **bãi bỏ hoàn toàn** bởi Nghị định 52/2024/NĐ-CP từ ngày 01/07/2024.
- **So sánh 3 mẫu thiết kế:**
  1. *Naive Prompt Chaining:* Dẫn chiếu nhầm NĐ 101/2012 cũ $\to$ Hồ sơ nộp NHNN bị trả về (Fatal Semantic Failure).
  2. *Chatty Multi-Agent (AutoGen Style):* Hai agent chat qua lại 4 lượt $\to$ Rơi vào bẫy tự nịnh bợ (Sycophancy trap), đồng thuận chọn luật cũ $\to$ Tốn 8.600 tokens mà vẫn sai!
  3. *Controlled Graph-State (Kiến trúc G4):*
     - Drafter đề xuất NĐ 101.
     - Claim Auditor gọi MCP Tool `vbpl_verify_status` $\to$ Bắt lỗi bãi bỏ luật.
     - Kích hoạt Re-route Edge $\to$ Thay thế bằng NĐ 52/2024 $\to$ Kết quả hội tụ chính xác 100% chỉ tốn 2.160 tokens.

### Cách chạy thử Demo ngay:
```bash
python3 demo_orchestration_trace.py
```

---

## 4. Hướng Dẫn Biên Dịch LaTeX

### 1. Biên dịch Slide Beamer (22 slides):
```bash
pdflatex slides_s1_7.tex
pdflatex slides_s1_7.tex   # Chạy lần 2 để hiển thị đúng số trang footline
```

### 2. Biên dịch Annotated Bibliography (Đúng 1 trang A4 duy nhất):
```bash
pdflatex annotated_bibliography.tex
```

### 3. Biên dịch AI-Use Statement:
```bash
pdflatex ai_use_statement.tex
```
*(Nếu làm việc trên Overleaf, chỉ cần nén toàn bộ thư mục `seminar-s1-7` thành file `.zip` và tải lên Overleaf).*
