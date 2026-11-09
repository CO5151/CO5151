# Guardrails & abstention — đo end-to-end (10 câu, 09/11/2026)

Mục đích: kiểm tra hai thứ mới thêm vào pipeline có **chặn oan** không.

- `SecurityGuardrails` ở đầu vào (S2-5, vector 2–8)
- `gate_answer` ở đầu ra: mọi dẫn chiếu phải có căn cứ
- `answer_status`: ok / unverified / insufficient_evidence / refused / needs_human

## Kết quả

| Trạng thái | Trước khi sửa prompt | Sau sửa prompt (lần 1) | Sau sửa + tự chữa lành (lần 2) |
|---|---|---|---|
| `ok` | 5 | 6 | 8 |
| `unverified` (cho qua, cần người duyệt) | 3 | 4 | 2 |
| `insufficient_evidence` (chặn hẳn) | **2** | **0** | **0** |

**Phương sai phải nói rõ:** hai lần chạy cùng cấu hình (sau khi thêm tự chữa lành)
cho `ok` = 8 và `ok` = 6. Với n = 10 và LLM không tất định, chênh lệch 6↔8 **không**
đủ để kết luận tự chữa lành cải thiện tỉ lệ `ok`. Điều tái lập được qua cả hai lần
là: **`insufficient_evidence` từ 2/10 xuống 0/10**. Thời gian 258s → 197–224s.

## Nguyên nhân chặn oan và cách sửa

Cổng đầu ra chặn khi bản nháp viện dẫn một văn bản **không có trong ngữ cảnh đã
truy xuất**. Đây là hành vi đúng — nhưng prompt của drafter chỉ nói chung
"dựa trên các điều khoản trên", không nêu **danh sách văn bản được phép**.

Sửa: chèn một dòng tường minh vào prompt:

```
DANH SÁCH VĂN BẢN ĐƯỢC PHÉP TRÍCH DẪN: 12/2022/TT-NHNN, 94/2025/ND-CP, ...
Tuyệt đối KHÔNG viện dẫn bất kỳ văn bản nào khác, kể cả để so sánh.
```

Kết quả: số câu bị chặn hẳn về 0, trong khi cổng vẫn bắt được 2–4 câu có dẫn
chiếu "đúng văn bản nhưng khác điều" và đánh dấu `unverified`.

## Tự chữa lành dẫn chiếu

Khi cổng bắt được một dẫn chiếu không nằm trong ngữ cảnh, orchestrator tra
**thẳng vào graph** xem điều đó có tồn tại không:

- Có thật → bổ sung vào ngữ cảnh, kiểm lại (cứu được câu trả lời đúng).
- Không tồn tại → đúng là bịa, không cứu (ví dụ model trích "Điều 13 Nghị định
  52/2024" trong khi nghị định này chỉ có Điều 12, 18, 22, 23, 24, 27).

Điểm quan trọng: không tin lời model — chỉ chấp nhận nếu graph xác nhận.

## Điều đáng lo còn lại

**4/10 câu `unverified`** nghĩa là model vẫn hay trích Điều không nằm trong tập
đã truy xuất (dù cùng văn bản). Với người dùng, câu trả lời vẫn ra nhưng bị gắn
cờ cần duyệt. Muốn giảm: tăng `dense_top_k` cho câu hỏi nhiều bước, hoặc cho
drafter xin thêm điều khoản khi thiếu.

## Chạy lại

```bash
python3 - <<'EOF'
import sys, json, logging
sys.path.insert(0, '.'); logging.disable(logging.WARNING)
from src.agents.orchestrator import LegalOrchestrator
qs = json.load(open('data/benchmarks/sbv_testset_tvpl.json', encoding='utf-8'))[:10]
o = LegalOrchestrator(); stats = {}
for q in qs:
    st = o.run(q['question'], enable_live_vbpl=False)
    stats[st.answer_status] = stats.get(st.answer_status, 0) + 1
print(stats)
EOF
```
