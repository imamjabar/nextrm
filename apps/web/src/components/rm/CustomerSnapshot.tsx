"use client";
import {useRM} from '@/components/rm/shared';
import {indexInsights,usable,shown,goalsOf,shownDate} from '@/lib/home-model';
import {ActivityItem} from '@/components/rm/Today';
import type {RMPartySnapshot} from '@/lib/rm.generated';

export function CustomerSnapshot({partyId,firstName}:{partyId:string;firstName:string}){
 const q=useRM<RMPartySnapshot>('/v1/rm/parties/'+partyId+'/snapshot',5000);
 if(!q.data||!q.data.available)return null;

 const insights=indexInsights(q.data.insights);
 const cashFlow=insights.cash_flow;
 const avail=usable(cashFlow)?shown(cashFlow,'available'):'';

 const spending=insights.spending_breakdown;
 const spent=usable(spending)?shown(spending,'total_spend'):'';

 const portfolio=insights.portfolio;
 const invest=usable(portfolio)?shown(portfolio,'total_value'):'';

 const netWorth=insights.net_worth;
 const worth=usable(netWorth)?shown(netWorth,'net_worth'):'';

 const termDeposit=insights.term_deposit;
 const tdBal=usable(termDeposit)?shown(termDeposit,'balance'):'';
 const tdMaturity=termDeposit?.values.maturity_date?shownDate(termDeposit.values.maturity_date):'';

 const goals=usable(insights.goal_progress)?goalsOf(insights.goal_progress).slice(0,3):[];

 return (
  <section className="today-section customer-snapshot">
   <div className="today-section-head">
    <div className="today-section-title">
     <h2>What {firstName} sees in the app</h2>
    </div>
    <p className="today-caption">Same calculation as the customer's Home · synthetic core-banking data</p>
   </div>

   <div className="snapshot-tiles">
    {Boolean(usable(cashFlow)&&avail)&&(
     <div className="snapshot-tile">
      <span className="snapshot-label">Available balance</span>
      <strong className="snapshot-val">{avail}</strong>
     </div>
    )}
    {Boolean(usable(spending)&&spent)&&(
     <div className="snapshot-tile">
      <span className="snapshot-label">Spent, last 30 days</span>
      <strong className="snapshot-val">{spent}</strong>
     </div>
    )}
    {Boolean(usable(portfolio)&&invest)&&(
     <div className="snapshot-tile">
      <span className="snapshot-label">Investments</span>
      <strong className="snapshot-val">{invest}</strong>
     </div>
    )}
    {Boolean(usable(netWorth)&&worth)&&(
     <div className="snapshot-tile">
      <span className="snapshot-label">Net worth</span>
      <strong className="snapshot-val">{worth}</strong>
     </div>
    )}
    {Boolean(usable(termDeposit)&&tdBal)&&(
     <div className="snapshot-tile">
      <span className="snapshot-label">Term deposit</span>
      <strong className="snapshot-val">{tdBal}</strong>
      {Boolean(tdMaturity)&&<small className="snapshot-sub">matures {tdMaturity}</small>}
     </div>
    )}
   </div>

   {goals.length>0&&(
    <div className="snapshot-goals">
     <span className="snapshot-label">Goals</span>
     <div className="snapshot-goals-list">
      {goals.map((g,i)=>(
       <div key={i} className="snapshot-goal-item">
        <span className="snapshot-goal-name">{g.label}</span>
        <span className="today-chip">{g.pctText}</span>
       </div>
      ))}
     </div>
    </div>
   )}

   <div className="snapshot-conversations-section">
    <h3>Recent conversations</h3>
    {q.data.conversations.length>0?(
     <ol className="today-feed" aria-live="polite" aria-relevant="additions">
      {q.data.conversations.map(c=>(
       <ActivityItem key={c.id} item={c}/>
      ))}
     </ol>
    ):(
     <p className="today-empty">No shared conversations yet.</p>
    )}
   </div>
  </section>
 );
}
