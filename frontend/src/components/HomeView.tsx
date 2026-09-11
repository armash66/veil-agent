import React from 'react';
import PromptComposer from './PromptComposer';
import { WebVeilLogo } from './WebVeilLogo';

interface HomeViewProps {
  onSubmitPrompt: (prompt: string) => void;
}

export function HomeView({ onSubmitPrompt }: HomeViewProps) {
  const suggestions = [
    'Compare products',
    'Summarize this page',
    'Find information',
    'Research a topic'
  ];

  return (
    <div className="w-full max-w-[760px] mx-auto pt-[17vh] flex flex-col items-center px-4">
      {/* Branding Logo */}
      <div className="mb-5 drop-shadow-sm">
        <WebVeilLogo size={36} />
      </div>

      {/* Heading */}
      <h1 className="text-[30px] font-semibold text-[#181817] leading-[1.2] tracking-[-0.025em] text-center mb-2.5">
        What can I help you do?
      </h1>

      {/* Subtitle */}
      <p className="text-[15px] leading-[1.5] text-[#6F6F6B] text-center max-w-[520px] mb-8">
        Search, research, compare, or get things done on the web.
      </p>

      {/* Prompt Composer (112px height container) */}
      <PromptComposer onSend={onSubmitPrompt} className="h-[112px] mb-[18px]" />

      {/* Suggestion Pills */}
      <div className="flex flex-wrap justify-center gap-2 mb-[32px]">
        {suggestions.map((text) => (
          <button
            key={text}
            onClick={() => onSubmitPrompt(text)}
            className="h-[34px] px-[14px] rounded-[17px] bg-[#FFFFFF] border border-[#E7E7E2] text-[13px] text-[#5F5F5B] hover:bg-[#F3F3EF] hover:border-[#D8D8D2] hover:text-[#181817] transition-colors cursor-pointer"
          >
            {text}
          </button>
        ))}
      </div>

      {/* Privacy Note */}
      <div className="flex items-center gap-2 text-[12px] text-[#858580] text-center mt-[32px]">
        <div className="w-[6px] h-[6px] rounded-full bg-[#16855B]" />
        <span>Privacy-first browsing. Sensitive information stays protected.</span>
      </div>
    </div>
  );
}
export default HomeView;
