# Script thuyết trình — Nguyễn Trung Phong (Slides 5–10)

**Thời lượng:** 9.5 phút · khoảng 1,380 từ (~10 phút ở 140 từ/phút, cần nói nhanh hơn một chút)

| Slide | Nội dung | Thời gian | Mốc cộng dồn |
|---|---|---|---|
| 5 | Workflows vs. Agents | 1:30 | 1:30 |
| 6 | Vì sao ưu tiên workflow | 2:00 | 3:30 |
| 7 | Prompt Chaining & Routing | 1:30 | 5:00 |
| 8 | Parallelization | 1:30 | 6:30 |
| 9 | Evaluator-Optimizer | 1:15 | 7:45 |
| 10 | Khi nào dùng agent | 1:45 | 9:30 |

Ký hiệu: *[nghiêng trong ngoặc]* là hành động trên sân khấu, không đọc thành tiếng.

---

## Slide 5 — Workflows vs. Agents: Ai Nắm Control Flow? (1:30)

Em xin bắt đầu phần thứ nhất. Trước khi nói đến pattern nào, có một câu hỏi cần trả lời trước: trong hệ thống của mình, **ai là người nắm control flow — code hay model?**

*[Chỉ cột trái]* Với **workflow**, control flow nằm trong code. LLM chỉ làm từng bước nhỏ trong pipeline viết sẵn, rẽ nhánh bằng if-else. Nhờ vậy hệ thống dễ đoán, chạy lại ra cùng kết quả, latency thấp và tốn ít token.

*[Chỉ cột phải]* Với **agent** thì ngược lại. Model tự quyết định trong một vòng lặp: gọi tool nào, khi nào dừng, đi tiếp hướng nào, tất cả dựa trên observation lúc runtime. Linh hoạt hơn, nhưng lỗi dễ cộng dồn và chi phí khó kiểm soát.

*[Chỉ hai hình phía dưới]* Hai hình này lấy từ bài của Anthropic. Hình trái là **augmented LLM**, tức LLM có thêm retrieval, tools và memory, viên gạch chung cho mọi pattern phía sau. Hình phải là **agent**: vẫn LLM đó nhưng chạy trong vòng lặp, gửi action ra environment, nhận feedback về và tự quyết khi nào stop.

*[Chỉ box định nghĩa]* Anthropic định nghĩa rất gọn: workflow là khi LLM và tool được điều phối qua *"predefined code paths"*, còn agent là khi LLM *"dynamically direct their own processes and tool usage"*. Ranh giới là **ai quyết định bước tiếp theo**.

> **Chuyển:** Vậy nếu agent linh hoạt hơn, tại sao Anthropic lại khuyên ưu tiên workflow?

---

## Slide 6 — Vì Sao Anthropic Khuyên Ưu Tiên Workflow? (2:00)

Lý do đầu tiên là **lỗi cộng dồn**.

*[Chỉ block trái]* Giả sử, chỉ để minh họa thôi, mỗi bước đúng 95% và các bước độc lập với nhau. Workflow 3 bước thì xác suất đúng toàn bộ còn khoảng 86%. Agent loop 8 bước còn 66%. 15 bước còn 46%, chưa bằng tung đồng xu. Con số 0.95 không phải số đo, nhưng hình dạng của nó thì đúng: **độ tin cậy giảm theo hàm mũ khi trajectory dài ra.**

*[Chỉ diagram bên dưới]* Và khác biệt thật sự không chỉ nằm ở số bước. Ở workflow, giữa các bước có check gate, nên lỗi bị chặn ngay tại chỗ. Ở agent loop, turn 1 sai thì turn 2 nhận input đã nhiễu, đến turn 3 thì thành hallucination.

*[Chỉ cột phải]* Ngoài lỗi cộng dồn còn bốn rủi ro khi vận hành:
- **Unbounded latency**: số turn do model quyết định.
- **Token tăng nhanh**: mỗi turn gửi lại toàn bộ history, tổng token tăng gần bình phương.
- **Khó debug**: lỗi hôm nay chưa chắc tái hiện được ngày mai.
- **Context drift**: tool output nhiễu tích tụ dần và kéo theo hallucination.

*[Chỉ box đỏ]* Nên câu trả lời cho câu hỏi trong đề cương là: Anthropic viết *"agentic systems often trade latency and cost for better task performance"*. Khi task đã rõ các bước thì sự đánh đổi đó không đáng, và họ nói thẳng: *"This might mean not building agentic systems at all."*

> **Chuyển:** Vậy nếu không dùng agent thì dùng gì? Anthropic đưa ra năm workflow pattern. Em trình bày bốn, còn orchestrator-workers sẽ do bạn Hưng trình bày.

---

## Slide 7 — Prompt Chaining và Routing (1:30)

Pattern đầu tiên là **prompt chaining**.

*[Chỉ hình trái]* Trong hình của Anthropic, output của LLM Call 1 đi qua một gate kiểm tra bằng code. Pass thì đi tiếp sang LLM Call 2 và 3, fail thì exit luôn. Mỗi bước chỉ làm một việc nên prompt dễ kiểm soát, và gate bắt lỗi trước khi nó lan xuống. Cái giá là latency cộng dồn theo số bước.

Theo Anthropic, pattern này hợp khi task chia được gọn thành các bước cố định. *[Chỉ box xanh]* Hai use case họ đưa ra: viết marketing copy rồi dịch sang ngôn ngữ khác; hoặc viết outline, kiểm tra outline có đạt tiêu chí không, rồi mới viết tài liệu theo outline đó.

Pattern thứ hai là **routing**.

*[Chỉ hình phải]* Router, có thể là LLM hoặc một classifier truyền thống, xác định input thuộc loại nào rồi chuyển sang đúng một nhánh chuyên biệt. Mỗi nhánh có prompt và tool riêng, không phải nhồi 50 tool vào một prompt. Cái giá là router phân loại sai thì cả nhánh phía sau sai theo.

*[Chỉ box xanh]* Use case của Anthropic: customer service chia query thành general question, refund request và technical support, mỗi loại đi một process riêng. Hoặc route theo độ khó: câu dễ sang Haiku, câu khó sang Sonnet.

> **Chuyển:** Hai pattern này mỗi lúc chỉ chạy một LLM call. Nếu các phần việc độc lập với nhau thì sao?

---

## Slide 8 — Parallelization (1:30)

*[Chỉ hình]* Pattern thứ ba là **parallelization**: nhiều LLM call chạy cùng lúc, rồi code gộp kết quả lại ở aggregator. Có hai dạng. **Sectioning** là chia task thành các phần độc lập, mỗi phần một call. **Voting** là chạy cùng một task nhiều lần rồi gộp các output.

Lợi ích là nhanh hơn, và theo Anthropic, mỗi call chỉ tập trung vào một khía cạnh nên làm tốt hơn. Cái giá là N nhánh thì tốn khoảng N lần token, latency bằng nhánh chậm nhất, và phải tự viết logic gộp.

*[Chỉ box xanh]* Use case cho sectioning: guardrails, một instance trả lời user, một instance khác song song lọc nội dung, và theo Anthropic, cách này hiệu quả hơn so với dồn cả hai việc vào một call. Cho voting: nhiều prompt khác nhau cùng review code tìm vulnerability, hoặc dùng ngưỡng vote để cân bằng false positive và false negative khi kiểm duyệt nội dung.

*[Chỉ box đỏ]* Lưu ý: hình này trông giống orchestrator-workers, nhưng ở đây subtask **viết sẵn trong code**. Ở orchestrator-workers, chính LLM quyết định chia thế nào; phần này bạn Hưng sẽ nói.

> **Chuyển:** Ba pattern vừa rồi đều chạy một chiều. Pattern cuối có vòng lặp.

---

## Slide 9 — Evaluator-Optimizer (1:15)

*[Chỉ hình]* **Evaluator-optimizer** có hai vai trò tách riêng. Generator tạo solution, evaluator chấm theo tiêu chí. Rejected thì feedback quay lại generator, accepted thì mới ra output.

Pattern này hợp khi có **tiêu chí đánh giá rõ ràng**: có feedback của con người thì output tốt lên rõ rệt, và LLM cũng tự đưa ra được feedback tương tự.

*[Chỉ box xanh]* Use case: dịch văn học, evaluator chỉ ra sắc thái bị bỏ sót; và complex search, evaluator quyết định có cần search thêm không.

*[Chỉ cột phải]* Nhưng pattern này có ba cái bẫy:
- **Token tăng theo số vòng:** K vòng thì khoảng K lần token.
- **Sycophancy:** evaluator dùng chung base model với generator dễ "gật đầu" cho qua.
- **Diminishing returns:** vòng đầu cải thiện nhiều nhất, các vòng sau dễ lòng vòng.

Cách khắc phục là dùng **external deterministic tools** như linter, unit test làm evaluator. Bạn Tùng sẽ nói kỹ ở phần deterministic oracles.

> **Chuyển:** Vậy tổng hợp lại, khi nào chọn pattern nào?

---

## Slide 10 — Khi Nào Dùng Workflow, Khi Nào Dùng Agent? (1:45)

*[Chỉ flowchart, đi từ trái sang phải]* Em gói lại thành bốn câu hỏi.

- **Câu 1:** các bước có cố định và tuần tự không? Nếu có thì dùng prompt chain, thậm chí chỉ một LLM call.
- **Câu 2:** có các nhóm task tách biệt không? Nếu có thì dùng routing.
- **Câu 3:** các subtask có độc lập và biết trước không? Nếu có thì dùng parallelization.
- **Câu 4:** subtask có chia được, nhưng phải tùy từng input không? Nếu có thì dùng orchestrator-workers, đây là phần bạn Hưng sẽ trình bày tiếp.

Chỉ khi cả bốn câu đều là không, tức bài toán open-ended, không đoán trước được số bước, mới đến lượt **autonomous agent**.

*[Chỉ ô nét đứt]* Evaluator-optimizer không nằm trên đường này, vì nó kết hợp được với bất kỳ pattern nào miễn là có tiêu chí đánh giá rõ ràng.

*[Chỉ box xanh cuối]* Vậy agent hợp với bài toán nào? Anthropic nêu hai use case. Một là **coding agent** giải task SWE-bench, với unit test làm feedback. Hai là **customer support**, agent tự lấy order history và xử lý refund, thành công đo bằng việc vấn đề được giải quyết. Điểm chung: có tiêu chí thành công rõ và có feedback loop.

*[Chỉ hai box giữa]* Và khi đã dùng agent thì phải kèm sandbox testing, guardrails và checkpointing.

**Kết phần:** Tóm lại, thông điệp của phần em là: **bắt đầu từ thứ đơn giản nhất, và chỉ tăng độ phức tạp khi có lý do đo được.**

> **Chuyển sang Hưng:** Câu hỏi tiếp theo là: khi đã buộc phải dùng orchestrator-workers, nó vận hành thế nào và tốn bao nhiêu? Em xin chuyển lời cho bạn Hưng.

---

## Chuẩn bị Q&A

**1. "Con số 0.95 lấy ở đâu?"**
Đây là số minh họa, không phải số đo, và có giả định các bước độc lập. Điều em muốn nói là hình dạng hàm mũ: cùng một độ chính xác mỗi bước, trajectory càng dài thì xác suất đúng toàn bộ càng giảm nhanh.

**2. "Workflow cũng nhiều bước, sao không bị $p^n$?"**
Workflow cũng bị. Khác biệt là số bước của workflow biết trước, và giữa các bước có gate để bắt lỗi và retry ngay tại chỗ, nên lỗi không trôi tiếp. Agent loop thì không biết trước số bước và thường không có gate.

**3. "Routing có phải là agent không, vì LLM cũng đang quyết định?"**
Không. Router chỉ chọn nhánh một lần ở đầu, sau đó control flow do code quản lý. Agent thì tự quyết định bước tiếp theo nhiều lần trong một vòng lặp.

**4. "Evaluator-optimizer có vòng lặp, vậy nó là agent à?"**
Theo phân loại của Anthropic, nó vẫn là workflow. Vòng lặp do code định nghĩa: ai là generator, ai là evaluator, điều kiện dừng và số vòng tối đa đều viết sẵn.

**5. "Làm sao biết đã đến lúc cần agent?"**
Khi evals cho thấy workflow không đạt yêu cầu và bài toán thật sự open-ended. Nguyên tắc của Anthropic là chỉ tăng độ phức tạp *"when needed"*, tức là cần có số đo chứng minh.

**6. "Sao không dùng framework như LangGraph ngay từ đầu?"**
Anthropic lưu ý framework thêm các lớp abstraction, che mất prompt và response thật bên dưới, làm việc debug khó hơn. Nên bắt đầu bằng gọi API trực tiếp, hiểu rõ từng bước rồi mới dùng framework. Phần sau, bạn Hưng sẽ nói khi nào LangGraph thật sự có ích.

**7. "Khi nào chọn sectioning, khi nào chọn voting?"**
Sectioning khi task tách được thành các phần **khác nhau** và độc lập, mục tiêu là nhanh hơn và mỗi call tập trung hơn. Voting khi cần **độ tin cậy cao hơn** cho cùng một câu hỏi, chấp nhận tốn N lần token. Chi phí của cả hai được so sánh ở bảng trade-off slide 17 của bạn Tùng.
