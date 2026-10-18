import type {RMInsight} from './rm.generated';
import {insightValue} from './engagement-presentation';
import {dateLabel} from './presentation';

export type Panel='spending'|'goals'|'invest'|'market'|'cash'|'worth'|'steps'|'explore';
export type Insights=Record<string,RMInsight|undefined>;
export type Row=Record<string,string>;
export type Direction='up'|'down'|'flat';

export function indexInsights(list:RMInsight[]):Insights{
  const index:Insights={};
  list.forEach(insight=>{index[insight.key]=insight;});
  return index;
}

export const usable=(insight?:RMInsight):insight is RMInsight=>insight!==undefined&&insight.status!=='UNAVAILABLE';

export function shown(card:RMInsight|undefined,key:string):string{
  const raw=card?.values[key];
  return card&&raw!==undefined?insightValue(key,raw,card.currency):'';
}

/** Chart geometry only: every figure shown to the customer stays the backend's own decimal string. */
export function geometry(value:string|undefined|null):number|null{
  if(value===undefined||value===null)return null;
  const match=/-?\d[\d,]*(?:\.\d+)?/.exec(String(value).replace(/\s/g,''));
  if(!match)return null;
  const parsed=Number(match[0].replace(/,/g,''));
  return Number.isFinite(parsed)?parsed:null;
}

export function shownDate(raw:string|undefined|null):string{
  if(!raw)return '';
  const label=dateLabel(raw);
  return label==='Not available'?raw:label;
}

export function direction(raw:string|undefined|null):Direction{
  const parsed=geometry(raw);
  return parsed===null||parsed===0?'flat':parsed>0?'up':'down';
}

export function signed(text:string):string{
  if(!text||/^[+-]/.test(text))return text;
  const parsed=geometry(text);
  return parsed!==null&&parsed>0?'+'+text:text;
}

const PALETTE=['var(--chart-1)','var(--chart-2)','var(--chart-3)','var(--chart-4)','var(--chart-5)','var(--chart-6)'];

export type Slice={label:string;weight:number;color:string;amount:string;share:string;change:string;direction:Direction};
export function spendingSlices(card?:RMInsight):Slice[]{
  if(!usable(card))return [];
  const rows=(card.rows||[]).slice(0,6);
  const byAmount=rows.length>0&&rows.every(row=>geometry(row.amount)!==null);
  return rows.map((row,index)=>({
    label:row.label||'Other',
    weight:(byAmount?geometry(row.amount):geometry(row.share_percent))||0,
    color:PALETTE[index%PALETTE.length],
    amount:row.amount||'',
    share:row.share_percent||'',
    change:row.change_percent||'',
    direction:direction(row.change_percent)
  })).filter(slice=>slice.weight>0);
}

export type Share={label:string;weight:number;color:string;text:string};
const ALLOCATION:Array<[string,string,string]>=[['Equity','equity_percent','var(--chart-1)'],['Bonds','bond_percent','var(--chart-3)'],['Money market','money_market_percent','var(--chart-4)']];
export function allocationOf(card?:RMInsight):Share[]{
  if(!usable(card))return [];
  const shares:Share[]=[];
  ALLOCATION.forEach(([label,key,color])=>{
    const raw=card.values[key],weight=geometry(raw);
    if(raw!==undefined&&weight!==null&&weight>0)shares.push({label,weight,color,text:insightValue(key,raw,null)});
  });
  return shares;
}

export type GoalTone='complete'|'behind'|'on_track';
export type Goal={label:string;pct:number;pctText:string;tone:GoalTone;toneText:string;saved:string;target:string;targetDate:string;monthsLeft:string;requiredMonthly:string;plannedMonthly:string;extraMonthly:string;shortfall:string};
const TONE_TEXT:Record<GoalTone,string>={complete:'Complete',behind:'Behind',on_track:'On track'};
function toneOf(status:string|undefined):GoalTone{
  const normalized=(status||'').toUpperCase().replace(/[\s-]/g,'_');
  return normalized.includes('COMPLETE')?'complete':normalized.includes('BEHIND')?'behind':'on_track';
}
function singleGoalRow(card:RMInsight):Row[]{
  const values=card.values;
  if(!values.goal_name)return [];
  const money=(key:string)=>values[key]?insightValue(key,values[key],card.currency):'';
  return [{label:values.goal_name,target:money('target_amount'),saved:money('saved_amount'),progress_percent:values.progress_percent?values.progress_percent+'%':'',target_date:values.target_date||'',required_monthly:money('required_monthly'),planned_monthly:money('planned_monthly'),extra_monthly_needed:money('extra_monthly_needed'),shortfall:money('shortfall_amount'),months_left:values.months_left||'',status:values.goal_status||'ON_TRACK'}];
}
export function goalsOf(card?:RMInsight):Goal[]{
  if(!usable(card))return [];
  const rows=card.rows&&card.rows.length>0?card.rows:singleGoalRow(card);
  return rows.map(row=>{
    const pct=Math.min(100,Math.max(0,geometry(row.progress_percent)||0));
    const tone=toneOf(row.status);
    return {label:row.label||'Financial goal',pct,pctText:row.progress_percent||pct+'%',tone,toneText:TONE_TEXT[tone],saved:row.saved||'',target:row.target||'',targetDate:shownDate(row.target_date),monthsLeft:row.months_left||'',requiredMonthly:row.required_monthly||'',plannedMonthly:row.planned_monthly||'',extraMonthly:row.extra_monthly_needed||'',shortfall:row.shortfall||''};
  });
}

export type Holding={label:string;kind:string;value:string;share:string;gain:string;gainPct:string;change30:string;since:string};
export function holdingsOf(card?:RMInsight):Holding[]{
  if(!usable(card))return [];
  return (card.rows||[]).map(row=>({label:row.label||'Holding',kind:row.asset_class||'',value:row.value||'',share:row.share_percent||'',gain:row.gain_loss||'',gainPct:row.gain_loss_percent||'',change30:row.change_30d_percent||'',since:row.holding_since||''}));
}

export type Bill={label:string;category:string;type:string;group:string;cadence:string;monthly:string;next:string;times:string;discretionary:boolean};
export function billsOf(card?:RMInsight):Bill[]{
  if(!usable(card))return [];
  return (card.rows||[]).map(row=>({label:row.label||'Recurring payment',category:row.category||'',type:row.type||'Recurring',group:row.group||'Bill or subscription',cadence:row.cadence||'',monthly:row.monthly_estimate||row.typical_amount||'',next:shownDate(row.next_expected),times:row.times_90d||'',discretionary:row.type==='Discretionary'}));
}

export type Step={rank:string;topic:string;action:string;reason:string};
export function stepsOf(card?:RMInsight):Step[]{
  if(!usable(card))return [];
  const ranked=(card.rows||[]).slice().sort((a,b)=>(geometry(a.rank)||99)-(geometry(b.rank)||99));
  return ranked.map((row,index)=>({rank:row.rank||String(index+1),topic:row.topic||'',action:row.action||'',reason:row.reason||''}));
}
export const PANEL_FOR_TOPIC:Record<string,Panel>={cash:'cash',debt:'worth',buffer:'cash',goal:'goals',spending:'cash',invest:'invest'};

const DEFAULT_STARTERS=['Help me manage my cash flow','Why has my spending increased?','Explain time deposits'];
const SERVICE_STARTER='I need help with a banking issue';
export function startersOf(insights:Insights):string[]{
  const picked:string[]=[];
  const spend=insights.spending_breakdown,goal=insights.goal_progress,step=stepsOf(insights.next_actions)[0];
  if(usable(spend)&&spend.values.biggest_increase_category)picked.push(`Why did my ${spend.values.biggest_increase_category.toLowerCase()} spending go up?`);
  if(usable(goal)&&goal.values.goal_status==='BEHIND'&&goal.values.goal_name)picked.push(`How can I catch up on my ${goal.values.goal_name} goal?`);
  if(step&&step.topic==='debt')picked.push('Should I pay off my credit card first?');
  if(usable(insights.safe_to_spend))picked.push('How much can I safely spend until payday?');
  return picked.concat(DEFAULT_STARTERS).filter((text,index,all)=>all.indexOf(text)===index).slice(0,3).concat(SERVICE_STARTER);
}

export type Tick={symbol:string;name:string;kind:string;price:string;changeText:string;direction:Direction;size:number};
export type Market={open:boolean;asOf:string;sentiment:string;headline?:Tick;ticks:Tick[]};
export function marketOf(card?:RMInsight):Market|null{
  if(!usable(card))return null;
  const rows=card.rows||[];
  const largest=Math.max.apply(null,[0].concat(rows.map(row=>Math.abs(geometry(row.change_percent)||0))));
  const ticks=rows.map(row=>{
    const change=geometry(row.change_percent)||0;
    const price=row.price?insightValue('price',row.price,null):'';
    return {symbol:row.symbol||'',name:row.name||'',kind:row.type||'',price:price&&row.type!=='INDEX'?'IDR '+price:price,changeText:signed(row.change_percent||''),direction:direction(row.change_percent),size:change===0||largest===0?0:Math.max(0.12,Math.abs(change)/largest)};
  });
  const headline=ticks.find(tick=>tick.symbol==='IHSG')||ticks.find(tick=>tick.kind==='INDEX');
  return {open:card.values.session!=='CLOSE',asOf:card.values.as_of||'',sentiment:card.values.sentiment||'',headline,ticks};
}

export type Pacing={headroom:number;everyday:number;goals:number;bills:number;card:number;gap:boolean;untilPayday:boolean};
export function pacingOf(cash?:RMInsight,safe?:RMInsight):Pacing|null{
  if(usable(safe)){
    const part=(key:string)=>geometry(safe.values[key])||0;
    const available=geometry(safe.values.available),headroom=geometry(safe.values.headroom_until_payday);
    if(available!==null&&available>0&&headroom!==null){
      const everyday=part('everyday_spending_until_payday'),goals=part('goal_contributions_reserved'),bills=part('commitments_until_payday'),card=part('card_payment_until_payday');
      const base=Math.max(available,everyday+goals+bills+card);
      return {headroom:Math.max(headroom,0)/base,everyday:everyday/base,goals:goals/base,bills:bills/base,card:card/base,gap:safe.status==='GAP'||headroom<0,untilPayday:true};
    }
  }
  if(usable(cash)){
    const available=geometry(cash.values.available),commitments=geometry(cash.values.commitments),free=geometry(cash.values.difference);
    if(available!==null&&available>0&&commitments!==null&&free!==null){
      const base=Math.max(available,commitments);
      return {headroom:Math.max(free,0)/base,everyday:0,goals:0,bills:commitments/base,card:0,gap:cash.status==='GAP'||free<0,untilPayday:false};
    }
  }
  return null;
}

export type Spark={line:string;area:string;end:[number,number];days:number};
export function sparkOf(card:RMInsight|undefined,width:number,height:number,pad=3):Spark|null{
  if(!usable(card))return null;
  const values:number[]=[];
  (card.series||[]).forEach(point=>{const parsed=geometry(point.balance);if(parsed!==null)values.push(parsed);});
  if(values.length<2)return null;
  const low=Math.min.apply(null,values),high=Math.max.apply(null,values),step=(width-pad*2)/(values.length-1);
  const points=values.map((value,index)=>[pad+index*step,pad+(1-(high===low?0.5:(value-low)/(high-low)))*(height-pad*2)]);
  const line=points.map((point,index)=>(index?'L':'M')+point[0].toFixed(1)+' '+point[1].toFixed(1)).join('');
  const first=points[0],last=points[points.length-1];
  return {line,area:line+'L'+last[0].toFixed(1)+' '+height+'L'+first[0].toFixed(1)+' '+height+'Z',end:[last[0],last[1]],days:values.length};
}

export type Arc={length:number;offset:number;color:string};
export function donutArcs(slices:Array<{weight:number;color:string}>,gap=0.8):Arc[]{
  const total=slices.reduce((sum,slice)=>sum+slice.weight,0);
  if(total<=0)return [];
  let used=0;
  return slices.map(slice=>{
    const share=slice.weight/total*100;
    const arc={length:Math.max(share-(slices.length>1?gap:0),0.01),offset:-used,color:slice.color};
    used+=share;
    return arc;
  });
}
