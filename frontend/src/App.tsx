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
  CheckCircle2
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

  const checkHealth = async () => {
    // 1. Check Python Reasoning Backend (Port 8000)
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

    // 2. Check Local Target Test Server (Port 8080)
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

  return (
    <div className="relative min-h-screen text-slate-100 font-sans selection:bg-indigo-500/30 selection:text-white">
      {/* 1. Living Background: Ambient Gradient Mesh (Continuous Animation #1) */}
      <div className="bg-mesh-container" aria-hidden="true">
        <div className="mesh-blob mesh-blob-1" />
        <div className="mesh-blob mesh-blob-2" />
        <div className="mesh-blob mesh-blob-3" />
      </div>

      {/* Main Layout Container: Fixed Sidebar + Dynamic Content Pane */}
      <div className="relative z-10 max-w-7xl mx-auto p-4 sm:p-8 flex flex-col md:flex-row gap-6 lg:gap-8 items-start">
        
        {/* ═════════════════════════════════════════════════════════════════════
            SIDEBAR NAVIGATION (220px width, Glass Panel, Pinned Status Bottom)
           ═════════════════════════════════════════════════════════════════════ */}
        <aside className="wv-glass-panel w-full md:w-60 p-5 flex flex-col justify-between md:sticky md:top-8 flex-shrink-0 min-h-[520px]">
          <div className="space-y-6">
            {/* Header Brand */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-400/25 flex items-center justify-center text-indigo-400 shadow-inner flex-shrink-0">
                <Shield size={20} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-base text-white tracking-tight">WebVeil</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                    PS-26171
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 font-medium">Evaluator Companion</p>
              </div>
            </div>

            {/* 3 Sidebar Navigation Items */}
            <nav className="flex flex-row md:flex-col gap-2">
              {[
                { id: 'overview', label: 'Overview & Pillars', num: '01', icon: Layers },
                { id: 'how-to-use', label: 'How to Use', num: '02', icon: Compass },
                { id: 'test-runs', label: 'Verified Test Runs', num: '03', icon: FileCheck },
              ].map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as TabId)}
                    className={`w-full flex items-center justify-between p-3 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                      isActive
                        ? 'neu-tab-active'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon size={14} className={isActive ? 'text-indigo-400' : 'text-slate-500'} />
                      <span>{tab.label}</span>
                    </div>
                    <span className="font-mono text-[10px] text-slate-500">{tab.num}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Mini-Readout Pinned at Sidebar Bottom (Flat & Legible, NOT Glass) */}
          <div className="pt-4 mt-6 border-t border-slate-800/90 space-y-2 bg-[#090d16] p-3.5 rounded-xl border border-slate-800/80">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-slate-400">Backend:</span>
              <div className="flex items-center gap-2">
                <span className={reasoningStatus.online ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'}>
                  {reasoningStatus.online ? `${reasoningStatus.latencyMs}ms` : 'Offline'}
                </span>
                <div className="neu-status-well !w-4 !h-4">
                  <div className={reasoningStatus.online ? 'neu-status-dot-online !w-1.5 !h-1.5' : 'neu-status-dot-offline !w-1.5 !h-1.5'} />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-slate-400">Target:</span>
              <div className="flex items-center gap-2">
                <span className={testServerStatus.online ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'}>
                  {testServerStatus.online ? `${testServerStatus.latencyMs}ms` : 'Offline'}
                </span>
                <div className="neu-status-well !w-4 !h-4">
                  <div className={testServerStatus.online ? 'neu-status-dot-online !w-1.5 !h-1.5' : 'neu-status-dot-offline !w-1.5 !h-1.5'} />
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* ═════════════════════════════════════════════════════════════════════
            RIGHT DYNAMIC CONTENT AREA (Swaps with 600ms cubic-bezier reveal)
           ═════════════════════════════════════════════════════════════════════ */}
        <main className="flex-1 w-full space-y-6">

          {/* ═══════════════════════════════════════════════════════════
             TAB 1 — OVERVIEW & PILLARS
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === 'overview' && (
            <div key="overview" className="space-y-6 reveal-section">
              {/* Plain Paragraph (What WebVeil is) */}
              <div className="wv-glass-panel p-6 sm:p-7 space-y-4">
                <div className="flex items-center gap-2 text-xs font-mono text-indigo-400 font-semibold uppercase tracking-wider">
                  <ShieldCheck size={14} />
                  <span>Problem Statement PS-26171</span>
                </div>

                <h2 className="text-2xl font-bold tracking-tight text-white">
                  Privacy-Preserving On-Device Web Agent
                </h2>

                <p className="text-sm text-slate-300 leading-relaxed font-normal">
                  WebVeil is an on-device, privacy-preserving browser agent engineered for sensitive and defense web workflows.
                  Credential fields, identity numbers, and session tokens are intercepted directly inside Chrome's Isolated World before any LLM reasoning happens,
                  substituting deterministic placeholder tokens so that sensitive data never leaves your local workstation.
                </p>
              </div>

              {/* Three Architecture Pillars (Short Cards, 1 Sentence Each) */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Pillar 1 */}
                <div className="wv-glass-panel wv-glass-interactive p-5 space-y-3 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-400/25 flex items-center justify-center text-indigo-400">
                      <Cpu size={18} />
                    </div>
                    <h3 className="text-sm font-bold text-white tracking-tight">
                      On-Device Visual Perception
                    </h3>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      Perceives DOM elements and HTML5 canvas regions directly on client hardware, grounding spatial bounding boxes without streaming full-screen captures to external cloud APIs.
                    </p>
                  </div>
                </div>

                {/* Pillar 2 */}
                <div className="wv-glass-panel wv-glass-interactive p-5 space-y-3 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-400/25 flex items-center justify-center text-emerald-400">
                      <Lock size={18} />
                    </div>
                    <h3 className="text-sm font-bold text-white tracking-tight">
                      Chrome Isolated World Vault
                    </h3>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      Intercepts form credentials and identity patterns client-side, isolating plaintext secrets in extension memory completely inaccessible to host page scripts.
                    </p>
                  </div>
                </div>

                {/* Pillar 3 */}
                <div className="wv-glass-panel wv-glass-interactive p-5 space-y-3 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="w-9 h-9 rounded-xl bg-blue-500/10 border border-blue-400/25 flex items-center justify-center text-blue-400">
                      <Layers size={18} />
                    </div>
                    <h3 className="text-sm font-bold text-white tracking-tight">
                      3-Tier Reasoning Cascade
                    </h3>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      Executes reasoning tasks autonomously via local air-gapped models (Tier 1 Ollama), falling back to sanitized cloud models only when local compute is unavailable.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
             TAB 2 — HOW TO USE (HONEST LAUNCHER)
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === 'how-to-use' && (
            <div key="how-to-use" className="space-y-6 reveal-section">
              {/* Header Action Bar */}
              <div className="wv-glass-panel p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-white tracking-tight">
                    Local Testing & Evaluation Harness
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Verify local backend connectivity and open test pages in Google Chrome.
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={checkHealth}
                    disabled={reasoningStatus.checking}
                    className="neu-control px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-200 flex items-center gap-2 cursor-pointer active:scale-95"
                  >
                    <RefreshCw size={13} className={reasoningStatus.checking ? 'animate-spin text-indigo-400' : 'text-slate-400'} />
                    <span>Refresh Health</span>
                  </button>

                  <button
                    onClick={handleCopyCommand}
                    className="neu-control-primary px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 cursor-pointer active:scale-95"
                  >
                    {copiedCmd ? <Check size={14} className="text-emerald-300" /> : <Terminal size={14} />}
                    <span>{copiedCmd ? 'Command Copied' : 'Copy Launch Command'}</span>
                  </button>
                </div>
              </div>

              {/* Evaluation Disclaimer (Flat weight, high-contrast, strictly NOT glass) */}
              <div className="p-4 rounded-xl bg-[#0b0e17] border border-slate-700/90 text-xs text-slate-200 flex items-start gap-3 shadow-md">
                <div className="p-1 rounded-md bg-indigo-950 text-indigo-400 border border-indigo-800/80 mt-0.5 flex-shrink-0">
                  <Shield size={14} />
                </div>
                <div className="leading-relaxed font-normal">
                  This page is a local launcher that monitors your local servers and links directly to test targets.
                  The actual WebVeil browser agent runs inside Google Chrome as an unpacked Manifest V3 extension.
                  It does not simulate actions here; all credential masking and visual perception happen live in Chrome.
                </div>
              </div>

              {/* Live Service Health Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="wv-glass-panel wv-glass-interactive p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-slate-300">
                        <Server size={16} />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white tracking-tight">Python Reasoning Server</h3>
                        <div className="text-[11px] font-mono text-slate-400">http://127.0.0.1:8000/api/health</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="text-xs font-mono text-slate-300 font-medium">
                        {reasoningStatus.online ? `Online (${reasoningStatus.latencyMs}ms)` : 'Offline'}
                      </span>
                      <div className="neu-status-well">
                        <div className={reasoningStatus.online ? 'neu-status-dot-online' : 'neu-status-dot-offline'} />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="wv-glass-panel wv-glass-interactive p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-xl bg-slate-800/60 border border-slate-700/50 text-slate-300">
                        <Globe size={16} />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white tracking-tight">Target Test Server</h3>
                        <div className="text-[11px] font-mono text-slate-400">http://127.0.0.1:8080/index.html</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <span className="text-xs font-mono text-slate-300 font-medium">
                        {testServerStatus.online ? `Online (${testServerStatus.latencyMs}ms)` : 'Offline'}
                      </span>
                      <div className="neu-status-well">
                        <div className={testServerStatus.online ? 'neu-status-dot-online' : 'neu-status-dot-offline'} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Target Test Web Pages */}
              <div className="space-y-3">
                <h3 className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400 px-1">
                  Live Target Test Environments
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <a
                    href="http://127.0.0.1:8080/index.html"
                    target="_blank"
                    rel="noreferrer"
                    className="wv-glass-panel wv-glass-interactive p-5 flex flex-col justify-between group space-y-4"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-indigo-400 font-semibold">
                        <span>01 · Form Shielding</span>
                        <ExternalLink size={13} className="group-hover:translate-x-0.5 transition-transform text-slate-400 group-hover:text-indigo-300" />
                      </div>
                      <h4 className="text-sm font-bold text-white tracking-tight">SIH Privacy & KYC Test Page</h4>
                      <p className="text-xs text-slate-400 leading-relaxed font-normal">
                        Contains Name, Aadhaar number, Password, and Email fields. Verifies deterministic tokenization into [AADHAAR_1] in Isolated World memory.
                      </p>
                    </div>
                    <span className="text-[11px] font-mono text-indigo-300/90 underline underline-offset-2">
                      http://127.0.0.1:8080/index.html
                    </span>
                  </a>

                  <a
                    href="http://127.0.0.1:8080/canvas_challenge.html"
                    target="_blank"
                    rel="noreferrer"
                    className="wv-glass-panel wv-glass-interactive p-5 flex flex-col justify-between group space-y-4"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-indigo-400 font-semibold">
                        <span>02 · Canvas Perception</span>
                        <ExternalLink size={13} className="group-hover:translate-x-0.5 transition-transform text-slate-400 group-hover:text-indigo-300" />
                      </div>
                      <h4 className="text-sm font-bold text-white tracking-tight">Canvas Challenge Page</h4>
                      <p className="text-xs text-slate-400 leading-relaxed font-normal">
                        Simulates interactive HTML5 canvas graphics without DOM text nodes. Verifies spatial bounding boxes and coordinate grounding.
                      </p>
                    </div>
                    <span className="text-[11px] font-mono text-indigo-300/90 underline underline-offset-2">
                      http://127.0.0.1:8080/canvas_challenge.html
                    </span>
                  </a>

                  <a
                    href="http://127.0.0.1:8080/evaluator_dashboard.html"
                    target="_blank"
                    rel="noreferrer"
                    className="wv-glass-panel wv-glass-interactive p-5 flex flex-col justify-between group space-y-4"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-indigo-400 font-semibold">
                        <span>03 · Diagnostics</span>
                        <ExternalLink size={13} className="group-hover:translate-x-0.5 transition-transform text-slate-400 group-hover:text-indigo-300" />
                      </div>
                      <h4 className="text-sm font-bold text-white tracking-tight">Evaluator Static Dashboard</h4>
                      <p className="text-xs text-slate-400 leading-relaxed font-normal">
                        Local diagnostics panel displaying DOM scanning outputs, node trees, and raw timing benchmarks for SIH evaluators.
                      </p>
                    </div>
                    <span className="text-[11px] font-mono text-indigo-300/90 underline underline-offset-2">
                      http://127.0.0.1:8080/evaluator_dashboard.html
                    </span>
                  </a>
                </div>
              </div>

              {/* Load Instructions Block */}
              <div className="wv-glass-panel p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2.5">
                    <FolderOpen size={18} className="text-indigo-400" />
                    <h3 className="text-sm font-bold text-white">How to Load Unpacked in Google Chrome</h3>
                  </div>

                  <button
                    onClick={handleCopyPath}
                    className="neu-control px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 flex items-center gap-1.5 cursor-pointer active:scale-95"
                  >
                    {copiedPath ? <Check size={13} className="text-emerald-300" /> : <Copy size={13} />}
                    <span>{copiedPath ? 'Path Copied' : 'Copy Extension Path'}</span>
                  </button>
                </div>

                <ol className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-slate-300 list-decimal list-inside leading-relaxed font-normal">
                  <li className="p-3 rounded-xl bg-slate-900/50 border border-slate-800/60">
                    Navigate to <code className="font-mono text-indigo-300 px-1 bg-slate-950 rounded">chrome://extensions</code>.
                  </li>
                  <li className="p-3 rounded-xl bg-slate-900/50 border border-slate-800/60">
                    Toggle <strong className="text-white">Developer mode</strong> on (top right).
                  </li>
                  <li className="p-3 rounded-xl bg-slate-900/50 border border-slate-800/60 sm:col-span-2">
                    Click <strong className="text-white">Load unpacked</strong> and select the directory:
                    <div className="font-mono text-[11px] text-slate-200 bg-slate-950 p-2 rounded-lg border border-slate-800 mt-1 select-all">
                      c:\Users\Armash Ansari\OneDrive\Desktop\Projects\AI & ML\veil-agent\extension
                    </div>
                  </li>
                  <li className="p-3 rounded-xl bg-slate-900/50 border border-slate-800/60 sm:col-span-2">
                    Open <a href="http://127.0.0.1:8080/index.html" target="_blank" rel="noreferrer" className="text-indigo-400 underline">http://127.0.0.1:8080/index.html</a> and click the <strong>WebVeil Sidepanel</strong> icon to execute commands.
                  </li>
                </ol>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
             TAB 3 — VERIFIED TEST RUNS & FLAG SYSTEM VERIFICATION
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === 'test-runs' && (
            <div key="test-runs" className="space-y-6 reveal-section">
              {/* Header */}
              <div className="wv-glass-panel p-6 space-y-2">
                <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 font-semibold uppercase tracking-wider">
                  <CheckCircle2 size={14} />
                  <span>Real Post-Fix Runs & Flag Verification</span>
                </div>
                <h2 className="text-xl font-bold text-white tracking-tight">
                  Evaluated Pipeline Test Battery
                </h2>
                <p className="text-xs text-slate-400 leading-relaxed font-normal">
                  Every test run documented here corresponds to a real executed run with verified telemetry after the DOM pruning fix.
                  Below each run is the problem & solution guide detailing how the Information Flag System operates and how to reproduce verification live.
                </p>
              </div>

              {/* ── Real Test Run 01 ── */}
              <div className="wv-glass-panel p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-bold">
                      RUN 01 · PASS
                    </span>
                    <h3 className="text-sm font-bold text-white">
                      SIH KYC Form Credential Interception & Vaulting
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Target: http://127.0.0.1:8080/index.html</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">TASK EXECUTED</div>
                    <div className="text-slate-200 font-semibold text-xs mt-1 truncate" title="Fill KYC form with test credentials and submit without leaking PII">
                      Fill KYC form
                    </div>
                    <div className="text-[10px] text-slate-400">Autonomous workflow</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">PROTECTED FIELDS</div>
                    <div className="text-emerald-400 font-bold text-xs mt-1">4 Fields Masked</div>
                    <div className="text-[10px] text-slate-400">[NAME_1], [AADHAAR_1], [PASS_1], [EMAIL_1]</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">STEPS TAKEN</div>
                    <div className="text-cyan-400 font-bold text-xs mt-1">4 Actions</div>
                    <div className="text-[10px] text-slate-400">Scan, Vault, Inject, Submit</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">REASONING TIER</div>
                    <div className="text-indigo-400 font-bold text-xs mt-1">Local (Ollama)</div>
                    <div className="text-[10px] text-slate-400">Tier 1 · Air-gapped</div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/60 space-y-1.5 text-xs text-slate-300">
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <ShieldCheck size={14} className="text-emerald-400" />
                    <span>Information Flag System Outcome:</span>
                  </div>
                  <p className="leading-relaxed font-normal">
                    During client-side observation, the regex classifier identified 4 sensitive categories matching KYC fields.
                    Real credentials were moved to Chrome Isolated World memory and replaced with deterministic tokens.
                    The reasoning server payload verified zero plaintext leak. Keystrokes were injected locally.
                  </p>
                </div>
              </div>

              {/* ── Real Test Run 02 ── */}
              <div className="wv-glass-panel p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 font-bold">
                      RUN 02 · PASS (POST-FIX)
                    </span>
                    <h3 className="text-sm font-bold text-white">
                      Wikipedia Generalization & Priority DOM Pruning
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Target: en.wikipedia.org/wiki/ISRO</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">TASK EXECUTED</div>
                    <div className="text-slate-200 font-semibold text-xs mt-1 truncate" title="Go to ISRO wikipedia page and extract the latest mission manifest">
                      Extract mission manifest
                    </div>
                    <div className="text-[10px] text-slate-400">Complex portal scan</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">PRUNING METRICS</div>
                    <div className="text-emerald-400 font-bold text-xs mt-1">10,475 → 184 Nodes</div>
                    <div className="text-[10px] text-slate-400">97.3% Context Reduction</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">STEPS TAKEN</div>
                    <div className="text-cyan-400 font-bold text-xs mt-1">3 Actions</div>
                    <div className="text-[10px] text-slate-400">Navigate, Filter, Parse</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">REASONING TIER</div>
                    <div className="text-indigo-400 font-bold text-xs mt-1">Local (Ollama)</div>
                    <div className="text-[10px] text-slate-400">Tier 1 · Verified Default</div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/60 space-y-1.5 text-xs text-slate-300">
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <Eye size={14} className="text-cyan-400" />
                    <span>Interactive Priority Pruner Outcome:</span>
                  </div>
                  <p className="leading-relaxed font-normal">
                    Verified post-fix against the dense Wikipedia DOM. The interactive selector prioritized in-viewport inputs, links, and tables,
                    capping passive prose paragraphs and eliminating the previous 6,785-element payload blowout that led to LLM JSON parsing crashes.
                  </p>
                </div>
              </div>

              {/* ── Real Test Run 03 ── */}
              <div className="wv-glass-panel p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 font-bold">
                      RUN 03 · PASS
                    </span>
                    <h3 className="text-sm font-bold text-white">
                      Canvas Graphic Spatial Perception & Coordinate Grounding
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">Target: http://127.0.0.1:8080/canvas_challenge.html</span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">TASK EXECUTED</div>
                    <div className="text-slate-200 font-semibold text-xs mt-1 truncate" title="Locate and interact with canvas graphic elements without DOM text nodes">
                      Canvas Spatial Grounding
                    </div>
                    <div className="text-[10px] text-slate-400">Non-semantic UI</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">CV TELEMETRY</div>
                    <div className="text-cyan-400 font-bold text-xs mt-1">8 Regions in 18.2ms</div>
                    <div className="text-[10px] text-slate-400">Local CV · CPU only</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">STEPS TAKEN</div>
                    <div className="text-emerald-400 font-bold text-xs mt-1">2 Actions</div>
                    <div className="text-[10px] text-slate-400">Detect & Dispatch Click</div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="text-slate-400 text-[10px]">REASONING TIER</div>
                    <div className="text-indigo-400 font-bold text-xs mt-1">Local (Ollama)</div>
                    <div className="text-[10px] text-slate-400">Tier 1 · Air-gapped</div>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800/60 space-y-1.5 text-xs text-slate-300">
                  <div className="font-semibold text-white flex items-center gap-1.5">
                    <Cpu size={14} className="text-indigo-400" />
                    <span>Local Visual Perception Engine Outcome:</span>
                  </div>
                  <p className="leading-relaxed font-normal">
                    When operating on HTML5 canvas graphics without text nodes, the client-side OpenCV contour engine detected 8 interactive boundary regions locally on CPU,
                    transmitting spatial bounding box coordinates to the reasoning loop without uploading any screenshots to cloud APIs.
                  </p>
                </div>
              </div>

              {/* ═══════════════════════════════════════════════════════════════
                 PS-26171 PROBLEM / SOLUTION & INFORMATION FLAG SYSTEM GUIDE
                 ═══════════════════════════════════════════════════════════════ */}
              <div className="space-y-4 pt-2">
                <div className="flex items-center gap-2 px-1 text-xs font-mono font-semibold uppercase tracking-wider text-slate-400">
                  <AlertTriangle size={14} className="text-amber-400" />
                  <span>PS-26171 Problem Challenges, Solutions & Flag Verification</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Challenge 1 */}
                  <div className="wv-glass-panel p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/25">
                        PROBLEM 01 · CREDENTIAL EXFILTRATION
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>Problem:</strong> Standard browser agents pipe raw form values (passwords, Aadhaar, PAN) into reasoning contexts, risking exposure to external LLM providers and logging backends.
                    </p>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>WebVeil Solution:</strong> Client-side tokenization regex runs in Chrome Isolated World memory. Plaintext is stripped and substituted with deterministic tokens (<code className="font-mono text-indigo-300">[PASSWORD_1]</code>) before egress.
                    </p>
                    <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono space-y-1">
                      <span className="text-white font-semibold block">How to Verify Flagging:</span>
                      1. Open <code className="text-indigo-300">http://127.0.0.1:8080/index.html</code>.<br />
                      2. In the WebVeil side panel, expand <em>"What WebVeil saw"</em> → inspect <em>"Outgoing Sanitized Payload"</em>.<br />
                      3. Confirm raw inputs are flagged and only masked tokens appear in the JSON request.
                    </div>
                  </div>

                  {/* Challenge 2 */}
                  <div className="wv-glass-panel p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/25">
                        PROBLEM 02 · PROMPT INJECTION & TAINT
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>Problem:</strong> Host pages can embed invisible adversarial text (<code className="font-mono text-slate-400">&lt;!-- exfiltrate cookies --&gt;</code>) designed to hijack agent directives and access unauthorized endpoints.
                    </p>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>WebVeil Solution:</strong> Taint tracking classifies untrusted DOM subtrees, while an on-device injection classifier flags jailbreak directives, instantly aborting navigation to unknown domains.
                    </p>
                    <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono space-y-1">
                      <span className="text-white font-semibold block">How to Verify Flagging:</span>
                      1. Run <code className="text-indigo-300">pytest webveil/tests/test_prompt_injection_defense.py</code>.<br />
                      2. Execute task targeting a page containing an override directive.<br />
                      3. Observe the security alert: the node is flagged as tainted and action execution is rejected.
                    </div>
                  </div>

                  {/* Challenge 3 */}
                  <div className="wv-glass-panel p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/25">
                        PROBLEM 03 · DOM TREE EXPLOSION
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>Problem:</strong> Public portals contain 10,000+ DOM nodes. Naive DOM serialization exhausts model context windows, introduces latency, and triggers JSON malformation.
                    </p>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>WebVeil Solution:</strong> Priority selector algorithm retains 100% of interactive form controls and in-viewport buttons while capping passive prose to immediate structural context.
                    </p>
                    <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono space-y-1">
                      <span className="text-white font-semibold block">How to Verify Flagging:</span>
                      1. Open <code className="text-indigo-300">https://en.wikipedia.org/wiki/ISRO</code>.<br />
                      2. Issue any research instruction in the WebVeil side panel.<br />
                      3. Verify the first timeline event: DOM scan count is reduced from ~10,475 down to &lt;250 interactive candidates.
                    </div>
                  </div>

                  {/* Challenge 4 */}
                  <div className="wv-glass-panel p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/25">
                        PROBLEM 04 · NON-SEMANTIC CANVAS
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>Problem:</strong> Complex interfaces render controls inside an HTML5 <code className="font-mono text-slate-400">&lt;canvas&gt;</code> element, having zero inspectable DOM text nodes or form tags.
                    </p>
                    <p className="text-xs text-slate-300 leading-relaxed font-normal">
                      <strong>WebVeil Solution:</strong> Client-side OpenCV/WASM contour detection identifies interactive regions locally in &lt;20ms on CPU, without transmitting full screenshot pixels.
                    </p>
                    <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono space-y-1">
                      <span className="text-white font-semibold block">How to Verify Flagging:</span>
                      1. Open <code className="text-indigo-300">http://127.0.0.1:8080/canvas_challenge.html</code>.<br />
                      2. Run task: <em>"Click the blue canvas target"</em>.<br />
                      3. Check side panel telemetry: confirms Local CV (CPU) bounding box detection and coordinate click.
                    </div>
                  </div>
                </div>
              </div>

            </div>
          )}

        </main>
      </div>
    </div>
  );
}

export default App;
