# Hướng dẫn Cài đặt Máy chủ và Kiểm thử Hệ thống LegalPilot-VN (Theme 9)
# LegalPilot-VN Server Setup & Testing Guide

> Tài liệu này hướng dẫn chi tiết quy trình dựng môi trường máy chủ cục bộ (Neo4j, Qdrant, SearXNG), nạp cơ sở dữ liệu đồ thị tri thức pháp luật, và chạy kiểm thử hệ thống Đa tác tử (Google ADK Multi-Agent System).

---

## 1. Yêu cầu hệ thống (Prerequisites)

* **Hệ điều hành:** macOS (Apple Silicon / Intel) hoặc Linux (Ubuntu 22.04+).
* **Container Runtime:** Docker Desktop hoặc **Colima** (khuyến nghị trên Mac: `colima start`).
* **Python:** Python 3.10 đến 3.12 (khuyên dùng môi trường ảo `venv`).
* **API Key:** Khóa API của mô hình ngôn ngữ (DeepSeek API hoặc OpenAI-compatible endpoint).

---

## 2. Các bước cài đặt từng bước (Step-by-Step Setup)

### Bước 1: Khởi tạo môi trường ảo Python và cài đặt thư viện
```bash
# 1. Di chuyển vào thư mục dự án
cd CO5151

# 2. Tạo môi trường ảo (nếu chưa có)
python3 -m venv .venv

# 3. Kích hoạt môi trường ảo
source .venv/bin/activate

# 4. Cài đặt các gói phụ thuộc
pip install -r requirements.txt
pip install google-adk neo4j qdrant-client sentence-transformers litellm
```

---

### Bước 2: Cấu hình biến môi trường (`.env`)
Sao chép file mẫu `.env.example` và điền cấu hình:
```bash
cp .env.example .env
```
Các thông số cốt lõi cần thiết trong `.env`:
```env
# LLM Provider Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key_here
LLM_MODEL=deepseek/deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1

# Neo4j Property Graph
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=legalpilot2026

# Qdrant Vector DB
QDRANT_HOST=localhost
QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334

# Self-hosted Legal Search
SEARXNG_URL=http://localhost:8080
```

---

### Bước 3: Khởi động các dịch vụ máy chủ qua Docker
```bash
# Nếu dùng Colima trên Mac:
colima start

# Khởi chạy cụm 3 container: Neo4j (Graph), Qdrant (Vector), SearXNG (Web Search)
docker compose up -d neo4j qdrant searxng
```

Kiểm tra trạng thái container:
```bash
docker ps
```
*Bạn sẽ thấy 3 container `legalpilot-neo4j` (port 7474, 7687), `legalpilot-qdrant` (port 6333), `legalpilot-searxng` (port 8080) đang ở trạng thái `Up`.*

---

### Bước 4: Nạp dữ liệu đồ thị tri thức pháp luật vào Neo4j (Seeding Graph)
Chạy script tự động khởi tạo Schema (ràng buộc duy nhất, chỉ mục tìm kiếm) và nạp toàn bộ cấu trúc văn bản QPPL:
```bash
python scripts/load_neo4j_from_export.py
```
*Kết quả hiển thị:*
```text
>>> Loaded 29 documents / 91 articles / 103 clauses
>>> Applied 8 cross-reference edges and validity overrides
>>> Graph now holds 32+ documents, 106+ clauses
```

Kiểm tra kết nối và số lượng node thực tế:
```bash
python -c "
from src.knowledge.neo4j_client import Neo4jClient
client = Neo4jClient()
print('Connected:', client.verify_connectivity())
res = client.execute_query('MATCH (d:Document) RETURN count(d) as total_docs')
print('Total Documents in Neo4j:', res[0]['total_docs'])
"
```

---

## 3. Hướng dẫn chạy thử nghiệm và kiểm thử (Testing Workflows)

### 3.1. Chạy Smoke Test tích hợp toàn bộ pipeline
Xác thực chuỗi 5 tác tử (`Planner` $\rightarrow$ `LawGraph` $\rightarrow$ `ClaimAuditor` $\rightarrow$ `LiveGazette` $\rightarrow$ `Drafter`):
```bash
python checkpoint_2/smoke_test.py
```
*Hệ thống sẽ chạy câu hỏi mẫu về vốn điều lệ ví điện tử, tự động gạt bỏ NĐ 101/2012 cũ và đối soát căn cứ NĐ 52/2024 mới (50 tỷ đồng).*

---

### 3.2. Chạy thử các câu hỏi chuẩn từ SBV Legal Benchmark
Hệ thống cung cấp script chạy mẫu trên bộ dữ liệu 100 câu hỏi chuẩn ngành ngân hàng:
```bash
# Chạy câu hỏi đơn lẻ (Ví dụ câu 16: Thông tư 02/2025/TT-NHNN)
python scripts/trace_one_question.py 16

# Chạy kiểm thử hàng loạt các ca tiêu biểu (Q1: Vay nước ngoài, Q5: Mở ví điện tử, Q41: Bảo lãnh ngân hàng)
python scripts/test_sample_questions.py
```

---

### 3.3. Khởi chạy Giao diện Web UI (LegalPilot-VN Workbench)
```bash
./run_adk_web.sh
```
*Truy cập trình duyệt tại:* **`http://localhost:8000`**
* Giao diện cho phép nhập câu hỏi tự do, chọn hồ sơ doanh nghiệp (FDI, TNHH, Vốn điều lệ), quan sát vết thực thi (Execution Trace) và kết quả kiểm toán điều khoản theo thời gian thực.

---

### 3.4. Trực quan hóa Đồ thị trên Neo4j Browser
Truy cập giao diện quản trị đồ thị trực tiếp:
* **Địa chỉ:** `http://localhost:7474`
* **Tài khoản:** `neo4j`
* **Mật khẩu:** `legalpilot2026`

Một số câu truy vấn Cypher trực quan hữu ích:
```cypher
// 1. Trực quan hóa quan hệ thay thế giữa NĐ 52/2024 và NĐ 101/2012
MATCH (n:Document)-[r:SUPERSEDES]->(o:Document)
RETURN n, r, o;

// 2. Xem toàn bộ cây phả hệ (Document -> Article -> Clause) của Nghị định 52/2024
MATCH path = (d:Document {doc_id: '52/2024/ND-CP'})-[:CONTAINS*1..2]->(x)
RETURN path LIMIT 25;
```

---

## 4. Dữ liệu đồ thị đã đồng bộ lên Git (Git Tracked Datasets)

Các file dữ liệu sau đã được mở quyền trong `.gitignore` để bất kỳ ai clone repo đều có thể dựng lại nguyên vẹn đồ thị tri thức:
* `data/processed/neo4j_graph_export.json`: Danh mục văn bản, điều khoản, cờ hiệu lực và quan hệ `SUPERSEDES`/`AMENDS`/`GUIDES`.
* `data/processed/qdrant_chunks_export.json`: 103 chunks văn bản pháp luật ngành ngân hàng kèm vector embeddings phục vụ tìm kiếm ngữ nghĩa.
* `data/raw/*.txt`: Toàn văn các văn bản QPPL cốt lõi (NĐ 52/2024, NĐ 101/2012, TT 40/2024).
* `data/benchmarks/sbv_testset_tvpl.json`: 100 câu hỏi benchmark chuẩn kèm ground truth từ Thư Viện Pháp Luật.
