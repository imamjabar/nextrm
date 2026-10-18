"use client";
import {useEffect,useState,Suspense} from 'react';import Link from 'next/link';import {useSearchParams,useRouter} from 'next/navigation';import {ArrowLeft,ChevronDown,FileText} from 'lucide-react';
import {CustomerBehavior} from '@/components/rm/CustomerBehavior';
import {RelationshipBrief} from '@/components/rm/RelationshipBrief';
import {CustomerSnapshot} from '@/components/rm/CustomerSnapshot';
import {AssistantDock,AssistantPanel} from '@/components/rm/AssistantPanel';
import {fetchApi} from '@/lib/api';import {PageTitle,Status,Notice,Field} from '@/components/ui/Workspace';
import {useRM,RequestState,SourceExcerpt,JourneyLink,requestKey,prefetchRelationship} from '@/components/rm/shared';import {label,dateLabel,timeAgo} from '@/lib/presentation';
import {contactSummary} from '@/components/rm/ContactPreference';
import {sortNeeds,NEED_GROUPS,SOURCE_PHRASE,urgencyChip,needStep} from '@/lib/needs';
import type {RMPartyDetail,RMSignal,RMReview,RMJourney,RMSource,RMCopilotAction,RMCopilotRef} from '@/lib/rm.generated';
const STEP_CHIP=['Dismissed','To check','Plan follow-up','Follow-up in progress','Done'];
function NeedRow({signal,source,journey,first,open,toggle,reload}:{signal:RMSignal;source:RMSource|undefined;journey:RMJourney|undefined;first:string;open:boolean;toggle:()=>void;reload:()=>void}){
 const router=useRouter();
 const [need,setNeed]=useState(signal.need),[reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(signal.confirmed),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [mode,setMode]=useState<''|'edit'|'dismiss'>('');
 const locked=['IN_PROGRESS','COMPLETED','DISMISSED'].includes(signal.workflow);
 const supported=['CUSTOMER_MESSAGE','SIMULATED_CUSTOMER_MESSAGE','CUSTOMER_RM_REQUEST'].includes(source?.kind||'')&&need===signal.need;
 const chat=(signal.origin==='CHAT'||signal.origin==='REQUEST')&&!!source;
 const happened=chat?source!.content:signal.need;
 const meaning=chat&&signal.need.trim().toLowerCase().replace(/[.!?"“”]+$/,'')!==happened.trim().toLowerCase().replace(/[.!?"“”]+$/,'')?signal.need:'';
 const urg=urgencyChip(signal.urgency);
 const {step,next}=needStep(signal);
 const review=async(decision:RMReview['decision'])=>{setError('');setBusy(true);try{await fetchApi(`/v1/rm/signals/${signal.id}/review`,{method:'POST',body:JSON.stringify({base_version:signal.version,decision,reason,need:decision==='EDITED'?need:null,confirmed:supported&&confirmed})});setMode('');reload();}catch(e:any){setError(e.message);}finally{setBusy(false);}};
 const follow=async()=>{setBusy(true);setError('');try{const x=await fetchApi<RMJourney>(`/v1/rm/signals/${signal.id}/follow-up`,{method:'POST',body:JSON.stringify({base_version:signal.version,request_key:requestKey()})});router.push('/follow-ups/'+x.id);}catch(e:any){setError(e.message);}finally{setBusy(false);}};
 const body='need-body-'+signal.id;
 return <section className="need-row" data-open={open||undefined} id={'signal-'+signal.id} tabIndex={-1}>
  <button type="button" className="need-row-head" aria-expanded={open} aria-controls={body} onClick={toggle}>
   <span className="need-row-main"><strong>{signal.title}</strong><span className="need-row-snippet">{chat?`“${happened}”`:happened}</span></span>
   <span className="need-row-side">{urg&&<Status tone={urg.tone}>{urg.text}</Status>}{signal.display_label==='Hot lead'&&<Status tone="good">Hot lead</Status>}<span className="need-chip" data-step={step}>{STEP_CHIP[step]}</span><span className="need-time">{timeAgo(signal.created_at)}</span><ChevronDown size={16} aria-hidden="true"/></span>
  </button>
  {open&&<div className="need-row-body" id={body}>
   <div className="need-what">{chat?<blockquote>“{happened}”</blockquote>:<p>{happened}</p>}<small>{chat?`${first} ${SOURCE_PHRASE[signal.origin]}`:SOURCE_PHRASE[signal.origin]}{source?' · '+dateLabel(source.event_at):''}</small></div>
   {meaning&&<p className="need-line"><span>Means</span>{meaning}</p>}
   {signal.contact_method&&<p className="need-line"><span>Reach</span>{contactSummary(signal.contact_method,signal.contact_window)} ({first||'Customer'}&apos;s choice)</p>}
   <p className="need-line"><span>Next</span>{next}</p>
   {step===1&&<>{supported&&<label className="check-label"><input type="checkbox" disabled={locked||busy} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>These are {first}&apos;s own words</span></label>}
    <div className="action-row"><button type="button" className="button button-primary" disabled={busy||locked||(signal.review==='ACCEPTED'&&need===signal.need&&confirmed===signal.confirmed)} onClick={()=>review('ACCEPTED')}>{busy?'Recording…':'Looks right'}</button><button type="button" className="button" aria-pressed={mode==='edit'} disabled={busy||locked} onClick={()=>setMode(m=>m==='edit'?'':'edit')}>Correct it</button><button type="button" className="button button-quiet" aria-pressed={mode==='dismiss'} disabled={busy||locked} onClick={()=>setMode(m=>m==='dismiss'?'':'dismiss')}>Not relevant</button></div>
    {mode==='edit'&&<div className="need-edit-block"><Field label="Corrected need"><textarea className="control" rows={3} disabled={locked||busy} value={need} onChange={e=>{setNeed(e.target.value);setConfirmed(false);}}/></Field><Field label="Why"><input className="control" disabled={locked||busy} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Required for a correction"/></Field><button type="button" className="button" disabled={busy||locked||reason.trim().length<3||need===signal.need} onClick={()=>review('EDITED')}>Save correction</button></div>}
    {mode==='dismiss'&&<div className="need-dismiss-block"><Field label="Why"><input className="control" disabled={locked||busy} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Required to dismiss"/></Field><button type="button" className="button button-quiet" disabled={busy||locked||reason.trim().length<3} onClick={()=>review('REJECTED')}>Dismiss</button></div>}</>}
   {step===2&&<div className="action-row"><button type="button" className="button button-primary" disabled={busy} onClick={follow}><FileText size={16}/> Prepare follow-up</button><span className="need-hint">You get a draft and a call script. Nothing is sent to {first}.</span></div>}
   {step>=3&&journey&&<div className="action-row"><Link className={'button'+(step===3?' button-primary':'')} href={'/follow-ups/'+journey.id}>Open follow-up</Link>{journey.due_at&&<span className="need-hint">Due {dateLabel(journey.due_at)}</span>}</div>}
   {error&&<Notice tone="bad">{error}<button className="text-link ml-3" onClick={reload}>Reload current version</button></Notice>}
   <details className="need-why"><summary>Why NextRM flagged this</summary><div className="need-why-content">{signal.rationale&&<p>{signal.rationale}</p>}{signal.uncertainty&&<p>{signal.uncertainty}</p>}<small className="need-why-meta">{label(signal.evidence)} · {label(signal.workflow)} · Review {label(signal.review)} · v{signal.version}</small>{source&&<SourceExcerpt source={source}/>}</div></details>
  </div>}
 </section>;
}
function RelationshipView({params}:{params:{id:string}}){
 const q=useRM<RMPartyDetail>('/v1/rm/parties/'+params.id,0);const [noteDraft,setNoteDraft]=useState<{text:string;key:number}|null>(null);
 const signalParam=useSearchParams().get('signal');
 const [chosenTab,setTab]=useState<string|null>(null),[openId,setOpenId]=useState<string|null>(null);
 const sorted=q.data?sortNeeds(q.data.signals):[];
 const active=sorted.filter(s=>{const n=needStep(s).step;return n>=1&&n<=3;}),closed=sorted.filter(s=>!active.includes(s));
 const tab=chosenTab??(signalParam||active.length?'needs':'overview');
 const expanded=openId??(signalParam&&sorted.some(s=>s.id===signalParam)?signalParam:active[0]?.id??'');
 const reveal=(id:string)=>{setTab('needs');setOpenId(id);requestAnimationFrame(()=>requestAnimationFrame(()=>{const el=document.getElementById('signal-'+id);el?.scrollIntoView({block:'start'});el?.focus({preventScroll:true});}));};
 useEffect(()=>{if(q.data&&signalParam&&sorted.some(s=>s.id===signalParam))reveal(signalParam);},[q.data?.party.id,signalParam]);
 const onAction=(a:RMCopilotAction)=>{if(a.kind==='NOTE'&&a.text){setTab('overview');setNoteDraft({text:a.text,key:Date.now()});return true;}if(a.kind==='FOLLOW_UP'&&a.record_id){reveal(a.record_id);return true;}return false;};
 const onRef=(r:RMCopilotRef)=>{if(r.record_type==='signal'&&r.record_id){reveal(r.record_id);return true;}if(r.record_type==='note'){setTab('history');return true;}if(['snapshot','chat','party','policy'].includes(r.record_type)){setTab('overview');return true;}return false;};
 const d=q.data,first=d?(d.party.kind==='PERSON'?d.party.name.split(' ')[0]:d.party.name):'';
 const row=(s:RMSignal)=><NeedRow key={s.id+'-'+s.version} signal={s} source={d?.sources.find(x=>x.id===s.source_id)} journey={d?.journeys.find(j=>j.signal_id===s.id)} first={first} open={expanded===s.id} toggle={()=>setOpenId(expanded===s.id?'':s.id)} reload={q.refresh}/>;
 const looseJourneys=d?d.journeys.filter(j=>!d.signals.some(s=>s.id===j.signal_id)):[];
 const tabs=[{id:'needs',label:'Needs',count:active.length},{id:'overview',label:'Overview'},{id:'behavior',label:'Behavior'},{id:'history',label:'Notes & history'}];
 return <AssistantDock label="Ask copilot" panel={(close,focus)=><AssistantPanel surface="RM" partyId={params.id} baseVersion={d?.party.version??null} subject={first||'this relationship'} onClose={close} autoFocus={focus} onReload={q.refresh} onAction={onAction} onRef={onRef}/>}>
  <Link className="text-link mb-5" href="/retention"><ArrowLeft size={15}/> Relationship work</Link><RequestState error={q.error} data={d} retry={q.refresh}/>
  {d&&<>
   <PageTitle title={d.party.name} description={`${d.party.kind==='PERSON'?'Person':'Business'} · ${d.party.segment.replace('_',' ').toLowerCase()} · ${d.party.locality} · ${label(d.party.relationship).toLowerCase()}`} action={<Link className="button" href="/follow-ups"><FileText size={16}/> All follow-ups</Link>}/>
   <p className="rel-facts"><span>Identity {label(d.party.identity).toLowerCase()}</span><span>Contact {label(d.party.contact).toLowerCase()}</span><span>RM {d.party.owner_name}</span><span>{d.party.products.length?'Holds '+d.party.products.join(', ').toLowerCase():'No product context'}</span></p>
   <nav className="customer-detail-tabs" aria-label="Customer information">{tabs.map(v=><button key={v.id} aria-current={tab===v.id?'page':undefined} onClick={()=>setTab(v.id)}>{v.label}{v.count?<span className="tab-count">{v.count}</span>:null}</button>)}</nav>
   <div hidden={tab!=='needs'} className="need-list">
    {active.length===0&&<section className="rm-primary-section"><h2>Nothing to act on</h2><p>{d.party.declared_goal||`No open need for ${first}. Start with a permitted discussion.`}</p></section>}
    {NEED_GROUPS.map(g=>{const rows=active.filter(s=>s.group===g.key);return rows.length?<div key={g.key} className="need-group"><h3>{g.title}<span>{rows.length}</span></h3>{rows.map(row)}</div>:null;})}
    {looseJourneys.length>0&&<div className="need-group"><h3>Other follow-ups<span>{looseJourneys.length}</span></h3>{looseJourneys.map(j=><JourneyLink key={j.id} journey={j}/>)}</div>}
    {closed.length>0&&<details className="need-closed"><summary>Done or dismissed ({closed.length})</summary>{closed.map(row)}</details>}
   </div>
   <div hidden={tab!=='overview'}>{d.party.kind==='PERSON'&&d.party.relationship==='EXISTING_CUSTOMER'&&<CustomerSnapshot partyId={d.party.id} firstName={first}/>}<RelationshipBrief partyId={d.party.id} partyVersion={d.party.version} reload={q.refresh} noteDraft={noteDraft}/></div>
   <div hidden={tab!=='behavior'}><CustomerBehavior partyId={d.party.id}/></div>
   <aside className="rm-side-section" hidden={tab!=='history'}><h2>Sources and relationship context</h2><p className="text-xs text-muted mb-4">Sources stay linked to the original message or event. Synthetic institution data.</p>{d.sources.map(s=><SourceExcerpt key={s.id} source={s}/>)}{d.party.contacts.length>0&&<><h3 className="mt-6">People connected to the business</h3>{d.party.contacts.map(c=><div key={c.id} className="contact-person"><strong>{c.name}</strong><p>{c.role}</p><small>{c.email} · {c.authority}</small></div>)}<p className="text-xs text-muted mt-3">A business contact role does not grant private personal-account access.</p></>}{d.internal_note&&<details className="source-excerpt mt-5"><summary>Internal RM note</summary><p>{d.internal_note}</p><small>Staff-only projection. Excluded from customer chat/model context.</small></details>}<h3 className="mt-6">Review history</h3>{d.review_history.length?d.review_history.map(e=><details key={e.id} className="source-excerpt"><summary>{label(e.action)} <small>{dateLabel(e.at)}</small></summary><p>{e.reason}</p><pre className="review-json">{JSON.stringify({before:e.before,after:e.after},null,2)}</pre></details>):<p className="text-secondary text-sm mt-2">No review recorded yet.</p>}</aside>
  </>}
 </AssistantDock>;
}
export default function Relationship({params}:{params:{id:string}}){
 useEffect(()=>{prefetchRelationship(params.id);},[params.id]);
 return <Suspense fallback={null}><RelationshipView params={params}/></Suspense>;
}
