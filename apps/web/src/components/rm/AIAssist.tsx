"use client";
import React, { useState } from 'react';
import { Status, Notice } from '@/components/ui/Workspace';
import { SourceExcerpt } from '@/components/rm/shared';
import { dateLabel, label } from '@/lib/presentation';
import type { RMSource, RMAIBrief, RMAIDraft } from '@/lib/rm.generated';

export function SourceChip({
  sourceId,
  sources,
  onSelect,
}: {
  sourceId: string;
  sources: RMSource[];
  onSelect?: (s: RMSource) => void;
}) {
  const source = sources.find(s => s.id === sourceId);
  if (!source) {
    const name = sourceId === 'rm-note' ? 'Internal RM note' : 'Source ' + sourceId;
    return <span className="source-chip" style={{ display: 'inline-flex', padding: '2px 8px', fontSize: '11px', borderRadius: '4px', border: '1px solid var(--stroke)', background: 'var(--surface-subtle)', color: 'var(--ink)' }}>{name}</span>;
  }

  return (
    <button
      type="button"
      className="source-chip"
      aria-label={`Source: ${source.title} (${label(source.kind)})`}
      onClick={() => onSelect?.(source)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '2px 8px',
        fontSize: '11px',
        fontWeight: 500,
        borderRadius: '4px',
        border: '1px solid var(--stroke)',
        background: 'var(--surface-subtle)',
        color: 'var(--ink)',
        cursor: 'pointer',
      }}
    >
      <span>{source.title}</span>
      <span style={{ color: 'var(--muted)' }}>· {dateLabel(source.event_at)}</span>
    </button>
  );
}

export function AIBriefView({ brief }: { brief: RMAIBrief }) {
  const [selectedSource, setSelectedSource] = useState<RMSource | null>(null);
  const isLive = brief.mode === 'LIVE';

  return (
    <div
      className="ai-brief-card"
      style={{
        marginTop: '16px',
        padding: '16px',
        border: '1px solid var(--stroke)',
        borderRadius: '8px',
        background: 'var(--surface)',
      }}
      role="region"
      aria-label="AI pre-call brief"
    >
      <div className="section-title" style={{ marginBottom: '12px' }}>
        <div>
          <span className="eyebrow">AI Pre-Call Brief</span>
          <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '2px 0 0' }}>Context & Talking Points</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Status tone={isLive ? 'good' : 'neutral'}>
            {isLive ? `Gemini · ${brief.model}` : 'Simulated (local engine)'}
          </Status>
          <small className="text-muted" style={{ fontSize: '11px' }}>
            {brief.latency_ms}ms · {brief.prompt_version}
          </small>
        </div>
      </div>

      <p className="brief-why-now" style={{ fontSize: '14px', lineHeight: 1.5 }}>
        {brief.summary}
      </p>

      {brief.talking_points?.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          <h4 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Talking points</h4>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '10px' }}>
            {brief.talking_points.map((tp: { text: string; source_ids: string[] }, i: number) => (
              <li key={i} style={{ background: 'var(--surface-subtle)', borderRadius: '6px', padding: '8px 10px' }}>
                <p style={{ margin: '0 0 4px', fontSize: '13px' }}>{tp.text}</p>
                {tp.source_ids?.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Sources:</span>
                    {tp.source_ids.map((sid: string) => (
                      <SourceChip
                        key={sid}
                        sourceId={sid}
                        sources={brief.sources || []}
                        onSelect={s => setSelectedSource(prev => (prev?.id === s.id ? null : s))}
                      />
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {brief.questions?.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          <h4 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Questions to explore</h4>
          <ul style={{ paddingLeft: '18px', margin: 0, display: 'grid', gap: '4px' }}>
            {brief.questions.map((q: string, i: number) => (
              <li key={i} style={{ fontSize: '13px' }}>
                {q}
              </li>
            ))}
          </ul>
        </div>
      )}

      {brief.cautions?.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          <h4 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: 'var(--warning)' }}>
            Cautions & boundaries
          </h4>
          <ul style={{ paddingLeft: '18px', margin: 0, display: 'grid', gap: '4px' }}>
            {brief.cautions.map((c: string, i: number) => (
              <li key={i} style={{ fontSize: '13px', color: 'var(--ink)' }}>
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {selectedSource && (
        <div style={{ marginTop: '14px' }}>
          <SourceExcerpt source={selectedSource} />
        </div>
      )}

      <p style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '16px', marginBottom: 0 }}>
        AI can make mistakes. Check sources before contacting the customer.
      </p>
    </div>
  );
}

export function AIDraftView({ draft }: { draft: RMAIDraft }) {
  const [copied, setCopied] = useState(false);
  const [selectedSource, setSelectedSource] = useState<RMSource | null>(null);
  const isLive = draft.mode === 'LIVE';

  const handleCopy = () => {
    const textToCopy = draft.subject ? `Subject: ${draft.subject}\n\n${draft.body}` : draft.body;
    navigator.clipboard?.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="ai-draft-card"
      style={{
        marginTop: '16px',
        padding: '16px',
        border: '1px solid var(--stroke)',
        borderRadius: '8px',
        background: 'var(--surface)',
      }}
      role="region"
      aria-label="Generated outreach draft"
    >
      <Notice tone="neutral">
        <strong>{draft.boundary}</strong>
      </Notice>

      <div className="section-title" style={{ margin: '14px 0 10px' }}>
        <div>
          <span className="eyebrow">Outreach draft</span>
          <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '2px 0 0' }}>Review before sending</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Status tone={isLive ? 'good' : 'neutral'}>
            {isLive ? `Gemini · ${draft.model}` : 'Simulated (local engine)'}
          </Status>
          <small className="text-muted" style={{ fontSize: '11px' }}>
            {draft.latency_ms}ms · {draft.prompt_version}
          </small>
        </div>
      </div>

      {draft.subject && (
        <div style={{ marginBottom: '10px', fontSize: '13px' }}>
          <strong>Subject: </strong>
          <span style={{ userSelect: 'text' }}>{draft.subject}</span>
        </div>
      )}

      <div
        className="ai-draft-body"
        tabIndex={0}
        aria-label="Draft text (read-only)"
        style={{
          userSelect: 'text',
          WebkitUserSelect: 'text',
          whiteSpace: 'pre-wrap',
          padding: '12px 14px',
          background: 'var(--canvas)',
          border: '1px solid var(--stroke)',
          borderRadius: '6px',
          fontSize: '13px',
          lineHeight: 1.5,
          fontFamily: 'inherit',
          outline: 'none',
        }}
      >
        {draft.body}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px' }}>
        <button
          type="button"
          className="button button-quiet"
          onClick={handleCopy}
          aria-label="Copy draft text"
        >
          {copied ? 'Copied to clipboard' : 'Copy draft'}
        </button>
      </div>

      {draft.source_ids?.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          <h4 style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>Cited sources</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {draft.source_ids.map((sid: string) => (
              <SourceChip
                key={sid}
                sourceId={sid}
                sources={draft.sources || []}
                onSelect={s => setSelectedSource(prev => (prev?.id === s.id ? null : s))}
              />
            ))}
          </div>
        </div>
      )}

      {selectedSource && (
        <div style={{ marginTop: '14px' }}>
          <SourceExcerpt source={selectedSource} />
        </div>
      )}

      <p style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '14px', marginBottom: 0 }}>
        AI can make mistakes. Check sources before contacting the customer.
      </p>
    </div>
  );
}
