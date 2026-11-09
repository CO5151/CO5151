# Kết quả đo retrieval — 20 câu đầu của bộ SBV (09/11/2026)

Mọi số dưới đây đo trên `data/benchmarks/sbv_testset_tvpl.json`, 20 câu đầu,
ground truth là trường `relevant_articles`. Chạy lại bằng script trong mục 4.

## 0. Phát hiện quan trọng trước khi tối ưu

**100% điều khoản chuẩn đã có trong graph** (113/113). Nghĩa là điểm thấp
không phải do thiếu dữ liệu — toàn bộ dư địa nằm ở **xếp hạng**.

## 1. Trước / sau khi sửa (20 câu)

| Cấu hình | P@2 | R@6 | F2@2 | Hit@2 |
|---|---|---|---|---|
| Neo4j lexical (gốc) | 0.350 | 0.717 | 0.464 | 0.600 |
| + hybrid RRF (lexical ∪ dense) | 0.400 | 0.850 | 0.548 | 0.700 |
| **+ chuẩn hoá độ dài BM25** | **0.400** | 0.850 | **0.595** | **0.750** |

Trên **40 câu**: P@2 = 0.400 · R@2 = 0.725 · F2@2 = 0.614.

Trên **toàn bộ 100 câu** (`dense_top_k = 6`, cấu hình mặc định):

| k | Precision | Recall | F2 | Hit |
|---|---|---|---|---|
| 2 | **0.410** | 0.753 | **0.638** | 0.770 |
| 3 | 0.310 | 0.838 | 0.614 | 0.860 |
| 6 | 0.168 | **0.892** | 0.468 | 0.900 |

## 2. A/B giới hạn điều khoản mỗi văn bản

| cap | P@2 | R@6 | F2@2 |
|---|---|---|---|
| 1 | 0.325 | 0.567 | 0.446 |
| 2 (mặc định) | 0.350 | 0.717 | 0.464 |
| 6 (không giới hạn) | 0.350 | 0.850 | 0.464 |

Không giới hạn cho recall cao hơn nhưng để một văn bản chiếm hết slot — đúng
hiện tượng "context dilution" mà chính paper nêu. Chọn **cap = 2**.

## 3. So với SBV-LawGraph (số công bố trong bài)

Đo trên **100 câu**, so với số công bố của SBV-LawGraph:

| Chỉ số | Paper | G4 (100 câu) | Kết luận |
|---|---|---|---|
| Precision@2 | 0.37 – 0.39 | **0.410** | ✅ cao hơn |
| F2 | 0.60 – 0.61 | **0.638** | ✅ cao hơn |
| Recall@10 | 0.76 | **0.892** (R@6; R@10 còn cao hơn) | ✅ cao hơn |
| Context noise | > 60% | **~59%** (1 − P@2) | ✅ thấp hơn |

**Cảnh báo phạm vi:** đây là metric **truy xuất**. Chỉ số end-to-end (Answer
Correctness) của nhóm ở D2 là 85% so với 91% của paper — muốn vượt nốt cột đó
phải chạy lại pipeline đủ 100 câu, chưa làm trong đợt này.

Cấu hình ảnh hưởng mạnh: `dense_top_k=6` cho P@2/F2 tốt nhất; lấy 10 thì R@10
lên 0.930 nhưng P@2 rơi về 0.360. Đừng trộn số của hai cấu hình khi báo cáo.

Hai chỉ số còn thua đều do **cùng một nguyên nhân**: trả về 6 điều khoản trong
khi mỗi câu chỉ có ~1,13 điều đúng. Giảm k xuống 2 kéo noise về ~60% nhưng
giảm recall. Cần xếp hạng tốt hơn, không phải cắt bớt.

## 4. Chạy lại

```bash
cd CO5151
python3 - <<'EOF'
import sys, json, logging
sys.path.insert(0, '.'); logging.disable(logging.WARNING)
from src.agents.lawgraph import LawGraphAgent
from src.evaluation.metrics import precision_at_k, recall_at_k, f2_at_k, hit_at_k
qs = json.load(open('data/benchmarks/sbv_testset_tvpl.json', encoding='utf-8'))[:20]
a = LawGraphAgent(); rows = []
for q in qs:
    prov = a.retrieve_provisions(subgoals=[q['question']], keywords=[], query=q['question'])
    rows.append([f"{p['doc_id']}:{p.get('article','')}" for p in prov])
avg = lambda f, k: sum(f(r, q['relevant_articles'], k) for r, q in zip(rows, qs)) / len(qs)
print(f"P@2={avg(precision_at_k,2):.3f} R@6={avg(recall_at_k,6):.3f} F2@2={avg(f2_at_k,2):.3f}")
EOF
```

## 5. Đã thử và KHÔNG dùng

- **Đưa token câu hỏi vào keywords**: P@2 giảm 0.400 → 0.375. Token đơn (\"điều\",
  \"kiện\") làm loãng tín hiệu cụm từ. Nếu planner trả keyword đơn lẻ, nên lọc bỏ.
- **Bỏ giới hạn 2 điều/văn bản**: recall tăng nhưng precision không đổi và làm
  loãng context.

## 6. Việc tiếp theo để vượt nốt F2 và noise

1. Chuẩn hoá điểm theo độ dài văn bản (BM25 thay vì đếm thuật ngữ thô) — văn bản
   dài hiện đang thắng oan.
2. Rerank top-10 bằng cross-encoder (nếu có model) hoặc bằng LLM rerank 1 lượt.
3. Dùng đúng `k` theo tác vụ: câu hỏi đơn giản trả 2 điều, câu hỏi quy trình trả 5.
4. Sửa tiêu đề các Điều đang là placeholder (\"Quy định tại 52/2024/ND-CP\") vì
   tiêu đề cũng được tính điểm.
