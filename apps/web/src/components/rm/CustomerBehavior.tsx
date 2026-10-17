"use client";
import {useRM,RequestState} from './shared';
import {Status} from '@/components/ui/Workspace';
import {dateLabel} from '@/lib/presentation';
import type {RMBehavior} from '@/lib/rm.generated';
const products:Record<string,string>={DEPOSIT:'Time deposit',LOAN:'Loan',SAVINGS:'Savings',NONE:'RM contact'};
export function CustomerBehavior({partyId}:{partyId:string}){
  const q=useRM<RMBehavior>(`/v1/rm/parties/${partyId}/behavior`);
  return <section className="customer-behavior"><div className="section-title"><div><span className="eyebrow">App activity, with evidence</span><h2>What brought this customer here</h2></div><button className="text-link" onClick={q.refresh}>Refresh activity</button></div><RequestState data={q.data} error={q.error} retry={q.refresh}/>{q.data&&<>{q.data.events.length?<div className="behavior-rows">{q.data.events.map(e=><div key={e.kind+e.product+e.mode}><div><strong>{e.kind==='PRODUCT_VIEW'?products[e.product]+' explored':e.kind==='APPLICATION_FAILED'?products[e.product]+' opening error reported':'RM contact details viewed'}</strong><p>{e.interpretation}</p><small>{e.window} · Latest {dateLabel(e.latest_at)}</small></div><div><strong>{e.count} {e.kind==='PRODUCT_VIEW'?'views':'events'}</strong><Status>{e.mode==='SIMULATED'?'Simulated source':'Observed'}</Status></div></div>)}</div>:<p>No permitted app activity recorded in the current window.</p>}<details className="source-excerpt"><summary>How to use these signals</summary><p>{q.data.method}</p><p>Prepare a useful conversation, verify the current need, and use the bank’s official email or phone channels. The customer is speaking with an AI assistant in the app, not messaging the RM.</p></details></>}</section>;
}
