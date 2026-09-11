import React, { useState } from 'react';
import { Settings, X } from 'lucide-react';
import { WebVeilLogo } from './WebVeilLogo';

export function Header() {
  const [showSettings, setShowSettings] = useState(false);

  return (
    <>
      <header className="h-[64px] w-full bg-[#FAFAF8] border-b border-[#E7E7E2] px-6 flex items-center justify-between flex-shrink-0">
        {/* Left: WebVeil logo + wordmark */}
        <div className="flex items-center gap-2.5">
          <WebVeilLogo size={22} />
          <span className="text-[18px] font-semibold text-[#181817] tracking-tight">WebVeil</span>
        </div>

        {/* Right: Settings button */}
        <button
          onClick={() => setShowSettings(true)}
          className="w-[36px] h-[36px] border-none bg-transparent rounded-[10px] hover:bg-[#F0F0EC] transition-colors flex items-center justify-center text-[#6F6F6B] cursor-pointer"
          title="Settings"
        >
          <Settings className="w-[18px] h-[18px]" />
        </button>
      </header>

      {/* Settings Modal */}
      {showSettings && (
        <div
          className="fixed inset-0 bg-black/30 z-50 flex items-start justify-end p-6"
          onClick={() => setShowSettings(false)}
        >
          <div
            className="w-[320px] bg-[#FFFFFF] border border-[#E7E7E2] rounded-[16px] shadow-[0_12px_40px_rgba(0,0,0,0.10)] p-5 text-[#181817]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#E7E7E2]">
              <span className="text-[15px] font-semibold">Settings</span>
              <button
                onClick={() => setShowSettings(false)}
                className="text-[#6F6F6B] hover:text-[#181817] p-1 rounded-md transition-colors cursor-pointer"
              >
                <X className="w-[16px] h-[16px]" />
              </button>
            </div>
            
            <div className="space-y-4 text-[13px]">
              <div>
                <label className="block text-[#6F6F6B] text-[12px] mb-1">Appearance</label>
                <div className="px-3 py-2 bg-[#FAFAF8] border border-[#E7E7E2] rounded-lg text-[#181817] font-medium">
                  Light Default
                </div>
              </div>
              <div>
                <label className="block text-[#6F6F6B] text-[12px] mb-1">Model</label>
                <div className="px-3 py-2 bg-[#FAFAF8] border border-[#E7E7E2] rounded-lg text-[#181817] font-medium">
                  Gemini 3.6 Flash
                </div>
              </div>
              <div>
                <label className="block text-[#6F6F6B] text-[12px] mb-1">Privacy Engine</label>
                <div className="px-3 py-2 bg-[#ECF8F2] border border-[#16855B]/30 rounded-lg text-[#16855B] font-semibold flex items-center gap-2">
                  <div className="w-[6px] h-[6px] rounded-full bg-[#16855B]" />
                  Zero-Leakage Local Gate Active
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
export default Header;
