"use client";
import {useState} from 'react';
import Link from 'next/link';
import {Search} from 'lucide-react';
import {PageTitle, Empty} from '@/components/ui/Workspace';
import {useRM, RequestState, JourneyLink} from '@/components/rm/shared';
import type {RMJourneys} from '@/lib/rm.generated';

export default function Followups() {
  const q = useRM<RMJourneys>('/v1/rm/follow-ups', 5000);
  const [view, setView] = useState('open'), [search, setSearch] = useState('');
  const tasks = q.data?.journeys || [];
  const open = tasks.filter(t => !['DONE', 'CANCELLED'].includes(t.status));
  const snoozed = open.filter(t => t.snoozed_until && new Date(t.snoozed_until).getTime() > Date.now());
  const overdue = open.filter(t => t.due_at && new Date(t.due_at).getTime() < Date.now());
  const rows = (view === 'snoozed' ? snoozed : view === 'overdue' ? overdue : view === 'history' ? tasks.filter(t => ['DONE', 'CANCELLED'].includes(t.status)) : open)
    .filter(t => (t.name + ' ' + t.need).toLowerCase().includes(search.toLowerCase()))
    .sort((a,b) => (a.due_at ? new Date(a.due_at).getTime() : Infinity) - (b.due_at ? new Date(b.due_at).getTime() : Infinity));
  return <><PageTitle title="A request deserves follow-through." description="Prepare the conversation, set a due date and record what you did. Done means RM work recorded." action={<Link className="button" href="/retention">Review customer needs</Link>}/>
    <div className="rm-toolbar"><div className="rm-segmented">{[{key:'open', title:'Open', count:open.length},{key:'overdue', title:'Overdue', count:overdue.length},{key:'snoozed', title:'Snoozed', count:snoozed.length},{key:'history', title:'History', count:tasks.length-open.length}].map(v => <button key={v.key} aria-pressed={view === v.key} onClick={() => setView(v.key)}>{v.title} · {v.count}</button>)}</div><label className="rm-search"><Search size={17}/><input aria-label="Search follow-ups" value={search} onChange={e => setSearch(e.target.value)} placeholder="Person or discussion need"/></label></div>
    <RequestState error={q.error} data={q.data} retry={q.refresh}/>
    {q.data && <section className="rm-primary-section"><div className="queue-heading"><div><h2>{view === 'history' ? 'Recorded work' : view === 'overdue' ? 'Needs your attention' : 'Your follow-up plan'}</h2><p>{rows.length} matching follow-ups · Due dates first · Drafts are not sent.</p></div></div>{rows.length ? rows.map(x => <JourneyLink key={x.id} journey={x}/>) : <Empty title={search ? 'No matching follow-ups' : view === 'overdue' ? 'No overdue follow-ups' : view === 'history' ? 'No completed or cancelled work yet' : 'Your follow-up plan is clear'}>Review a sourced need in Existing customers or Acquisition, then choose Prepare RM follow-up.</Empty>}</section>}
  </>;
}
