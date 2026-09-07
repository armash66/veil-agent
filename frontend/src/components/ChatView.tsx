import React from 'react';
import PromptComposer from './PromptComposer';

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

interface ChatViewProps {
  messages: ChatMessage[];
  onSendMessage: (text: string) => void;
}

export function ChatView({ messages, onSendMessage }: ChatViewProps) {
  return (
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

      {/* Sticky Bottom Chat Composer */}
      <div className="py-4 bg-[#FAFAF8] sticky bottom-0 border-t border-[#E7E7E2]">
        <PromptComposer
          onSend={onSendMessage}
          placeholder="Ask a follow-up..."
          className="h-[68px]"
        />
      </div>
    </div>
  );
}
export default ChatView;
