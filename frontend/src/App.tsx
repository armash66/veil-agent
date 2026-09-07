import React, { useState } from 'react';
import Header from './components/Header';
import HomeView from './components/HomeView';

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

export type AppView = 'home' | 'chat';

export function App() {
  const [view, setView] = useState<AppView>('home');
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const handlePromptSubmit = (promptText: string) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: promptText,
    };

    let assistantReply: ChatMessage;

    if (promptText.toLowerCase().includes('laptop') || promptText.toLowerCase().includes('compare')) {
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
        content: `I will assist you with "${promptText}". Privacy boundary verified — zero raw data leaves your local device.`,
      };
    }

    setMessages((prev) => [...prev, userMsg, assistantReply]);
    setView('chat');
  };

  const handleFollowUp = (followUpText: string) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: followUpText,
    };

    const assistantReply: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: `Processing follow-up request: "${followUpText}".`,
    };

    setMessages((prev) => [...prev, userMsg, assistantReply]);
  };

  return (
    <div className="w-screen h-screen min-h-screen bg-[#FAFAF8] text-[#181817] flex flex-col overflow-hidden font-sans">
      <Header />
      <main className="flex-1 overflow-hidden">
        {view === 'home' ? (
          <HomeView onSubmitPrompt={handlePromptSubmit} />
        ) : (
          <div className="flex-1 w-full max-w-[760px] mx-auto flex flex-col h-[calc(100vh-64px)] px-4">
            {/* Scrollable Message History */}
            <div className="flex-1 overflow-y-auto pt-6 pb-4 space-y-6">
              {messages.map((msg) => (
                <div key={msg.id} className="w-full flex flex-col">
                  {msg.role === 'user' ? (
                    <div className="self-end max-w-[620px] bg-[#F0F0EC] text-[#181817] text-[14px] leading-[1.6] rounded-[16px] px-4 py-3">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="self-start max-w-[680px] text-[#292927] text-[14px] leading-[1.65]">
                      <div className="text-[13px] font-semibold text-[#181817] mb-[6px]">WebVeil</div>
                      <div className="whitespace-pre-wrap">{msg.content}</div>

                      {/* Structured Result Cards */}
                      {msg.products && msg.products.length > 0 && (
                        <div className="space-y-3 mt-3">
                          {msg.products.map((prod, idx) => (
                            <div
                              key={idx}
                              className="w-full bg-[#FFFFFF] border border-[#E7E7E2] rounded-[14px] p-4 text-[#181817]"
                            >
                              <div className="text-[15px] font-semibold">{prod.title}</div>
                              <div className="text-[18px] font-semibold mt-1">{prod.price}</div>
                              <div className="text-[12px] text-[#777772] mt-1">{prod.spec}</div>
                            </div>
                          ))}
                        </div>
                      )}

                      {msg.cheapestProduct && (
                        <div className="mt-3 text-[14px] font-semibold text-[#181817]">
                          Cheapest: {msg.cheapestProduct}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Sticky Bottom Chat Composer (68px height) */}
            <div className="py-4 bg-[#FAFAF8] sticky bottom-0 border-t border-[#E7E7E2]">
              <div className="w-full max-w-[760px] bg-[#FFFFFF] border border-[#DCDCD6] focus-within:border-[#B9B9B2] rounded-[16px] shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-3.5 h-[68px] flex items-center justify-between">
                <input
                  type="text"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.currentTarget.value.trim()) {
                      handleFollowUp(e.currentTarget.value.trim());
                      e.currentTarget.value = '';
                    }
                  }}
                  placeholder="Ask a follow-up..."
                  className="w-full bg-transparent border-none outline-none text-[14px] text-[#181817] placeholder-[#9A9A95]"
                />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
