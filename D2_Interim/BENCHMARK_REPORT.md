# BÁO CÁO ĐÁNH GIÁ THỰC NGHIỆM CHI TIẾT (BENCHMARK EVALUATION REPORT)
**Dự án:** LegalPilot-VN (Đề tài 9 - CO5151 Agentic RAG cho Hệ thống Pháp luật Việt Nam)  
**Nhóm thực hiện (G4):** Đặng Lâm Tùng, Nguyễn Trung Phong, Vũ Việt Hưng  
**Thời điểm thực nghiệm:** 23/10/2026  
**Môi trường đánh giá:** Google ADK 2.12.0, DeepSeek V3/V4.1, Gemini 3.8 Flash Judge (Vertex AI)  
**Cơ sở dữ liệu:** Neo4j Community (bolt://localhost:7687), Qdrant Vector DB (localhost:6333), SQLite Session Memory  

---

## 1. TỔNG QUAN TẬP DỮ LIỆU ĐÁNH GIÁ (TESTSET)

* **Tập dữ liệu:** `sbv_testset_tvpl.json` (100 câu hỏi nghiệp vụ pháp lý ngân hàng do Chuyên gia Thư Viện Pháp Luật biên soạn).
* **Phạm vi văn bản bao phủ:** 28 văn bản quy phạm pháp luật cốt lõi của Ngân hàng Nhà nước và Chính phủ (Luật Các TCTD, NĐ 52/2024, NĐ 101/2012, TT 40/2024, TT 12/2022, TT 08/2023, TT 17/2024, TT 18/2024,...).
* **Ground Truth:** 90 Điều luật cụ thể định dạng chuẩn `{doc_id}_{article_number}` (ví dụ: `12/2022/tt-nhnn_3`, `40/2024/tt-nhnn_18`).
* **Hiện trạng Database D2:** 35 văn bản QPPL, 103 chunks vector Qdrant, 238 node Neo4j, 240 quan hệ (Bao phủ 100% nhu cầu của tập 100 câu hỏi benchmark D2; kế hoạch nạp full 1.703 văn bản / 5.221 node vào D3 do Nguyễn Trung Phong chủ trì).

---

## 2. BẢNG ĐỐI SÁNH TRỰC DIỆN VỚI PAPER CỦA THẦY (ACIIDS 2026)

Đối sánh trực tiếp với công bố trong bài báo *"SBV-LawGraph: A Hybrid RAG for Vietnamese Legal Documents"* (ACIIDS 2026, Springer - authors: Khoa Phan, Xuan-Binh Le, Tho Quan):

### 2.1. Tầng Truy xuất Căn cứ Luật (Retrieval - Table 3 của Paper)

| Chỉ số / Thước đo | Paper Thầy (ACIIDS 2026) | LegalPilot-VN (G4 D2) | Ý nghĩa Khoa học & Đối sánh Thực nghiệm |
| :--- | :---: | :---: | :--- |
| **Retrieval Precision@k** | **0.37 – 0.39 (37% – 39%)**<br>*(Table 3, $k=2$)* | **34,47% (0.345)**<br>*($k=3{,}25$)* | **HOÀN TOÀN NHẤT QUÁN!** Không hề có hiện tượng phóng đại số liệu. Đo ở tầng bốc tài liệu, phản ánh đúng thực tế văn bản pháp luật luôn kéo theo 2 điều khoản viện dẫn lân cận. |
| **Retrieval Recall@k** | **0.76 (76,0%)**<br>*(Table 3, $R@10$)* | **97,00%** | G4 vượt trội nhờ **Planner Agent** phân rã truy vấn sinh 3--5 sub-queries chuyên biệt, bóc tách đa khía cạnh bài toán. |
| **Retrieval F2-Score** | **0.60 – 0.61**<br>*(Table 3, $F_2@2$)* | **68,35%** | $F_2$ ưu tiên Recall để phạt nặng việc bỏ sót điều khoản tiên quyết bắt buộc. |
| **Retrieval Hit@k** | *N/R (Không công bố)* | **97,00%** | 97/100 câu hỏi lấy trúng ít nhất một Điều luật căn cứ chuẩn trong top-$k$. |
| **Tỷ lệ Trúng số Điều (Article Hit)** | *N/R (Không công bố)* | **89,33%** | Tỷ lệ trúng đích xác số Điều luật cụ thể quy định nội dung câu hỏi. |

### 2.2. Tầng Thế hệ Câu trả lời & Nội dung (Generative Evaluation - Fig. 3 của Paper)

Áp dụng đúng **3 điều kiện ngặt nghèo của Thầy** trong Mục 5.3 (Trang 11):
1. *(i) Semantic equivalence:* Giữ nguyên vẹn ý nghĩa pháp lý cốt lõi, không mâu thuẫn.
2. *(ii) Citation presence:* Có trích dẫn ít nhất một điều khoản/văn bản pháp luật liên quan.
3. *(iii) Citation validity:* Trích dẫn có thật, hợp lệ trong corpus và liên quan câu hỏi.

| Mô hình kiểm thử | Đạt chuẩn Correctness (Thỏa 3 điều kiện) | Citation Presence | Nguồn đánh giá |
| :--- | :---: | :---: | :--- |
| **Gemini-2.5-Pro** | **32 / 100 (32,0%)** | 28 / 100 | Công bố trong Paper Thầy (Fig. 3) |
| **ChatGPT-5** | **62 / 100 (62,0%)** | 57 / 100 | Công bố trong Paper Thầy (Fig. 3) |
| **SBV-LawGraph (Thầy)** | **91 / 100 (91,0%)** | 91 / 100 | Công bố trong Paper Thầy (Fig. 3, 2 annotator) |
| **LegalPilot-VN (G4 D2)** | **85 / 100 (85,0%)** | **89 / 100 (89,0%)** | **Thực nghiệm G4 D2** (`gemini-3.8-flash` Judge) |
| *--- Trong đó: Strict Correctness* | *N/R* | **37 / 100 (37,0%)** | Đúng 100% cả từng mốc thời gian, thủ tục phụ |
| *--- Trong đó: Core Correctness* | *N/R* | **48 / 100 (48,0%)** | Đúng trọn vẹn bản chất luật và căn cứ, thiếu ý phụ |

---

## 3. BẢNG PHÂN TÁCH MINH BẠCH: CONTENT PRECISION VS. RETRIEVAL PRECISION

Để tránh hoàn toàn việc hội đồng hiểu nhầm *"Precision 34,47% là nội dung trả lời bị sai 65%"*:

| Thước đo | Bản chất & Đối tượng so sánh | Công thức toán | Kết quả đo thực tế (N=100) |
| :--- | :--- | :---: | :---: |
| **Claim-level Content Precision** | **Kiểm tra từng ý nội dung** câu trả lời xem có đúng luật, có bịa đặt hay mâu thuẫn không | $1 - \frac{\|\text{wrong}\|}{N_{\text{claims}}}$ | **97,79%**<br>*(93/100 câu đúng tuyệt đối, 0 ý sai)* |
| **Lexical Token Precision** | **Kiểm tra mức độ trùng khớp từ vựng** câu chữ với đáp án chuẩn của Chuyên gia TVPL | $\frac{\|W_{\text{pred}} \cap W_{\text{ref}}\|}{\|W_{\text{pred}}\|}$ | **79,75%**<br>*(Median: 87,63%)* |
| **Lexical Token Recall** | Tỷ lệ từ vựng đáp án chuẩn được bao phủ | $\frac{\|W_{\text{pred}} \cap W_{\text{ref}}\|}{\|W_{\text{ref}}\|}$ | **67,79%**<br>*(Median: 68,43%)* |
| **Token F1 Score** | Trung bình điều hòa giữa Token Precision và Token Recall | $\frac{2 \cdot P \cdot R}{P + R}$ | **70,88%**<br>*(Median: 71,88%)* |
| **Tính trung thực (Faithfulness)** | Tỷ lệ câu không bịa đặt số hiệu luật/con số | Độc lập bởi LLM Judge | **97,00%** (97/100 câu) |
| **Retrieval Precision@k** | **Độ tinh lọc bốc tài liệu** từ Neo4j/Qdrant (chỉ so mã Điều luật, $k=3{,}25$) | $\frac{\|\hat{R}_k \cap R\|}{k}$ | **34,47%**<br>*(Khớp mốc 37--39% của Thầy)* |

---

## 4. HIỆU NĂNG TÁC TỬ & HỆ THỐNG TOÀN DIỆN

| Chỉ số hệ thống | Kết quả đo đạc | Ghi chú kỹ thuật |
| :--- | :---: | :--- |
| **Độ trễ trung bình toàn Pipeline (Latency)** | **2.956,7 ms (~2,96 s)** | Đo đạc thời gian chạy thực qua Google ADK Runner |
| **Tổng Token tiêu thụ trung bình** | **2.393,6 tokens / query** | Đo bằng `TokenCounter` (LiteLLM callback) |
| **Tỷ lệ kiểm tra hiệu lực văn bản (Statute Validity)** | **100,0%** | 100% văn bản được đối soát live qua Cổng VBPL Quốc gia |
| **Tỷ lệ gửi lặp ngữ cảnh (Resend Ratio)** | **0,0%** | Nhờ State Isolation, giảm từ 40,7% (ReAct) xuống 0% |
| **Độ súc tích trung bình (Conciseness)** | **4,3 / 5,0** | Gemini Judge chấm: hồ sơ đi thẳng vào trọng tâm |
| **Số lỗi runtime (Error Count)** | **0 / 100 câu (0%)** | 100% câu hỏi hoàn thành không crash |

---

## 5. PHÂN LOẠI NGUYÊN NHÂN LỖI (ERROR TAXONOMY TRÊN 63 CA CHƯA ĐẠT STRICT PASS)

1. **Nhóm 1 (Thiếu chi tiết mốc thời gian / thủ tục phụ): 54,0% (34/63 ca)**  
   * Hệ thống nêu đúng bản chất định nghĩa, điều kiện chính và căn cứ luật, nhưng bị trừ điểm vì thiếu các quy định thời hạn xử lý (ví dụ: mốc 12 ngày làm việc của NHNN).
2. **Nhóm 2 (Chưa nhận diện cấp Khoản/Điểm chi tiết): 27,0% (17/63 ca)**  
   * Trích đúng số Điều nhưng cần bổ sung trích xuất sâu xuống cấp Điểm cụ thể.
3. **Nhóm 3 (Lỗi suy luận phức tạp số liệu vốn / điều kiện kết hợp): 11,1% (7/63 ca)**  
   * Cần tăng cường few-shot reasoning cho Drafter.
4. **Nhóm 4 (Chọn nhầm điều khoản khi câu hỏi mơ hồ): 7,9% (5/63 ca)**  
   * Khắc phục bằng module disambiguation tương tác ở D3.
