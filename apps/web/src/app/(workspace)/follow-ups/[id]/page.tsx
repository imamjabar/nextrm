"use client";
import {useEffect,useId,useRef,useState} from 'react';
import Link from 'next/link';
import {PageTitle,Status,Notice,Field,ErrorState,Loading} from '@/components/ui/Workspace';
import {useRM,RequestState,SourceExcerpt,requestKey} from '@/components/rm/shared';
import {MenuLinks} from '@/components/rm/MenuLinks';
import {AIDraftView} from '@/components/rm/AIAssist';
import {contactSummary} from '@/components/rm/ContactPreference';
import {dateLabel,label} from '@/lib/presentation';
import {localDateTimeValue} from '@/lib/engagement-presentation';
import {fetchApi} from '@/lib/api';
import type {RMJourney,RMFollowupUpdate,RMSource,RMAIDraft,RMAIDraftRequest} from '@/lib/rm.generated';
function OriginalSource({id}:{id:string}){const q=useRM<RMSource>('/v1/rm/sources/'+id);return <><RequestState data={q.data} error={q.error} retry={q.refresh}/>{q.data&&<SourceExcerpt source={q.data}/>}</>;}
const outcomeLabels:Record<NonNullable<RMFollowupUpdate['outcome']>,string>={PREPARATION_RECORDED:'Preparation recorded',CUSTOMER_DECLINED_DISCUSSION:'Customer declined the discussion',NO_CURRENT_NEED:'No current need',INFORMATION_MISSING:'More information needed',DISCUSSION_RECORDED:'Discussion recorded',CUSTOMER_REPORTS_CONTINUING_ELSEWHERE:'Customer reports continuing in another bank menu'};
export default function Followup({params}:{params:{id:string}}){
  const q=useRM<RMJourney>('/v1/rm/follow-ups/'+params.id);const [committed,setCommitted]=useState<RMJourney|null>(null);const x=committed?.id===params.id&&(!q.data||committed.version>q.data.version)?committed:q.data;
  const [outcome,setOutcome]=useState<NonNullable<RMFollowupUpdate['outcome']>>('PREPARATION_RECORDED');
  const [note,setNote]=useState(''),[due,setDue]=useState(''),[dueEdited,setDueEdited]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState('');
  const [draftOpen,setDraftOpen]=useState(false),[draftChan,setDraftChan]=useState<RMAIDraftRequest['channel']>('EMAIL');
  const [aiDraft,setAiDraft]=useState<RMAIDraft|null>(null),[aiBusy,setAiBusy]=useState(false),[aiError,setAiError]=useState(''),[restricted,setRestricted]=useState('');
  const key=useRef<{signature:string;body:RMFollowupUpdate|null}>({signature:'',body:null});const dueHint=useId(),errorId=useId();
  const draftOutreach=async(c=draftChan)=>{
    if(!x)return;setAiBusy(true);setAiError('');setRestricted('');setAiDraft(null);
    try{const res=await fetchApi<RMAIDraft>(`/v1/rm/follow-ups/${x.id}/ai-draft`,{method:'POST',body:JSON.stringify({channel:c})});setAiDraft(res);}
    catch(e:any){const msg=e.message||'Draft generation failed';if(msg.includes('Commercial contact is restricted')||msg.includes('restricted'))setRestricted(msg);else setAiError(msg);}
    finally{setAiBusy(false);}
  };
  useEffect(()=>{if(x&&!dueEdited)setDue(localDateTimeValue(x.due_at));},[x?.id,x?.due_at,dueEdited]);
  useEffect(()=>{if(x?.contact_method)setDraftChan(x.contact_method==='EMAIL'?'EMAIL':'PHONE_SCRIPT');},[x?.id,x?.contact_method]);
  const closed=x&&['DONE','CANCELLED'].includes(x.status);
  const dueTime=due?new Date(due).getTime():NaN,validDue=!due||Number.isFinite(dueTime),futureDue=Number.isFinite(dueTime)&&dueTime>Date.now();
  const act=async(action:RMFollowupUpdate['action'])=>{
    if(!x)return;
    if(!validDue||action==='SNOOZE'&&!futureDue){setError('Choose a valid future date to snooze the follow-up.');return;}
    setBusy(true);setError('');setSaved('');
    try{
      const intent={action,note,outcome:action==='COMPLETE'?outcome:null,due_at:due?new Date(due).toISOString():null};
      const signature=JSON.stringify(intent);
      if(signature!==key.current.signature||!key.current.body)key.current={signature,body:{...intent,base_version:x.version,request_key:requestKey()}};
      const result=await fetchApi<RMJourney>('/v1/rm/follow-ups/'+x.id,{method:'POST',body:JSON.stringify(key.current.body)});setCommitted(result);setDue(localDateTimeValue(result.due_at));
      key.current={signature:'',body:null};setNote('');setDueEdited(false);
      setSaved(action==='SNOOZE'?'Follow-up paused until the chosen date.':action==='COMPLETE'?'RM work and outcome recorded.':action==='CANCEL'?'Follow-up cancelled; its history is retained.':action==='START'?'Preparation started.':'Note and due date recorded.');
      await q.refresh();
    }catch(e:unknown){const message=e instanceof Error?e.message:'The action could not be confirmed. Check the current record before retrying.';setError(message);if(message.includes('This record changed'))key.current={signature:'',body:null};}
    finally{setBusy(false);}
  };
  const [copied,setCopied]=useState(false);
  const copyScript=()=>{
    const text=aiDraft?.body||x?.draft||'';
    if(!text)return;
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(()=>setCopied(false),2000);
  };
  const custFirstName=x?.name?.trim().split(/\s+/)[0]||'Customer';
  const custAppText=x?.status==='DONE'?'Completed'
    :x?.due_at?`Maya plans to contact you by ${dateLabel(x.due_at)}`
    :'Maya will look at this soon.';
  return <><Link className="text-link mb-5" href="/follow-ups">← RM follow-ups</Link><RequestState data={x} error={q.error} retry={q.refresh}/>{x&&<>
    <header className="followup-header">
      <div>
        <span className="eyebrow">{x.name} · Assigned customer</span>
        <h1 className="followup-title">Follow-up with {custFirstName}</h1>
      </div>
      <div className="followup-header-status">
        <Status tone={x.status==='DONE'?'good':'neutral'}>{label(x.status)}</Status>
      </div>
    </header>

    <div className="followup-sync-banner">
      <div className="sync-item">
        <strong>Preferred channel</strong>
        <span>{x.contact_method?contactSummary(x.contact_method,x.contact_window):'Official bank channel'}</span>
      </div>
      <div className="sync-item sync-customer-preview">
        <strong>Customer sees on phone</strong>
        <span className="sync-badge">"{custAppText}"</span>
      </div>
      <div className="sync-item">
        <strong>Due date</strong>
        <span>{x.due_at?dateLabel(x.due_at):'No due date set'}</span>
      </div>
    </div>

    <div className="rm-detail-grid mt-6">
      <section className="rm-primary-section">
        {/* STAGE 1: BEFORE CALLING */}
        <div className="followup-stage-card stage-prep">
          <div className="stage-header">
            <span className="stage-pill">Stage 1</span>
            <div>
              <h2>Before the call (Pre-call prep)</h2>
              <p>Review {custFirstName}’s request and use the prepared script when calling from your bank phone.</p>
            </div>
          </div>

          <div className="stage-quote-box">
            <span className="stage-quote-label">Customer's words</span>
            <blockquote>“{x.need}”</blockquote>
          </div>

          <div className="stage-script-box">
            <div className="script-header">
              <div>
                <strong>Outreach script</strong>
                <small>Draft only · Review and speak or send via bank channels</small>
              </div>
              <button className="button button-quiet" type="button" onClick={copyScript} aria-label="Copy script">
                {copied?'Copied!':'Copy script'}
              </button>
            </div>
            <p className="script-body">{aiDraft?aiDraft.body:x.draft}</p>
          </div>

          <div className="stage-draft-actions">
            {!draftOpen ? (
              <button className="button" type="button" onClick={()=>{setDraftOpen(true);draftOutreach(draftChan);}} aria-label="Draft outreach with Gemini">
                Refine script with Gemini
              </button>
            ) : (
              <div className="ai-draft-controls">
                <Field label="Channel">
                  <select className="control" value={draftChan} disabled={aiBusy} onChange={e=>setDraftChan(e.target.value as RMAIDraftRequest['channel'])}>
                    <option value="PHONE_SCRIPT">Phone script</option>
                    <option value="EMAIL">Email</option>
                  </select>
                </Field>
                <div className="action-row mt-3">
                  <button className="button button-primary" type="button" disabled={aiBusy} onClick={()=>draftOutreach(draftChan)}>
                    {aiBusy?'Drafting…':'Generate with Gemini'}
                  </button>
                  <button className="button button-quiet" type="button" onClick={()=>setDraftOpen(false)}>
                    Close
                  </button>
                </div>
                {aiError&&<Notice tone="bad">{aiError}</Notice>}
                {restricted&&<Notice tone="neutral">{restricted}</Notice>}
              </div>
            )}
          </div>
        </div>

        {/* STAGE 2: AFTER CALLING */}
        <div className="followup-stage-card stage-outcome mt-6">
          <div className="stage-header">
            <span className="stage-pill">Stage 2</span>
            <div>
              <h2>After the call (Log outcome & CRM)</h2>
              <p>Record what was discussed with {custFirstName}. Marking done closes this follow-up and updates {custFirstName}’s mobile app to Done.</p>
            </div>
          </div>

          {x.snoozed_until&&<Notice>{new Date(x.snoozed_until).getTime()>Date.now()?'Snoozed until '+dateLabel(x.snoozed_until):'The snooze ended on '+dateLabel(x.snoozed_until)+'. Ready for follow-up.'}</Notice>}
          {x.outcome&&<p className="mb-4">Recorded outcome: <strong>{outcomeLabels[x.outcome as keyof typeof outcomeLabels]||label(x.outcome)}</strong>. Human recorded.</p>}

          {!closed ? (
            <div className="followup-editor" aria-busy={busy}>
              <Field label="Outcome when recording done">
                <select className="control" value={outcome} disabled={busy} onChange={e=>setOutcome(e.target.value as typeof outcome)}>
                  {Object.entries(outcomeLabels).map(([value,caption])=><option key={value} value={value}>{caption}</option>)}
                </select>
              </Field>
              <Field label="RM note or outcome" hint="Add a note before saving, snoozing, completing or cancelling.">
                <textarea className="control" rows={4} value={note} disabled={busy} maxLength={1500} aria-describedby={error?errorId:undefined} onChange={e=>setNote(e.target.value)} placeholder="What did you discuss, learn or agree with the customer?"/>
              </Field>
              <Field label="Follow-up due date (your local time)">
                <input className="control" type="datetime-local" value={due} disabled={busy} aria-describedby={dueHint} aria-invalid={!validDue?true:undefined} onChange={e=>{setDue(e.target.value);setDueEdited(true);}}/>
              </Field>
              <p id={dueHint} className="field-guidance">
                {due&&futureDue?'Snooze pauses the task until '+dateLabel(new Date(due).toISOString())+'.':'Choose a future date and add a note to snooze. You can save a note without snoozing.'}
              </p>
              <div className="action-row mt-4">
                <button className="button button-primary" disabled={busy||note.trim().length<3||!validDue} onClick={()=>act('COMPLETE')}>
                  Record follow-up done
                </button>
                <button className="button" disabled={busy||note.trim().length<3||!futureDue} onClick={()=>act('SNOOZE')}>
                  Snooze until due date
                </button>
                <button className="button" disabled={busy||note.trim().length<3||!validDue} onClick={()=>act('NOTE')}>
                  Save note and due date
                </button>
              </div>
              <details className="source-excerpt followup-cancel mt-4">
                <summary>Cancel this follow-up</summary>
                <p>Add a clear note explaining why the work is being cancelled. The original need and history remain.</p>
                <button className="button button-quiet" disabled={busy||note.trim().length<3} onClick={()=>act('CANCEL')}>
                  Cancel follow-up
                </button>
              </details>
            </div>
          ) : (
            <Notice tone="good">This follow-up is closed. All notes and outcomes are permanently preserved in the customer audit log.</Notice>
          )}
        </div>

        {busy&&<p role="status" className="field-guidance mt-3">Recording your action…</p>}
        {saved&&<Notice tone="good">{saved}</Notice>}
        {error&&<Notice tone="bad"><p id={errorId}>{error}</p><button className="text-link" onClick={q.refresh}>Check current record</button></Notice>}

        <div className="mt-6">
          <h3>RM activity history</h3>
          {x.history.length?x.history.map((h,i)=><div className="journey-event" key={i}><strong>{label(h.event)} · {label(h.status)}</strong><p>{h.note}</p><small>{dateLabel(h.at)} · Human-recorded RM work</small></div>):<p className="text-secondary mt-3">Follow-up prepared; no later activity recorded.</p>}
          <Link className="text-link mt-5" href={'/relationships/'+x.party_id}>Open person and retained source history</Link>
        </div>
      </section>
      <aside>
        <section className="rm-side-section">
          <h2>Original customer request</h2>
          <OriginalSource id={x.source_id}/>
          <small>Follow-up {x.id} · v{x.version}</small>
        </section>
        <details className="source-excerpt mt-5">
          <summary>Bank product and service menus</summary>
          <MenuLinks/>
        </details>
      </aside>
    </div>
  </>}</>;
}
