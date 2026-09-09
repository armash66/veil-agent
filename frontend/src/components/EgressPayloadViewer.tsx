import React, { useState } from 'react';
import { X, Copy, Check, ShieldCheck, FileJson } from 'lucide-react';

export interface EgressPayloadViewerProps {
  isOpen: boolean;
  onClose: () => void;
  payloadJson: string | object | null;
  sanitizedDomSnippet: string;
}

export function EgressPayloadViewer({
  isOpen,
  onClose,
  payloadJson,
  sanitizedDomSnippet,
}: EgressPayloadViewerProps) {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const formattedJson = typeof payloadJson === 'string'
    ? payloadJson
    : JSON.stringify(payloadJson || { info: 'No egress payload transmitted yet' }, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(formattedJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(9, 9, 11, 0.65)',
        backdropFilter: 'blur(4px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justify: 'center',
        padding: '24px',
        fontFamily: 'Inter, system-ui, sans-serif',
      }}
    >
      <div
        style={{
          width: '800px',
          maxWidth: '92vw',
          maxHeight: '85vh',
          backgroundColor: '#09090B',
          color: '#FAFAFA',
          border: '1px solid #27272A',
          borderRadius: '14px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #27272A',
            display: 'flex',
            alignItems: 'center',
            justify: 'space-between',
            backgroundColor: '#121215',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FileJson size={18} color="#60A5FA" />
            <div>
              <div style={{ fontWeight: 600, fontSize: '14px', color: '#FAFAFA' }}>
                Remote Egress Stream Inspection
              </div>
              <div style={{ fontSize: '11px', color: '#A1A1AA' }}>
                Exact sanitized text & redacted DOM tree transmitted to reasoning model
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                backgroundColor: '#064E3B',
                color: '#34D399',
                border: '1px solid #059669',
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
              }}
            >
              <ShieldCheck size={14} />
              <span>Zero Raw Secrets</span>
            </div>

            <button
              onClick={handleCopy}
              style={{
                backgroundColor: '#27272A',
                color: '#FAFAFA',
                border: '1px solid #3F3F46',
                borderRadius: '6px',
                padding: '6px 10px',
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {copied ? <Check size={14} color="#34D399" /> : <Copy size={14} />}
              <span>{copied ? 'Copied' : 'Copy JSON'}</span>
            </button>

            <button
              onClick={onClose}
              style={{
                backgroundColor: 'transparent',
                color: '#A1A1AA',
                border: 'none',
                cursor: 'pointer',
                padding: '6px',
                borderRadius: '6px',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Sanitized DOM Snippet Panel */}
          {sanitizedDomSnippet && (
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: '#A1A1AA', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                Pruned & Tokenized DOM Tree (Sent to LLM)
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: '14px',
                  backgroundColor: '#18181B',
                  border: '1px solid #27272A',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  color: '#93C5FD',
                  overflowX: 'auto',
                  maxHeight: '180px',
                  lineHeight: '1.4',
                }}
              >
                {sanitizedDomSnippet}
              </pre>
            </div>
          )}

          {/* Full Outgoing Payload JSON */}
          <div>
            <div style={{ fontSize: '11px', fontWeight: 600, color: '#A1A1AA', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
              Full Outgoing Payload Stream
            </div>
            <pre
              style={{
                margin: 0,
                padding: '14px',
                backgroundColor: '#18181B',
                border: '1px solid #27272A',
                borderRadius: '8px',
                fontFamily: 'monospace',
                fontSize: '12px',
                color: '#A7F3D0',
                overflowX: 'auto',
                maxHeight: '320px',
                lineHeight: '1.4',
              }}
            >
              {formattedJson}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EgressPayloadViewer;
