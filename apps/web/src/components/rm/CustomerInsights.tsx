"use client";
import {useEffect,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {Activity,ChevronRight,Compass,Lightbulb,PieChart,Scale,Target,TrendingUp,Wallet} from 'lucide-react';
import {useRM,RequestState} from './shared';
import {dateLabel} from '@/lib/presentation';
import {allocationOf,direction,geometry,goalsOf,indexInsights,marketOf,pacingOf,shown,shownDate,signed,sparkOf,spendingSlices,stepsOf,usable} from '@/lib/home-model';
import type {Insights,Panel} from '@/lib/home-model';
import type {RMEngagementFeed,RMEnrichedNudge} from '@/lib/rm.generated';
import {Progress,Sparkline,StackBar,TickBars} from './HomeCharts';
import {PanelView} from './HomePanels';

type Open=(panel:Panel)=>void;
type TileProps={insights:Insights;open:Open};

const SPARK_WIDTH=104,SPARK_HEIGHT=40;
const DIRECTION_TONE={up:'good',down:'bad',flat:'neutral'} as const;
const SPEND_TONE={up:'warn',down:'good',flat:'neutral'} as const;

function Hero({insights}:{insights:Insights}){
  const cash=insights.cash_flow,safe=insights.safe_to_spend,trend=insights.balance_trend;
  const pace=pacingOf(cash,safe),spark=sparkOf(trend,SPARK_WIDTH,SPARK_HEIGHT);
  const balance=shown(cash,'available')||shown(safe,'available');
  const updated=shownDate(safe?.values.as_of)||(cash?.source?dateLabel(cash.source.event_at):'');
  const days=safe?.values.days_to_payday;
  const parts:Array<{name:string;value:string;color:string;weight:number}>=!pace?[]:pace.untilPayday
    ?[{name:days?`Safe to spend · ${days} days to payday`:'Safe to spend until payday',value:shown(safe,'headroom_until_payday'),color:'var(--chart-1)',weight:pace.headroom},
      {name:'Everyday spending until payday',value:shown(safe,'everyday_spending_until_payday'),color:'var(--chart-2)',weight:pace.everyday},
      {name:'Goal contributions set aside',value:shown(safe,'goal_contributions_reserved'),color:'var(--chart-3)',weight:pace.goals},
      {name:'Bills due before payday',value:shown(safe,'commitments_until_payday'),color:'var(--chart-4)',weight:pace.bills},
      {name:'Card payment due before payday',value:shown(safe,'card_payment_until_payday'),color:'var(--chart-5)',weight:pace.card}]
    :[{name:'Free after commitments',value:shown(cash,'difference'),color:'var(--chart-1)',weight:pace.headroom},{name:'Commitments in 14 days',value:shown(cash,'commitments'),color:'var(--chart-4)',weight:pace.bills}];
  const visible=parts.filter((part,index)=>part.value&&(index===0||part.weight>0));
  return <section className="mvp-hero" aria-label="Available balance">
    <div className="mvp-hero-top">
      <div>
        <span className="mvp-eyebrow">Available balance{updated&&updated!=='Not available'?' · as of '+updated:''}</span>
        <strong className="mvp-hero-amount tabular">{balance||'Not available'}</strong>
      </div>
      {spark&&<Sparkline spark={spark} width={SPARK_WIDTH} height={SPARK_HEIGHT} label={`Balance over the last ${spark.days} days. Low ${shown(trend,'balance_30d_min')}, average ${shown(trend,'balance_30d_avg')}, now ${shown(trend,'balance_now')}.`}/>}
    </div>
    {pace&&<>
      {pace.gap&&<p className="mvp-alert" role="alert">Projected shortfall before payday</p>}
      <StackBar height={8} label={'Available balance split: '+visible.map(part=>part.name+' '+part.value).join(', ')} parts={visible.filter(part=>part.weight>0).map(part=>({weight:part.weight,color:part.color}))}/>
      <ul className="mvp-hero-legend">{visible.map((part,index)=><li key={part.name} data-lead={index===0||undefined}><i style={{background:part.color}} aria-hidden="true"/><span>{part.name}</span><b className="tabular">{part.value}</b></li>)}</ul>
    </>}
  </section>;
}

function Tile({panel,icon,title,aside,label,open,children}:{panel:Panel;icon:ReactNode;title:string;aside?:ReactNode;label:string;open:Open;children:ReactNode}){
  return <button type="button" className="mvp-tile" data-open={panel} aria-label={label} onClick={()=>open(panel)}>
    <span className="mvp-tile-head"><span>{icon}{title}</span>{aside||<ChevronRight size={14} aria-hidden="true"/>}</span>
    {children}
  </button>;
}

function EmptyTile({icon,title,message}:{icon:ReactNode;title:string;message:string}){
  return <div className="mvp-tile" data-empty="true"><span className="mvp-tile-head"><span>{icon}{title}</span></span><span className="mvp-tile-note">{message}</span></div>;
}

function More({rows}:{rows:Array<[string,string,string]>}){
  if(rows.length===0)return null;
  return <span className="mvp-tile-more mvp-tile-rows">{rows.map(([name,value,color])=><span key={name}><i style={{background:color}} aria-hidden="true"/><span>{name}</span><b className="tabular">{value}</b></span>)}</span>;
}

function SpendingTile({insights,open}:TileProps){
  const breakdown=insights.spending_breakdown,change=insights.spending,icon=<PieChart size={14} aria-hidden="true"/>;
  if(usable(breakdown)){
    const rise=geometry(breakdown.values.biggest_increase_percent),category=breakdown.values.biggest_increase_category;
    return <Tile panel="spending" icon={icon} title="Spending" aside={<small>30 days</small>} open={open} label={`Spending: ${shown(breakdown,'total_spend')} in the last 30 days. Open details.`}>
      <span className="mvp-tile-figure tabular">{shown(breakdown,'total_spend')}</span>
      <More rows={spendingSlices(breakdown).slice(0,3).map(slice=>[slice.label,slice.share,slice.color])}/>
      <StackBar parts={spendingSlices(breakdown)} label="Spending by category" height={8}/>
      {rise!==null&&rise>0&&category?<span className="mvp-chip" data-tone="warn">{category} {signed(shown(breakdown,'biggest_increase_percent'))}</span>:<span className="mvp-tile-note">Largest: {breakdown.values.top_category||'not available'}</span>}
    </Tile>;
  }
  if(usable(change)){
    const risePercent=signed(shown(change,'change_percent'));
    return <Tile panel="spending" icon={icon} title="Spending" aside={<small>30 days</small>} open={open} label={`${change.title}: ${shown(change,'current_spend')}. Open details.`}>
      <span className="mvp-tile-figure tabular">{shown(change,'current_spend')}</span>
      {risePercent&&<span className="mvp-chip" data-tone={SPEND_TONE[direction(change.values.change_percent)]}>{change.title.replace(/ spending$/i,'')} {risePercent}</span>}
    </Tile>;
  }
  return <EmptyTile icon={icon} title="Spending" message="Not available yet."/>;
}

function GoalsTile({insights,open}:TileProps){
  const goals=goalsOf(insights.goal_progress),icon=<Target size={14} aria-hidden="true"/>;
  if(goals.length===0)return <EmptyTile icon={icon} title="Goals" message="No goal recorded."/>;
  return <Tile panel="goals" icon={icon} title="Goals" aside={<small>{goals.length} {goals.length===1?'goal':'goals'}</small>} open={open} label={'Goals: '+goals.map(goal=>`${goal.label}, ${goal.pctText}, ${goal.toneText}`).join('; ')+'. Open details.'}>
    {goals.slice(0,2).map(goal=><span className="mvp-mini-goal" key={goal.label}>
      <span><b>{goal.label}</b><i className="tabular">{goal.pctText}</i></span>
      <Progress decorative pct={goal.pct} tone={goal.tone} label={goal.label+' progress'}/>
      {goal.saved&&<small className="mvp-tile-more tabular">{goal.saved} saved</small>}
    </span>)}
    {goals.length>2&&<span className="mvp-tile-note">+{goals.length-2} more</span>}
  </Tile>;
}

function InvestTile({insights,open}:TileProps){
  const card=insights.portfolio,icon=<TrendingUp size={14} aria-hidden="true"/>;
  if(!usable(card))return <EmptyTile icon={icon} title="Investments" message="No holdings linked."/>;
  const shares=allocationOf(card);
  return <Tile panel="invest" icon={icon} title="Investments" open={open} label={`Investments: portfolio value ${shown(card,'total_value')}. Open details.`}>
    <span className="mvp-tile-figure tabular">{shown(card,'total_value')}</span>
    <span className="mvp-tile-chips">
      {card.values.gain_loss_percent!==undefined&&<span className="mvp-chip" data-tone={DIRECTION_TONE[direction(card.values.gain_loss_percent)]}>{signed(shown(card,'gain_loss_percent'))}</span>}
      {card.values.change_30d_percent!==undefined&&<span className="mvp-chip" data-tone={DIRECTION_TONE[direction(card.values.change_30d_percent)]}>{signed(shown(card,'change_30d_percent'))} 30d</span>}
    </span>
    {shares.length>0&&<More rows={shares.map(share=>[share.label,share.text,share.color])}/>}
    {shares.length>0&&<StackBar parts={shares} height={6} label={'Allocation: '+shares.map(share=>share.label+' '+share.text).join(', ')}/>}
  </Tile>;
}

function MarketTile({insights,open}:TileProps){
  const market=marketOf(insights.market_insights),icon=<Activity size={14} aria-hidden="true"/>;
  if(!market)return <EmptyTile icon={icon} title="Market" message="Not available yet."/>;
  const head=market.headline,movers=market.ticks.filter(tick=>tick.kind!=='INDEX').slice(0,5);
  return <Tile panel="market" icon={icon} title="Market" aside={<small>{market.open?'Open':'Close'}</small>} open={open} label={`Market: ${head?head.symbol+' '+head.changeText:'update'}. Open details.`}>
    {head&&<span className="mvp-tile-figure">{head.symbol} <span className="mvp-delta" data-direction={head.direction}>{head.changeText}</span></span>}
    {market.asOf&&<small className="mvp-tile-more">{market.asOf} · sample data</small>}
    {movers.length>0&&<TickBars ticks={movers}/>}
  </Tile>;
}

function Lead({insights,nudges,open}:TileProps&{nudges:RMEnrichedNudge[]}){
  const step=stepsOf(insights.next_actions)[0];
  const lead=step?{caption:'Next step',text:step.action,panel:'steps' as Panel}:nudges[0]?{caption:'For you',text:nudges[0].title,panel:'explore' as Panel}:null;
  if(!lead)return null;
  return <button type="button" className="mvp-lead" data-open={lead.panel} onClick={()=>open(lead.panel)}>
    <Lightbulb size={16} aria-hidden="true"/>
    <span><small>{lead.caption}</small><strong>{lead.text}</strong></span>
    <ChevronRight size={16} aria-hidden="true"/>
  </button>;
}

function Shortcut({panel,icon,title,figure,open}:{panel:Panel;icon:ReactNode;title:string;figure:string;open:Open}){
  return <button type="button" className="mvp-shortcut" data-open={panel} aria-label={`${title}${figure?': '+figure:''}. Open details.`} onClick={()=>open(panel)}>
    <span>{icon}{title}</span>
    {figure&&<small className="tabular">{figure}</small>}
  </button>;
}

export function CustomerInsights({personId,active,compose,viewProduct,onInsights}:{personId:string;active:boolean;compose:(text:string)=>void;viewProduct:(product:'DEPOSIT'|'SAVINGS')=>void;onInsights?:(insights:Insights)=>void}){
  const q=useRM<RMEngagementFeed>(`/v1/rm/chat/${personId}/engagement`),prior=useRef(active);
  const [panel,setPanel]=useState<Panel|null>(null);
  const root=useRef<HTMLElement>(null),title=useRef<HTMLHeadingElement>(null),origin=useRef<Panel|null>(null);
  useEffect(()=>{if(active&&!prior.current)q.refresh();prior.current=active;},[active,q.refresh]);
  useEffect(()=>{if(q.data)onInsights?.(indexInsights(q.data.insights));},[q.data,onInsights]);
  useEffect(()=>{
    if(panel)title.current?.focus({preventScroll:true});
    else if(origin.current)root.current?.querySelector<HTMLElement>(`[data-open="${origin.current}"]`)?.focus({preventScroll:true});
  },[panel]);
  const open:Open=next=>{origin.current=next;setPanel(next);};
  const insights=indexInsights(q.data?q.data.insights:[]),nudges=q.data?q.data.nudges:[];
  return <section className="mvp-insights" ref={root} onKeyDown={event=>{if(panel&&event.key==='Escape'){event.stopPropagation();setPanel(null);}}}>
    <RequestState data={q.data} error={q.error} retry={q.refresh}/>
    {q.data&&(panel
      ?<PanelView panel={panel} insights={insights} nudges={nudges} comparisons={q.data.comparisons} compose={compose} open={open} close={()=>setPanel(null)} viewProduct={viewProduct} titleRef={title}/>
      :<div className="mvp-home">
        <h1 className="sr-only">Your money overview</h1>
        <Hero insights={insights}/>
        <div className="mvp-tiles">
          <SpendingTile insights={insights} open={open}/>
          <GoalsTile insights={insights} open={open}/>
          <InvestTile insights={insights} open={open}/>
          <MarketTile insights={insights} open={open}/>
        </div>
        <Lead insights={insights} nudges={nudges} open={open}/>
        <div className="mvp-shortcuts">
          <Shortcut panel="cash" icon={<Wallet size={16} aria-hidden="true"/>} title="Bills" figure={shown(insights.recurring,'bills_monthly_total')?shown(insights.recurring,'bills_monthly_total')+'/mo':''} open={open}/>
          <Shortcut panel="worth" icon={<Scale size={16} aria-hidden="true"/>} title="Net worth" figure={shown(insights.net_worth,'net_worth')} open={open}/>
          <Shortcut panel="explore" icon={<Compass size={16} aria-hidden="true"/>} title="Explore" figure="Products, guides" open={open}/>
        </div>
      </div>)}
  </section>;
}
