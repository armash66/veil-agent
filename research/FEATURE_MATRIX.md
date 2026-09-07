# WebVeil Feature Matrix & Open-Source Repository Comparison

This feature matrix analyzes 9 key open-source web agent, privacy, and benchmark repositories to evaluate their technical mechanisms, licenses, efficiency, and relevance to the **SIH Problem Statement: On-device Visual Perception for Light-weight Browser Agents**.

---

## 1. Browser Agent Capabilities

| Feature | Candidate / Best Implementation | Why It Stand Out | What WebVeil Should Use | Implementation Difficulty | License Constraint | Expected Effect on LLM Calls | Expected Effect on SIH Metrics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Navigation & Tab Control** | **Browser Use** | Native Playwright context manager handling multiple tabs, popups, and standard navigation events seamlessly. | Reimplement lightweight Playwright wrapper supporting clean tab/page lifecycle management. | Low | MIT (Safe to study/reimplement) | Neutral | Improves latency (15%) and reliability. |
| **Click / Type / Keyboard / Scroll** | **Browser Use & BrowserGym** | Browser Use provides clean string action parsing (`click_element(index)`, `input_text(index, text)`), while BrowserGym standardizes action spaces. | Standardized action schema (`click`, `type`, `scroll`, `press_key`, `wait`, `finish`) targeting numeric node IDs or redacted coordinates. | Medium | MIT / Apache-2.0 | Reduces LLM calls through concise action tokens. | Direct impact on end-to-end task execution. |
| **DOM Extraction & Pruning** | **Browser Use** | Prunes non-interactive elements, injects visible index attributes (`[0]`, `[1]`), and outputs a concise tree. | Enhanced DOM pruner that injects node IDs while filtering non-interactive nodes AND removing PII text locally. | Medium | MIT | **Drastic reduction (up to 70%)** in DOM prompt tokens. | Improves visual context accuracy (25%) & latency (15%). |
| **Accessibility Tree Parsing** | **BrowserGym & Stagehand** | Uses browser's native `accessibility` tree API for screen-reader friendly node hierarchy. | Hybrid fallback: DOM tree for interactive elements, Accessibility tree for custom ARIA widgets. | Medium | Apache-2.0 / MIT | Reduces token overhead compared to raw HTML. | Improves visual context accuracy (25%). |
| **Visual Grounding** | **Skyvern** | Combines OpenCV visual bounding box detection with VLM visual coordinate layout analysis. | Lightweight local visual grounding using Playwright element bounding boxes + local OCR/CV contour boxes. | High | AGPL-3.0 (**Must reimplement independently**) | Reduces VLM calls by resolving element positions locally. | Critical for Visual Context Accuracy (25%). |
| **OCR & Local Text Extraction** | **SafeScreen** | Uses local OCR engines (EasyOCR/Tesseract) to extract text directly from visual viewport render. | On-device OCR (EasyOCR / RapidOCR / Tesseract) for canvas/image text PII identification. | Medium | MIT | Zero extra cloud LLM calls for text extraction. | Core to PII Detection Precision (20%) & Recall (20%). |
| **Multimodal Perception** | **VisualWebArena** | Pairs visual screenshot overlays with DOM tree structures to evaluate grounding on complex UIs. | Local dual-view perception: Sanitized Visual Viewport + Sanitized DOM Tree. | Medium | Apache-2.0 | Enables low-cost multimodal models (e.g. Gemini Flash) to reason effectively. | Maximizes Visual Context Accuracy (25%). |
| **Agent Loop & Execution** | **Browser Use** | Simple, robust iterative loop: Observe -> Plan/Decide -> Act -> Verify. | Asynchronous local perceive-redact-transmit-act-verify loop. | Medium | MIT | Prevents redundant loops via fast local validation. | Improves end-to-end latency (15%). |
| **Deterministic Execution & Fallback** | **Stagehand** | Caching action-selector pairs (`observe` -> `act`) so repeated tasks skip LLM reasoning. | Local rule engine & deterministic cached action playback for common patterns (e.g., standard login/submit). | High | MIT | **Eliminates 100% of LLM calls** for cached deterministic steps. | Reduces Latency (15%) and Client Resource Utilization (20%). |
| **Human Takeover & Real Browser Bridge** | **BrowserSkill** | Attaches to existing user browser session via CDP without taking over user focus. | Local CDP attachment module for optional human-in-the-loop authentication/verification. | High | MIT | Avoids LLM struggling with complex CAPTCHAs/MFA. | Increases overall task success. |

---

## 2. Privacy & Security Architecture

| Feature | Candidate / Best Implementation | Why It Stand Out | What WebVeil Should Use | Implementation Difficulty | License Constraint | Expected Effect on LLM Calls | Expected Effect on SIH Metrics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Local PII Detection (DOM)** | **SafeScreen** | Scans input types (`password`, `email`, `tel`), attributes (`autocomplete`), and regex patterns for PII. | Multi-tier local DOM scanner using regex (Aadhaar, SSN, phone, card), input metadata, and local SpaCy NER. | Medium | MIT | Zero LLM calls for PII identification. | **Directly drives PII Precision (20%) & Recall (20%)**. |
| **Local PII Detection (Visual/OCR)** | **SafeScreen** | Runs OCR on visual screenshot to locate rendered text matching PII patterns. | On-device OCR + bounding box mapper to detect visually rendered PII (e.g., identity cards, image text). | High | MIT | Zero LLM calls. | Essential for PII Recall (20%) on visual elements. |
| **Screenshot Redaction & Masking** | **SafeScreen** | Blurs/covers PII bounding boxes on local canvas before saving/transmitting image. | Local OpenCV canvas redactor applying solid color masks + semantic overlay tags (`[AADHAAR_1]`, `[FACE_1]`). | Medium | MIT | None | **Directly drives Redaction Precision (20%)**. |
| **Semantic Placeholder Scheme** | **WebVeil Native Architecture** | Replaces sensitive raw text with typed token placeholders (`[EMAIL_1]`, `[PASSWORD_1]`) in both DOM and Screenshot. | Local bidirectional mapping dictionary (`Client Vault`): `[EMAIL_1]` <-> `real_user@domain.com`. | Medium | N/A (WebVeil Novel Core) | Reduces token count by replacing variable-length sensitive strings. | Enforces strict Privacy Guarantee (0% raw PII leakage). |
| **Local Un-redaction at Execution** | **SafeScreen** | Swaps placeholders back to real values locally right before executing Playwright action. | Client Action Execution Handler: intercepts `type([PASSWORD_1])` and substitutes actual secret from local Vault into Playwright input stream. | Low | MIT | None | Ensures execution fidelity while keeping server 100% blind to raw PII. |
| **Prompt-Injection Defense** | **Stagehand & Skyvern** | Sanitizes web page text to strip malicious instruction injections (`Ignore previous instructions...`). | Local DOM text filter stripping prompt injection heuristics from web page context before sending to server. | Medium | MIT / AGPL-3.0 | Prevents hijacked LLM loops. | Protects agent integrity & prevents unintended data exfiltration. |
| **Domain & Action Permissions** | **WebVeil Native** | Restricts agent actions based on origin trust boundaries. | Strict domain sandbox & confirmation boundary for sensitive state changes (e.g., payment submission). | Low | N/A | Saves LLM calls on unauthorized domains. | Essential for secure client execution. |

---

## 3. Efficiency & Minimum-LLM Strategy

| Feature | Candidate / Best Implementation | Why It Stand Out | What WebVeil Should Use | Implementation Difficulty | License Constraint | Expected Effect on LLM Calls | Expected Effect on SIH Metrics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Hierarchy of Escalation** | **WebVeil Native Strategy** | Multi-level decision cascade: Local Rules -> DOM Extraction -> Local OCR/CV -> Deterministic Cache -> Server VLM. | `LLMBudgetManager` enforcing local rule matching before delegating to server LLM. | Medium | N/A | **Reduces LLM calls by 50-80%** on routine forms/pages. | **Directly optimizes End-to-End Latency (15%) & Client Resource Utilization (20%)**. |
| **Action Selector Caching** | **Stagehand** | Remembers DOM paths / visual descriptors for tasks on recurring domains. | Local SQLite/JSON Action Cache storing `(page_hash, intent) -> selector_action`. | Medium | MIT | **100% reduction** on repeated workflow steps. | Drastically improves Latency (15%). |
| **Selective Screenshot Transmission** | **Browser Use** | Transmits screenshots only when DOM tree ambiguity is high or visual validation is requested. | Conditional screenshot capture: send visual state only on dynamic/canvas pages or upon explicit request. | Low | MIT | Saves bandwidth & token costs. | Optimizes Client Resource Utilization (20%) & Latency (15%). |
| **Local Lightweight Models** | **AgentLab & Skyvern** | Uses small local models (e.g., MobileNet, ONNX models, small transformers) for perception tasks. | Local ONNX/Python lightweight detectors (OCR + Regex + regex NER) running on client CPU/GPU. | High | Apache-2.0 | Zero external LLM calls for perception. | Maximizes Client Resource Efficiency (20%). |

---

## 4. Evaluation & SIH Metrics Harness

| Feature | Candidate / Best Implementation | Why It Stand Out | What WebVeil Should Use | Implementation Difficulty | License Constraint | Expected Effect on LLM Calls | Expected Effect on SIH Metrics |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Gym Environment Wrapper** | **BrowserGym** | Standardized `gym.Env` interface with unified observation/action space. | `WebVeilGymEnv` wrapping local browser + local privacy pipeline for reproducible testing. | Medium | Apache-2.0 | Enables programmatic batch evaluation. | Enables automated metric tracking across benchmarks. |
| **SIH Metrics Evaluator** | **WebVeil Native Harness** | Tracks the 5 exact SIH metrics: Visual Accuracy (25%), PII Precision (20%), PII Recall (20%), Redaction Precision (20%), Resource Utilization (20%), Latency (15%). | `SIHMetricsEvaluator` producing real-time benchmark scores and visual dashboard reports. | Medium | N/A | Standardizes system performance validation. | Core metric dashboard for hackathon judging. |
| **Synthetic Canary Dataset** | **WebVeil Safety Harness** | Injects synthetic test PII (`EMAIL_CANARY_123`, `AADHAAR_CANARY_789`) into test pages to audit leaks. | Automated zero-leakage test suite asserting 0% canary presence in all egress network payloads. | Low | N/A | None | Verifies strict privacy compliance. |

