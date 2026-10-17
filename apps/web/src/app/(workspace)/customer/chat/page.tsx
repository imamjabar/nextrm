"use client";
import {useEffect,useRef,useState} from 'react';
import {Send,MessageSquare,Landmark,Signal,BatteryFull,ChartNoAxesCombined,ArrowUpRight,UserRound,Sparkles,Home,Plus,History} from 'lucide-react';
import {CustomerInsights} from '@/components/rm/CustomerInsights';
import {RMContactSheet} from '@/components/rm/RMContactSheet';
import {MenuLinks} from '@/components/rm/MenuLinks';
import {fetchApi} from '@/lib/api';
import {Notice} from '@/components/ui/Workspace';
import {useRM,RequestState,requestKey} from '@/components/rm/shared';
import type {RMParties,RMConversation,RMTurn,RMChatRequest,RMActivityRequest,RMChatSessions,RMChatSession} from '@/lib/rm.generated';

type View='home'|'chat'|'history';
function BankingPhone({personId}:{personId:string}){
  const [selected,setSelected]=useState<string|null>(null),[historyCursor,setHistoryCursor]=useState('');
  const q=useRM<RMConversation>('/v1/rm/chat/'+personId+(selected?'/sessions/'+selected:''));
  const sessions=useRM<RMChatSessions>('/v1/rm/chat/'+personId+'/sessions'+(historyCursor?'?cursor='+encodeURIComponent(historyCursor):''));
  const [earlierTurns,setEarlier]=useState<RMTurn[]>([]),[earlierCursor,setEarlierCursor]=useState<string|null|undefined>(undefined);
  const newKey=useRef(''),drafts=useRef(new Map<string,string>());
  const [creating,setCreating]=useState(false);
  const [view,setView]=useState<View>('home'),[input,setInput]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[unknown,setUnknown]=useState(false),[contactOpen,setContactOpen]=useState(false);
  const messages=useRef<HTMLDivElement>(null),composer=useRef<HTMLTextAreaElement>(null),request=useRef<RMChatRequest|null>(null),focusNext=useRef(false);
  const data=selected&&q.data?.id!==selected?null:q.data,pending=unknown||data?.turns.some(t=>t.status==='PENDING');
  const activity=(kind:RMActivityRequest['kind'],product:RMActivityRequest['product'])=>{fetchApi(`/v1/rm/chat/${personId}/activity`,{method:'POST',body:JSON.stringify({kind,product,request_key:requestKey()})}).catch(()=>{/* Optional institutional telemetry does not interrupt customer help. */});};
  const switchSession=(id:string)=>{drafts.current.set(selected||'blank',input);setEarlier([]);setEarlierCursor(undefined);setSelected(id);setInput(drafts.current.get(id)||'');request.current=null;setUnknown(false);setError('');setView('chat');};
  const createChat=async(text='')=>{if(creating||busy||pending)return;setCreating(true);setError('');newKey.current ||=requestKey();try{const created=await fetchApi<RMChatSession>(`/v1/rm/chat/${personId}/sessions`,{method:'POST',body:JSON.stringify({request_key:newKey.current})});newKey.current='';drafts.current.set(selected||'blank',input);setEarlier([]);setEarlierCursor(undefined);setSelected(created.id);setInput(text);request.current=null;setUnknown(false);setView('chat');focusNext.current=true;await sessions.refresh();}catch(e:any){setError(e.message);}finally{setCreating(false);}};
  const compose=(text:string)=>{if(!selected){createChat(text);return;}setInput(text);focusNext.current=true;setView('chat');};
  const contact=()=>{setContactOpen(true);activity('RM_CONTACT_VIEW','NONE');};
  useEffect(()=>{if(view==='chat'&&focusNext.current){composer.current?.focus();focusNext.current=false;}},[view,input,data?.id]);
  useEffect(()=>{if(view==='chat'&&messages.current)messages.current.scrollTo({top:messages.current.scrollHeight,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});},[data?.turns.length,view,busy]);
  const send=async(text=input)=>{
    if(!data||!selected||!text.trim()||busy||pending)return;setBusy(true);setError('');setInput(text);
    if(!request.current||request.current.message!==text)request.current={message:text,base_version:data.version,request_key:requestKey(),session_id:selected};
    try{
      const turn=await fetchApi<RMTurn>(`/v1/rm/chat/${personId}/turns`,{method:'POST',body:JSON.stringify(request.current)});
      if(turn.status==='COMPLETED'){setInput('');request.current=null;setUnknown(false);}
      else{setUnknown(turn.status==='PENDING');if(turn.status==='FAILED')request.current=null;setError(turn.status==='PENDING'?'Your answer is still being prepared. Check its status before sending again.':turn.answer||'The assistant is temporarily unavailable.');}
      await q.refresh();await sessions.refresh();
    }catch(e:unknown){const message=e instanceof Error?e.message:'The response could not be confirmed. Your question is retained.';setError(message);setUnknown(true);if(message.includes('This record changed'))request.current=null;}
    finally{setBusy(false);}
  };
  const check=async()=>{await q.refresh();setUnknown(false);};
  return <div className="mvp-device"><div className="mvp-hardware" aria-hidden="true"><span>9:41</span><div/><span><Signal size={13}/><BatteryFull size={17}/></span></div><div className="mvp-screen">
    <header className="mvp-bank-header"><div><span><Landmark size={20}/></span><div><strong>{data?.institution_name||'Your bank'}</strong><small>{view==='home'?'Your banking overview':'AI assistant'}</small></div></div><button aria-label="Contact your RM" title="Contact your RM" onClick={contact}><UserRound size={21}/></button></header>
    {error&&<Notice tone="bad">{error}<button className="text-link" onClick={check}>Check current chat status</button></Notice>}<RequestState data={data} error={q.error} retry={q.refresh}/>{data&&<>
    <div className="mvp-chat-view" hidden={view!=='chat'}><div className="mvp-chat-tools"><button disabled={busy||!!pending||creating} onClick={()=>createChat()}><Plus size={15}/>New chat</button><button onClick={()=>{setView('history');sessions.refresh();}}><History size={15}/>History</button><span>{sessions.data?.sessions.find(s=>s.id===selected)?.title||'New conversation'}</span></div>
      <div className="mvp-messages" ref={messages} role="log" aria-label="Conversation with the banking AI assistant" aria-live="polite" aria-relevant="additions text">
        {!data.turns.length&&<section className="mvp-chat-welcome"><span className="mvp-assistant-symbol"><Sparkles size={24}/></span><p>Hello, {data.party.name.split(' ')[0]}.</p><h1>What can I help<br/>you with today?</h1><p>Understand your money.<br/>Make your next step clearer.</p><div className="mvp-starters">{['Help me manage my cash flow','Why has my spending increased?','Explain time deposits','I need help with a banking issue'].map(text=><button key={text} disabled={busy} onClick={()=>compose(text)}>{text}<ArrowUpRight size={14}/></button>)}</div></section>}
        {(earlierCursor===undefined?data.older_cursor:earlierCursor)&&<button className="text-link" onClick={async()=>{try{const earlier=await fetchApi<RMConversation>(`/v1/rm/chat/${personId}/sessions/${selected}?before=${encodeURIComponent((earlierCursor===undefined?data.older_cursor:earlierCursor)!)}`);setEarlier(current=>[...earlier.turns,...current]);setEarlierCursor(earlier.older_cursor||null);}catch(e:any){setError(e.message);}}}>Earlier messages</button>}{[...earlierTurns,...data.turns].map((turn,index)=><div className="mvp-turn" key={turn.id}><div className="mvp-customer-message"><p>{turn.message}</p></div><div className="mvp-assistant-message"><span><Sparkles size={13}/> AI assistant{turn.status==='COMPLETED'&&<small className="mvp-answer-mode">{turn.mode==='LIVE'?'Gemini · live':'Simulated'}</small>}</span><p className="answer-text">{turn.answer||'Preparing your answer…'}</p>{turn.sources.length>0&&<details className="mvp-answer-evidence"><summary>Sources · {turn.sources.length}</summary>{turn.sources.map(source=><section key={source.id}><strong>{source.title}</strong><p>{source.kind.endsWith('FINANCIAL_SUMMARY')?'Based on your bank’s validated financial snapshot. View Insights for amounts, comparison periods and availability.':source.content}</p></section>)}</details>}{turn.route==='LOAN'&&turn.status==='COMPLETED'&&<details className="mvp-answer-evidence"><summary>Continue in your bank</summary><MenuLinks route="LOAN" compact/></details>}{index===earlierTurns.length+data.turns.length-1&&turn.status==='COMPLETED'&&!!turn.suggestions?.length&&<div className="mvp-followups" aria-label="Suggested next questions">{turn.suggestions.map(text=><button key={text} type="button" disabled={busy||!!pending||!data.provider_ready} onClick={()=>send(text)}>{text}<ArrowUpRight size={13}/></button>)}</div>}{index===earlierTurns.length+data.turns.length-1&&turn.status==='COMPLETED'&&(!turn.governance||((turn.governance.steps as string[])||[]).includes('OFFER_RM_CONTACT'))&&<button className="mvp-human-contact" onClick={contact}><UserRound size={15}/> Need a person? Contact your RM <ArrowUpRight size={14}/></button>}</div></div>)}
        {busy&&<div className="mvp-thinking" role="status"><span/><span/><span/><small>Preparing your answer</small></div>}
      </div>
      <form className="mvp-composer" onSubmit={e=>{e.preventDefault();send();}}><label htmlFor="customer-message" className="sr-only">Your banking question</label><div><textarea id="customer-message" ref={composer} value={input} rows={1} maxLength={1500} disabled={busy||!!pending} onChange={e=>setInput(e.target.value)} placeholder="Ask about your money…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}}/><button type="submit" aria-label="Send banking question" disabled={busy||!!pending||!input.trim()||!data.provider_ready}><Send size={18}/></button></div>{!data.provider_ready&&<p className="mvp-unavailable">The assistant is currently unavailable. You can still view insights and RM contact details.</p>}</form>
    </div>
    <div className="mvp-insights-view" hidden={view!=='home'}><CustomerInsights personId={personId} active={view==='home'} compose={compose} viewProduct={product=>activity('PRODUCT_VIEW',product)}/></div>
    {view==='history'&&<section className="mvp-history"><div className="mvp-section-heading"><h1>Your conversations</h1><button className="text-link" disabled={creating||busy||!!pending} onClick={()=>createChat()}>New chat</button></div><RequestState data={sessions.data} error={sessions.error} retry={sessions.refresh}/>{sessions.data?.sessions.length?sessions.data.sessions.map(session=><button className="mvp-history-row" key={session.id} disabled={busy||!!pending} onClick={()=>switchSession(session.id)}><div><strong>{session.title}</strong><small>{new Date(session.updated_at).toLocaleDateString('en-GB')} · {session.turn_count} messages</small></div><ArrowUpRight size={15}/></button>):<p>No saved conversations yet. Start a new chat when you need help.</p>}{sessions.data?.next_cursor&&<button className="text-link" onClick={()=>setHistoryCursor(sessions.data!.next_cursor!)}>Next conversations</button>}{historyCursor&&<button className="text-link" onClick={()=>setHistoryCursor('')}>Most recent conversations</button>}</section>}
    <p className="mvp-ai-caution">AI can make mistakes. Always check important info.</p>
    <nav className="mvp-navigation" aria-label="Customer banking sections"><button aria-current={view==='home'?'page':undefined} onClick={()=>setView('home')}><Home size={20}/><span>Home</span></button><button aria-current={view==='chat'||view==='history'?'page':undefined} disabled={creating} onClick={()=>selected?setView('chat'):createChat()}><MessageSquare size={20}/><span>Chats</span></button></nav>
    </>}
    <RMContactSheet personId={personId} open={contactOpen} close={()=>setContactOpen(false)}/>
  </div><div className="mvp-home-indicator" aria-hidden="true"/></div>;
}
export default function CustomerChat(){
  const q=useRM<RMParties>('/v1/rm/parties');const person=q.data?.parties.find(p=>p.kind==='PERSON'&&p.relationship==='EXISTING_CUSTOMER');
  return <div className="mvp-customer-stage"><RequestState data={q.data} error={q.error} retry={q.refresh}/>{person?<BankingPhone key={person.id} personId={person.id}/>:q.data?<Notice>No customer relationship is assigned to this account.</Notice>:null}<p className="mvp-demo-caption">MVP demo · Sample bank data · Each answer shows whether live Gemini or a simulation wrote it<br/>Relevant conversations and permitted app activity can inform your RM.</p></div>;
}
