import React, { useState } from 'react';
import { ArrowUp } from 'lucide-react';

interface PromptComposerProps {
  onSend: (text: string) => void;
  initialValue?: string;
  placeholder?: string;
  className?: string;
}

export function PromptComposer({ onSend, initialValue = '', placeholder = 'Ask WebVeil to do something...', className = '' }: PromptComposerProps) {
  const [value, setValue] = useState(initialValue);

  const handleSubmit = () => {
    if (!value.trim()) return;
    onSend(value.trim());
    setValue('');
  };

  return (
    <div className={`w-full max-w-[760px] bg-[#FFFFFF] border border-[#DCDCD6] focus-within:border-[#B9B9B2] rounded-[18px] shadow-[0_2px_10px_rgba(0,0,0,0.04)] p-4 flex flex-col justify-between transition-colors ${className}`}>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
        placeholder={placeholder}
        className="w-full h-[65px] bg-transparent border-none outline-none resize-none text-[15px] leading-[1.5] text-[#181817] placeholder-[#9A9A95]"
      />
      <div className="h-[32px] flex justify-end items-center">
        <button
          onClick={handleSubmit}
          disabled={!value.trim()}
          className={`w-[36px] h-[36px] rounded-[10px] flex items-center justify-center transition-colors cursor-pointer ${
            value.trim()
              ? 'bg-[#181817] text-[#FFFFFF] hover:bg-[#30302E]'
              : 'bg-[#E7E7E2] text-[#9A9A95] cursor-not-allowed'
          }`}
        >
          <ArrowUp className="w-[16px] h-[16px]" />
        </button>
      </div>
    </div>
  );
}
export default PromptComposer;
