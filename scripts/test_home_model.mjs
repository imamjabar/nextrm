/** Home view-model invariants in Node; chart geometry must follow the backend's figures. No browser/computer automation. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../apps/web/package.json',import.meta.url));
const ts=require('typescript');
const root=path.resolve('apps/web/src/lib');
const cache=new Map();
function load(file){
  const full=path.resolve(root,file);
  if(cache.has(full))return cache.get(full).exports;
  const module={exports:{}};cache.set(full,module);
  const code=ts.transpileModule(fs.readFileSync(full,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText;
  const resolve=id=>id.startsWith('.')?load(id.replace(/^\.\//,'')+'.ts'):require(id);
  vm.runInNewContext(`(function(require,module,exports){${code}\n})`,{Intl,Date,Number,Math,String,Array,Object,RegExp},{filename:full})(resolve,module,module.exports);
  return module.exports;
}
const m=load('home-model.ts');
const card=(key,values,rows=[],extra={})=>({key,title:key,status:'AVAILABLE',explanation:'',currency:'IDR',values,rows,method:'TEST',...extra});
const near=(actual,expected,message)=>assert.ok(Math.abs(actual-expected)<1e-9,`${message}: ${actual} vs ${expected}`);
const same=(actual,expected,message)=>assert.deepEqual(JSON.parse(JSON.stringify(actual)),expected,message);

assert.equal(m.geometry('IDR 1,800,000'),1800000);
assert.equal(m.geometry('-1.20%'),-1.2);
assert.equal(m.geometry('IDR -275,000'),-275000);
assert.equal(m.geometry(''),null);
assert.equal(m.geometry('not available'),null);
same(['27.78%','-1.20%','+2.50%','0.00%'].map(m.signed),['+27.78%','-1.20%','+2.50%','0.00%']);

const spending=card('spending_breakdown',{total_spend:'6035000.00'},[
  {label:'Groceries',amount:'IDR 1,800,000',share_percent:'29.83%',change_percent:'0.00%'},
  {label:'Education',amount:'IDR 1,500,000',share_percent:'24.86%',change_percent:'0.00%'},
  {label:'Transport',amount:'IDR 1,150,000',share_percent:'19.06%',change_percent:'27.78%'}
]);
const slices=m.spendingSlices(spending);
same(slices.map(s=>[s.label,s.weight,s.share]),[['Groceries',1800000,'29.83%'],['Education',1500000,'24.86%'],['Transport',1150000,'19.06%']]);
same(slices.map(s=>s.direction),['flat','flat','up']);
assert.equal(new Set(slices.map(s=>s.color)).size,3);
same(m.spendingSlices(card('spending_breakdown',{},[{label:'Rent',amount:'n/a',share_percent:'40%'},{label:'Food',amount:'IDR 5',share_percent:'60%'}])).map(s=>s.weight),[40,60],'one unreadable amount switches every slice to shares so weights stay comparable');
same(m.spendingSlices({...spending,status:'UNAVAILABLE'}),[]);

const arcs=m.donutArcs(slices);
const gap=0.8,total=arcs.reduce((sum,arc)=>sum+arc.length,0)+gap*arcs.length;
near(total,100,'arcs and gaps close the ring');
near(arcs[1].offset,-(slices[0].weight/4450000*100),'each arc starts where the previous share ended');
assert.equal(m.donutArcs([{weight:5,color:'x'}])[0].length,100,'a single slice is a full ring without a gap');
same(m.donutArcs([{weight:0,color:'x'}]),[]);

const portfolio=card('portfolio',{equity_percent:'54.43',bond_percent:'19.44',money_market_percent:'26.13'});
same(m.allocationOf(portfolio).map(s=>[s.label,s.weight,s.text]),[['Equity',54.43,'54.43%'],['Bonds',19.44,'19.44%'],['Money market',26.13,'26.13%']]);
same(m.allocationOf(card('portfolio',{equity_percent:'100.00',bond_percent:'0.00'})).map(s=>s.label),['Equity'],'zero and missing classes are not drawn');

const cash=card('cash_flow',{available:'12500000.00',commitments:'4700000.00',difference:'7800000.00'});
const safe=card('safe_to_spend',{available:'12500000.00',commitments_until_payday:'0.00',expected_spending_until_payday:'1856111.11',headroom_until_payday:'10643888.89'});
const pace=m.pacingOf(cash,safe);
near(pace.headroom+pace.spending+pace.commitments,1,'pacing shares add up to the available funds');
assert.ok(pace.untilPayday&&!pace.gap&&pace.headroom>0.85&&pace.headroom<0.86);
const shortfall=m.pacingOf(cash,card('safe_to_spend',{available:'1000.00',expected_spending_until_payday:'1500.00',commitments_until_payday:'0.00',headroom_until_payday:'-500.00'},[],{status:'GAP'}));
assert.ok(shortfall.gap&&shortfall.headroom===0);
near(shortfall.headroom+shortfall.spending+shortfall.commitments,1,'a shortfall still fills the bar exactly once');
const fortnight=m.pacingOf(cash,undefined);
assert.ok(!fortnight.untilPayday);near(fortnight.headroom+fortnight.commitments,1,'cash-flow fallback adds up');
assert.equal(m.pacingOf(card('cash_flow',{available:'0.00',commitments:'1.00',difference:'-1.00'}),undefined),null,'no balance, no bar');

const trend=card('balance_trend',{},[],{series:[{date:'2026-10-16',balance:'100.00'},{date:'2026-10-17',balance:'300.00'},{date:'2026-10-18',balance:'200.00'}]});
const spark=m.sparkOf(trend,104,40);
assert.equal(spark.days,3);assert.ok(spark.line.startsWith('M3.0 37.0'),'the lowest balance sits on the bottom padding');
near(spark.end[0],101,'the line ends at the right padding');near(spark.end[1],3+(1-(200-100)/200)*34,'the dot sits on the latest balance');
assert.equal(m.sparkOf({...trend,series:[{date:'2026-10-18',balance:'200.00'}]},104,40),null,'one point is not a trend');
assert.ok(m.sparkOf(card('balance_trend',{},[],{series:[{date:'a',balance:'5'},{date:'b',balance:'5'}]}),104,40).line.includes('20.0'),'a flat balance is centred');

const market=m.marketOf(card('market_insights',{session:'CLOSE',as_of:'18 Oct 2026, 16:00 WIB'},[
  {symbol:'IHSG',name:'Indeks',type:'INDEX',price:'7645.20',change_percent:'-1.45%'},
  {symbol:'BBCA',name:'BCA',type:'STOCK',price:'10250.00',change_percent:'-2.90%'},
  {symbol:'TLKM',name:'Telkom',type:'STOCK',price:'3080.00',change_percent:'+0.33%'},
  {symbol:'ASII',name:'Astra',type:'STOCK',price:'5150.00',change_percent:'0.00%'}
]));
assert.equal(market.open,false);assert.equal(market.headline.symbol,'IHSG');
same(market.ticks.map(t=>[t.price,t.direction]),[['7,645.20','down'],['IDR 10,250','down'],['IDR 3,080','up'],['IDR 5,150','flat']]);
same(market.ticks.map(t=>t.size),[0.5,1,0.12,0],'bars scale to the largest mover; flat has no bar and small moves stay visible');
assert.equal(m.marketOf({...card('market_insights',{}),status:'UNAVAILABLE'}),null);

const goals=m.goalsOf(card('goal_progress',{},[
  {label:'School',progress_percent:'25.00%',status:'Behind',target_date:'1 Jul 2027'},
  {label:'Done',progress_percent:'130.00%',status:'Complete'},
  {label:'Odd',progress_percent:'-5%',status:'On track'}
]));
same(goals.map(g=>[g.tone,g.pct]),[['behind',25],['complete',100],['on_track',0]],'progress is clamped to the bar');
assert.equal(goals[0].targetDate,'1 Jul 2027');
const single=m.goalsOf(card('goal_progress',{goal_name:'Fund',target_amount:'1000.00',saved_amount:'250.00',progress_percent:'25.00',goal_status:'BEHIND',target_date:'2027-07-01'}));
same([single[0].label,single[0].target,single[0].saved,single[0].pctText,single[0].tone,single[0].targetDate],['Fund','IDR 1,000','IDR 250','25.00%','behind','1 Jul 2027']);

const steps=m.stepsOf(card('next_actions',{},[{rank:'2',topic:'buffer',action:'B'},{rank:'1',topic:'debt',action:'A'}]));
same(steps.map(s=>s.action),['A','B']);
assert.equal(m.PANEL_FOR_TOPIC.debt,'worth');

console.log('PASS Home view-model: geometry parsing, ring and bar proportions, shortfall and flat-line edges, market bars, goal clamping');
