import React, { useEffect, useRef } from 'react';

export type AgentPointerState =
  | 'IDLE'
  | 'OBSERVING'
  | 'MOVING'
  | 'CLICKING'
  | 'TYPING'
  | 'SELECTING'
  | 'WAITING'
  | 'VERIFYING'
  | 'DONE';

export interface AgentPointerProps {
  isAgentActive?: boolean;
  agentState?: AgentPointerState;
  targetPos?: { x: number; y: number } | null;
  actionLabel?: string | null;
}

export function AgentPointer({
  isAgentActive = false,
  agentState = 'IDLE',
  targetPos = null,
  actionLabel = null,
}: AgentPointerProps) {
  const pointerRef = useRef<HTMLDivElement>(null);
  const posRef = useRef({ x: -100, y: -100 });
  const rafId = useRef<number | null>(null);

  const prefersReducedMotion = useRef(
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  // Agent Mode Target Navigation
  useEffect(() => {
    if (!isAgentActive || !targetPos) return;

    if (prefersReducedMotion.current) {
      posRef.current = targetPos;
      if (pointerRef.current) {
        pointerRef.current.style.transform = `translate3d(${targetPos.x}px, ${targetPos.y}px, 0)`;
      }
    } else {
      const startX = posRef.current.x < 0 ? targetPos.x : posRef.current.x;
      const startY = posRef.current.y < 0 ? targetPos.y : posRef.current.y;
      const startTime = performance.now();
      const duration = 320; // 320ms smooth travel

      const animateMove = (now: number) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);

        posRef.current.x = startX + (targetPos.x - startX) * easeOut;
        posRef.current.y = startY + (targetPos.y - startY) * easeOut;

        if (pointerRef.current) {
          pointerRef.current.style.transform = `translate3d(${posRef.current.x}px, ${posRef.current.y}px, 0)`;
        }

        if (progress < 1) {
          rafId.current = requestAnimationFrame(animateMove);
        }
      };

      rafId.current = requestAnimationFrame(animateMove);
    }

    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [isAgentActive, targetPos]);

  // Only render when the agent is actively operating
  if (!isAgentActive) {
    return null;
  }

  return (
    <div
      ref={pointerRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        pointerEvents: 'none',
        zIndex: 99999,
        willChange: 'transform',
        transform: 'translate3d(-100px, -100px, 0)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        userSelect: 'none',
      }}
    >
      {/* 
        Distinctive Hollow WebVeil Agent Pointer Shape:
        Large, pointed, monochrome black chevron/arrow with empty cut-out center.
      */}
      <svg
        width="28"
        height="32"
        viewBox="0 0 28 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          filter: 'drop-shadow(0 2px 5px rgba(0,0,0,0.3))',
          transition: 'transform 150ms cubic-bezier(0.22, 1, 0.36, 1)',
          transform: agentState === 'CLICKING' ? 'scale(0.88)' : 'scale(1)',
        }}
      >
        {/* Subtle white outer stroke separation for visibility on any background */}
        <path
          d="M2 2L26 14L15 17.5L10.5 28.5L2 2Z"
          stroke="#FFFFFF"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        {/* Outer Black Body with Hollow/Empty Center Cutout */}
        <path
          d="M2 2L26 14L15 17.5L10.5 28.5L2 2Z"
          fill="#111111"
          stroke="#111111"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        {/* Hollow Open Center Cutout */}
        <path
          d="M6 7.5L19.5 14.2L12.8 16.2L9.8 22.8L6 7.5Z"
          fill="#FAFAFA"
          fillOpacity="0.15"
        />
      </svg>

      {/* Contextual Action Badge in Agent Mode */}
      {actionLabel && (
        <span
          style={{
            backgroundColor: '#111111',
            color: '#FFFFFF',
            fontSize: '11px',
            fontWeight: 600,
            padding: '3px 8px',
            borderRadius: '6px',
            letterSpacing: '0.02em',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            whiteSpace: 'nowrap',
            border: '1px solid #3A3A3A',
          }}
        >
          {actionLabel}
        </span>
      )}
    </div>
  );
}

export default AgentPointer;
