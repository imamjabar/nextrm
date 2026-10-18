"use client";
import {useRef,useEffect,useState} from 'react';
import Link from 'next/link';
import {ChevronRight} from 'lucide-react';
import {PersonMark,prefetchRelationship} from '@/components/rm/shared';
import {Status} from '@/components/ui/Workspace';
import {NEED_GROUPS,SOURCE_PHRASE,urgencyChip,needStep} from '@/lib/needs';
import {timeAgo,dateLabel,label} from '@/lib/presentation';
import type {RMToday,RMTodayNeed,RMFeedItem,RMJourney,RMProspect,RMTodayCustomer} from '@/lib/rm.generated';
function getGreeting(rmName:string):{greeting:string;dateStr:string}{
 const dateStr=new Intl.DateTimeFormat('en-GB',{weekday:'long',day:'numeric',month:'long',timeZone:'Asia/Jakarta'}).format(new Date());
 const hourStr=new Intl.DateTimeFormat('en-GB',{hour:'numeric',hourCycle:'h23',timeZone:'Asia/Jakarta'}).format(new Date());
 const hour=Number.parseInt(hourStr,10);
 const timeGreeting=hour<12?'Good morning':hour<18?'Good afternoon':'Good evening';
 const firstName=rmName?rmName.trim().split(/\s+/)[0]:'RM';
 return {greeting:`${timeGreeting}, ${firstName}`,dateStr};
}

function getSummary(counts:RMToday['counts']):string{
 const parts:string[]=[];
 if(counts.needs_to_review>0)parts.push(`${counts.needs_to_review} ${counts.needs_to_review===1?'need':'needs'} to review`);
 if(counts.urgent_service>0)parts.push(`${counts.urgent_service} urgent service`);
 if(counts.followups_overdue>0)parts.push(`${counts.followups_overdue} overdue ${counts.followups_overdue===1?'follow-up':'follow-ups'}`);
 if(!parts.length)return 'Your book is clear. A good moment for prospects.';
 const sentence=parts.join(', ')+'.';
 return sentence.charAt(0).toUpperCase()+sentence.slice(1);
}

export function ActivityItem({item,isNew}:{item:RMFeedItem;isNew?:boolean}){
 return (
  <li className="today-feed-row">
   <div className="today-avatar-wrap">
    <PersonMark name={item.name}/>
   </div>
   <div className="today-feed-content">
    <Link
     className="today-feed-title"
     href={`/relationships/${item.party_id}`}
     onPointerEnter={()=>prefetchRelationship(item.party_id)}
     onFocus={()=>prefetchRelationship(item.party_id)}
    >
     {item.title}
    </Link>
    <p className="today-feed-text">{item.kind==='CHAT'?`“${item.text}”`:item.text}</p>
   </div>
   <div className="today-feed-meta">
    <span className="today-feed-time">{timeAgo(item.at)}</span>
    {item.signal_id&&(
     <Link
      className="today-feed-action"
      href={`/relationships/${item.party_id}?signal=${item.signal_id}`}
      onPointerEnter={()=>prefetchRelationship(item.party_id)}
      onFocus={()=>prefetchRelationship(item.party_id)}
     >
      Raised a need
     </Link>
    )}
    {isNew&&<Status tone="neutral">New</Status>}
   </div>
  </li>
 );
}

function QueueRow({item}:{item:RMTodayNeed}){
 const s=item.signal;
 const urgency=urgencyChip(s.urgency);
 const step=needStep(s);
 return (
  <Link
   className="today-row"
   href={`/relationships/${s.party_id}?signal=${s.id}`}
   onPointerEnter={()=>prefetchRelationship(s.party_id)}
   onFocus={()=>prefetchRelationship(s.party_id)}
  >
   <div className="today-avatar-wrap">
    <PersonMark name={s.name}/>
   </div>
   <div className="today-row-content">
    <div className="today-row-top">
     <span className="today-row-ident"><strong>{s.name}</strong> · {SOURCE_PHRASE[s.origin]}</span>
     <span className="today-row-time">{timeAgo(s.created_at)}</span>
    </div>
    <div className="today-row-title">{s.title}</div>
    <p className="today-row-need">{s.origin==='CHAT'&&item.quote?`“${item.quote}”`:s.need}</p>
    <div className="today-row-chips">
     {urgency&&<Status tone={urgency.tone}>{urgency.text}</Status>}
     <Status tone={step.step===2?'good':step.step===1?'warn':'neutral'}>{step.status}</Status>
     {s.display_label==='Hot lead'&&<Status tone="good">Hot lead</Status>}
    </div>
   </div>
   <ChevronRight size={16} className="today-row-chevron" aria-hidden="true"/>
  </Link>
 );
}

function FollowupRow({journey}:{journey:RMJourney}){
 const isOverdue=Boolean(journey.due_at&&new Date(journey.due_at).getTime()<Date.now());
 return (
  <Link className="today-sub-row" href={`/follow-ups/${journey.id}`}>
   <div className="today-sub-content">
    <strong>{journey.name}</strong>
    <p className="today-sub-need">{journey.need}</p>
   </div>
   <div className="today-sub-chips">
    {isOverdue?(
     <span className="today-chip" data-tone="bad">Overdue · due {dateLabel(journey.due_at)}</span>
    ):journey.due_at?(
     <span className="today-chip">Due {dateLabel(journey.due_at)}</span>
    ):(
     <span className="today-chip">No due date</span>
    )}
    <span className="today-chip">{label(journey.status)}</span>
   </div>
  </Link>
 );
}

function ProspectRow({prospect}:{prospect:RMProspect}){
 return (
  <Link className="today-sub-row" href={`/acquisition?selected=${prospect.id}`}>
   <div className="today-avatar-wrap">
    <PersonMark name={prospect.party.name} kind={prospect.party.kind}/>
   </div>
   <div className="today-sub-content">
    <strong>{prospect.party.name}</strong>
    <p className="today-sub-need">{prospect.reasons[0]||prospect.need}</p>
   </div>
   <div className="today-sub-chips">
    <span className="today-chip">{label(prospect.priority_tier)}</span>
   </div>
  </Link>
 );
}

export function TodayDesk({data}:{data:RMToday}){
 const {greeting,dateStr}=getGreeting(data.rm_name);
 const summary=getSummary(data.counts);
 const initialIds=useRef<Set<string>|null>(null);
 const [expandedGroups,setExpandedGroups]=useState<Record<string,boolean>>({});
 const [showAllActivity,setShowAllActivity]=useState(false);

 useEffect(()=>{
  if(initialIds.current===null&&data?.activity){
   initialIds.current=new Set(data.activity.map(x=>x.id));
  }
 },[data?.activity]);

 const groups=NEED_GROUPS.map(g=>({
  ...g,
  items:data.queue.filter(item=>item.signal.group===g.key),
 })).filter(g=>g.items.length>0);

 const visibleActivity=showAllActivity?data.activity:data.activity.slice(0,5);

 return (
  <div className="today-desk">
   <header className="today-head">
    <div>
     <span className="today-eyebrow">{dateStr}</span>
     <h1>{greeting}</h1>
     <p className="today-summary">{summary}</p>
    </div>
    <span className="today-live"><i aria-hidden="true"/>Live · updated {timeAgo(data.generated_at)}</span>
   </header>

   <div className="today-kpis">
    <Link className="today-kpi" href="/retention">
     <span className="today-kpi-label">To review</span>
     <strong className="today-kpi-val">{data.counts.needs_to_review}</strong>
     <span className={`today-kpi-foot ${data.counts.urgent_service>0?'today-foot-warn':''}`}>{data.counts.urgent_service} urgent service</span>
    </Link>
    <Link className="today-kpi" href="/follow-ups">
     <span className="today-kpi-label">Follow-ups</span>
     <strong className="today-kpi-val">{data.counts.followups_open}</strong>
     <span className={`today-kpi-foot ${data.counts.followups_overdue>0?'today-foot-bad':''}`}>{data.counts.followups_overdue>0?`${data.counts.followups_overdue} overdue`:'None overdue'}</span>
    </Link>
    <Link className="today-kpi" href="#activity">
     <span className="today-kpi-label">Conversations today</span>
     <strong className="today-kpi-val">{data.counts.conversations_today}</strong>
     <span className="today-kpi-foot">across {data.counts.customers} customers</span>
    </Link>
    <Link className="today-kpi" href="/acquisition">
     <span className="today-kpi-label">Prospects ready</span>
     <strong className="today-kpi-val">{data.counts.prospects_ready}</strong>
     <span className="today-kpi-foot">Sourced and permitted</span>
    </Link>
   </div>

   <div className="today-board">
    <section className="today-section">
     <div className="today-section-head">
      <div className="today-section-title">
       <h2>Who needs you first</h2>
       <Status>{data.counts.needs_open}</Status>
      </div>
      <Link className="today-section-link" href="/retention">All needs</Link>
     </div>
     {groups.length>0?(
      groups.map(g=>{
       const isExpanded=Boolean(expandedGroups[g.key]);
       const visible=isExpanded?g.items:g.items.slice(0,3);
       const remaining=g.items.length-3;
       return (
        <div className="today-group" key={g.key}>
         <div className="today-group-head">
          <h3>{g.title}</h3>
          <Status>{g.items.length}</Status>
         </div>
         <p className="today-group-hint">{g.hint}</p>
         <div className="today-queue">
          {visible.map(item=><QueueRow key={item.signal.id} item={item}/>)}
         </div>
         {remaining>0&&(
          <button
           type="button"
           className="today-more"
           onClick={()=>setExpandedGroups(prev=>({...prev,[g.key]:!prev[g.key]}))}
          >
           {isExpanded?'Show less':`Show ${remaining} more`}
          </button>
         )}
        </div>
       );
      })
     ):(
      <p className="today-empty">Nothing waiting. New customer requests appear here within seconds.</p>
     )}
    </section>

    <div className="today-board-side">
     <section className="today-section" id="activity">
      <div className="today-section-head">
       <div className="today-section-title">
        <h2>What customers are doing</h2>
        <span className="today-chip today-chip-live"><i aria-hidden="true"/>Live</span>
       </div>
       <p className="today-caption">Shared by bank policy. Private chats never appear here.</p>
      </div>
      {data.activity.length>0?(
       <>
        <ol className="today-feed" aria-live="polite" aria-relevant="additions">
         {visibleActivity.map(item=>(
          <ActivityItem key={item.id} item={item} isNew={Boolean(initialIds.current&&!initialIds.current.has(item.id))}/>
         ))}
        </ol>
        {data.activity.length>5&&(
         <button
          type="button"
          className="today-more"
          onClick={()=>setShowAllActivity(v=>!v)}
         >
          {showAllActivity?'Show less':`Show all ${data.activity.length}`}
         </button>
        )}
       </>
      ):(
       <p className="today-empty">No customer activity yet. Chats and app events appear here as they happen.</p>
      )}
     </section>

     <section className="today-section">
      <div className="today-section-head">
       <div className="today-section-title">
        <h2>Your customers</h2>
        <Status>{data.customers.length}</Status>
       </div>
      </div>
      {data.customers.length>0?(
       <ul className="today-people">
        {data.customers.map(c=>{
         const p=c.party;
         const occ=p.occupation||'';
         return (
          <li key={p.id}>
           <Link
            className="today-person-row"
            href={`/relationships/${p.id}`}
            onPointerEnter={()=>prefetchRelationship(p.id)}
            onFocus={()=>prefetchRelationship(p.id)}
           >
            <div className="today-avatar-wrap">
             <PersonMark name={p.name} kind={p.kind}/>
            </div>
            <div className="today-person-content">
             <strong>{p.name}</strong>
             <span className="today-person-sub">{occ?`${occ} · ${label(p.segment)}`:label(p.segment)}</span>
            </div>
            <div className="today-person-meta">
             {c.open_needs>0&&<Status tone="warn">{c.open_needs} open</Status>}
             <span className="today-person-time">{c.last_activity_at?timeAgo(c.last_activity_at):'No recent activity'}</span>
            </div>
           </Link>
          </li>
         );
        })}
       </ul>
      ):(
       <p className="today-empty">No assigned customers in your book.</p>
      )}
     </section>
    </div>
   </div>
   <div className="today-twoup">
    <section className="today-section">
     <div className="today-section-head">
      <div className="today-section-title">
       <h2>Follow-ups due</h2>
      </div>
      <Link className="today-section-link" href="/follow-ups">All follow-ups</Link>
     </div>
     {data.followups.length>0?(
      <div className="today-sub-list">
       {data.followups.slice(0,5).map(j=><FollowupRow key={j.id} journey={j}/>)}
      </div>
     ):(
      <p className="today-empty">No follow-ups due.</p>
     )}
    </section>

    <section className="today-section">
     <div className="today-section-head">
      <div className="today-section-title">
       <h2>Prospects to meet</h2>
      </div>
      <Link className="today-section-link" href="/acquisition">Acquisition map</Link>
     </div>
     {data.prospects.length>0?(
      <div className="today-sub-list">
       {data.prospects.slice(0,4).map(p=><ProspectRow key={p.id} prospect={p}/>)}
      </div>
     ):(
      <p className="today-empty">No prospects waiting for review.</p>
     )}
    </section>
   </div>
  </div>
 );
}
