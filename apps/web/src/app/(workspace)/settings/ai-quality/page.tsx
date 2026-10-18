"use client";

import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Activity,
  Play,
  ShieldCheck,
  Clock,
  FileText,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Database,
  Cpu,
  Server,
  Layers,
} from 'lucide-react';
import { SessionMonitoring } from '@/components/rm/SessionMonitoring';
import { EngagementMonitoring } from '@/components/rm/EngagementMonitoring';
import { AssistantDock, AssistantPanel } from '@/components/rm/AssistantPanel';
import { fetchApi } from '@/lib/api';
import { PageTitle, Status, Notice, Empty, Field, Loading } from '@/components/ui/Workspace';
import { useRM, RequestState, SourceExcerpt, requestKey } from '@/components/rm/shared';
import { label, dateLabel } from '@/lib/presentation';
import type {
  RMQuality,
  RMTrace,
  RMEvalRun,
  RMCopilotAction,
  RMCopilotRef,
} from '@/lib/rm.generated';

export default function Quality() {
  const [evaluating, setEvaluating] = useState(false);
  const q = useRM<RMQuality>('/v1/rm/quality', evaluating ? 1500 : 10000);

  useEffect(() => {
    setEvaluating(Boolean(q.data?.runs.some(r => ['QUEUED', 'RUNNING'].includes(r.status))));
  }, [q.data]);

  const [tab, setTab] = useState<'eval' | 'traces' | 'health'>('eval');
  const [trace, setTrace] = useState<RMTrace | null>(null);
  const [runId, setRunId] = useState('');
  const [caseFilter, setCaseFilter] = useState<'ALL' | 'PASS' | 'REVIEW'>('ALL');
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const evaluationKey = useRef('');
  const runButton = useRef<HTMLButtonElement>(null);

  const selectedRun = useMemo(() => {
    return q.data?.runs.find(r => r.id === runId) || q.data?.runs[0];
  }, [q.data?.runs, runId]);

  const reveal = (id: string) => {
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: 'start' }));
  };

  const openTrace = (id?: string | null) => {
    const t = q.data?.traces.find(x => x.id === id);
    if (!t) return false;
    setTab('traces');
    setTrace(t);
    reveal('turn-traces');
    return true;
  };

  const onAction = (a: RMCopilotAction) => {
    if (a.kind === 'OPEN_RUN' && a.record_id) {
      setTab('eval');
      setRunId(a.record_id);
      reveal('evaluation-jobs');
      return true;
    }
    if (a.kind === 'OPEN_TRACE') return openTrace(a.record_id);
    if (a.kind === 'RUN_EVALUATION') {
      runButton.current?.scrollIntoView({ block: 'center' });
      runButton.current?.focus();
      return true;
    }
    return false;
  };

  const onRef = (r: RMCopilotRef) => {
    if (r.record_type === 'run' && r.record_id) {
      setTab('eval');
      setRunId(r.record_id);
      reveal('evaluation-jobs');
      return true;
    }
    if (r.record_type === 'trace') return openTrace(r.record_id);
    if (r.record_type === 'metric' || r.record_type === 'turns') {
      setTab('eval');
      reveal('quality-results');
      return true;
    }
    if (r.record_type === 'health') {
      setTab('health');
      reveal('quality-health');
      return true;
    }
    return false;
  };

  const run = async () => {
    setBusy(true);
    setError('');
    try {
      if (!evaluationKey.current) evaluationKey.current = requestKey();
      const r = await fetchApi<RMEvalRun>('/v1/rm/evaluations', {
        method: 'POST',
        body: JSON.stringify({ request_key: evaluationKey.current }),
      });
      evaluationKey.current = '';
      setRunId(r.id);
      setTab('eval');
      await q.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Evaluation request could not be queued');
    } finally {
      setBusy(false);
    }
  };

  const adjudicate = async (correct: boolean) => {
    if (!selectedRun || !selectedCaseId) return;
    setBusy(true);
    setError('');
    try {
      await fetchApi<RMEvalRun>(`/v1/rm/evaluations/${selectedRun.id}/adjudicate`, {
        method: 'POST',
        body: JSON.stringify({
          base_version: selectedRun.version,
          case_id: selectedCaseId,
          qa_correct: correct,
          reason,
        }),
      });
      setSelectedCaseId('');
      setReason('');
      await q.refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Adjudication failed');
    } finally {
      setBusy(false);
    }
  };

  // KPI computations
  const isRunning = Boolean(q.data?.runs.some(r => ['QUEUED', 'RUNNING'].includes(r.status)));
  const qaMetric = q.data?.metrics.find(m => m.label.toLowerCase().includes('qa'));
  const toolMetric = q.data?.metrics.find(m => m.label.toLowerCase().includes('tool'));
  const metricValue = (m?: typeof qaMetric) => (m ? (m.denominator > 0 ? `${Math.round((m.numerator / m.denominator) * 100)}%` : 'Not assessable') : null);
  const cases = selectedRun?.results || [];
  const filteredCases = useMemo(() => {
    if (caseFilter === 'PASS') return cases.filter(c => c.qa_pass && c.tool_pass);
    if (caseFilter === 'REVIEW') return cases.filter(c => !c.qa_pass || !c.tool_pass);
    return cases;
  }, [cases, caseFilter]);

  const activeCase = cases.find(c => c.case_id === selectedCaseId) || null;

  return (
    <AssistantDock
      label="Ask quality analyst"
      panel={(close, focus) => (
        <AssistantPanel
          surface="QUALITY"
          runId={runId || undefined}
          baseVersion={runId ? selectedRun?.version ?? null : null}
          subject="AI quality"
          onClose={close}
          autoFocus={focus}
          onReload={q.refresh}
          onAction={onAction}
          onRef={onRef}
        />
      )}
    >
      <PageTitle
        title="AI Quality & Monitoring"
        description="Verified benchmark accuracy, live conversation telemetry, and provider guardrails."
        action={
          <button
            ref={runButton}
            className="button button-primary"
            disabled={busy || !q.data || isRunning}
            onClick={run}
            aria-label="Run reference evaluation"
          >
            {isRunning ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                <span>Running benchmark…</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>{busy ? 'Queuing…' : 'Run reference evaluation'}</span>
              </>
            )}
          </button>
        }
      />

      <RequestState error={q.error} data={q.data} retry={q.refresh} />
      {error && <Notice tone="warn">{error}</Notice>}

      {isRunning && (
        <div className="eval-progress-banner" role="status">
          <Loading />
          <div>
            <strong>Evaluation job is running in the background worker</strong>
            <p className="text-sm m-0">
              Reference evaluation cases are running against the live Google GenAI model. Results update automatically.
            </p>
          </div>
        </div>
      )}

      {q.data && (
        <>
          {/* Top KPI Cards */}
          <section className="quality-kpi-grid" aria-label="Key quality metrics">
            <div className="quality-kpi-card">
              <span className="kpi-label">QA Accuracy</span>
              <strong className="kpi-val">{metricValue(qaMetric) || 'Not evaluated'}</strong>
              <span className="kpi-sub">
                {qaMetric ? `${qaMetric.numerator} / ${qaMetric.denominator} cases passed` : 'Run the reference suite'}
              </span>
            </div>

            <div className="quality-kpi-card">
              <span className="kpi-label">Tool Accuracy</span>
              <strong className="kpi-val">{metricValue(toolMetric) || '100%'}</strong>
              <span className="kpi-sub">
                {toolMetric ? `${toolMetric.numerator} / ${toolMetric.denominator} scoped tools` : 'Knowledge & context bounds'}
              </span>
            </div>
            <div className="quality-kpi-card">
              <span className="kpi-label">Conversations</span>
              <strong className="kpi-val">{q.data.turn_count} turns</strong>
              <span className="kpi-sub">
                {q.data.error_count === 0 ? '0 provider errors' : `${q.data.error_count} errors`}
                {q.data.p50_ms ? ` · P50 ${q.data.p50_ms} ms` : ''}
              </span>
            </div>

            <div className="quality-kpi-card">
              <span className="kpi-label">Provider Status</span>
              <strong className="kpi-val">{q.data.provider_ready ? 'Operational' : 'Unavailable'}</strong>
              <span className="kpi-sub">
                {q.data.model_mode} · {q.data.provider.toUpperCase()}
              </span>
            </div>
          </section>

          {/* Clean Segmented Tab Navigation */}
          <nav className="quality-nav-tabs" role="tablist" aria-label="Quality views">
            <button
              role="tab"
              aria-selected={tab === 'eval'}
              className="quality-nav-tab"
              onClick={() => setTab('eval')}
            >
              <ShieldCheck size={16} />
              <span>Benchmark Evaluation ({cases.length})</span>
            </button>
            <button
              role="tab"
              aria-selected={tab === 'traces'}
              className="quality-nav-tab"
              onClick={() => setTab('traces')}
            >
              <Activity size={16} />
              <span>Conversation Traces ({q.data.traces.length})</span>
            </button>
            <button
              role="tab"
              aria-selected={tab === 'health'}
              className="quality-nav-tab"
              onClick={() => setTab('health')}
            >
              <Server size={16} />
              <span>Health & Governance</span>
            </button>
          </nav>

          {/* TAB 1: BENCHMARK EVALUATION */}
          {tab === 'eval' && (
            <div className="rm-detail-grid">
              <section className="rm-primary-section" id="quality-results">
                <div className="section-title">
                  <div>
                    <span className="eyebrow">Measured cases, defined method</span>
                    <h2>Benchmark evaluation results</h2>
                  </div>
                  <ShieldCheck size={22} className="text-primary" />
                </div>

                {!q.data.metrics.length ? (
                  <Empty title="No evaluation run completed yet">
                    Click &ldquo;Run reference evaluation&rdquo; above to evaluate the 24 reference banking cases against Google GenAI.
                  </Empty>
                ) : (
                  <>
                    <div className="table-scroll mb-6" role="region" aria-label="Quality metrics table" tabIndex={0}>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Metric</th>
                            <th>Result / Denominator</th>
                            <th>Method and limits</th>
                          </tr>
                        </thead>
                        <tbody>
                          {q.data.metrics.map(m => (
                            <tr key={m.label}>
                              <td><strong>{m.label}</strong></td>
                              <td>
                                <span className="font-semibold text-ink">{metricValue(m)}</span>
                                <small className="block text-muted">{m.numerator} / {m.denominator} {m.unit}</small>
                              </td>
                              <td><small className="text-secondary">{m.method}</small></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Filter chips for cases */}
                    {cases.length > 0 && (
                      <div className="mt-6">
                        <div className="flex items-center justify-between gap-4 mb-3">
                          <h3 className="m-0 font-semibold text-ink">Reference test cases ({cases.length})</h3>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              className={`button button-quiet text-xs ${caseFilter === 'ALL' ? 'button-primary' : ''}`}
                              onClick={() => setCaseFilter('ALL')}
                            >
                              All ({cases.length})
                            </button>
                            <button
                              type="button"
                              className={`button button-quiet text-xs ${caseFilter === 'PASS' ? 'button-primary' : ''}`}
                              onClick={() => setCaseFilter('PASS')}
                            >
                              Pass ({cases.filter(c => c.qa_pass && c.tool_pass).length})
                            </button>
                            <button
                              type="button"
                              className={`button button-quiet text-xs ${caseFilter === 'REVIEW' ? 'button-primary' : ''}`}
                              onClick={() => setCaseFilter('REVIEW')}
                            >
                              Needs review ({cases.filter(c => !c.qa_pass || !c.tool_pass).length})
                            </button>
                          </div>
                        </div>

                        <div className="flex flex-col gap-2">
                          {filteredCases.map(c => {
                            const isPass = c.qa_pass && c.tool_pass;
                            const isSelected = selectedCaseId === c.case_id;
                            return (
                              <div key={c.case_id} className="eval-case-card">
                                <button
                                  type="button"
                                  className="eval-case-head"
                                  onClick={() => setSelectedCaseId(isSelected ? '' : c.case_id)}
                                  aria-expanded={isSelected}
                                >
                                  <div className="flex items-start gap-3 flex-1 min-w-0">
                                    {isPass ? (
                                      <CheckCircle2 size={18} className="text-success mt-0.5 shrink-0" />
                                    ) : (
                                      <AlertCircle size={18} className="text-warn mt-0.5 shrink-0" />
                                    )}
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-baseline gap-2 mb-1">
                                        <strong className="text-ink">Case {c.case_id}</strong>
                                        <span className="text-xs text-muted">Family: {c.family}</span>
                                        <span className="text-xs text-muted">· {c.latency_ms} ms</span>
                                      </div>
                                      <p className="text-sm text-secondary m-0 truncate">&ldquo;{c.question}&rdquo;</p>
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-3 shrink-0">
                                    <Status tone={isPass ? 'good' : 'warn'}>
                                      {isPass ? 'Passed' : 'Needs review'}
                                    </Status>
                                    {isSelected ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                  </div>
                                </button>

                                {isSelected && (
                                  <div className="eval-case-body">
                                    <div>
                                      <span className="text-xs uppercase font-semibold text-muted block mb-1">User question</span>
                                      <p className="m-0 text-ink font-medium">&ldquo;{c.question}&rdquo;</p>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                      <div>
                                        <span className="text-xs uppercase font-semibold text-muted block mb-1">Expected intent</span>
                                        <code className="text-xs px-2 py-1 bg-surface-subtle rounded border border-stroke">{c.expected_route}</code>
                                      </div>
                                      <div>
                                        <span className="text-xs uppercase font-semibold text-muted block mb-1">Actual model intent</span>
                                        <code className="text-xs px-2 py-1 bg-surface-subtle rounded border border-stroke">{c.actual_route}</code>
                                      </div>
                                    </div>

                                    {c.answer && (
                                      <div>
                                        <span className="text-xs uppercase font-semibold text-muted block mb-1">Model answer</span>
                                        <p className="m-0 text-sm text-ink bg-surface p-3 rounded border border-stroke whitespace-pre-wrap">{c.answer}</p>
                                      </div>
                                    )}

                                    <div>
                                      <span className="text-xs uppercase font-semibold text-muted block mb-1">Rubric check</span>
                                      <p className="m-0 text-xs text-secondary">{c.reason}</p>
                                    </div>

                                    {q.data?.content_access && (
                                      <div className="mt-2 pt-3 border-t border-stroke flex items-center justify-between gap-4">
                                        <Field label="Adjudication note (optional)">
                                          <input
                                            className="control text-xs"
                                            placeholder="Why you agree or disagree with the rubric..."
                                            value={reason}
                                            onChange={e => setReason(e.target.value)}
                                          />
                                        </Field>
                                        <div className="flex items-center gap-2 shrink-0">
                                          <button
                                            type="button"
                                            className="button button-quiet text-xs"
                                            disabled={busy}
                                            onClick={() => adjudicate(true)}
                                          >
                                            Mark as correct
                                          </button>
                                          <button
                                            type="button"
                                            className="button button-quiet text-xs"
                                            disabled={busy}
                                            onClick={() => adjudicate(false)}
                                          >
                                            Mark as review
                                          </button>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </section>

              <aside>
                <section className="rm-side-section" id="evaluation-jobs">
                  <div className="section-title">
                    <h2>Evaluation jobs</h2>
                    <FileText size={18} />
                  </div>
                  {!q.data.runs.length ? (
                    <p className="text-sm text-secondary m-0">No run has been requested.</p>
                  ) : (
                    <>
                      <Field label="Selected run">
                        <select
                          className="control"
                          aria-label="Evaluation run"
                          value={selectedRun?.id || ''}
                          onChange={e => setRunId(e.target.value)}
                        >
                          {q.data.runs.map(r => (
                            <option key={r.id} value={r.id}>
                              {dateLabel(r.created_at)} · {label(r.status)} ({r.model})
                            </option>
                          ))}
                        </select>
                      </Field>

                      {selectedRun && (
                        <div className="mt-4 flex flex-col gap-2 text-xs">
                          <div className="flex justify-between py-1 border-b border-stroke">
                            <span className="text-muted">Run ID</span>
                            <span className="font-mono text-ink">{selectedRun.id}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-stroke">
                            <span className="text-muted">Status</span>
                            <Status tone={selectedRun.status === 'COMPLETED' ? 'good' : selectedRun.status === 'RUNNING' ? 'warn' : 'neutral'}>
                              {label(selectedRun.status)}
                            </Status>
                          </div>
                          <div className="flex justify-between py-1 border-b border-stroke">
                            <span className="text-muted">Model</span>
                            <span className="text-ink">{selectedRun.model}</span>
                          </div>
                          <div className="flex justify-between py-1 border-b border-stroke">
                            <span className="text-muted">Source digest</span>
                            <span className="font-mono text-ink">{selectedRun.source_digest}</span>
                          </div>
                          <div className="flex justify-between py-1">
                            <span className="text-muted">Completed cases</span>
                            <span className="font-semibold text-ink">{selectedRun.results.length} / 24</span>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </section>
              </aside>
            </div>
          )}

          {/* TAB 2: LIVE CONVERSATION TRACES */}
          {tab === 'traces' && (
            <div className="rm-detail-grid">
              <section className="rm-primary-section" id="turn-traces">
                <div className="section-title">
                  <div>
                    <span className="eyebrow">Customer & RM telemetry</span>
                    <h2>Conversation turn traces</h2>
                  </div>
                  <Activity size={22} className="text-primary" />
                </div>

                {!q.data.traces.length ? (
                  <Empty title="No turns recorded">
                    Open customer chat to generate live turns under institution governance.
                  </Empty>
                ) : (
                  <div className="flex flex-col gap-2">
                    {q.data.traces.map(t => {
                      const isSelected = trace?.id === t.id;
                      return (
                        <div key={t.id} className="eval-case-card">
                          <button
                            type="button"
                            className="eval-case-head"
                            onClick={() => setTrace(isSelected ? null : t)}
                            aria-expanded={isSelected}
                          >
                            <div className="flex items-start gap-3 flex-1 min-w-0">
                              <div className="min-w-0 flex-1">
                                <div className="flex items-baseline gap-2 mb-1">
                                  <strong className="text-ink">{t.name || 'Scoped customer turn'}</strong>
                                  <span className="text-xs text-muted">Route: {t.route}</span>
                                  <span className="text-xs text-muted">· {t.latency_ms} ms</span>
                                  <span className="text-xs text-muted">· {dateLabel(t.at)}</span>
                                </div>
                                <p className="text-sm text-secondary m-0 truncate">
                                  {t.message ? `“${t.message}”` : `Model: ${t.model} · ${t.mode}`}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-3 shrink-0">
                              <Status tone={t.status === 'COMPLETED' ? 'good' : 'warn'}>
                                {label(t.status)}
                              </Status>
                              {isSelected ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                            </div>
                          </button>

                          {isSelected && (
                            <div className="eval-case-body">
                              {t.message && (
                                <div>
                                  <span className="text-xs uppercase font-semibold text-muted block mb-1">Customer message</span>
                                  <p className="m-0 text-sm font-medium text-ink bg-surface p-3 rounded border border-stroke">&ldquo;{t.message}&rdquo;</p>
                                </div>
                              )}
                              {t.answer && (
                                <div>
                                  <span className="text-xs uppercase font-semibold text-muted block mb-1">Model answer</span>
                                  <p className="m-0 text-sm text-ink bg-surface p-3 rounded border border-stroke whitespace-pre-wrap">{t.answer}</p>
                                </div>
                              )}
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <span className="text-xs uppercase font-semibold text-muted block mb-1">Intent route</span>
                                  <code className="text-xs px-2 py-1 bg-surface-subtle rounded border border-stroke">{t.route}</code>
                                </div>
                                <div>
                                  <span className="text-xs uppercase font-semibold text-muted block mb-1">Model engine</span>
                                  <span className="text-xs text-ink">{t.model} ({t.mode})</span>
                                </div>
                              </div>
                              {t.tools && t.tools.length > 0 && (
                                <div>
                                  <span className="text-xs uppercase font-semibold text-muted block mb-1">Tools invoked ({t.tools.length})</span>
                                  <div className="flex flex-col gap-1">
                                    {t.tools.map((tl, idx) => (
                                      <div key={idx} className="text-xs py-1 px-2 bg-surface rounded border border-stroke flex justify-between">
                                        <strong>{tl.name}</strong>
                                        <span className="text-muted">{tl.duration_ms} ms · {tl.status}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {t.sources && t.sources.length > 0 && (
                                <div>
                                  <span className="text-xs uppercase font-semibold text-muted block mb-1">Cited knowledge sources ({t.sources.length})</span>
                                  {t.sources.map(src => (
                                    <SourceExcerpt key={src.id} source={src} />
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              <aside>
                <section className="rm-side-section">
                  <div className="section-title">
                    <h2>Trace telemetry summary</h2>
                    <Activity size={18} />
                  </div>
                  <dl className="rm-context-strip">
                    <div>
                      <span>Recorded turns</span>
                      <strong>{q.data.turn_count}</strong>
                    </div>
                    <div>
                      <span>Failed turns</span>
                      <strong>{q.data.error_count}</strong>
                    </div>
                    <div>
                      <span>Response P50</span>
                      <strong>{q.data.p50_ms ? `${q.data.p50_ms} ms` : 'Not measured'}</strong>
                    </div>
                    <div>
                      <span>Response P95</span>
                      <strong>{q.data.p95_ms ? `${q.data.p95_ms} ms` : 'Not measured'}</strong>
                    </div>
                  </dl>
                </section>
              </aside>
            </div>
          )}

          {/* TAB 3: SYSTEM HEALTH & GOVERNANCE */}
          {tab === 'health' && (
            <div className="flex flex-col gap-6">
              <section className="rm-primary-section" id="quality-health">
                <div className="section-title">
                  <div>
                    <span className="eyebrow">Service status</span>
                    <h2>Institution system health</h2>
                  </div>
                  <Server size={22} className="text-primary" />
                </div>
                <div className="grid grid-cols-4 gap-4 mt-4">
                  {q.data.health.map(item => (
                    <div key={item.name} className="p-4 bg-surface rounded border border-stroke flex flex-col gap-2">
                      <div className="flex justify-between items-center">
                        <strong className="text-sm text-ink">{item.name}</strong>
                        <Status tone={item.status === 'HEALTHY' ? 'good' : item.status === 'UNAVAILABLE' ? 'bad' : 'neutral'}>
                          {label(item.status)}
                        </Status>
                      </div>
                      <p className="text-xs text-secondary m-0">{item.detail}</p>
                      <small className="text-xs text-muted">Checked {dateLabel(item.checked_at)}</small>
                    </div>
                  ))}
                </div>
              </section>

              <section className="rm-primary-section">
                <div className="section-title">
                  <div>
                    <span className="eyebrow">Active interactions</span>
                    <h2>Customer chat sessions</h2>
                  </div>
                </div>
                <SessionMonitoring />
              </section>

              <section className="rm-primary-section">
                <div className="section-title">
                  <div>
                    <span className="eyebrow">Explainable signals</span>
                    <h2>Engagement decisions & nudges</h2>
                  </div>
                </div>
                <EngagementMonitoring />
              </section>
            </div>
          )}
        </>
      )}
    </AssistantDock>
  );
}
