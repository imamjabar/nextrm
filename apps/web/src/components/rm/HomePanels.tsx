"use client";
import type {ReactNode,Ref} from 'react';
import {ArrowUpRight,ChevronLeft,ChevronRight} from 'lucide-react';
import {allocationOf,billsOf,direction,goalsOf,holdingsOf,marketOf,PANEL_FOR_TOPIC,shown,shownDate,signed,spendingSlices,stepsOf,usable} from '@/lib/home-model';
import type {Direction,GoalTone,Insights,Panel} from '@/lib/home-model';
import type {RMComparison,RMEnrichedNudge} from '@/lib/rm.generated';
import {ChangeBar,Donut,Progress,StackBar} from './HomeCharts';

type Compose=(text:string)=>void;
type Props={insights:Insights;compose:Compose;open:(panel:Panel)=>void};

const TONE_BY_DIRECTION:Record<Direction,string>={up:'good',down:'bad',flat:'neutral'};
const TONE_BY_GOAL:Record<GoalTone,string>={complete:'good',on_track:'good',behind:'warn'};

export const PANEL_META:Record<Panel,{title:string;note:string}>={
  spending:{title:'Where your money went',note:'Last 30 days'},
  goals:{title:'Your goals',note:'Progress to each target date'},
  invest:{title:'Investments',note:'Holdings snapshot'},
  market:{title:'Market insights',note:'Context for your portfolio'},
  cash:{title:'Bills and cash',note:'Until your next payday'},
  worth:{title:'Net worth and financial health',note:'Assets, debts and buffer'},
  steps:{title:'Suggested next steps',note:'Ranked by fixed rules'},
  explore:{title:'Explore with confidence',note:'Approved education'}
};

function Chip({tone,children}:{tone:string;children:ReactNode}){
  return <span className="mvp-chip" data-tone={tone}>{children}</span>;
}

function Ask({text,label,compose}:{text:string;label?:string;compose:Compose}){
  return <button type="button" className="mvp-ask" onClick={()=>compose(text)}><span>{label||text}</span><ArrowUpRight size={14} aria-hidden="true"/></button>;
}

function Stats({items}:{items:Array<[string,string|undefined]>}){
  const present=items.filter(item=>item[1]);
  if(present.length===0)return null;
  return <dl className="mvp-stats">{present.map(([name,value])=><div key={name}><dt>{name}</dt><dd className="tabular">{value}</dd></div>)}</dl>;
}

function Block({title,note,children}:{title:string;note?:string;children:ReactNode}){
  return <section className="mvp-block" aria-label={title}><header><h3>{title}</h3>{note&&<small>{note}</small>}</header>{children}</section>;
}

function Missing({children}:{children:ReactNode}){
  return <p className="mvp-empty">{children}</p>;
}

function SpendingPanel({insights,compose}:Props){
  const breakdown=insights.spending_breakdown,change=insights.spending,slices=spendingSlices(breakdown);
  if(!usable(breakdown)&&!usable(change))return <Missing>Comparable spending information is not available yet.</Missing>;
  return <>
    {slices.length>0&&<Block title="By category" note="Last 30 days">
      <div className="mvp-spend-top">
        <Donut slices={slices} size={116}><strong className="tabular">{slices[0].share}</strong><small>{slices[0].label}</small></Donut>
        <div>
          <span className="mvp-eyebrow">Total spending</span>
          <strong className="mvp-figure">{shown(breakdown,'total_spend')}</strong>
          <Stats items={[['Spend-to-income',shown(breakdown,'spend_to_income_percent')],['Savings rate',shown(breakdown,'savings_rate_percent')]]}/>
        </div>
      </div>
      <ul className="mvp-legend">{slices.map(slice=><li key={slice.label}>
        <i style={{background:slice.color}} aria-hidden="true"/>
        <span>{slice.label}{slice.direction!=='flat'&&<Chip tone={slice.direction==='up'?'warn':'good'}>{signed(slice.change)}</Chip>}</span>
        <b className="tabular">{slice.amount}</b>
        <small className="tabular">{slice.share}</small>
      </li>)}</ul>
    </Block>}
    {usable(change)&&<Block title={change.title} note="Against the previous 30 days">
      <p className="mvp-sentence"><strong className="tabular">{shown(change,'current_spend')}</strong> now against <span className="tabular">{shown(change,'previous_spend')}</span> before{change.values.change_percent!==undefined?<>, a <strong className="tabular">{shown(change,'change_percent')}</strong> change</>:'; the percentage change is unavailable'}.</p>
    </Block>}
    <Ask text="Where is my money going and how can I spend less?" compose={compose}/>
    {usable(change)&&<Ask text="Help me understand the change in my spending and plan my budget." label="Talk through the change" compose={compose}/>}
  </>;
}

function GoalsPanel({insights,compose}:Props){
  const card=insights.goal_progress,goals=goalsOf(card);
  if(goals.length===0)return <Missing>No savings goal is recorded for this profile.</Missing>;
  const totals:Array<[string,string]>=[['Needed each month',shown(card,'required_monthly_total')],['Planned each month',shown(card,'planned_total_monthly')],['Extra needed each month',shown(card,'extra_monthly_needed_total')],['Shortfall at target dates',shown(card,'shortfall_total')]];
  return <>
    {(card?.values.goal_savings||card?.values.goal_contributions_reserved)&&<Block title="Goal pockets" note="Held apart from your balance">
      <Stats items={[['Saved in goal pockets',shown(card,'goal_savings')],['Set aside this month',shown(card,'goal_contributions_reserved')]]}/>
      <p className="mvp-caption">This month's planned contributions are already subtracted from safe to spend on Home.</p>
    </Block>}
    {goals.map(goal=><section className="mvp-block mvp-goal" key={goal.label} aria-label={goal.label}>
      <header><h3>{goal.label}</h3><Chip tone={TONE_BY_GOAL[goal.tone]}>{goal.toneText}</Chip></header>
      <Progress pct={goal.pct} tone={goal.tone} label={goal.label+' progress'}/>
      <p className="mvp-goal-line"><span><strong className="tabular">{goal.saved||'IDR 0'}</strong> of <span className="tabular">{goal.target}</span></span><b className="tabular">{goal.pctText}</b></p>
      <Stats items={[['Target date',goal.targetDate],['Time left',goal.monthsLeft?goal.monthsLeft+' months':''],['Needed each month',goal.requiredMonthly],['Planned each month',goal.plannedMonthly],['Extra needed each month',goal.tone==='complete'?'':goal.extraMonthly],['Shortfall at target date',goal.tone==='complete'?'':goal.shortfall]]}/>
    </section>)}
    {goals.length>1&&totals.some(item=>item[1])&&<Block title="All goals together"><Stats items={totals}/></Block>}
    {card&&card.explanation&&<p className="mvp-caption">{card.explanation}</p>}
    <Ask text="Am I on track for my goals?" compose={compose}/>
  </>;
}

function InvestPanel({insights,compose}:Props){
  const card=insights.portfolio;
  if(!usable(card))return <Missing>No investment holdings are linked to this profile.</Missing>;
  const shares=allocationOf(card),holdings=holdingsOf(card);
  const asOf=shownDate(card.values.as_of||card.source?.event_at)||'today';
  const returnDirection=direction(card.values.gain_loss_percent),changeDirection=direction(card.values.change_30d_percent);
  return <>
    <Block title="Portfolio value">
      <strong className="mvp-figure">{shown(card,'total_value')}</strong>
      <div className="mvp-chips">
        {card.values.gain_loss_percent!==undefined&&<Chip tone={TONE_BY_DIRECTION[returnDirection]}>{signed(shown(card,'gain_loss_percent'))} since purchase</Chip>}
        {card.values.change_30d_percent!==undefined&&<Chip tone={TONE_BY_DIRECTION[changeDirection]}>{signed(shown(card,'change_30d_percent'))} in 30 days</Chip>}
      </div>
      <Stats items={[['Gain or loss',shown(card,'gain_loss')],['30-day change',shown(card,'change_30d')],['Cost basis',shown(card,'total_cost')],['Holdings',card.values.holdings_count?card.values.holdings_count+' assets':'']]}/>
    </Block>
    {shares.length>0&&<Block title="Allocation">
      <StackBar parts={shares} height={10} label={'Allocation: '+shares.map(share=>share.label+' '+share.text).join(', ')}/>
      <ul className="mvp-legend mvp-legend-compact">{shares.map(share=><li key={share.label}><i style={{background:share.color}} aria-hidden="true"/><span>{share.label}</span><b className="tabular">{share.text}</b></li>)}</ul>
    </Block>}
    {holdings.length>0&&<Block title="Holdings">
      <ul className="mvp-rows">{holdings.map(holding=><li key={holding.label}>
        <span><strong>{holding.label}</strong><small>{holding.kind}{holding.share?' · '+holding.share:''}{holding.since?' · since '+holding.since:''}</small></span>
        <span><b className="tabular">{holding.value}</b><small className="tabular">{[holding.gainPct&&holding.gainPct+' total',holding.change30&&holding.change30+' in 30d'].filter(Boolean).join(' · ')}</small></span>
      </li>)}</ul>
    </Block>}
    <p className="mvp-caption">Snapshot as of {asOf}. Information, not advice.</p>
    <Ask text="How are my investments doing?" compose={compose}/>
    {changeDirection==='down'&&<Ask text="Why did my fund drop?" compose={compose}/>}
  </>;
}

function MarketPanel({insights,compose}:Props){
  const market=marketOf(insights.market_insights);
  if(!market)return <Missing>Market information is not available yet.</Missing>;
  const head=market.headline;
  return <>
    {head&&<Block title={head.name||head.symbol} note={market.open?'Market open':'Market close'}>
      <strong className="mvp-figure">{head.price} <span className="mvp-delta" data-direction={head.direction}>{head.changeText}</span></strong>
      {market.sentiment&&<p className="mvp-sentence">Context: {market.sentiment}.</p>}
    </Block>}
    {market.ticks.length>0&&<Block title="Index and large-cap movers" note="Change on the day">
      <ul className="mvp-rows">{market.ticks.map(tick=><li key={tick.symbol}>
        <span><strong>{tick.symbol}</strong><small>{tick.name}</small></span>
        <span className="mvp-tick-values"><b className="tabular">{tick.price}</b><small className="tabular mvp-delta" data-direction={tick.direction}>{tick.changeText}</small></span>
        <ChangeBar tick={tick}/>
      </li>)}</ul>
    </Block>}
    <p className="mvp-caption">Sample market data{market.asOf?' as of '+market.asOf:''}. Context, not investment advice.</p>
    <Ask text={head&&head.direction==='down'?'Why did Indonesian equities and my portfolio drop today?':'How is the market today and how does it affect my portfolio?'} compose={compose}/>
  </>;
}

function Waterfall({rows}:{rows:Array<[string,string,string]>}){
  const present=rows.filter(row=>row[2]);
  if(present.length===0)return null;
  return <dl className="mvp-waterfall">{present.map(([sign,name,value])=><div key={name} data-sign={sign}><dt><span aria-hidden="true">{sign}</span>{name}</dt><dd className="tabular">{value}</dd></div>)}</dl>;
}

function CashPanel({insights,compose}:Props){
  const safe=insights.safe_to_spend,salary=insights.salary,recurring=insights.recurring,idle=insights.idle_cash,deposit=insights.term_deposit;
  const bills=billsOf(recurring);
  if(!usable(safe)&&!usable(salary)&&bills.length===0&&!usable(idle)&&!usable(deposit))return <Missing>Cash and bill information is not available yet.</Missing>;
  const days=safe?.values.days_to_payday,payday=shownDate(safe?.values.payday);
  const fixed=bills.filter(bill=>bill.group==='Bill or subscription'),regular=bills.filter(bill=>bill.group!=='Bill or subscription');
  const billRow=(bill:typeof bills[number])=><li key={bill.label+bill.next}>
    <span><strong>{bill.label}</strong><small>{[bill.cadence,bill.category,bill.next?'next '+bill.next:''].filter(Boolean).join(' · ')}</small></span>
    <span><b className="tabular">{bill.monthly}</b><small>a month · {bill.discretionary?<Chip tone="warn">{bill.type}</Chip>:bill.type}</small></span>
  </li>;
  const list=(items:typeof bills)=><>
    {items.length>0&&<ul className="mvp-rows">{items.slice(0,4).map(billRow)}</ul>}
    {items.length>4&&<details className="mvp-more"><summary>Show {items.length-4} more</summary><ul className="mvp-rows">{items.slice(4).map(billRow)}</ul></details>}
  </>;
  return <>
    {usable(safe)&&<Block title="Safe to spend" note={payday?'Until payday, '+payday:'Next 30 days'}>
      {safe.status==='GAP'&&<p className="mvp-alert" role="alert">Projected shortfall before payday</p>}
      <Waterfall rows={[['','Available balance',shown(safe,'available')],['−','Bills due before payday',shown(safe,'commitments_until_payday')],['−','Card payment due before payday',shown(safe,'card_payment_until_payday')],['−','Goal contributions set aside',shown(safe,'goal_contributions_reserved')],['−','Everyday spending'+(days?' for '+days+' days':''),shown(safe,'everyday_spending_until_payday')],['=','Safe to spend',shown(safe,'headroom_until_payday')]]}/>
      <Stats items={[['Projected balance in 30 days',shown(safe,'projected_30d_balance')],['Monthly surplus before goals',shown(safe,'monthly_surplus_estimate')],['Emergency buffer',safe.values.buffer_months?safe.values.buffer_months+' months':'']]}/>
      <p className="mvp-caption">Everyday spending is your 90-day average without bills. Goal savings sit in separate pockets.</p>
      <Ask text="How much can I safely spend this month?" compose={compose}/>
    </Block>}
    {(usable(recurring)||bills.length>0)&&<Block title="Bills and subscriptions" note={shown(recurring,'bills_monthly_total')?shown(recurring,'bills_monthly_total')+' a month':'Monthly estimates'}>
      {list(fixed)}
      {regular.length>0&&<>
        <header className="mvp-subhead"><h4>Regular spending</h4><small className="tabular">{shown(recurring,'regular_monthly_total')?shown(recurring,'regular_monthly_total')+' a month':''}</small></header>
        {list(regular)}
      </>}
      <p className="mvp-caption">Monthly estimates from 90 days. No payment or cancellation is made here.</p>
      <Ask text="Are there subscriptions or recurring costs I can cut?" compose={compose}/>
    </Block>}
    {usable(salary)&&<Block title={salary.title}>
      <Stats items={[['Salary',shown(salary,'salary_amount')],['Usually paid on day',salary.values.salary_day]]}/>
      {salary.explanation&&<p className="mvp-caption">{salary.explanation}</p>}
    </Block>}
    {usable(idle)&&<Block title={idle.title}>
      <p className="mvp-sentence">{shown(idle,'idle_cash')} surplus above 3x monthly outflow. {idle.explanation}</p>
      <Ask text="How should I think about liquidity before discussing a deposit?" label="Explore liquidity options" compose={compose}/>
    </Block>}
    {usable(deposit)&&<Block title={deposit.title}>
      <p className="mvp-sentence">{shown(deposit,'balance')} maturing on {shownDate(deposit.values.maturity_date)||'an upcoming date'}. {deposit.explanation}</p>
      <Ask text="What should I discuss with my RM before my deposit matures?" label="Prepare deposit discussion" compose={compose}/>
    </Block>}
  </>;
}

function WorthPanel({insights,compose}:Props){
  const worth=insights.net_worth,debt=insights.debt;
  if(!usable(worth)&&!usable(debt))return <Missing>Account coverage is unavailable for this profile.</Missing>;
  return <>
    {usable(worth)&&<Block title="Net worth">
      <strong className="mvp-figure">{shown(worth,'net_worth')}</strong>
      <Stats items={[['Total assets',shown(worth,'assets_total')],['Total liabilities',shown(worth,'liabilities_total')],['30-day asset change',shown(worth,'assets_change_30d_percent')],['Emergency buffer',worth.values.buffer_months?worth.values.buffer_months+' months':''],['Savings rate',shown(worth,'savings_rate_percent')],['Debt-to-income',shown(worth,'debt_to_income_percent')]]}/>
      {(worth.rows||[]).length>0&&<ul className="mvp-rows">{(worth.rows||[]).map(row=><li key={row.label}><span><strong>{row.label}</strong></span><b className="tabular">{row.amount}</b></li>)}</ul>}
      <Ask text="How is my overall financial health?" compose={compose}/>
    </Block>}
    {usable(debt)&&<Block title="Credit card cost" note="Debt overview">
      <strong className="mvp-figure">{shown(debt,'outstanding_total')}</strong>
      <Stats items={[['Interest each month',shown(debt,'monthly_interest_cost')],['Card rate',shown(debt,'card_rate_percent')],['Minimum payment',shown(debt,'minimum_payment_total')],['Months to clear at minimum',debt.values.months_to_clear_at_minimum?debt.values.months_to_clear_at_minimum+' months':''],['Interest at minimum',shown(debt,'interest_paid_at_minimum')],['Buffer after repayment',debt.values.buffer_months_after_repayment?debt.values.buffer_months_after_repayment+' months':'']]}/>
      {debt.values.savings_interest_percent&&<p className="mvp-sentence">Savings earn {shown(debt,'savings_interest_percent')} against {shown(debt,'card_rate_percent')} on the card{debt.values.monthly_interest_earned_on_same_amount?`; the same amount in savings earns ${shown(debt,'monthly_interest_earned_on_same_amount')} a month`:''}.</p>}
      {(debt.rows||[]).length>0&&<ul className="mvp-rows">{(debt.rows||[]).map(row=><li key={row.label}>
        <span><strong>{row.label}</strong><small>{row.rate_percent?'Rate '+row.rate_percent:''}{row.due_day?' · due '+row.due_day:''}</small></span>
        <span><b className="tabular">{row.outstanding}</b><small className="tabular">{row.minimum_payment?'Minimum '+row.minimum_payment:''}</small></span>
      </li>)}</ul>}
      <Ask text="Should I pay down my credit card or save more?" compose={compose}/>
    </Block>}
  </>;
}

function StepsPanel({insights,compose,open}:Props){
  const steps=stepsOf(insights.next_actions);
  if(steps.length===0)return <Missing>Not enough linked information to suggest next steps.</Missing>;
  return <>
    <ol className="mvp-steps">{steps.map(step=>{
      const target=PANEL_FOR_TOPIC[step.topic.toLowerCase()];
      return <li key={step.rank+step.action}>
        <span className="mvp-step-rank" aria-hidden="true">{step.rank}</span>
        <div>
          {step.topic&&<small className="mvp-topic">{step.topic}</small>}
          <strong>{step.action}</strong>
          {step.reason&&<p>{step.reason}</p>}
          {target&&<button type="button" className="mvp-inline" onClick={()=>open(target)}>See the figures<ChevronRight size={14} aria-hidden="true"/></button>}
        </div>
      </li>;
    })}</ol>
    {insights.next_actions?.explanation&&<p className="mvp-caption">{insights.next_actions.explanation}</p>}
    <Ask text="What should I do next to improve my finances?" compose={compose}/>
  </>;
}

function ExplorePanel({compose,nudges,comparisons,viewProduct}:{compose:Compose;nudges:RMEnrichedNudge[];comparisons:RMComparison[];viewProduct:(product:'DEPOSIT'|'SAVINGS')=>void}){
  return <>
    {nudges.length>0&&<Block title="For you">
      <ul className="mvp-nudges">{nudges.slice(0,3).map(nudge=><li key={nudge.id}>
        <strong>{nudge.title}</strong>
        <p>{nudge.body}</p>
        <button type="button" className="mvp-inline" onClick={()=>compose(nudge.prompt)}>Ask the assistant<ArrowUpRight size={14} aria-hidden="true"/></button>
      </li>)}</ul>
    </Block>}
    {comparisons.length>0&&<Block title="Banking products" note="Approved education">
      <div className="mvp-product-list">{comparisons.map(item=><details className="mvp-product-detail" key={item.title} onToggle={event=>{if(event.currentTarget.open)viewProduct(item.title.toLowerCase().includes('deposit')?'DEPOSIT':'SAVINGS');}}>
        <summary><div><strong>{item.title}</strong><span>{item.ownership==='Already held'?'Get help with your existing product':'Understand the features and tradeoffs'}</span></div><ChevronRight size={17} aria-hidden="true"/></summary>
        <p>{item.education}</p>
        <small>{item.eligibility} · {item.terms_status}</small>
        <button onClick={()=>compose('Explain '+item.title+' and the access, term and fee information I should check.')}>Ask the assistant about this <ArrowUpRight size={14} aria-hidden="true"/></button>
      </details>)}</div>
    </Block>}
    {nudges.length===0&&comparisons.length===0&&<Missing>Nothing to explore right now.</Missing>}
    <p className="mvp-caption">Personal insights use permitted bank information. Product eligibility, fees and current terms require the bank’s own checks.</p>
  </>;
}

export function PanelView({panel,insights,nudges,comparisons,compose,open,close,viewProduct,titleRef}:Props&{panel:Panel;nudges:RMEnrichedNudge[];comparisons:RMComparison[];close:()=>void;viewProduct:(product:'DEPOSIT'|'SAVINGS')=>void;titleRef:Ref<HTMLHeadingElement>}){
  const meta=PANEL_META[panel];
  const props={insights,compose,open};
  return <section className="mvp-panel" aria-labelledby="mvp-panel-title">
    <header className="mvp-panel-head">
      <button type="button" className="mvp-back" onClick={close} aria-label="Back to overview"><ChevronLeft size={22} aria-hidden="true"/></button>
      <div><h2 id="mvp-panel-title" ref={titleRef} tabIndex={-1}>{meta.title}</h2><small>{meta.note}</small></div>
    </header>
    <div className="mvp-panel-body">
      {panel==='spending'&&<SpendingPanel {...props}/>}
      {panel==='goals'&&<GoalsPanel {...props}/>}
      {panel==='invest'&&<InvestPanel {...props}/>}
      {panel==='market'&&<MarketPanel {...props}/>}
      {panel==='cash'&&<CashPanel {...props}/>}
      {panel==='worth'&&<WorthPanel {...props}/>}
      {panel==='steps'&&<StepsPanel {...props}/>}
      {panel==='explore'&&<ExplorePanel compose={compose} nudges={nudges} comparisons={comparisons} viewProduct={viewProduct}/>}
    </div>
  </section>;
}
