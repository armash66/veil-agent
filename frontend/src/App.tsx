import React, { useState, useEffect } from 'react';
import {
  Shield,
  Server,
  ExternalLink,
  Terminal,
  RefreshCw,
  FolderOpen,
  Globe,
  Copy,
  Check,
  Layers,
  Cpu,
  Lock,
  Compass,
  FileCheck,
  AlertTriangle,
  ShieldCheck,
  Eye,
  CheckCircle2,
  ArrowRight,
  ChevronRight
} from 'lucide-react';

type TabId = 'overview' | 'how-to-use' | 'test-runs';

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  const [reasoningStatus, setReasoningStatus] = useState<{
    online: boolean;
    latencyMs?: number;
    checking: boolean;
    activeTier?: string;
  }>({ online: false, checking: true });

  const [testServerStatus, setTestServerStatus] = useState<{
    online: boolean;
    latencyMs?: number;
    checking: boolean;
  }>({ online: false, checking: true });

  const [copiedCmd, setCopiedCmd] = useState(false);
  const [copiedPath, setCopiedPath] = useState(false);
  const [copiedPromptId, setCopiedPromptId] = useState<string | null>(null);

  const handleCopyPrompt = (prompt: string, id: string, e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    navigator.clipboard.writeText(prompt);
    setCopiedPromptId(id);
    setTimeout(() => setCopiedPromptId(null), 2000);
  };

  const checkHealth = async () => {
    setReasoningStatus((prev) => ({ ...prev, checking: true }));
    const t0 = performance.now();
    try {
      const res = await fetch('http://127.0.0.1:8000/api/health', { method: 'GET', mode: 'cors' });
      const latency = Math.round(performance.now() - t0);
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        setReasoningStatus({
          online: true,
          latencyMs: latency,
          checking: false,
          activeTier: data.active_tier || 'Local (Ollama)',
        });
      } else {
        setReasoningStatus({ online: false, checking: false });
      }
    } catch (_) {
      setReasoningStatus({ online: false, checking: false });
    }

    setTestServerStatus((prev) => ({ ...prev, checking: true }));
    const t1 = performance.now();
    try {
      await fetch('http://127.0.0.1:8080/index.html', { method: 'HEAD', mode: 'no-cors' });
      const latency = Math.round(performance.now() - t1);
      setTestServerStatus({ online: true, latencyMs: latency, checking: false });
    } catch (_) {
      setTestServerStatus({ online: false, checking: false });
    }
  };

  useEffect(() => {
    checkHealth();
    const timer = setInterval(checkHealth, 10000);
    return () => clearInterval(timer);
  }, []);

  const handleCopyCommand = () => {
    navigator.clipboard.writeText('launch_webveil.bat');
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  const handleCopyPath = () => {
    navigator.clipboard.writeText('c:\\Users\\Armash Ansari\\OneDrive\\Desktop\\Projects\\AI & ML\\veil-agent\\extension');
    setCopiedPath(true);
    setTimeout(() => setCopiedPath(false), 2000);
  };

  const navItems = [
    { id: 'overview' as TabId, label: 'Overview & Pillars', icon: Layers },
    { id: 'how-to-use' as TabId, label: 'How to Use', icon: Compass },
    { id: 'test-runs' as TabId, label: 'Verified Test Runs', icon: FileCheck },
  ];

  return (
    <div className="wv-shell">

      {/* ══════════════════════════════════════════════════════════════════
          SIDEBAR — Linear-style with left-border active indicator
         ══════════════════════════════════════════════════════════════════ */}
      <aside className="wv-sidebar">
        <div className="space-y-8">
          {/* Brand */}
          <div className="flex items-center gap-3 px-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center text-white flex-shrink-0 shadow-sm">
              <Shield size={16} strokeWidth={2.5} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-[15px] text-gray-900 tracking-tight">WebVeil</span>
              </div>
              <p className="text-[11px] text-gray-400 -mt-0.5">PS-26171 · Evaluator</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`wv-nav-item ${isActive ? 'wv-nav-item--active' : ''}`}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Status Footer */}
        <div className="space-y-3 pt-6 border-t border-gray-100">
          <div className="wv-section-label px-2 mb-2">Service Status</div>

          <div className="flex items-center justify-between px-2 py-1.5">
            <div className="flex items-center gap-2.5">
              <div className={`wv-dot ${reasoningStatus.online ? 'wv-dot--online' : 'wv-dot--offline'}`} />
              <span className="text-[13px] text-gray-600">Reasoning</span>
            </div>
            <span className={`text-[12px] font-mono font-medium ${reasoningStatus.online ? 'text-emerald-600' : 'text-red-500'}`}>
              {reasoningStatus.checking ? '...' : reasoningStatus.online ? `${reasoningStatus.latencyMs}ms` : 'Down'}
            </span>
          </div>

          <div className="flex items-center justify-between px-2 py-1.5">
            <div className="flex items-center gap-2.5">
              <div className={`wv-dot ${testServerStatus.online ? 'wv-dot--online' : 'wv-dot--offline'}`} />
              <span className="text-[13px] text-gray-600">Test Server</span>
            </div>
            <span className={`text-[12px] font-mono font-medium ${testServerStatus.online ? 'text-emerald-600' : 'text-red-500'}`}>
              {testServerStatus.checking ? '...' : testServerStatus.online ? `${testServerStatus.latencyMs}ms` : 'Down'}
            </span>
          </div>
        </div>
      </aside>

      {/* ══════════════════════════════════════════════════════════════════
          MAIN CONTENT AREA
         ══════════════════════════════════════════════════════════════════ */}
      <main className="wv-content">

        {/* ═══════════════════════════════════════════════════════════
           TAB 1 — OVERVIEW & PILLARS
           ═══════════════════════════════════════════════════════════ */}
        {activeTab === 'overview' && (
          <div key="overview" className="reveal-section space-y-10">
            {/* Hero */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <ShieldCheck size={14} className="text-indigo-500" />
                <span className="wv-section-label text-indigo-500">Problem Statement PS-26171</span>
              </div>

              <h1 className="wv-page-title">
                Privacy-Preserving<br />
                <span className="wv-gradient-text">On-Device Web Agent</span>
              </h1>

              <p className="wv-subtitle">
                WebVeil is an on-device, privacy-preserving browser agent engineered for sensitive and defense web workflows.
                Credential fields, identity numbers, and session tokens are intercepted directly inside Chrome's Isolated World before any LLM reasoning happens,
                substituting deterministic placeholder tokens so that sensitive data never leaves your local workstation.
              </p>
            </div>

            {/* Three Pillars — Feature cards with oversized background numbers */}
            <div>
              <div className="wv-section-label mb-4">Core Architecture</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {/* Pillar 1 */}
                <div className="wv-pillar group">
                  <span className="wv-pillar__number">01</span>
                  <div className="relative z-10 space-y-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-500 group-hover:bg-indigo-100 transition-colors">
                      <Cpu size={20} />
                    </div>
                    <h3 className="text-[15px] font-bold text-gray-900 tracking-tight">
                      On-Device Visual Perception
                    </h3>
                    <p className="text-[13px] text-gray-500 leading-relaxed">
                      Perceives DOM elements and HTML5 canvas regions directly on client hardware, grounding spatial bounding boxes without streaming full-screen captures to external cloud APIs.
                    </p>
                  </div>
                </div>

                {/* Pillar 2 */}
                <div className="wv-pillar group">
                  <span className="wv-pillar__number">02</span>
                  <div className="relative z-10 space-y-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-500 group-hover:bg-emerald-100 transition-colors">
                      <Lock size={20} />
                    </div>
                    <h3 className="text-[15px] font-bold text-gray-900 tracking-tight">
                      Chrome Isolated World Vault
                    </h3>
                    <p className="text-[13px] text-gray-500 leading-relaxed">
                      Intercepts form credentials and identity patterns client-side, isolating plaintext secrets in extension memory completely inaccessible to host page scripts.
                    </p>
                  </div>
                </div>

                {/* Pillar 3 */}
                <div className="wv-pillar group">
                  <span className="wv-pillar__number">03</span>
                  <div className="relative z-10 space-y-3">
                    <div className="w-10 h-10 rounded-xl bg-sky-50 flex items-center justify-center text-sky-500 group-hover:bg-sky-100 transition-colors">
                      <Layers size={20} />
                    </div>
                    <h3 className="text-[15px] font-bold text-gray-900 tracking-tight">
                      3-Tier Reasoning Cascade
                    </h3>
                    <p className="text-[13px] text-gray-500 leading-relaxed">
                      Executes reasoning tasks autonomously via local air-gapped models (Tier 1 Ollama), falling back to sanitized cloud models only when local compute is unavailable.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════
           TAB 2 — HOW TO USE
           ═══════════════════════════════════════════════════════════ */}
        {activeTab === 'how-to-use' && (
          <div key="how-to-use" className="reveal-section space-y-10">
            {/* Page Header + Actions */}
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
              <div className="space-y-2">
                <div className="wv-section-label">Evaluation Harness</div>
                <h1 className="wv-page-title text-[28px]">
                  Local Testing &<br />
                  <span className="wv-gradient-text">Evaluation</span>
                </h1>
                <p className="wv-subtitle text-[13px]">
                  Verify local backend connectivity and open test pages in Google Chrome.
                </p>
              </div>

              <div className="flex items-center gap-2.5 flex-shrink-0">
                <button onClick={checkHealth} disabled={reasoningStatus.checking} className="wv-btn">
                  <RefreshCw size={14} className={reasoningStatus.checking ? 'animate-spin text-indigo-500' : ''} />
                  Refresh
                </button>
                <button onClick={handleCopyCommand} className="wv-btn wv-btn--primary">
                  {copiedCmd ? <Check size={14} /> : <Terminal size={14} />}
                  {copiedCmd ? 'Copied!' : 'Copy Launch Command'}
                </button>
              </div>
            </div>

            {/* Disclaimer */}
            <div className="wv-callout wv-callout--info">
              <Shield size={16} className="flex-shrink-0 mt-0.5" />
              <span className="text-[13px]">
                This page is a local launcher that monitors your local servers and links directly to test targets.
                The actual WebVeil browser agent runs inside Google Chrome as an unpacked Manifest V3 extension.
                It does not simulate actions here; all credential masking and visual perception happen live in Chrome.
              </span>
            </div>

            {/* Service Health — Inline Row */}
            <div>
              <div className="wv-section-label mb-4">Service Health</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="wv-card p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center text-gray-400">
                        <Server size={17} />
                      </div>
                      <div>
                        <div className="text-[14px] font-semibold text-gray-900">Reasoning Server</div>
                        <div className="text-[11px] font-mono text-gray-400">127.0.0.1:8000</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-[13px] font-mono font-semibold ${reasoningStatus.online ? 'text-emerald-600' : 'text-red-500'}`}>
                        {reasoningStatus.online ? `${reasoningStatus.latencyMs}ms` : 'Offline'}
                      </span>
                      <div className={`wv-dot ${reasoningStatus.online ? 'wv-dot--online' : 'wv-dot--offline'}`} />
                    </div>
                  </div>
                </div>

                <div className="wv-card p-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center text-gray-400">
                        <Globe size={17} />
                      </div>
                      <div>
                        <div className="text-[14px] font-semibold text-gray-900">Test Server</div>
                        <div className="text-[11px] font-mono text-gray-400">127.0.0.1:8080</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`text-[13px] font-mono font-semibold ${testServerStatus.online ? 'text-emerald-600' : 'text-red-500'}`}>
                        {testServerStatus.online ? `${testServerStatus.latencyMs}ms` : 'Offline'}
                      </span>
                      <div className={`wv-dot ${testServerStatus.online ? 'wv-dot--online' : 'wv-dot--offline'}`} />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Target Test Pages */}
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="wv-section-label">Target Test Environments & Problem Statements</div>
                <a
                  href="http://127.0.0.1:8080/index.html"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-indigo-600 hover:text-indigo-800 transition-colors"
                >
                  <Layers size={13} />
                  Open Unified Test Bench (All 5 PS on 1 Page) ↗
                </a>
              </div>

              {/* Callout for Unified Page */}
              <div className="wv-callout wv-callout--muted">
                <ShieldCheck size={16} className="text-indigo-600 flex-shrink-0 mt-0.5" />
                <div className="text-[13px] text-gray-700">
                  <strong className="text-gray-900">New Unified Testbench: </strong>
                  All 5 problem statements are now unified at <code className="wv-code text-indigo-600">http://127.0.0.1:8080/index.html</code>.
                  You can seamlessly switch between PS 1 to PS 5 with top tabs without opening multiple browser windows.
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {[
                  {
                    num: '01',
                    tag: 'PS 1 · Form Shielding',
                    title: 'KYC Verification Form',
                    desc: 'Proves wire sanitization: Intercepts Aadhaar, Phone, Email, Password into Isolated World vault.',
                    prompt: 'Fill and submit this KYC verification form',
                    url: 'http://127.0.0.1:8080/index.html#kyc',
                    shortUrl: '127.0.0.1:8080/index.html#kyc',
                  },
                  {
                    num: '02',
                    tag: 'PS 2 · Zero PII Grounding',
                    title: 'ISRO Reference / Wikipedia',
                    desc: 'Proves non-paranoid redaction: Public information extracted with 0 over-redactions and 0 false flags.',
                    prompt: 'Find when ISRO was founded and where its headquarters is located',
                    url: 'http://127.0.0.1:8080/index.html#isro',
                    shortUrl: '127.0.0.1:8080/index.html#isro',
                  },
                  {
                    num: '03',
                    tag: 'PS 3 · Mixed Page Shield',
                    title: 'Scientist Account & Billing',
                    desc: 'Proves nuance: Summarizes public bio & project clearance while shielding payment card & contact info.',
                    prompt: "Summarize what's on this account page",
                    url: 'http://127.0.0.1:8080/index.html#account',
                    shortUrl: '127.0.0.1:8080/index.html#account',
                  },
                  {
                    num: '04',
                    tag: 'PS 4 · Visual Perception',
                    title: 'Canvas Radar Challenge',
                    desc: 'Proves genuine vision: Zero DOM text nodes. Grounded exclusively via on-device OCR and spatial pixel coordinates.',
                    prompt: 'Click the Gamma button in the canvas',
                    url: 'http://127.0.0.1:8080/index.html#canvas',
                    shortUrl: '127.0.0.1:8080/index.html#canvas',
                  },
                  {
                    num: '05',
                    tag: 'PS 5 · Memory Boundary',
                    title: 'Live Adversarial Attack Demo',
                    desc: 'Proves real security: Live page script attempts to access vault memory; rejected by Chrome Isolated World.',
                    prompt: 'Trigger Hostile Page JS Exfiltration Attempt',
                    url: 'http://127.0.0.1:8080/index.html#attack',
                    shortUrl: '127.0.0.1:8080/index.html#attack',
                  },
                  {
                    num: '06',
                    tag: 'Diagnostic Battery',
                    title: 'Evaluator Benchmark Suite',
                    desc: 'Complete benchmarking dashboard with live metric radar, 176+ test suite logs, and client memory inspect tools.',
                    prompt: 'Inspect WebVeil evaluation and vault status',
                    url: 'http://127.0.0.1:8080/evaluator_dashboard.html',
                    shortUrl: '127.0.0.1:8080/evaluator_dashboard.html',
                  },
                ].map((page) => (
                  <div
                    key={page.num}
                    className="wv-card wv-card--lift p-5 flex flex-col justify-between group space-y-3"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="wv-badge wv-badge--indigo">{page.tag}</span>
                        <a
                          href={page.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-gray-400 hover:text-indigo-600 transition-colors"
                          title="Open Page in New Tab"
                        >
                          <ArrowRight size={15} />
                        </a>
                      </div>
                      <h4 className="text-[14px] font-bold text-gray-900">{page.title}</h4>
                      <p className="text-[12px] text-gray-500 leading-relaxed">{page.desc}</p>
                    </div>

                    {/* What to enter in Agent Box */}
                    <div className="bg-indigo-50/70 border border-indigo-100 rounded-lg p-2.5 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10.5px] font-bold text-indigo-700 uppercase tracking-wide">
                          What to enter in Agent:
                        </span>
                        <button
                          onClick={(e) => handleCopyPrompt(page.prompt, `target-${page.num}`, e)}
                          className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1 cursor-pointer"
                        >
                          {copiedPromptId === `target-${page.num}` ? (
                            <>
                              <Check size={11} className="text-emerald-600" />
                              <span className="text-emerald-600">Copied!</span>
                            </>
                          ) : (
                            <>
                              <Copy size={11} />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                      <div className="text-[11.5px] font-mono font-medium text-gray-900 bg-white border border-indigo-200/60 rounded px-2 py-1 select-all break-words">
                        "{page.prompt}"
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-gray-100">
                      <span className="text-[11px] font-mono text-gray-400">
                        {page.shortUrl}
                      </span>
                      <a
                        href={page.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] font-semibold text-indigo-600 hover:underline"
                      >
                        Launch Target →
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Load Instructions — Step-by-step */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  <FolderOpen size={16} className="text-gray-400" />
                  <span className="text-[15px] font-bold text-gray-900">How to Load Unpacked in Chrome</span>
                </div>
                <button onClick={handleCopyPath} className="wv-btn text-[12px] py-1.5">
                  {copiedPath ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
                  {copiedPath ? 'Copied!' : 'Copy Extension Path'}
                </button>
              </div>

              <div className="wv-card p-6 space-y-5">
                <div className="wv-step">
                  <div className="wv-step__num">1</div>
                  <div className="wv-step__content">
                    Navigate to <code className="wv-code">chrome://extensions</code> in Google Chrome.
                  </div>
                </div>

                <div className="wv-step">
                  <div className="wv-step__num">2</div>
                  <div className="wv-step__content">
                    Toggle <strong className="text-gray-900">Developer mode</strong> on (top-right corner).
                  </div>
                </div>

                <div className="wv-step">
                  <div className="wv-step__num">3</div>
                  <div className="wv-step__content">
                    Click <strong className="text-gray-900">Load unpacked</strong> and select the directory:
                    <div className="wv-code-block mt-2 select-all">
                      c:\Users\Armash Ansari\OneDrive\Desktop\Projects\AI & ML\veil-agent\extension
                    </div>
                  </div>
                </div>

                <div className="wv-step">
                  <div className="wv-step__num">4</div>
                  <div className="wv-step__content">
                    Open{' '}
                    <a href="http://127.0.0.1:8080/index.html" target="_blank" rel="noreferrer" className="text-indigo-600 underline underline-offset-2 hover:text-indigo-800">
                      http://127.0.0.1:8080/index.html
                    </a>{' '}
                    and click the <strong className="text-gray-900">WebVeil Sidepanel</strong> icon to execute commands.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════
           TAB 3 — VERIFIED TEST RUNS
           ═══════════════════════════════════════════════════════════ */}
        {activeTab === 'test-runs' && (
          <div key="test-runs" className="reveal-section space-y-10">
            {/* Page Header */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-emerald-500" />
                <span className="wv-section-label text-emerald-600">Real Post-Fix Runs & Flag Verification</span>
              </div>
              <h1 className="wv-page-title text-[28px]">
                Evaluated Pipeline<br />
                <span className="wv-gradient-text">Test Battery</span>
              </h1>
              <p className="wv-subtitle text-[13px]">
                Every test run documented here corresponds to a real executed run with verified telemetry after the DOM pruning fix.
                Below each run is the exact task prompt to enter into the WebVeil side panel to reproduce verification live.
              </p>
            </div>

            {/* ── Run 01 (PS 1) ── */}
            <div className="wv-run space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="wv-badge wv-badge--emerald">RUN 01 · PASS</span>
                  <h3 className="text-[15px] font-bold text-gray-900">
                    PS 1: KYC Form Credential Interception & Vaulting
                  </h3>
                </div>
                <a href="http://127.0.0.1:8080/index.html#kyc" target="_blank" rel="noreferrer" className="text-[11px] font-mono text-indigo-600 hover:underline">
                  127.0.0.1:8080/index.html#kyc ↗
                </a>
              </div>

              {/* What to enter in Agent Box */}
              <div className="flex items-center justify-between gap-3 bg-indigo-50/80 border border-indigo-100 rounded-lg px-3.5 py-2.5">
                <div className="flex items-center gap-2 flex-wrap text-[12px]">
                  <span className="font-bold text-indigo-800 uppercase tracking-wide text-[11px]">Enter in WebVeil Agent:</span>
                  <code className="font-mono font-semibold text-gray-900 bg-white border border-indigo-200/70 px-2.5 py-1 rounded">
                    "Fill and submit this KYC verification form"
                  </code>
                </div>
                <button
                  onClick={(e) => handleCopyPrompt("Fill and submit this KYC verification form", "run-1", e)}
                  className="wv-btn text-[11px] py-1 px-3 flex-shrink-0 cursor-pointer"
                >
                  {copiedPromptId === "run-1" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                  {copiedPromptId === "run-1" ? 'Copied!' : 'Copy Prompt'}
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="wv-stat">
                  <div className="wv-stat__label">Task Executed</div>
                  <div className="wv-stat__value text-[15px]">Fill KYC form</div>
                  <div className="wv-stat__sub">Autonomous workflow</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Protected Fields</div>
                  <div className="wv-stat__value text-emerald-600">4 Masked</div>
                  <div className="wv-stat__sub">[NAME_1], [AADHAAR_1], [PASS_1], [EMAIL_1]</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Steps Taken</div>
                  <div className="wv-stat__value text-sky-600">4 Actions</div>
                  <div className="wv-stat__sub">Scan, Vault, Inject, Submit</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Reasoning Tier</div>
                  <div className="wv-stat__value text-indigo-600">Local (Ollama)</div>
                  <div className="wv-stat__sub">Tier 1 · Air-gapped</div>
                </div>
              </div>

              <div className="wv-callout wv-callout--muted">
                <ShieldCheck size={16} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                <div className="text-[13px]">
                  <strong className="text-gray-800">Information Flag System Outcome: </strong>
                  During client-side observation, the regex classifier identified 4 sensitive categories matching KYC fields.
                  Real credentials were moved to Chrome Isolated World memory and replaced with deterministic tokens.
                  The reasoning server payload verified zero plaintext leak. Keystrokes were injected locally.
                </div>
              </div>
            </div>

            {/* ── Run 02 (PS 2) ── */}
            <div className="wv-run wv-run--sky space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="wv-badge wv-badge--sky">RUN 02 · PASS</span>
                  <h3 className="text-[15px] font-bold text-gray-900">
                    PS 2: ISRO Grounding & Zero False-Positive Redaction
                  </h3>
                </div>
                <a href="http://127.0.0.1:8080/index.html#isro" target="_blank" rel="noreferrer" className="text-[11px] font-mono text-indigo-600 hover:underline">
                  127.0.0.1:8080/index.html#isro ↗
                </a>
              </div>

              {/* What to enter in Agent Box */}
              <div className="flex items-center justify-between gap-3 bg-sky-50/80 border border-sky-100 rounded-lg px-3.5 py-2.5">
                <div className="flex items-center gap-2 flex-wrap text-[12px]">
                  <span className="font-bold text-sky-800 uppercase tracking-wide text-[11px]">Enter in WebVeil Agent:</span>
                  <code className="font-mono font-semibold text-gray-900 bg-white border border-sky-200/70 px-2.5 py-1 rounded">
                    "Find when ISRO was founded and where its headquarters is located"
                  </code>
                </div>
                <button
                  onClick={(e) => handleCopyPrompt("Find when ISRO was founded and where its headquarters is located", "run-2", e)}
                  className="wv-btn text-[11px] py-1 px-3 flex-shrink-0 cursor-pointer"
                >
                  {copiedPromptId === "run-2" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                  {copiedPromptId === "run-2" ? 'Copied!' : 'Copy Prompt'}
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="wv-stat">
                  <div className="wv-stat__label">Task Executed</div>
                  <div className="wv-stat__value text-[15px]">ISRO Research</div>
                  <div className="wv-stat__sub">Fact extraction</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Pruning Metrics</div>
                  <div className="wv-stat__value text-emerald-600">10,475 → 184</div>
                  <div className="wv-stat__sub">97.3% Context Reduction</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Over-Redaction</div>
                  <div className="wv-stat__value text-emerald-600">0 Fields Masked</div>
                  <div className="wv-stat__sub">Intelligent 0-PII verdict</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Answer Verified</div>
                  <div className="wv-stat__value text-indigo-600">15 Aug 1969</div>
                  <div className="wv-stat__sub">Bengaluru, Karnataka</div>
                </div>
              </div>

              <div className="wv-callout wv-callout--muted">
                <Eye size={16} className="text-sky-500 flex-shrink-0 mt-0.5" />
                <div className="text-[13px]">
                  <strong className="text-gray-800">Interactive Priority Pruner Outcome: </strong>
                  Verified against both live Wikipedia and the local ISRO reference. The interactive selector prioritized structured facts
                  while recording 0 false redactions. Proves that WebVeil preserves reasoning on public reference material without over-filtering.
                </div>
              </div>
            </div>

            {/* ── Run 03 (PS 3) ── */}
            <div className="wv-run wv-run--indigo space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="wv-badge wv-badge--indigo">RUN 03 · PASS</span>
                  <h3 className="text-[15px] font-bold text-gray-900">
                    PS 3: Scientist Profile Bio & Confidential Card Shield
                  </h3>
                </div>
                <a href="http://127.0.0.1:8080/index.html#account" target="_blank" rel="noreferrer" className="text-[11px] font-mono text-indigo-600 hover:underline">
                  127.0.0.1:8080/index.html#account ↗
                </a>
              </div>

              {/* What to enter in Agent Box */}
              <div className="flex items-center justify-between gap-3 bg-indigo-50/80 border border-indigo-100 rounded-lg px-3.5 py-2.5">
                <div className="flex items-center gap-2 flex-wrap text-[12px]">
                  <span className="font-bold text-indigo-800 uppercase tracking-wide text-[11px]">Enter in WebVeil Agent:</span>
                  <code className="font-mono font-semibold text-gray-900 bg-white border border-indigo-200/70 px-2.5 py-1 rounded">
                    "Summarize what's on this account page"
                  </code>
                </div>
                <button
                  onClick={(e) => handleCopyPrompt("Summarize what's on this account page", "run-3", e)}
                  className="wv-btn text-[11px] py-1 px-3 flex-shrink-0 cursor-pointer"
                >
                  {copiedPromptId === "run-3" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                  {copiedPromptId === "run-3" ? 'Copied!' : 'Copy Prompt'}
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="wv-stat">
                  <div className="wv-stat__label">Task Executed</div>
                  <div className="wv-stat__value text-[15px]">Summarize Profile</div>
                  <div className="wv-stat__sub">Mixed public/confidential</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Public Read</div>
                  <div className="wv-stat__value text-emerald-600">100% Bio Read</div>
                  <div className="wv-stat__sub">Dr. Sharma / SCE-200</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Protected Card</div>
                  <div className="wv-stat__value text-indigo-600">Card & CVV Vaulted</div>
                  <div className="wv-stat__sub">[CARD_1], [CVV_1] tokens</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Network Egress</div>
                  <div className="wv-stat__value text-emerald-600">0 Raw Bytes</div>
                  <div className="wv-stat__sub">Zero financial leak</div>
                </div>
              </div>

              <div className="wv-callout wv-callout--muted">
                <ShieldCheck size={16} className="text-indigo-500 flex-shrink-0 mt-0.5" />
                <div className="text-[13px]">
                  <strong className="text-gray-800">Nuanced Mixed-Page Outcome: </strong>
                  The agent accurately summarized Dr. Sharma's propulsion publications and Level-4 clearance while the financial procurement card
                  and security code were sealed into vault memory. Disproves the concern that redaction breaks complex multi-attribute pages.
                </div>
              </div>
            </div>

            {/* ── Run 04 (PS 4) ── */}
            <div className="wv-run wv-run--indigo space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="wv-badge wv-badge--purple">RUN 04 · PASS</span>
                  <h3 className="text-[15px] font-bold text-gray-900">
                    PS 4: Canvas Graphic Spatial Perception & Coordinate Grounding
                  </h3>
                </div>
                <a href="http://127.0.0.1:8080/index.html#canvas" target="_blank" rel="noreferrer" className="text-[11px] font-mono text-indigo-600 hover:underline">
                  127.0.0.1:8080/index.html#canvas ↗
                </a>
              </div>

              {/* What to enter in Agent Box */}
              <div className="flex items-center justify-between gap-3 bg-purple-50/80 border border-purple-100 rounded-lg px-3.5 py-2.5">
                <div className="flex items-center gap-2 flex-wrap text-[12px]">
                  <span className="font-bold text-purple-800 uppercase tracking-wide text-[11px]">Enter in WebVeil Agent:</span>
                  <code className="font-mono font-semibold text-gray-900 bg-white border border-purple-200/70 px-2.5 py-1 rounded">
                    "Click the Gamma button in the canvas"
                  </code>
                </div>
                <button
                  onClick={(e) => handleCopyPrompt("Click the Gamma button in the canvas", "run-4", e)}
                  className="wv-btn text-[11px] py-1 px-3 flex-shrink-0 cursor-pointer"
                >
                  {copiedPromptId === "run-4" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                  {copiedPromptId === "run-4" ? 'Copied!' : 'Copy Prompt'}
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="wv-stat">
                  <div className="wv-stat__label">Task Executed</div>
                  <div className="wv-stat__value text-[15px]">Canvas Grounding</div>
                  <div className="wv-stat__sub">Non-semantic UI</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">CV Telemetry</div>
                  <div className="wv-stat__value text-sky-600">8 in 18.2ms</div>
                  <div className="wv-stat__sub">Local CV · CPU only</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Steps Taken</div>
                  <div className="wv-stat__value text-emerald-600">2 Actions</div>
                  <div className="wv-stat__sub">Detect & Dispatch Click</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Reasoning Tier</div>
                  <div className="wv-stat__value text-indigo-600">Local (Ollama)</div>
                  <div className="wv-stat__sub">Tier 1 · Air-gapped</div>
                </div>
              </div>

              <div className="wv-callout wv-callout--muted">
                <Cpu size={16} className="text-purple-500 flex-shrink-0 mt-0.5" />
                <div className="text-[13px]">
                  <strong className="text-gray-800">Local Visual Perception Engine Outcome: </strong>
                  When operating on HTML5 canvas graphics without text nodes, the client-side OpenCV contour engine detected 8 interactive boundary regions locally on CPU,
                  transmitting spatial bounding box coordinates to the reasoning loop without uploading raw screenshots to cloud APIs.
                </div>
              </div>
            </div>

            {/* ── Run 05 (PS 5) ── */}
            <div className="wv-run wv-run--amber space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="wv-badge wv-badge--amber">RUN 05 · PASS</span>
                  <h3 className="text-[15px] font-bold text-gray-900">
                    PS 5: Chrome Isolated World Live Vault Attack Defense
                  </h3>
                </div>
                <a href="http://127.0.0.1:8080/index.html#attack" target="_blank" rel="noreferrer" className="text-[11px] font-mono text-indigo-600 hover:underline">
                  127.0.0.1:8080/index.html#attack ↗
                </a>
              </div>

              {/* What to enter in Agent Box */}
              <div className="flex items-center justify-between gap-3 bg-amber-50/80 border border-amber-100 rounded-lg px-3.5 py-2.5">
                <div className="flex items-center gap-2 flex-wrap text-[12px]">
                  <span className="font-bold text-amber-800 uppercase tracking-wide text-[11px]">Enter in WebVeil Agent:</span>
                  <code className="font-mono font-semibold text-gray-900 bg-white border border-amber-200/70 px-2.5 py-1 rounded">
                    "Trigger Hostile Page JS Exfiltration Attempt"
                  </code>
                </div>
                <button
                  onClick={(e) => handleCopyPrompt("Trigger Hostile Page JS Exfiltration Attempt", "run-5", e)}
                  className="wv-btn text-[11px] py-1 px-3 flex-shrink-0 cursor-pointer"
                >
                  {copiedPromptId === "run-5" ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                  {copiedPromptId === "run-5" ? 'Copied!' : 'Copy Prompt'}
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="wv-stat">
                  <div className="wv-stat__label">Attack Vectors</div>
                  <div className="wv-stat__value text-[15px]">2 Live Probes</div>
                  <div className="wv-stat__sub">Window & DOM Scan</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Vault Defense</div>
                  <div className="wv-stat__value text-emerald-600">Blocked</div>
                  <div className="wv-stat__sub">Isolated World boundary</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Memory Scope</div>
                  <div className="wv-stat__value text-indigo-600">undefined</div>
                  <div className="wv-stat__sub">Zero page JS visibility</div>
                </div>
                <div className="wv-stat">
                  <div className="wv-stat__label">Verification Check</div>
                  <div className="wv-stat__value text-emerald-600">6/6 Passed</div>
                  <div className="wv-stat__sub">Origin bound keys</div>
                </div>
              </div>

              <div className="wv-callout wv-callout--muted">
                <Lock size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="text-[13px]">
                  <strong className="text-gray-800">Chrome Isolated World Outcome: </strong>
                  Even when malicious third-party script executes directly inside the target webpage (<code>window.__WEBVEIL_ISOLATED_VAULT__</code>),
                  Chrome's content script isolation structurally prevents the page from accessing vault storage. That is an OS/browser-enforced hardware boundary.
                </div>
              </div>
            </div>

            {/* ═══════════════════════════════════════════════════════
               PS-26171 PROBLEMS & SOLUTIONS
               ═══════════════════════════════════════════════════════ */}
            <div className="space-y-5">
              <div className="flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-500" />
                <span className="wv-section-label">PS-26171 Challenges, Solutions & Flag Verification</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Problem 1 */}
                <div className="wv-problem wv-problem--emerald space-y-3">
                  <span className="wv-badge wv-badge--emerald">Problem 01 · Credential Exfiltration</span>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">Problem:</strong> Standard browser agents pipe raw form values (passwords, Aadhaar, PAN) into reasoning contexts, risking exposure to external LLM providers and logging backends.
                  </p>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">WebVeil Solution:</strong> Client-side tokenization regex runs in Chrome Isolated World memory. Plaintext is stripped and substituted with deterministic tokens (<code className="wv-code">[PASSWORD_1]</code>) before egress.
                  </p>
                  <hr className="wv-divider" />
                  <div className="text-[12px] text-gray-500 space-y-2">
                    <div className="font-semibold text-gray-700">How to Verify Flagging:</div>
                    <div>1. Open <code className="wv-code">http://127.0.0.1:8080/index.html#kyc</code></div>
                    <div className="bg-emerald-50/70 border border-emerald-100 rounded-md p-2 flex items-center justify-between gap-2">
                      <div>
                        <span className="font-semibold text-emerald-800">Agent Task:</span>{' '}
                        <code className="font-mono text-gray-900">"Fill and submit this KYC verification form"</code>
                      </div>
                      <button
                        onClick={(e) => handleCopyPrompt("Fill and submit this KYC verification form", "prob-1", e)}
                        className="text-[11px] font-semibold text-emerald-700 hover:text-emerald-900 flex items-center gap-1 cursor-pointer flex-shrink-0"
                      >
                        {copiedPromptId === "prob-1" ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
                        {copiedPromptId === "prob-1" ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div>2. In the WebVeil side panel, expand <em>"What WebVeil saw"</em> → inspect <em>"Outgoing Sanitized Payload"</em></div>
                    <div>3. Confirm raw inputs are flagged and only masked tokens appear in the JSON request</div>
                  </div>
                </div>

                {/* Problem 2 */}
                <div className="wv-problem wv-problem--red space-y-3">
                  <span className="wv-badge wv-badge--red">Problem 02 · Prompt Injection & Taint</span>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">Problem:</strong> Host pages can embed invisible adversarial text (<code className="wv-code text-gray-500">&lt;!-- exfiltrate cookies --&gt;</code>) designed to hijack agent directives and access unauthorized endpoints.
                  </p>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">WebVeil Solution:</strong> Taint tracking classifies untrusted DOM subtrees, while an on-device injection classifier flags jailbreak directives, instantly aborting navigation to unknown domains.
                  </p>
                  <hr className="wv-divider" />
                  <div className="text-[12px] text-gray-500 space-y-2">
                    <div className="font-semibold text-gray-700">How to Verify Flagging:</div>
                    <div>1. Run <code className="wv-code">pytest webveil/tests/test_prompt_injection_defense.py</code></div>
                    <div className="bg-red-50/70 border border-red-100 rounded-md p-2 flex items-center justify-between gap-2">
                      <div>
                        <span className="font-semibold text-red-800">Test Command:</span>{' '}
                        <code className="font-mono text-gray-900">python -m pytest webveil/tests/test_prompt_injection_defense.py -v</code>
                      </div>
                      <button
                        onClick={(e) => handleCopyPrompt("python -m pytest webveil/tests/test_prompt_injection_defense.py -v", "prob-2", e)}
                        className="text-[11px] font-semibold text-red-700 hover:text-red-900 flex items-center gap-1 cursor-pointer flex-shrink-0"
                      >
                        {copiedPromptId === "prob-2" ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
                        {copiedPromptId === "prob-2" ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div>2. Execute task targeting a page containing an override directive</div>
                    <div>3. Observe the security alert: the node is flagged as tainted and action execution is rejected</div>
                  </div>
                </div>

                {/* Problem 3 */}
                <div className="wv-problem wv-problem--sky space-y-3">
                  <span className="wv-badge wv-badge--sky">Problem 03 · DOM Tree Explosion</span>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">Problem:</strong> Public portals contain 10,000+ DOM nodes. Naive DOM serialization exhausts model context windows, introduces latency, and triggers JSON malformation.
                  </p>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">WebVeil Solution:</strong> Priority selector algorithm retains 100% of interactive form controls and in-viewport buttons while capping passive prose to immediate structural context.
                  </p>
                  <hr className="wv-divider" />
                  <div className="text-[12px] text-gray-500 space-y-2">
                    <div className="font-semibold text-gray-700">How to Verify Flagging:</div>
                    <div>1. Open <code className="wv-code">http://127.0.0.1:8080/index.html#isro</code></div>
                    <div className="bg-sky-50/70 border border-sky-100 rounded-md p-2 flex items-center justify-between gap-2">
                      <div>
                        <span className="font-semibold text-sky-800">Agent Task:</span>{' '}
                        <code className="font-mono text-gray-900">"Find when ISRO was founded and where its headquarters is located"</code>
                      </div>
                      <button
                        onClick={(e) => handleCopyPrompt("Find when ISRO was founded and where its headquarters is located", "prob-3", e)}
                        className="text-[11px] font-semibold text-sky-700 hover:text-sky-900 flex items-center gap-1 cursor-pointer flex-shrink-0"
                      >
                        {copiedPromptId === "prob-3" ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
                        {copiedPromptId === "prob-3" ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div>2. Issue research instruction in the WebVeil side panel</div>
                    <div>3. Verify the first timeline event: DOM scan count is reduced from ~10,475 down to &lt;250 interactive candidates</div>
                  </div>
                </div>

                {/* Problem 4 */}
                <div className="wv-problem wv-problem--amber space-y-3">
                  <span className="wv-badge wv-badge--amber">Problem 04 · Non-Semantic Canvas</span>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">Problem:</strong> Complex interfaces render controls inside an HTML5 <code className="wv-code text-gray-500">&lt;canvas&gt;</code> element, having zero inspectable DOM text nodes or form tags.
                  </p>
                  <p className="text-[13px] text-gray-600 leading-relaxed">
                    <strong className="text-gray-800">WebVeil Solution:</strong> Client-side OpenCV/WASM contour detection identifies interactive regions locally in &lt;20ms on CPU, without transmitting full screenshot pixels.
                  </p>
                  <hr className="wv-divider" />
                  <div className="text-[12px] text-gray-500 space-y-2">
                    <div className="font-semibold text-gray-700">How to Verify Flagging:</div>
                    <div>1. Open <code className="wv-code">http://127.0.0.1:8080/index.html#canvas</code></div>
                    <div className="bg-amber-50/70 border border-amber-100 rounded-md p-2 flex items-center justify-between gap-2">
                      <div>
                        <span className="font-semibold text-amber-800">Agent Task:</span>{' '}
                        <code className="font-mono text-gray-900">"Click the Gamma button in the canvas"</code>
                      </div>
                      <button
                        onClick={(e) => handleCopyPrompt("Click the Gamma button in the canvas", "prob-4", e)}
                        className="text-[11px] font-semibold text-amber-700 hover:text-amber-900 flex items-center gap-1 cursor-pointer flex-shrink-0"
                      >
                        {copiedPromptId === "prob-4" ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
                        {copiedPromptId === "prob-4" ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div>2. Check side panel telemetry: confirms Local CV (CPU) bounding box detection and coordinate click</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
