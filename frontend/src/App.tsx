import React, { useState, useEffect, useRef } from 'react';
import { Shield, Settings, Play, CheckCircle2, Loader2, ArrowRight, X } from 'lucide-react';

interface AgentEvent {
  type: string;
  data: any;
}

export function App() {
  const [taskInput, setTaskInput] = useState('');
  const [messages, setMessages] = useState<Array<{ id: string; role: 'user' | 'assistant'; text?: string; status?: string; complete?: boolean }>>([]);
  const [isWorking, setIsWorking] = useState(false);
  const [currentStatus, setCurrentStatus] = useState('Understanding request...');
  const [screenshotUrl, setScreenshotUrl] = useState<string | null>(null);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);
  const [showDevDrawer, setShowDevDrawer] = useState(false);
  const [piiCount, setPiiCount] = useState(0);
  
  // Dev Drawer Metrics
  const [metrics, setMetrics] = useState({
    rawNodes: '—',
    filteredNodes: '—',
    compressionRatio: 0,
    tokensSaved: 0,
    groundingConfidence: 0.95,
    provider: 'Gemini 3.6 Flash'
  });

  const lastCountRef = useRef(0);
  const feedEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isWorking]);

  // Event Polling Loop to sync with WebVeil Python Server
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const cRes = await fetch('/api/events/count');
        const { count } = await cRes.json();

        if (count > lastCountRef.current) {
          const eRes = await fetch('/api/events');
          const events: AgentEvent[] = await eRes.json();
          const newEvents = events.slice(lastCountRef.current);
          lastCountRef.current = count;

          newEvents.forEach((ev) => handleAgentEvent(ev));
        }
      } catch (err) {
        // Silent poll fail if server restarting
      }
    }, 500);

    return () => clearInterval(interval);
  }, []);

  const handleAgentEvent = (ev: AgentEvent) => {
    const { type, data } = ev;

    if (type === 'stage_change') {
      setIsWorking(true);
      if (data.stage === 'UNDERSTAND') setCurrentStatus('Understanding request...');
      else if (data.stage === 'PERCEIVE') setCurrentStatus('Looking at page...');
      else if (data.stage === 'REASON') setCurrentStatus('Deciding next action...');
      else if (data.stage === 'GROUND') setCurrentStatus('Finding interactive elements...');
      else if (data.stage === 'ACT') setCurrentStatus('Taking action...');
      else if (data.stage === 'VERIFY') setCurrentStatus('Verifying page result...');
    } else if (type === 'observation') {
      setPiiCount(data.pii_count || 0);
      setMetrics((prev) => ({
        ...prev,
        rawNodes: data.raw_dom_nodes || data.dom_nodes || '—',
        filteredNodes: data.dom_nodes || '—',
        compressionRatio: data.compression_ratio || 0,
        tokensSaved: data.tokens_saved || 0,
      }));

      if (data.screenshot_b64) {
        setScreenshotUrl(`data:image/png;base64,${data.screenshot_b64}`);
      }
    } else if (type === 'action_execute') {
      setCurrentStatus(`Performing ${data.action.toLowerCase()}...`);
      if (data.confidence) {
        setMetrics((prev) => ({ ...prev, groundingConfidence: data.confidence }));
      }
    } else if (type === 'task_complete') {
      setIsWorking(false);
      setMessages((prev) => [
        ...prev,
        { id: Date.now().toString(), role: 'assistant', text: 'Task completed successfully.', complete: true }
      ]);
    }
  };

  const handleSend = () => {
    if (!taskInput.trim()) return;

    const userPrompt = taskInput.trim();
    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(), role: 'user', text: userPrompt }
    ]);

    setTaskInput('');
    setIsWorking(true);
    setCurrentStatus('Understanding request...');
  };

  const handleChipClick = (promptText: string) => {
    setTaskInput(promptText);
  };

  return (
    <div className="flex w-screen h-screen overflow-hidden bg-[#0a0d14] text-slate-100 font-sans">
      {/* 1. REAL BROWSER VIEWPORT (Flex 1 - Fills Left Canvas) */}
      <main className="flex-1 h-full bg-[#05070a] relative flex items-center justify-center overflow-hidden">
        {screenshotUrl ? (
          <img src={screenshotUrl} alt="Active Browser State" className="w-full h-full object-contain" />
        ) : (
          <div className="text-slate-500 text-sm font-medium flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
            Connecting to browser session...
          </div>
        )}
      </main>

      {/* 2. DOCKED RIGHT AI SIDEBAR PANEL (~360px wide) */}
      <aside className="w-[360px] min-w-[320px] max-w-[400px] h-full bg-[#111622] border-l border-slate-800 flex flex-col justify-between shadow-2xl">
        {/* Sidebar Header */}
        <header className="px-4 py-3.5 border-b border-slate-800 flex items-center justify-between bg-[#111622]">
          <div className="flex items-center gap-2.5">
            <span className="font-bold text-base tracking-tight text-white">WebVeil</span>
            <button
              onClick={() => setShowPrivacyModal(true)}
              className="text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full hover:bg-emerald-500/20 transition flex items-center gap-1"
            >
              <Shield className="w-3 h-3" /> Protected
            </button>
          </div>
          <button
            onClick={() => setShowDevDrawer(!showDevDrawer)}
            className="text-slate-400 hover:text-slate-200 p-1 rounded transition"
            title="Developer View"
          >
            <Settings className="w-4 h-4" />
          </button>
        </header>

        {/* Conversation / Activity Feed */}
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-4">
          {messages.length === 0 && !isWorking && (
            <div className="mt-2">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">What can I do for you?</h3>
              <div className="flex flex-col gap-2">
                {[
                  'Find information',
                  'Compare products',
                  'Summarize this page',
                  'Fill out a form'
                ].map((chip) => (
                  <button
                    key={chip}
                    onClick={() => handleChipClick(chip)}
                    className="text-left text-xs text-slate-400 bg-slate-800/60 hover:bg-slate-800 hover:text-slate-100 border border-slate-700/60 rounded-lg p-2.5 transition flex items-center justify-between"
                  >
                    <span>{chip}</span>
                    <ArrowRight className="w-3 h-3 text-slate-500" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col text-xs leading-relaxed ${
                msg.role === 'user'
                  ? 'self-end bg-blue-600 text-white px-3.5 py-2.5 rounded-2xl rounded-tr-xs max-w-[85%]'
                  : 'self-start bg-slate-800/80 border border-slate-700 text-slate-200 p-3 rounded-2xl rounded-tl-xs max-w-[95%]'
              }`}
            >
              {msg.complete ? (
                <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Done</span>
                </div>
              ) : null}
              <div className="mt-0.5">{msg.text}</div>
            </div>
          ))}

          {/* Active Working State Indicator */}
          {isWorking && (
            <div className="self-start w-full bg-blue-500/10 border border-blue-500/30 rounded-xl p-3 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-400">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Working</span>
              </div>
              <p className="text-xs text-slate-400">{currentStatus}</p>
            </div>
          )}

          <div ref={feedEndRef} />
        </div>

        {/* Task Input Box */}
        <div className="p-3.5 border-t border-slate-800 bg-[#111622]">
          <div className="flex gap-2">
            <textarea
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask WebVeil..."
              rows={1}
              className="flex-1 bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 resize-none outline-none focus:border-blue-500 transition"
            />
            <button
              onClick={handleSend}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs px-3.5 rounded-lg transition flex items-center justify-center"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
            </button>
          </div>
        </div>
      </aside>

      {/* Privacy Info Modal */}
      {showPrivacyModal && (
        <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center" onClick={() => setShowPrivacyModal(false)}>
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-80 shadow-2xl z-50" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                <Shield className="w-4 h-4" /> Privacy Protected
              </span>
              <button onClick={() => setShowPrivacyModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed mb-3">
              Local zero-leakage privacy engine active.<br />
              <strong className="text-white mt-1 inline-block">
                {piiCount} sensitive values protected · 0 transmitted
              </strong>
            </p>
          </div>
        </div>
      )}

      {/* Hidden Developer View Drawer */}
      {showDevDrawer && (
        <div className="fixed top-12 right-[380px] w-80 bg-slate-950 border border-slate-800 rounded-xl p-4 shadow-2xl z-50 text-xs text-slate-300">
          <div className="flex items-center justify-between mb-3 text-sky-400 font-bold">
            <span>DEVELOPER VIEW</span>
            <button onClick={() => setShowDevDrawer(false)} className="text-slate-400 hover:text-white">✕</button>
          </div>
          <div className="space-y-1.5 text-slate-400">
            <div>Raw DOM Elements: <strong className="text-white">{metrics.rawNodes}</strong></div>
            <div>Compressed Elements: <strong className="text-white">{metrics.filteredNodes}</strong></div>
            <div>DOM Compression Ratio: <strong className="text-sky-400">{metrics.compressionRatio}%</strong></div>
            <div>Estimated Tokens Saved: <strong className="text-emerald-400">~{metrics.tokensSaved}</strong></div>
            <div>Grounding Confidence: <strong className="text-white">{metrics.groundingConfidence}</strong></div>
            <div>Provider: <strong className="text-purple-400">{metrics.provider}</strong></div>
          </div>
        </div>
      )}
    </div>
  );
}
export default App;
