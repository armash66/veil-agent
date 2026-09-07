# WebVeil — Privacy-Preserving Browser Agent

> **SIH Problem Statement 26171 — "On-device Visual Perception for Light-weight Browser Agents"**

WebVeil is a browser agent where **local AI sees and protects, remote AI thinks, and the local client executes and verifies**. Raw PII and screenshots never leave the device.

```
┌──────────────────────────────────────────────────────────┐
│                  USER DEVICE (Trust Boundary)             │
│                                                           │
│  Browser → DOM + A11y + OCR → Local World Model           │
│                                    │                      │
│                              Privacy Engine               │
│                          (PII detect + redact + vault)    │
│                                    │                      │
│                              Egress Gate                  │
│                          (zero-leakage enforcement)       │
│                                    │                      │
│                         ═══ SANITIZED ONLY ═══            │
│                                    ↓                      │
│                          Reasoning Provider               │
│                     (Gemini / OpenAI / Ollama)             │
│                                    │                      │
│                         Action Plan (1-5 actions)         │
│                                    ↓                      │
│                          Local Firewall                   │
│                    (validate each action individually)    │
│                                    ↓                      │
│                           Execute + Verify                │
└──────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Configure (optional — works without API key using mock provider)
cp .env.example .env
# Edit .env to add your GEMINI_API_KEY or OPENAI_API_KEY

# 3. Run a demo
python -m webveil --scenario kyc              # Privacy demo
python -m webveil --scenario web              # Web navigation demo
python -m webveil --scenario visual           # Visual perception demo

# Custom task
python -m webveil --task "Fill this form" --url "http://example.com" --provider gemini
```

## Architecture

### Three-Layer Local Observation
| Layer | Source | What It Captures |
|-------|--------|-----------------|
| **DOM** | Playwright JS extraction | Interactive elements, text, values, attributes |
| **Accessibility** | Playwright A11y API | Semantic roles, names, states (checked, disabled) |
| **Visual/OCR** | Tesseract (optional) | Text in `<canvas>`, SVG, images — not in DOM |

### Privacy Pipeline
1. **PII Detector** — Regex patterns + DOM metadata for email, phone, Aadhaar, passwords, credit cards
2. **Redactor** — Replaces PII with semantic placeholders (`[EMAIL_1]`, `[PASSWORD_1]`) in DOM and screenshots
3. **Client Vault** — Ephemeral token→secret mapping with origin/node/type verification
4. **Egress Gate** — Final zero-leakage enforcement before any data leaves the device
5. **Action Firewall** — Validates every proposed action, restores vault secrets locally

### Reasoning Providers
| Provider | Setup | Best For |
|----------|-------|----------|
| `gemini` | Set `GEMINI_API_KEY` | Free tier, fast, good structured output |
| `openai` | Set `OPENAI_API_KEY` | Excellent reasoning, paid |
| `ollama` | Run Ollama locally | Zero network, full privacy |
| `mock` | No setup needed | Offline testing, CI |

## SIH Evaluation Metrics

| Metric | Weight | What We Measure |
|--------|--------|----------------|
| Visual Context Accuracy | 25% | DOM + A11y + OCR observation completeness |
| PII Detection (F1) | 20% | Precision and recall of PII detection |
| Redaction Precision | 20% | No over-redaction, no under-redaction |
| Resource Utilization | 20% | Python + Chromium combined RAM & CPU |
| End-to-End Latency | 15% | Full observe-reason-act-verify loop time |

## Demo Scenarios

### Demo A — Privacy (KYC Form)
Fills a form containing email, phone, Aadhaar, and password. All PII is detected, replaced with placeholders for reasoning, and restored locally during execution.

### Demo B — General Agent (Web Navigation)
Navigates Wikipedia, searches for a topic, and extracts information. No hardcoded behavior — the agent reasons through unfamiliar DOM.

### Demo C — Visual Perception (Canvas Challenge)
Interacts with a `<canvas>` element where text is rendered visually with no DOM representation. The agent uses local OCR to "see" the canvas and act on visual instructions.

## Tests

```bash
# Privacy & security tests (no browser needed)
python -m pytest webveil/tests/test_privacy_canary.py -v
python -m pytest webveil/tests/test_adversarial_security.py -v

# Live browser tests (needs Playwright)
python -m pytest webveil/tests/test_live_playwright_security.py -v
```

## Project Structure

```
webveil/
├── agent_loop.py              # Core agent: observe → reason → act → verify
├── config.py                  # Configuration from .env
├── __main__.py                # CLI entry point
├── browser/
│   ├── base_adapter.py        # Abstract browser interface
│   └── playwright_adapter.py  # Playwright implementation
├── core/
│   ├── models/schema.py       # All data types
│   ├── observation/
│   │   ├── world_model.py     # Three-layer world model builder
│   │   ├── a11y_observer.py   # Accessibility tree extraction
│   │   └── ocr_observer.py    # Local Tesseract OCR (optional)
│   ├── privacy/
│   │   ├── pii_detector.py    # On-device PII detection
│   │   └── redactor.py        # DOM + screenshot redaction
│   ├── vault/
│   │   └── client_vault.py    # Ephemeral secret store
│   └── verification/
│       └── local_verifier.py  # Post-action verification
├── reasoning/
│   ├── provider.py            # ReasoningProvider protocol + factory
│   └── providers/
│       ├── gemini_provider.py # Google Gemini adapter
│       ├── openai_provider.py # OpenAI / Ollama adapter
│       └── mock_provider.py   # Offline heuristic engine
├── security/
│   ├── egress/privacy_gate.py # Zero-leakage enforcement
│   ├── firewall/action_firewall.py  # Action validation + vault restore
│   └── sanitizers/url_error_sanitizer.py
├── evaluation/metrics.py      # SIH 5-metric scorer
├── dashboard/
│   ├── index.html             # Web dashboard (single-file)
│   └── server.py              # Dashboard HTTP server
├── demos/scenarios.py         # Predefined demo configurations
└── tests/                     # Unit + integration tests
```

## License

MIT
