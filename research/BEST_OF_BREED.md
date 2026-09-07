# Best-of-Breed Architecture Selection for WebVeil

WebVeil does not clone or copy any single repository. Instead, it extracts the strongest underlying mechanisms from 9 state-of-the-art open-source projects, adapting them to build a privacy-first, on-device browser agent framework optimized for the **SIH Problem Statement**.

---

## 1. Subsystem Candidate Selection

| Subsystem | Selected Repository Pattern | Core Idea & Architectural Reason | WebVeil Implementation Strategy |
| :--- | :--- | :--- | :--- |
| **Browser Control & Lifecycle** | **Browser Use** | Native Python Playwright async interface with clean page context management and tab lifecycle handling. | **Independently implement** `PlaywrightController` in Python with async context management. |
| **DOM Perception & Element Tagging** | **Browser Use** | Prunes non-interactive DOM nodes and injects numeric identifiers (`[0]`, `[1]`) into interactive nodes for token-efficient grounding. | **Independently implement** `DOMPruner` with interactive element tagging, stripped scripts/styles, and token minimization. |
| **Visual Perception & Grounding** | **Skyvern & VisualWebArena** | Visual bounding-box extraction combined with screenshot coordinate mapping. | **Independently implement** `VisualGrounder` combining Playwright bounding boxes with local image coordinate mapping. |
| **Action Abstraction & Execution** | **BrowserGym** | Clean, structured JSON action space (`click(node_id)`, `type(node_id, text)`, `scroll(direction)`, `finish(result)`). | **Independently implement** `ActionSpace` with explicit local validation and error feedback. |
| **Deterministic Caching & Action Replay** | **Stagehand** | Caches selector-action pairs for repeated intents on identical page signatures to bypass LLM inference. | **Independently implement** `ActionCache` storing `(DOM_signature, intent) -> action_step`. |
| **Local Privacy & PII Detection** | **SafeScreen** | Dual-layer scanning: DOM metadata analysis + regex pattern matching + local OCR scanning. | **Independently implement** `LocalPIIDetector` combining Regex rules, DOM input types, SpaCy NER, and EasyOCR. |
| **Redaction & Sanitization Engine** | **SafeScreen + WebVeil Innovation** | Overlays visual masks on screenshots and replaces raw PII with semantic placeholders (`[EMAIL_1]`, `[PASSWORD_1]`). | **Independently implement** `LocalRedactor` with OpenCV visual box redaction and DOM placeholder substitution. |
| **Local Vault & Confidentiality Boundary** | **WebVeil Native Core** | Ensures raw sensitive data NEVER leaves client memory; un-redacts placeholders locally during Playwright execution. | **Independently implement** `ClientVault` maintaining bidirectional ephemeral token mapping (`[EMAIL_1]` <-> real text). |
| **Minimum-LLM Escalation Cascade** | **WebVeil Native Core** | Tiered execution pipeline: Local Rules -> Action Cache -> Local Heuristics -> Small Model -> Server VLM. | **Independently implement** `LLMBudgetManager` tracking token usage, latency, and cost per request. |
| **Evaluation & Benchmark Infrastructure** | **BrowserGym & AgentLab** | Standardized evaluation environment with metric logging and task tracking. | **Independently implement** `SIHMetricsEvaluator` and dashboard logger tracking the 5 SIH evaluation criteria. |

---

## 2. Components WebVeil Must Implement Independently

1. **`LocalPIIDetector` (On-Device Privacy Engine)**:
   - Evaluates text nodes, input values, and visual OCR frames on-device.
   - Detects emails, phone numbers, passwords, Aadhaar/SSN formats, credit cards, and facial regions.

2. **`LocalRedactor` & `ClientVault` (Sanitization & Local Execution)**:
   - Generates semantic placeholders (`[AADHAAR_1]`, `[EMAIL_1]`).
   - Draws visual redaction boxes on client-side screenshots.
   - Restores real secret data locally inside Playwright input actions before dispatching to the DOM.

3. **`LLMBudgetManager` (Minimum-LLM Hierarchy)**:
   - Prevents unnecessary VLM calls by first evaluating deterministic caches, local DOM heuristics, and pattern matching.

4. **`SIHMetricsEvaluator` (Benchmark Infrastructure)**:
   - Measures Visual Accuracy (25%), PII Precision (20%), PII Recall (20%), Redaction Precision (20%), Resource Utilization (20%), and Latency (15%).

---

## 3. What WebVeil Rejects / Avoids

- **No AGPL Copying**: WebVeil will not copy code from Skyvern (AGPL-3.0) to prevent copyleft licensing conflicts. Skyvern's architectural ideas (Planner-Agent-Validator loop) will be reimplemented from scratch under MIT/Apache compatibility.
- **No Direct Raw Context Transmission**: WebVeil rejects the raw DOM/screenshot transmission model used in standard Browser Use setups.
- **No Heavy Distributed Dependencies**: No Celery, Redis, Kubernetes, or vector databases required for V0 prototype.
- **No External Cloud Redaction APIs**: All redaction occurs strictly on-device prior to network transport.

