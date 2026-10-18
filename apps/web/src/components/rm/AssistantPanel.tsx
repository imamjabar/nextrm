"use client";
import React,{useCallback,useEffect,useId,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import {ArrowUp,FileText,PanelRightClose,RotateCcw,ShieldCheck,Sparkles} from 'lucide-react';
import {fetchApi} from '@/lib/api';
import {dateLabel} from '@/lib/presentation';
import {useRM} from './shared';
import type {RMCopilotAction,RMCopilotContext,RMCopilotRef,RMCopilotTurn} from '@/lib/rm.generated';

export type AssistantSurface='RM'|'QUALITY';
type Failure={status:number;message:string};
type Exchange={id:string;question:string;turn?:RMCopilotTurn;failure?:Failure};
type Props={
  surface:AssistantSurface;
  partyId?:string;
  runId?:string;
  baseVersion?:number|null;
  subject:string;
  onAction?:(action:RMCopilotAction)=>boolean|void;
  onRef?:(ref:RMCopilotRef)=>boolean|void;
  onReload?:()=>Promise<unknown>|void;
  onClose?:()=>void;
  autoFocus?:boolean;
};

const FOOTER='AI can make mistakes. Always check important info.';
const PENDING=['Reading the records in scope…','Checking every figure against its record…'];

function failureCopy(surface:AssistantSurface,f:Failure){
  if(f.status===403)return {title:'Outside your access',body:surface==='RM'?'The copilot only reads relationships assigned to you.':'This account needs an explicit AI quality grant.',retry:false};
  if(f.status===409)return {title:'This record changed',body:'Someone updated it after you opened it. Reload to see the current version, then ask again.',retry:false};
  if(f.status===503)return {title:'Gemini is not available',body:'No simulated answer was substituted. Try again shortly or work from the records on the page.',retry:true};
  if(f.status===502)return {title:'Answer withheld',body:'The answer did not pass the evidence checks, so it was not shown.',retry:true};
  return {title:'Could not reach NextRM',body:'Check your connection and try again.',retry:true};
}

function Evidence({evidence,label}:{evidence:string;label:string}){
  return <span className={'evidence-tag evidence-'+evidence.toLowerCase().replace('_','-')}>{label}</span>;
}

function Answer({turn,surface,onRef,onAction,ask,busy}:{turn:RMCopilotTurn;surface:AssistantSurface;onRef:(r:RMCopilotRef)=>void;onAction:(a:RMCopilotAction)=>void;ask:(q:string)=>void;busy:boolean}){
  const [open,setOpen]=useState<string|null>(null);
  const refs=Object.fromEntries(turn.refs.map(r=>[r.id,r]));
  const excerpt=open?refs[open]?.source:null;
  return <div className="copilot-answer">
    <p className="copilot-lead">{turn.answer}</p>
    {turn.points.length>0&&<ul className="copilot-points">{turn.points.map((p,i)=><li key={i} className={p.evidence==='INFERENCE'?'is-inference':undefined}>
      <Evidence evidence={p.evidence} label={p.evidence_label}/>
      <p>{p.text}</p>
      {p.refs.length>0&&<div className="copilot-refs">{p.refs.map(id=>refs[id]&&<button type="button" key={id} className="ref-chip" aria-expanded={refs[id].source?open===id:undefined} onClick={()=>refs[id].source?setOpen(open===id?null:id):onRef(refs[id])}>
        <FileText size={12} aria-hidden="true"/>{refs[id].label}
      </button>)}</div>}
    </li>)}</ul>}
    {excerpt&&<blockquote className="copilot-excerpt"><p>{excerpt.content}</p><small>{excerpt.title} · {dateLabel(excerpt.event_at)} · v{excerpt.version}</small></blockquote>}
    {turn.action&&<div className="copilot-action">
      {turn.action.text&&<p className="copilot-note-draft">{turn.action.text}</p>}
      <button type="button" className="button" disabled={!turn.action.available} onClick={()=>onAction(turn.action!)}>{turn.action.label}</button>
      <small>{turn.action.available?(surface==='RM'?'Opens the existing form. You review and confirm.':'Opens it on this page. You confirm.'):turn.action.reason}</small>
    </div>}
    <div className="copilot-meta"><span className={'copilot-mode '+(turn.mode==='LIVE'?'is-live':'')}>{turn.mode==='LIVE'?'Gemini · live':'Simulated'}</span><span>{(turn.latency_ms/1000).toFixed(1)} s</span><span>{turn.refs.length} {turn.refs.length===1?'record':'records'} cited</span></div>
    {turn.suggestions.length>0&&<div className="copilot-suggestions">{turn.suggestions.map(s=><button type="button" key={s} disabled={busy} onClick={()=>ask(s)}>{s}</button>)}</div>}
  </div>;
}

export function AssistantPanel({surface,partyId,runId,baseVersion,subject,onAction,onRef,onReload,onClose,autoFocus}:Props){
  const router=useRouter();
  const contextPath=surface==='RM'?'/v1/rm/copilot/context'+(partyId?'?party_id='+encodeURIComponent(partyId):''):'/v1/rm/quality-assistant/context'+(runId?'?run_id='+encodeURIComponent(runId):'');
  const turnsPath=surface==='RM'?'/v1/rm/copilot/turns':'/v1/rm/quality-assistant/turns';
  const ctx=useRM<RMCopilotContext>(contextPath,0);
  const [log,setLog]=useState<Exchange[]>([]),[draft,setDraft]=useState(''),[busy,setBusy]=useState(false),[phase,setPhase]=useState(0);
  const input=useRef<HTMLTextAreaElement>(null),logRef=useRef<HTMLDivElement>(null),scope=useRef('');
  const inputId=useId();
  useEffect(()=>{if(autoFocus)input.current?.focus();},[autoFocus]);
  const key=surface+':'+(partyId||'all');
  useEffect(()=>{if(scope.current&&scope.current!==key)setLog([]);scope.current=key;},[key]);
  useEffect(()=>{
    const el=logRef.current;if(!el)return;
    const rows=el.querySelectorAll<HTMLElement>('.copilot-exchange');const last=rows[rows.length-1];
    el.scrollTop=!last?0:busy?el.scrollHeight:Math.max(0,last.offsetTop-12);
  },[log,busy]);
  useEffect(()=>{if(!busy){setPhase(0);return;}const t=setTimeout(()=>setPhase(1),1200);return()=>clearTimeout(t);},[busy]);
  useEffect(()=>{
    const onKey=(e:KeyboardEvent)=>{
      const target=e.target as HTMLElement|null;
      const typing=!!target&&(target.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(target.tagName));
      if(e.key==='/'&&!typing&&!e.metaKey&&!e.ctrlKey&&!e.altKey){e.preventDefault();input.current?.focus();}
    };
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[]);
  const ask=useCallback(async(text:string)=>{
    const question=text.trim();if(!question||busy)return;
    const id=crypto.randomUUID();setDraft('');setBusy(true);setLog(l=>[...l,{id,question}]);
    const history=log.filter(x=>x.turn).slice(-4).map(x=>({question:x.question,answer:x.turn!.answer}));
    try{
      const turn=await fetchApi<RMCopilotTurn>(turnsPath,{method:'POST',body:JSON.stringify({message:question,party_id:partyId||null,run_id:runId||null,base_version:baseVersion??null,history})});
      setLog(l=>l.map(x=>x.id===id?{...x,turn}:x));
    }catch(e:any){
      setLog(l=>l.map(x=>x.id===id?{...x,failure:{status:Number(e?.status)||0,message:String(e?.message||'')}}:x));
    }finally{setBusy(false);input.current?.focus();}
  },[busy,log,turnsPath,partyId,runId,baseVersion]);
  const openRef=(r:RMCopilotRef)=>{if(onRef?.(r))return;if(r.href)router.push(r.href);};
  const act=(a:RMCopilotAction)=>{if(onAction?.(a))return;if(a.href)router.push(a.href);};
  const reset=()=>{setLog([]);setDraft('');input.current?.focus();};
  const reload=async(question:string)=>{await onReload?.();await ctx.refresh();setLog(l=>l.filter(x=>!(x.failure?.status===409&&x.question===question)));};
  const c=ctx.data;
  return <aside className="copilot" aria-label={surface==='RM'?'RM copilot':'AI quality analyst'} onKeyDown={e=>{if(e.key==='Escape'&&onClose){e.stopPropagation();onClose();}}}>
    <header className="copilot-head">
      <div className="copilot-title">
        <span className="copilot-kicker"><Sparkles size={14} aria-hidden="true"/>{surface==='RM'?'Copilot':'Quality analyst'}</span>
        <strong>{c?.scope_label||subject}</strong>
        <small>{c?c.scope_detail:'Loading the records in scope…'}</small>
      </div>
      <div className="copilot-tools">
        <button type="button" className="icon-button" onClick={reset} disabled={!log.length||busy} aria-label="New chat" title="New chat"><RotateCcw size={16}/></button>
        {onClose&&<button type="button" className="icon-button" onClick={onClose} aria-label="Close copilot" title="Close (Esc)"><PanelRightClose size={16}/></button>}
      </div>
    </header>
    <p className="copilot-access"><ShieldCheck size={14} aria-hidden="true"/><span>{c?.access||'Checking your access…'}</span>{c&&<span className={'copilot-mode '+(c.mode==='LIVE'?'is-live':'')}>{c.mode==='LIVE'?'Gemini':'Simulated'}</span>}</p>
    <div className="copilot-log" ref={logRef} role="log" aria-live="polite" aria-relevant="additions" aria-busy={busy}>
      {ctx.error&&!c&&<div className="copilot-failure" role="alert"><strong>{failureCopy(surface,{status:ctx.error.includes('assigned')||ctx.error.includes('grant')?403:0,message:ctx.error}).title}</strong><p>{ctx.error}</p><button type="button" className="text-link" onClick={()=>ctx.refresh()}>Try again</button></div>}
      {!log.length&&c&&<div className="copilot-empty">
        <h3>Ask about {subject}</h3>
        <p>Answers use only the {c.record_count} records in scope and name the record behind each point.</p>
        <div className="copilot-starters">{c.starters.map(s=><button type="button" key={s} onClick={()=>ask(s)} disabled={busy}>{s}</button>)}</div>
      </div>}
      {log.map(x=><div className="copilot-exchange" key={x.id}>
        <p className="copilot-question">{x.question}</p>
        {x.turn&&<Answer turn={x.turn} surface={surface} onRef={openRef} onAction={act} ask={ask} busy={busy}/>}
        {x.failure&&(()=>{const f=failureCopy(surface,x.failure);return <div className="copilot-failure" role="alert">
          <strong>{f.title}</strong><p>{f.body}</p>{x.failure.message&&<small>{x.failure.message}</small>}
          <div className="copilot-failure-actions">
            {x.failure.status===409&&<button type="button" className="button" onClick={()=>reload(x.question)}>Reload record</button>}
            {f.retry&&<button type="button" className="text-link" disabled={busy} onClick={()=>{setLog(l=>l.filter(y=>y.id!==x.id));ask(x.question);}}>Try again</button>}
          </div>
        </div>;})()}
        {!x.turn&&!x.failure&&<div className="copilot-pending" role="status"><span>{PENDING[phase]}</span><i/><i/><i/></div>}
      </div>)}
    </div>
    <form className="copilot-composer" onSubmit={e=>{e.preventDefault();ask(draft);}}>
      <label htmlFor={inputId} className="sr-only">Ask the {surface==='RM'?'copilot':'quality analyst'}</label>
      <textarea id={inputId} ref={input} rows={1} value={draft} maxLength={1500} placeholder={'Ask about '+subject+'…'} onChange={e=>{setDraft(e.target.value);e.target.style.height='auto';e.target.style.height=Math.min(e.target.scrollHeight,132)+'px';}} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();ask(draft);}}}/>
      <button type="submit" className="copilot-send" disabled={busy||!draft.trim()} aria-label="Send question"><ArrowUp size={18}/></button>
    </form>
    <p className="copilot-hint"><kbd>/</kbd> to focus · <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> new line{onClose?<> · <kbd>Esc</kbd> to close</>:null}</p>
    <p className="copilot-footer">{FOOTER}</p>
  </aside>;
}

export function AssistantDock({children,panel,label}:{children:React.ReactNode;panel:(close:()=>void,focus:boolean)=>React.ReactNode;label:string}){
  const [open,setOpen]=useState<boolean|null>(null);
  const launcher=useRef<HTMLButtonElement>(null),panelRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const el=panelRef.current;if(!open||!el)return;
    const wide=window.matchMedia('(min-width: 1200px)');let frame=0;
    const fit=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{if(!wide.matches){el.style.height='';return;}el.style.height=Math.max(window.innerHeight-Math.max(el.getBoundingClientRect().top,0)-24,420)+'px';});};
    fit();window.addEventListener('scroll',fit,{passive:true});window.addEventListener('resize',fit);
    return()=>{cancelAnimationFrame(frame);window.removeEventListener('scroll',fit);window.removeEventListener('resize',fit);};
  },[open]);
  useEffect(()=>{setOpen(window.matchMedia('(min-width: 1200px)').matches);},[]);
  useEffect(()=>{
    const onKey=(e:KeyboardEvent)=>{
      const target=e.target as HTMLElement|null;
      const typing=!!target&&(target.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(target.tagName));
      if(e.key==='/'&&!typing&&!e.metaKey&&!e.ctrlKey&&!e.altKey)setOpen(true);
    };
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[]);
  const close=useCallback(()=>{setOpen(false);requestAnimationFrame(()=>launcher.current?.focus());},[]);
  const [focus,setFocus]=useState(false);
  useEffect(()=>{if(open===false)setFocus(true);},[open]);
  return <div className={'copilot-dock'+(open?' is-open':'')}>
    <div className="copilot-dock-main">{children}</div>
    {open?<div className="copilot-dock-panel" ref={panelRef}>{panel(close,focus)}</div>:open===false&&<button ref={launcher} type="button" className="copilot-launcher" onClick={()=>setOpen(true)}><Sparkles size={16} aria-hidden="true"/>{label}<kbd>/</kbd></button>}
  </div>;
}
