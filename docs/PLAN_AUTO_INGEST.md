# Plan: tự động nạp thông tư / nghị định mới vào LawGraph

> Trạng thái: đề xuất (chưa code). Mục tiêu: văn bản mới xuất hiện trên vbpl.vn thì
> trong vòng 1 ngày làm việc đã có trong graph, có hiệu lực đúng ngày, và **không
> bao giờ** làm bẩn graph đang chạy.

## 1. Vì sao cần — bằng chứng đo được

| Vấn đề | Bằng chứng |
|---|---|
| Cùng một văn bản bị tách 2 node | `52/2024/ND-CP` và `52/2024/NĐ-CP` cùng tồn tại; mỗi node giữ một phần điều khoản (5 vs 2) |
| Điều bị nhân đôi sau khi gộp | `52/2024/ND-CP` có 2 node cho Điều 24 |
| Nội dung article là placeholder | Tiêu đề "Quy định tại 52/2024/ND-CP", nội dung 527 ký tự lặp lại → retrieval không tìm ra "ví điện tử" |
| Corpus chưa đủ | Graph 34 văn bản; SBV-LawGraph công bố 1.703 văn bản |
| Không có cơ chế nạp định kỳ | Không có cron/queue; `scripts/` chỉ có script chạy tay |

## 2. Kiến trúc 6 tầng (map vào C0–C4 của S2-5)

```
[Nguồn]  vbpl.vn / Công báo / data/raw
   │
   1. WATCH      — phát hiện văn bản mới/ sửa đổi      (C0: read-only)
   │
   2. FETCH      — tải toàn văn, lưu raw + hash         (C0)
   │
   3. NORMALIZE  — chuẩn hoá số hiệu, ngày, loại         (C1: tính nội bộ)
   │
   4. EXTRACT    — bóc Điều/Khoản, LLM structured output (C1)
   │
   5. VALIDATE   — cổng kiểm chứng + đối chiếu chéo      (C1, tất định)
   │
   6. PUBLISH    — ghi graph + qdrant, có version, có rollback (C3: cần 2 người)
```

Nguyên tắc: **không ghi thẳng vào graph đang phục vụ**. Mọi văn bản mới vào
`staging` trước, chỉ publish khi qua cổng ở tầng 5.

## 3. Từng tầng

### 3.1 WATCH
- Nguồn: RSS/HTML vbpl.vn (đã có `VBPL_SEARCH_URL` trong `.env`), thư mục `data/inbox/`.
- So khớp với `Document.doc_id` (đã chuẩn hoá bằng `src/core/doc_ids.canonical_doc_id`).
- Phát hiện 2 loại thay đổi: **văn bản mới** và **văn bản sửa đổi** (đã có `AMENDS`).
- Idempotent theo `(doc_id, content_hash)`; chạy lại không tạo bản ghi mới.

### 3.2 FETCH
- Lưu nguyên văn vào `data/raw/{doc_id}.txt` + `.meta.json` (url, ngày tải, hash).
- Giới hạn: 1 request/2s, timeout 10s, retry 3 lần có backoff — tránh bị chặn.
- Nếu hash không đổi → dừng, không làm gì tiếp.

### 3.3 NORMALIZE
- `doc_id = canonical_doc_id(raw)` — **bắt buộc**, đây là chỗ từng sinh ra 2 node.
- Ngày: ISO `YYYY-MM-DD`; thiếu `effective_date` thì lấy `issue_date + 45 ngày`
  (Luật Ban hành VBQPPL) và đánh dấu `effective_date_inferred=true`.
- Loại văn bản: Nghị định / Thông tư / Quyết định / Luật.

### 3.4 EXTRACT
- Bóc theo cấu trúc "Điều N." → "Khoản M." → "Điểm a)".
- Dùng LLM structured output cho phần khó, nhưng **luôn** kiểm lại bằng regex:
  số điều bóc được phải khớp số "Điều" đếm được trong văn bản.
- Lưu `article_number`, `article_title`, `content` — **không** lưu placeholder.
- Kiểm tối thiểu: `len(content) >= 200` ký tự, khác rỗng, không trùng tiêu đề chung.

### 3.5 VALIDATE (cổng — quan trọng nhất)
Chạy trước khi publish, tất định, không cần LLM:

1. **Chống trùng**: `canonical_doc_id` chưa tồn tại, hoặc đang là bản cũ hơn.
2. **Chống placeholder**: không có article nào có tiêu đề `Quy định tại <doc_id>`
   và nội dung lặp lại giữa ≥3 điều.
3. **Đủ cấu trúc**: số article ≥ 80% số "Điều" đếm được trong raw.
4. **Dẫn chiếu chéo**: mọi `supersedes` / `amends` trỏ tới doc_id tồn tại.
5. **Hiệu lực**: không nạp văn bản đã hết hiệu lực vào tập active (vẫn lưu để tra cứu lịch sử).

Không qua bất kỳ mục nào → vào `staging/rejected/` kèm lý do, **không** publish.

### 3.6 PUBLISH
- Ghi `Document` → `Article` → `Clause`, cạnh tranh bằng `MERGE` theo khoá chuẩn.
- Ghi Qdrant theo batch, `doc_id` + `article` trong payload để join ngược.
- Đánh version: `Document.graph_version = n`, giữ `previous_version` để rollback.
- Chạy lại `scripts/repair_duplicate_docs.py` sau mỗi lần publish (rẻ, idempotent).

## 4. Vòng đời hiệu lực (temporal)

- Mỗi `Document` có `effective_date`, `expiration_date`, `status`.
- Khi văn bản mới `SUPERSEDES` văn bản cũ: cập nhật `revoked_by` của bản cũ,
  **không xoá** — vẫn cần để trả lời câu hỏi lịch sử.
- `selective_traversal` đã hỗ trợ `reference_date` — dùng nó để trả lời
  "tại thời điểm 2022 thì quy định nào có hiệu lực".

## 5. Người duyệt ở đâu

Theo S2-5: nạp văn bản là hành động **không hoàn tác** (C3). Đề xuất:
- Tự động hoàn toàn cho văn bản **đọc thêm** (không xoá gì).
- Cần 1 người duyệt khi: (a) văn bản làm thay đổi hiệu lực của văn bản đang có,
  (b) validate tầng 5 fail nhưng người thấy có thể chấp nhận, (c) xoá/gộp node.
- Hộp duyệt phải hiện **diff** (điều nào thêm/xoá) và **nguồn** (url + hash).

## 6. Việc cần làm (thứ tự)

| # | Việc | File | Ước lượng |
|---|---|---|---|
| 1 | Chuẩn hoá doc_id ở mọi chỗ ghi graph | `src/core/doc_ids.py` ✅ đã có | xong |
| 2 | Repair trùng + placeholder | `scripts/repair_duplicate_docs.py` ✅ | xong |
| 3 | Hàm `validate_document()` tầng 5 | ✅ `src/knowledge/validate.py` + 12 test, đã nối vào `ingest_file` (bật `LEGALPILOT_STRICT_INGEST=1` để chặn thật) | xong |
| 4 | `watch_and_ingest.py` chạy tay được | `scripts/watch_and_ingest.py` | 2 ngày |
| 5 | Nạp lại 52/2024 đúng nội dung | ✅ đã làm 09/11: Điều 22–23 có tiêu đề + nội dung thật | xong |
| 6 | Cron 6h/lần + báo Slack khi có văn bản mới | `launchd`/`cron` | 0.5 ngày |
| 7 | Mở rộng corpus 34 → 1.703 văn bản (nền tảng để so với SBV-LawGraph) | hàng loạt | 3–5 ngày |

## 7. Đo lường

- `ingest_success_rate`, `validate_reject_rate` (mục tiêu < 5%),
- `duplicate_doc_rate` (mục tiêu = 0 — hiện đã về 0 sau repair),
- `placeholder_article_rate` (mục tiêu = 0),
- độ trễ: văn bản xuất hiện trên vbpl.vn → có trong graph (mục tiêu < 24h).

## 8. Rủi ro đã biết

- **Nội dung sai từ nguồn**: chỉ cần hash + người duyệt cho văn bản làm đổi hiệu lực.
- **vbpl.vn đổi cấu trúc HTML**: parser phải fail loudly (không im lặng trả rỗng).
- **LLM bóc sai số điều**: luôn kiểm lại bằng regex đếm "Điều".
- **Nạp trùng khi chạy song song**: khoá `(doc_id, content_hash)` + MERGE.
