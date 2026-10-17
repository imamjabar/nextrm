"use client";
import Link from 'next/link';
import {MessageSquare, ArrowUpRight, MapPin, Activity, Clock, CheckCircle2, Users} from 'lucide-react';
import {PageTitle, Status} from '@/components/ui/Workspace';
import {useRM, RequestState, SignalRows, PersonName, Mode, JourneyLink} from '@/components/rm/shared';
import type {RMHome, RMPulse} from '@/lib/rm.generated';

export default function Workspace() {
  const q = useRM<RMHome>('/v1/rm/home', 4000);
  const pulse = useRM<RMPulse>('/v1/rm/pulse', 4000);
  const shortlist = (q.data?.prospect_preview || []).filter(p => ['READY_FOR_DISCUSSION', 'REVIEW_FIRST', 'REVIEW'].includes(p.priority_tier));
  const overdue = (pulse.data?.followups || []).filter(t => t.due_at && new Date(t.due_at).getTime() < Date.now());
  return <><Mode provider={q.data?.provider}/><PageTitle title="Today’s relationship briefing." description="Your relationship desk: customer needs, promising conversations and the follow-through they deserve." action={<Link className="button button-primary" href="/retention"><Users size={17}/> Review customer needs</Link>}/>
    <RequestState error={q.error} data={q.data} retry={q.refresh}/>
    {q.data && <>
      <div className="desk-summary"><span><CheckCircle2 size={16}/> Assigned to you</span><p>{q.data.customers} customer relationships · {q.data.prospects} supplied prospects · {q.data.open_followups} open follow-ups</p><Link className="text-link" href="/pulse">Relationship pulse <ArrowUpRight size={14}/></Link></div>
      <div className="rm-home-grid">
        <section className="rm-primary-section"><div className="section-title"><div><span className="eyebrow">01 / Existing relationships</span><h2>Who needs your help?</h2></div><Status tone={pulse.data?.urgent_service ? 'warn' : 'neutral'}>{pulse.data ? pulse.data.needs_review + ' to review' : q.data.open_signals + ' open'}</Status></div><p className="section-context">Service urgency comes first. Review each need against what the customer said.</p><SignalRows signals={q.data.signals}/><Link className="button button-quiet desk-view-all" href="/retention">Open all customer needs <ArrowUpRight size={15}/></Link></section>
        <section className="rm-side-section"><div className="section-title"><div><span className="eyebrow">02 / New relationships</span><h2>Who should you meet?</h2></div><MapPin size={19}/></div><p className="section-context">A sourced shortlist, ordered by permission, freshness and a reviewable need.</p><div className="prospect-shortlist">{shortlist.length ? shortlist.map(p => <Link key={p.id} href={'/acquisition?selected=' + p.id}><PersonName party={p.party}/><p>{p.reasons[0]}</p><small className="prospect-next-label">{p.next_action} <ArrowUpRight size={13}/></small></Link>) : <p className="section-context">No actionable prospect in this preview. Review all assigned sources and held records.</p>}</div><Link href="/acquisition" className="button button-quiet desk-view-all">Explore acquisition & POI <ArrowUpRight size={16}/></Link></section>
      </div>
      <section className="desk-followthrough"><div className="section-title"><div><span className="eyebrow">03 / Follow-through</span><h2>{overdue.length ? 'Bring overdue work back into focus.' : 'Keep your promises in view.'}</h2></div><Link className="text-link" href="/follow-ups"><Clock size={16}/> Open follow-ups</Link></div>{pulse.error ? <RequestState error={pulse.error} data={pulse.data} retry={pulse.refresh}/> : !pulse.data ? <p className="section-context">Checking your follow-up records…</p> : pulse.data.followups.length ? (overdue.length ? overdue : pulse.data.followups).slice(0,3).map(j => <JourneyLink key={j.id} journey={j}/>) : <p className="section-context">Review a customer or prospect need, then prepare an RM follow-up. Notes and due dates stay attached to the source.</p>}</section>
      <section className="rm-workflow-note"><MessageSquare size={20}/><div><h3>Help → Evidence → Review → Prepare</h3><p>The customer stays in control. The RM gets the source and a useful next step.</p></div><Link href="/follow-ups" className="text-link">Open my follow-up plan <ArrowUpRight size={16}/></Link></section>
    </>}
  </>;
}
