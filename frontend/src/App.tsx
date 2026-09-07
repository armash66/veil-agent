import React, { useState } from 'react';
import { ArrowUp, Settings, X, Plus, Clock, Bookmark, Shield, Sparkles } from 'lucide-react';
import AgentPointer from './components/AgentPointer';

export type AppView = 'home' | 'chat';

export interface ProductItem {
  title: string;
  price: string;
  spec: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  products?: ProductItem[];
  cheapestProduct?: string;
}

export function App() {
  const [view, setView] = useState<AppView>('home');
  const [promptText, setPromptText] = useState('');
  const [chatInputText, setChatInputText] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showSettings, setShowSettings] = useState(false);

  // Agent Pointer State Model (Driven by real WebVeil lifecycle events)
  const [isAgentActive, setIsAgentActive] = useState(false);
  const [agentState, setAgentState] = useState<AgentPointerState>('IDLE');
  const [targetPos, setTargetPos] = useState<{ x: number; y: number } | null>(null);
  const [actionLabel, setActionLabel] = useState<string | null>(null);

  const handleNewTask = () => {
    setMessages([]);
    setView('home');
    setIsAgentActive(false);
  };

  const handleSendPrompt = (text: string) => {
    if (!text.trim()) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text.trim(),
    };

    let assistantReply: ChatMessage;

    if (text.toLowerCase().includes('laptop') || text.toLowerCase().includes('compare')) {
      assistantReply = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'I found three laptops matching your requirements.',
        products: [
          { title: 'Acer Aspire One', price: '₹38,990', spec: '16GB RAM' },
          { title: 'ASUS Vivobook 15', price: '₹64,990', spec: '16GB RAM' },
          { title: 'HP 15', price: '₹78,990', spec: '16GB RAM' },
        ],
        cheapestProduct: 'Acer Aspire One',
      };
    } else {
      assistantReply = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `I will assist you with "${text.trim()}". Privacy boundary verified — zero raw data leaves your local device.`,
      };
    }

    setMessages((prev) => [...prev, userMsg, assistantReply]);
    setPromptText('');
    setView('chat');
  };

  const handleFollowUp = () => {
    if (!chatInputText.trim()) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: chatInputText.trim(),
    };

    const assistantReply: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: `Processing follow-up request: "${chatInputText.trim()}".`,
    };

    setMessages((prev) => [...prev, userMsg, assistantReply]);
    setChatInputText('');
  };

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', overflow: 'hidden' }}>
      {/* 
        WebVeil Cursor System:
        Normal Mode: Small companion cursor.
        Agent Mode: Single distinct hollow black chevron pointer with smooth movement & state animations.
      */}
      <AgentPointer
        isAgentActive={isAgentActive}
        agentState={agentState}
        targetPos={targetPos}
        actionLabel={actionLabel}
      />

      {/* 1. Bharpai-Inspired Application Navigation Sidebar (210px) */}
      <aside className="wv-nav-sidebar">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Original WebVeil Veil-Layer Identity */}
          <div className="wv-brand-logo" onClick={handleNewTask}>
            <div className="wv-veil-mark">
              <div className="wv-veil-layer-1" />
              <div className="wv-veil-layer-2" />
            </div>
            <span className="wv-brand-name">WebVeil</span>
          </div>

          {/* Primary Action Button */}
          <button className="wv-btn-new-task" onClick={handleNewTask}>
            <Plus size={16} />
            <span>New Task</span>
          </button>

          {/* Navigation Options */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div className={`wv-nav-item ${view === 'home' ? 'active' : ''}`} onClick={handleNewTask}>
              <Sparkles size={16} />
              <span>Workspace</span>
            </div>
            <div className="wv-nav-item">
              <Clock size={16} />
              <span>Recent Tasks</span>
            </div>
            <div className="wv-nav-item">
              <Bookmark size={16} />
              <span>Saved</span>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div style={{ fontSize: '11px', color: '#888888', padding: '0 4px' }}>
          WebVeil 1.0 • Privacy Core
        </div>
      </aside>

      {/* 2. Main Content Workspace */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        {/* Top Header */}
        <header className="wv-header-bar">
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#111111' }}>
            {view === 'home' ? 'Workspace' : 'Task Conversation'}
          </div>
          <button onClick={() => setShowSettings(true)} className="wv-icon-btn" title="Settings">
            <Settings size={18} />
          </button>
        </header>

        {/* Content Area */}
        <main style={{ flex: 1, overflow: 'hidden' }}>
          {view === 'home' ? (
            <div className="wv-main-home">
              {/* Logo Mark */}
              <div className="wv-veil-mark" style={{ width: '28px', height: '28px' }}>
                <div className="wv-veil-layer-1" style={{ width: '24px', height: '24px' }} />
                <div className="wv-veil-layer-2" style={{ width: '24px', height: '24px' }} />
              </div>

              <h1 className="wv-home-heading">What can I help you do?</h1>
              <p className="wv-home-subtitle">Search, research, compare, or get things done on the web.</p>

              {/* Primary Task Composer */}
              <div className="wv-hero-composer">
                <textarea
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendPrompt(promptText);
                    }
                  }}
                  placeholder="Ask WebVeil to do something..."
                  className="wv-hero-textarea"
                />
                <div className="wv-composer-controls">
                  <span className="wv-badge-mode">Privacy Guard</span>
                  <button
                    onClick={() => handleSendPrompt(promptText)}
                    disabled={!promptText.trim()}
                    className={`wv-send-icon-btn ${promptText.trim() ? 'active' : 'disabled'}`}
                  >
                    <ArrowUp size={16} />
                  </button>
                </div>
              </div>

              {/* Compact Suggestions */}
              <div className="wv-suggestion-row">
                {['Compare products', 'Summarize this page', 'Find information', 'Research a topic'].map((text) => (
                  <button key={text} onClick={() => handleSendPrompt(text)} className="wv-suggestion-pill">
                    {text}
                  </button>
                ))}
              </div>

              {/* Quiet Privacy Message */}
              <div className="wv-privacy-footer">
                <div className="wv-privacy-indicator" />
                <span>Privacy-first browsing. Sensitive information stays protected.</span>
              </div>
            </div>
          ) : (
            <div className="wv-chat-layout">
              <div className="wv-chat-history">
                {messages.map((msg) => (
                  <div key={msg.id} style={{ display: 'flex', flexDirection: 'column' }}>
                    {msg.role === 'user' ? (
                      <div className="wv-user-bubble">{msg.content}</div>
                    ) : (
                      <div className="wv-assistant-block">
                        <div className="wv-assistant-name">WebVeil</div>
                        <div>{msg.content}</div>

                        {msg.products && msg.products.length > 0 && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '14px' }}>
                            {msg.products.map((prod, idx) => (
                              <div key={idx} className="wv-product-card">
                                <div style={{ fontSize: '15px', fontWeight: 700 }}>{prod.title}</div>
                                <div style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px' }}>{prod.price}</div>
                                <div style={{ fontSize: '12px', color: '#6B6B6B', marginTop: '4px' }}>{prod.spec}</div>
                              </div>
                            ))}
                          </div>
                        )}

                        {msg.cheapestProduct && (
                          <div style={{ marginTop: '14px', fontSize: '14px', fontWeight: 700, color: '#111111' }}>
                            Cheapest: {msg.cheapestProduct}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Chat Composer Sticky Footer */}
              <div className="wv-chat-composer-sticky">
                <div className="wv-chat-input-box">
                  <input
                    type="text"
                    value={chatInputText}
                    onChange={(e) => setChatInputText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        handleFollowUp();
                      }
                    }}
                    placeholder="Ask a follow-up..."
                    style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', fontSize: '14px', color: '#111111' }}
                  />
                  <button
                    onClick={handleFollowUp}
                    disabled={!chatInputText.trim()}
                    className={`wv-send-icon-btn ${chatInputText.trim() ? 'active' : 'disabled'}`}
                    style={{ width: '34px', height: '34px', borderRadius: '8px' }}
                  >
                    <ArrowUp size={16} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Settings Popover Modal */}
      {showSettings && (
        <div
          style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.3)', zIndex: 50, display: 'flex', justifyContent: 'flex-end', padding: '24px' }}
          onClick={() => setShowSettings(false)}
        >
          <div
            style={{ width: '320px', backgroundColor: '#FFFFFF', border: '1px solid #E0E0E0', borderRadius: '16px', padding: '22px', boxShadow: '0 12px 40px rgba(0,0,0,0.10)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '10px', borderBottom: '1px solid #EBEBEB' }}>
              <span style={{ fontSize: '15px', fontWeight: 700, color: '#111111' }}>Settings</span>
              <button onClick={() => setShowSettings(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6B6B6B' }}>
                <X size={16} />
              </button>
            </div>
            <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ color: '#6B6B6B', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Appearance</label>
                <div style={{ padding: '8px 12px', backgroundColor: '#F7F7F7', border: '1px solid #E0E0E0', borderRadius: '8px', fontWeight: 500, color: '#111111' }}>Monochrome Default</div>
              </div>
              <div>
                <label style={{ color: '#6B6B6B', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Model</label>
                <div style={{ padding: '8px 12px', backgroundColor: '#F7F7F7', border: '1px solid #E0E0E0', borderRadius: '8px', fontWeight: 500, color: '#111111' }}>Gemini 3.6 Flash</div>
              </div>
              <div>
                <label style={{ color: '#6B6B6B', fontSize: '12px', display: 'block', marginBottom: '4px' }}>Privacy Engine</label>
                <div style={{ padding: '8px 12px', backgroundColor: '#F3F3F3', border: '1px solid #C7C7C7', borderRadius: '8px', color: '#111111', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Shield size={14} />
                  Zero-Leakage Gate Active
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
