# WebVeil Local Privacy & Redaction Architecture

## 1. Primary Privacy Axiom

> **"RAW SCREENSHOTS AND UNMASKED PII MUST NEVER LEAVE THE CLIENT MACHINE."**

The client machine is the **Trust Boundary**. The network interface between the local client and the server VLM/LLM is an untrusted channel from a privacy standpoint.

```
+-----------------------------------------------------------------------------------+
|                               LOCAL CLIENT BOUNDARY                               |
|                                                                                   |
|  +---------+     +---------+     +-------------------+     +------------------+   |
|  | Play-   | --> | Visual  | --> | Local PII         | --> | Redaction Engine |   |
|  | wright  |     | Capture |     | Detector          |     | & Vault          |   |
|  +---------+     +---------+     +-------------------+     +------------------+   |
+------------------------------------------------------------------|----------------+
                                                                   | SANITIZED ONLY
                                                                   v
                                                        +---------------------+
                                                        | SERVER VLM / LLM    |
                                                        | (Reasoning Engine)  |
                                                        +---------------------+
```

---

## 2. Privacy Pipeline Flow

1. **Browser Capture**:
   - `Playwright` extracts DOM tree and captures viewport screenshot in memory.
2. **Local Perception**:
   - `DOM Scanner` evaluates tag names, `type="password"`, `type="email"`, `autocomplete`, labels, and text nodes.
   - `Local OCR` (EasyOCR / Tesseract) extracts visible text strings from rendered images/canvas.
   - `Visual Face/Bounding Box Detector` locates face regions or document photos.
3. **Sensitive Data Detection**:
   - Matches text against PII rules: Email regex, Phone regex, Aadhaar 12-digit pattern, Credit Card Luhn, Password fields, SSN patterns, and Name entities.
4. **Redaction & Sanitization**:
   - **DOM Level**: Replaces sensitive text strings and values with typed semantic placeholders (`[EMAIL_1]`, `[AADHAAR_1]`, `[PASSWORD_1]`).
   - **Visual Level**: Draws solid bounding boxes over detected PII and face regions on the screenshot, labeling each box with its corresponding semantic placeholder tag.
   - **Vault Injection**: Stores `[TOKEN_ID] -> raw_value` mapping in `ClientVault` residing in ephemeral client memory.
5. **Sanitized Payload Egress**:
   - Transmits ONLY the sanitized DOM tree + redacted screenshot + action history to the server VLM/LLM.
6. **Server Action Proposal**:
   - Server VLM responds with action using semantic placeholders (e.g., `type(node_id=4, text="[EMAIL_1]")`).
7. **Local Action Un-Redaction & Execution**:
   - Client interceptor inspects proposed action text.
   - If action contains `[EMAIL_1]`, client looks up `[EMAIL_1]` in `ClientVault`, retrieves real `user@example.com`, and executes `page.fill(selector, "user@example.com")` directly in local Playwright browser.
   - Server never learns the contents of `user@example.com`.

---

## 3. Semantic Placeholder Scheme

| Sensitive Data Category | Raw Example (Client Only) | Transmitted Placeholder | Visual Overlay Label |
| :--- | :--- | :--- | :--- |
| **Email Address** | `armash@example.com` | `[EMAIL_1]` | `[EMAIL_1]` |
| **Aadhaar Number** | `9876 5432 1098` | `[AADHAAR_1]` | `[AADHAAR_1]` |
| **Phone Number** | `+91 98765 43210` | `[PHONE_1]` | `[PHONE_1]` |
| **Password** | `SecretPass123!` | `[PASSWORD_1]` | `[PASSWORD_1]` |
| **Person Name** | `Armash Ansari` | `[NAME_1]` | `[NAME_1]` |
| **Credit Card** | `4532 1111 2222 3333` | `[CARD_1]` | `[CARD_1]` |
| **User Face / ID Photo** | Raw pixel region | `[FACE_1]` | Solid Redaction Box (`[FACE_1]`) |

---

## 4. Verification & Synthetic Canary Leakage Testing

To prove zero-leakage compliance, WebVeil includes a **Synthetic Canary Auditing System**:

- Synthetic canary strings are injected during automated testing:
  - `EMAIL_CANARY_99`
  - `AADHAAR_CANARY_88`
  - `PHONE_CANARY_77`
  - `PASSWORD_CANARY_66`
- An egress network proxy interceptor audits all outgoing requests to the server model.
- **Assertion**: If any canary value or raw PII substring is detected in the network payload, the pipeline immediately halts and throws a `PrivacyViolationError`.

