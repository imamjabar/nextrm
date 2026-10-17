"use client";

import {useRef, useState} from 'react';
import {ArrowUpRight, CheckCircle2, Lightbulb, X} from 'lucide-react';
import {fetchApi} from '@/lib/api';
import {Notice} from '@/components/ui/Workspace';
import {useRM, SourceExcerpt, requestKey} from './shared';
import type {RMNudge, RMNudges, RMNudgeAction} from '@/lib/rm.generated';

function Suggestion({nudge, share, locked, explore, requested, refresh}: {
  nudge: RMNudge; share: boolean; locked: boolean;
  explore: (text: string) => void; requested: (signal: string) => void;
  refresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const retry = useRef<RMNudgeAction | null>(null);
  const act = async (action: RMNudgeAction['action']) => {
    setBusy(true); setError('');
    if (!retry.current || retry.current.action !== action || retry.current.share_with_rm !== share) {
      retry.current = {action, base_version: nudge.version, request_key: requestKey(), share_with_rm: share};
    }
    try {
      const result = await fetchApi<RMNudge>(`/v1/rm/chat/${nudge.party_id}/nudges/${nudge.id}`, {
        method: 'POST', body: JSON.stringify(retry.current),
      });
      retry.current = null;
      if (action === 'EXPLORE') explore(result.prompt);
      if (result.signal_id) requested(result.signal_id);
      await refresh();
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  const done = nudge.state === 'REQUESTED';
  return <section className={'customer-nudge ' + (done ? 'requested' : '')} aria-label="Personalized suggestion">
    <div className="nudge-heading"><span><Lightbulb size={15}/> For your stated goal</span>
      {!done && <button aria-label={'Dismiss suggestion: ' + nudge.title} disabled={busy || locked} onClick={() => act('DISMISS')}><X size={16}/></button>}
    </div>
    <h3>{nudge.title}</h3><p>{nudge.body}</p>
    {done ? <p className="nudge-receipt"><CheckCircle2 size={16}/> RM help requested. Your discussion need is awaiting review.</p> : <>
      <div className="nudge-actions">
        <button className="text-link" disabled={busy || locked} onClick={() => act('EXPLORE')}>Explore in chat <ArrowUpRight size={14}/></button>
        <button className="button button-primary" disabled={busy || locked || !share} onClick={() => act('REQUEST_RM')}>{busy ? 'Saving…' : 'Request RM help'}</button>
      </div>
      {!share && <small>Turn on request sharing below to ask your RM. You can explore privately.</small>}
    </>}
    <details className="nudge-evidence"><summary>Why this suggestion?</summary><p>{nudge.why}</p><SourceExcerpt source={nudge.source}/><SourceExcerpt source={nudge.knowledge}/><small>Exploring is not purchase interest. An RM request asks for a conversation only. Synthetic context.</small></details>
    {error && <Notice tone="bad">{error}<button className="text-link" onClick={refresh}>Check current suggestion</button></Notice>}
  </section>;
}

export function CustomerNudges({personId, share, locked, explore, requested}: {
  personId: string; share: boolean; locked: boolean;
  explore: (text: string) => void; requested: (signal: string) => void;
}) {
  const q = useRM<RMNudges>(`/v1/rm/chat/${personId}/nudges`, 5000);
  if (q.error) return <Notice tone="warn">Suggestions unavailable.<button className="text-link" onClick={q.refresh}>Check again</button></Notice>;
  return <>{q.data?.nudges.map(n => <Suggestion key={n.id + '-' + n.version} nudge={n} share={share} locked={locked} explore={explore} requested={requested} refresh={q.refresh}/>)}</>;
}
