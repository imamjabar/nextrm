"use client";
import React, {useState} from 'react';
import {useRM} from '@/components/rm/shared';
import {dateLabel,timeAgo} from '@/lib/presentation';
import {contactSummary,ContactPreferencePicker,methodVerb} from '@/components/rm/ContactPreference';
import {MessageRMSheet} from '@/components/rm/MessageRM';
import type {RMCustomerRequest,RMCustomerRequests} from '@/lib/rm.generated';

function progress(item:RMCustomerRequest,Who:string):{step:0|1|2|3;text:string}{
  switch(item.status){
    case 'REVIEWED':return {step:2,text:`${Who} has read it and will contact you.`};
    case 'FOLLOWUP_PLANNED': {
      const verb = methodVerb(item.contact_method);
      return {step:2,text:item.due_at?`${Who} plans to ${verb} by ${dateLabel(item.due_at)}.`:`${Who} plans to ${verb}.`};
    }
    case 'RM_PREPARING':return {step:2,text:`${Who} is getting ready to contact you.`};
    case 'RM_WORK_RECORDED':return {step:3,text:`${Who} has followed up on this.`};
    case 'CLOSED':return {step:0,text:'Closed without a follow-up. Ask again in chat if you still need help.'};
    default:return {step:1,text:`${Who} will look at this soon.`};
  }
}

export function CustomerRequests({personId,rmName}:{personId:string;rmName:string}){
  const {data,refresh}=useRM<RMCustomerRequests>(`/v1/rm/chat/${personId}/requests`,5000);
  const [editingId,setEditingId]=useState<string|null>(null);
  const [sheetOpen,setSheetOpen]=useState(false);
  if(!data)return null;
  const who=rmName==='Relationship service team'?'your RM team':(rmName.trim().split(/\s+/)[0]||'your RM');
  const Who=who[0].toUpperCase()+who.slice(1);
  const rank=[3,1,0,2];
  const items=(data.requests||[]).map(item=>({item,...progress(item,Who)})).sort((a,b)=>rank[a.step]-rank[b.step]).slice(0,3);
  const stages=['Sent',`${Who} contacts you`,'Done'];
  return (
    <section className="req-card" aria-labelledby="req-card-title">
      <div className="req-card-head">
        <h2 id="req-card-title">Your RM, {Who}</h2>
        <button type="button" className="button button-quiet req-msg-btn" onClick={()=>setSheetOpen(true)}>
          Message {Who}
        </button>
      </div>
      {items.length===0?(
        <p className="req-empty">Need help from {Who}? Send a message and choose how {Who} contacts you.</p>
      ):(
        <>
          <p className="req-card-sub">{Who} contacts you outside this app, the way you choose.</p>
          <ul className="req-list">
            {items.map(({item,step,text})=>(
              <li key={item.id} className="req-item" data-closed={step===0||undefined}>
                <p className="req-quote">&ldquo;{item.message}&rdquo;</p>
                {step>0&&<ol className="req-track" aria-label={`Step ${step} of 3`}>
                  {stages.map((stage,i)=><li key={stage} data-state={i+1<step||step===3?'done':i+1===step?'current':undefined}>{stage}</li>)}
                </ol>}
                {(step===1||step===2)&&<div className="req-pref">
                  {item.contact_method?(
                    <><span>{contactSummary(item.contact_method,item.contact_window)}</span><button type="button" className="text-link req-pref-btn" onClick={()=>setEditingId(editingId===item.id?null:item.id)}>Change</button></>
                  ):(
                    <button type="button" className="text-link req-pref-btn" onClick={()=>setEditingId(editingId===item.id?null:item.id)}>Tell {Who} how to reach you</button>
                  )}
                </div>}
                {(step===1||step===2)&&editingId===item.id&&<ContactPreferencePicker personId={personId} request={item} who={who} onSaved={async()=>{setEditingId(null);await refresh();}} onCancel={()=>setEditingId(null)}/>}
                <p className="req-status">{text}<span>{timeAgo(item.updated_at)}</span></p>
              </li>
            ))}
          </ul>
        </>
      )}
      <MessageRMSheet
        personId={personId}
        who={who}
        open={sheetOpen}
        initialMessage=""
        turnId={null}
        onClose={()=>setSheetOpen(false)}
        onSent={async()=>{await refresh();}}
      />
    </section>
  );
}
