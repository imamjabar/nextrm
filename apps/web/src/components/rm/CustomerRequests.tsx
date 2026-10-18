"use client";
import React from 'react';
import {useRM} from '@/components/rm/shared';
import {dateLabel,timeAgo} from '@/lib/presentation';
import type {RMCustomerRequests} from '@/lib/rm.generated';

function getStatusInfo(status: string, who: string): {step: number; text: string} {
  switch (status) {
    case 'AWAITING_REVIEW':
      return {step: 1, text: 'Received, waiting for review'};
    case 'REVIEWED':
      return {step: 2, text: `Reviewed by ${who}`};
    case 'FOLLOWUP_PLANNED':
      return {step: 2, text: 'Follow-up planned'};
    case 'RM_PREPARING':
      return {step: 3, text: `${who} is preparing`};
    case 'RM_WORK_RECORDED':
      return {step: 4, text: `${who} recorded the follow-up`};
    case 'CLOSED':
      return {step: 0, text: 'Closed'};
    default:
      return {step: 1, text: 'Received, waiting for review'};
  }
}

export function CustomerRequests({personId,rmName}:{personId:string;rmName:string}){
  const {data}=useRM<RMCustomerRequests>(`/v1/rm/chat/${personId}/requests`,5000);
  if(!data||!data.requests||data.requests.length===0)return null;
  const who=rmName==='Relationship service team'?'your RM team':(rmName.trim().split(/\s+/)[0]||'your RM');
  const items=data.requests.slice(0,3);
  return (
    <section className="mvp-requests" aria-labelledby="mvp-requests-title">
      <h2 id="mvp-requests-title">Your requests with {who}</h2>
      <div className="mvp-req-list">
        {items.map(item=>{
          const info=getStatusInfo(item.status,who);
          return (
            <div key={item.id} className="mvp-req-item">
              <p className="mvp-req-message">&ldquo;{item.message}&rdquo;</p>
              <div className="mvp-req-steps" aria-hidden="true">
                {[0,1,2,3].map(i=><span key={i} data-done={i<info.step?'true':undefined}/>)}
              </div>
              <div className="mvp-req-meta">
                <span className="mvp-req-status">{info.text}</span>
                {item.due_at&&<span className="mvp-req-due">Due {dateLabel(item.due_at)}</span>}
                <span className="mvp-req-updated">Updated {timeAgo(item.updated_at)}</span>
              </div>
            </div>
          );
        })}
      </div>
      <small>Shows your RM's work only. Product or account changes happen in your bank's official channels.</small>
    </section>
  );
}
