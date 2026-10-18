"use client";
import {useState} from 'react';
import Link from 'next/link';
import {Search, MessageSquare, ArrowUpRight, ListFilter} from 'lucide-react';
import {SharedPool} from '@/components/rm/SharedPool';
import {PageTitle, Status, Empty} from '@/components/ui/Workspace';
import {useRM, RequestState, SignalRows, PersonName, Mode} from '@/components/rm/shared';
import type {RMSignals} from '@/lib/rm.generated';

export default function Retention() {
  const q = useRM<RMSignals>('/v1/rm/signals', 5000);
  const [search, setSearch] = useState(''), [filter, setFilter] = useState('active'), [view, setView] = useState('signals');
  const all = q.data?.signals || [];
  const active = all.filter(s => !['COMPLETED', 'DISMISSED'].includes(s.workflow));
  const matches = (s: typeof all[number]) => filter === 'all' || filter === 'active' && active.includes(s) || filter === 'review' && s.review === 'PROPOSED' && active.includes(s) || filter === 'ready' && ['ACCEPTED', 'EDITED'].includes(s.review) && s.workflow === 'REVIEWED' || s.category === filter && active.includes(s);
  const visible = all.filter(s => (s.name + ' ' + s.need + ' ' + s.title).toLowerCase().includes(search.toLowerCase()) && matches(s));
  const people = (q.data?.parties || []).filter(p => (p.name + ' ' + p.locality).toLowerCase().includes(search.toLowerCase()));
  const counters = [
    {key: 'active', title: 'Active needs', count: active.length},
    {key: 'review', title: 'Awaiting your review', count: active.filter(s => s.review === 'PROPOSED').length},
    {key: 'SERVICE_ISSUE', title: 'Service help', count: active.filter(s => s.category === 'SERVICE_ISSUE').length},
    {key: 'ready', title: 'Ready for follow-up', count: active.filter(s => ['ACCEPTED', 'EDITED'].includes(s.review) && s.workflow === 'REVIEWED').length},
  ];
  return <><Mode/><PageTitle title="Existing customers." description="Review what the customer actually said, then make the next conversation useful." action={<Link className="button button-primary" href="/follow-ups"><ArrowUpRight size={16}/> My follow-ups</Link>}/>
    {q.data && <div className="queue-counters">{counters.map(c => <button key={c.key} aria-pressed={filter === c.key && view === 'signals'} onClick={() => {setFilter(c.key); setView('signals');}}><span>{c.title}</span><strong>{c.count}</strong><small>{c.key === 'SERVICE_ISSUE' ? 'Help comes before sales' : 'Open this queue'} <ArrowUpRight size={13}/></small></button>)}</div>}
    <div className="rm-toolbar"><label className="rm-search"><Search size={17}/><input aria-label="Search existing customers" value={search} onChange={e => setSearch(e.target.value)} placeholder="Person, need or locality"/></label><select className="control !w-auto" aria-label="Signal category" value={filter} disabled={view === 'people'} onChange={e => setFilter(e.target.value)}><option value="active">All active needs</option><option value="review">Awaiting review</option><option value="ready">Ready for follow-up</option><option value="SERVICE_ISSUE">Service issues</option><option value="OPPORTUNITY">Opportunities</option><option value="GUIDANCE">Guidance</option><option value="RESEARCH">Research</option><option value="all">All history</option></select><div className="rm-segmented"><button aria-pressed={view === 'signals'} onClick={() => setView('signals')}>Needs</button><button aria-pressed={view === 'people'} onClick={() => setView('people')}>Customers</button><button aria-pressed={view === 'pool'} onClick={()=>setView('pool')}>Shared pool</button></div></div>
    <RequestState error={q.error} data={q.data} retry={q.refresh}/>
    {view==='pool'?<SharedPool/>:q.data && <section className="rm-primary-section"><div className="queue-heading"><div><h2>{view === 'signals' ? 'Your next conversations' : 'Your relationships'}</h2><p>{view === 'signals' ? `${visible.length} matching needs · Urgent service, evidence and freshness guide the order.` : `${people.length} matching people · Assigned relationships only.`}</p></div><ListFilter size={19}/></div>
      {view === 'signals' ? <SignalRows signals={visible}/> : <div className="relationship-rows">{people.length ? people.map(p => <Link key={p.id} className="relationship-row" href={`/relationships/${p.id}`}><PersonName party={p}/><div className="row-content"><p>{p.declared_goal || 'Confirm the current need before suggesting a product.'}</p><small>{p.products.join(' · ') || 'Authorized product context unavailable'}</small></div><Status tone={p.contact === 'ALLOWED' ? 'neutral' : 'warn'}>{p.contact === 'ALLOWED' ? 'Permitted purpose' : 'Contact restricted'}</Status></Link>) : <Empty title="No matching people">Try another name or locality.</Empty>}</div>}
    </section>}
  </>;
}
