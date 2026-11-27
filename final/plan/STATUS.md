# STATUS — nhật ký tiến độ G4 (điền cuối mỗi ngày)

Định dạng một dòng:

```
| Ngày | Việc (mã W) | Người | Bằng chứng (commit / trang / log) | Người kiểm | Trạng thái |
```

Trạng thái: `xong` · `một phần` · `chặn`.

## 26/11 — khung

| Ngày | Việc | Người | Bằng chứng | Người kiểm | Trạng thái |
|---|---|---|---|---|---|
| 26/11 | W0 dựng khung report/slide/plan | Tùng | `final/` (`77fb226`) | — | xong |
| 26/11 | W2.1–W2.2 bộ 20 ca injection + runner + đo 10 ca Pha A | Tùng | `final/security/attacks/` (`468a329`) | — | xong (10 ca indirect đang `STAGED`) |

## Việc đang chặn

| Việc | Chặn ai | Cần gì | Từ ngày |
|---|---|---|---|
| Phụ lục B — phản hồi góp ý D2 | Tùng | góp ý D2 từ GV (văn bản hoặc biên bản) | 26/11 |
| Baseline ngoài chạy được | Tùng | chốt 1 trong: dense-only / ReAct / GraphRAG off-the-shelf | 26/11 |
| Switch ablation C2 | Tùng | sửa `enable_selective_traversal` thành switch thật | 28/11 |
| Latency từng câu | Tùng | thêm `latency_ms` wall-clock vào raw | 28/11 |
