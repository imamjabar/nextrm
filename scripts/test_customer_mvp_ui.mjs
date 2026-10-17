/** React component and module contracts in Node; no browser/computer automation. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../apps/web/package.json',import.meta.url));
const React=require('react'),Renderer=require('react-test-renderer'),ts=require('typescript');
const {act}=Renderer;
const root=path.resolve('apps/web/src');
const cache=new Map(),overrides=new Map();
const storage=new Map();
const sessionStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,String(value)),removeItem:key=>storage.delete(key)};
let locationRequests=0,located,pathname='/customer/chat';
const window={matchMedia:()=>({matches:false,addEventListener(){},removeEventListener(){}}),addEventListener(){},removeEventListener(){},history:{replaceState(){}},location:{search:'',assign(value){pathname=value;}}};
const navigator={geolocation:{getCurrentPosition(success){locationRequests++;located=success;}}};
const document={visibilityState:'visible',getElementById:()=>null};
const link=({children,href,...props})=>React.createElement('a',{href,...props},children);
const router={push:href=>{pathname=href;},prefetch(){}};
function load(file){
 const full=path.resolve(root,file);if(cache.has(full))return cache.get(full).exports;
 const module={exports:{}};cache.set(full,module);
 const source=fs.readFileSync(full,'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 const resolve=(id)=>{
  if(overrides.has(id))return overrides.get(id);
  if(id==='next/link')return {__esModule:true,default:link};
  if(id==='next/navigation')return {useRouter:()=>router,usePathname:()=>pathname};
  if(id.startsWith('@/')||id.startsWith('.')){let target=id.startsWith('@/')?path.join(root,id.slice(2)):path.resolve(path.dirname(full),id);if(!path.extname(target))target=['.ts','.tsx'].map(ext=>target+ext).find(fs.existsSync);const alias='@/'+path.relative(root,target).replace(/\.(tsx?|jsx?)$/,'');if(overrides.has(alias))return overrides.get(alias);return load(target);}
  return require(id);
 };
 vm.runInNewContext(`(function(require,module,exports){${code}\n})`,{console,React,Error,process:{env:{NODE_ENV:'test'}},window,document,navigator,sessionStorage,Headers,URL,URLSearchParams,crypto:globalThis.crypto,fetch:(...args)=>globalThis.fetch(...args),setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame:fn=>setTimeout(fn,0),cancelAnimationFrame:clearTimeout},{filename:full})(resolve,module,module.exports);
 return module.exports;
}
const text=node=>typeof node==='string'||typeof node==='number'?String(node):Array.isArray(node)?node.map(text).join(''):node?.children?text(node.children):'';
const button=(tree,label)=>{const matches=tree.root.findAllByType('button').filter(node=>text(node.toJSON?node.toJSON():{children:node.children.map(c=>typeof c==='string'?c:c.toJSON?c.toJSON():c)})===label);if(matches.length!==1)throw new Error(`Expected one button ${label}; got ${matches.length}`);return matches[0];};
const labelText=node=>typeof node==='string'?node:node?.children?node.children.map(labelText).join(''):'';
const click=async(tree,name)=>{const found=tree.root.findAllByType('button').find(node=>labelText(node).trim()===name.trim());assert.ok(found,`Missing button: ${name}`);assert.ok(!found.props.disabled,`Disabled: ${name}`);await act(async()=>{found.props.onClick();});};
const options={createNodeMock:()=>({scrollTo(){},focus(){},scrollHeight:100})};
const shared=load('components/rm/shared.tsx'),api=load('lib/api.ts');
const party={id:'customer-one',name:'Dina Rahma',kind:'PERSON',relationship:'EXISTING_CUSTOMER',owner_name:'Maya Putri',products:['Savings'],contact:'ALLOWED',version:1};
const source={id:'source-one',title:'Savings guidance',kind:'APPROVED_KNOWLEDGE',content:'Approved education',mode:'SIMULATED',version:1,hash:'a'.repeat(64),event_at:'2026-10-03T00:00:00Z',ingested_at:'2026-10-03T00:00:00Z'};
let conversation={id:'conv',version:1,party,institution_name:'Demo bank',turns:[],provider:'local',provider_ready:true};
const feed={profile:{version:1,commercial_allowed:true},nudges:[],insights:[{key:'cash_flow',title:'Cash flow',status:'AVAILABLE',currency:'IDR',values:{available:'12500000.00',commitments:'4700000.00',difference:'7800000.00'},source,explanation:'Validated snapshot'},{key:'spending',title:'Transport spending',status:'AVAILABLE',currency:'IDR',values:{current_spend:'1150000.00',previous_spend:'900000.00',change_percent:'27.78'},source,explanation:'Comparable 30-day periods.'}],comparisons:[{title:'Term deposit discussion',ownership:'Not shown',education:'Approved facts',source}]};
const contact={name:'Maya Putri',email:null,phone:null,email_href:null,phone_href:null,status:'NOT_CONFIGURED',mode:'UNAVAILABLE'};
let calls=[];const refresh=async()=>{};
overrides.set('@/components/rm/shared',{...shared,useRM:path=>({data:path==='/v1/rm/parties'?{parties:[party]}:path.endsWith('/sessions')?{sessions:[{id:'chat-one',title:'A saved chat',version:1,created_at:'2026-10-03T00:00:00Z',updated_at:'2026-10-03T00:00:00Z',turn_count:0}],next_cursor:null}:path.includes('/sessions/')?{...conversation,id:'chat-one'}:path.endsWith('/engagement')?feed:path.endsWith('/rm-contact')?contact:conversation,error:'',refresh,pending:false})});
overrides.set('@/components/rm/MenuLinks',{MenuLinks:()=>null});
overrides.set('@/lib/api',{...api,fetchApi:async(path,options)=>{const body=JSON.parse(options.body);calls.push({path,body});if(path.endsWith('/sessions'))return {id:'chat-one',title:'New conversation',version:1,created_at:'2026-10-03T00:00:00Z',updated_at:'2026-10-03T00:00:00Z',turn_count:0};return path.endsWith('/activity')?{id:'event',mode:'SIMULATED',signal_id:null}:{id:'turn',status:'COMPLETED',sources:[source],signal_id:'captured-signal',answer:'Approved answer'};}});
const Phone=load('app/(workspace)/customer/chat/page.tsx').default;
const nodeOptions={createNodeMock:node=>node.type==='dialog'?{open:false,showModal(){this.open=true;},close(){this.open=false;}}:{focus(){},scrollTo(){},scrollHeight:500}};
let tree;await act(async()=>{tree=Renderer.create(React.createElement(Phone),nodeOptions);});
assert.equal(tree.root.findAllByType('input').filter(n=>n.props.type==='checkbox').length,0);
assert.equal(tree.root.findAllByType('button').filter(n=>labelText(n)==='Requests').length,0);
assert.ok(labelText(tree.root).includes('AI can make mistakes. Always check important info.'));
assert.equal(tree.root.findByProps({className:'mvp-chat-view'}).props.hidden,true);
assert.equal(tree.root.findByProps({className:'mvp-insights-view'}).props.hidden,false);
await click(tree,'Chats');
await act(async()=>tree.root.findByProps({id:'customer-message'}).props.onChange({target:{value:'I need help with cash flow.'}}));
await act(async()=>tree.root.findByType('form').props.onSubmit({preventDefault(){}}));
assert.equal('share_with_rm' in calls.at(-1).body,false);
await click(tree,'Home');assert.equal(tree.root.findByProps({className:'mvp-insights-view'}).props.hidden,false);
assert.ok(labelText(tree.root).includes('IDR 12,500,000')&&!labelText(tree.root).includes('12,500,000.00'));
assert.ok(labelText(tree.root).includes('27.78% change'));
assert.ok(!labelText(tree.root).includes('27.78 IDR'));
await click(tree,'Chats');await click(tree,'History');assert.ok(labelText(tree.root).includes('A saved chat'));await act(async()=>tree.root.findAllByType('button').find(n=>n.props.className==='mvp-history-row').props.onClick());await click(tree,'Home');
console.log('PASS focused home/new-chat/history, no sharing/request UI, correct snapshot/percentage units and exact AI caution');
const product=tree.root.findAllByType('details').find(n=>n.props.className==='mvp-product-detail');assert.ok(product);
await act(async()=>product.props.onToggle({currentTarget:{open:true}}));
await click(tree,'Ask the assistant about this');
assert.equal(calls.at(-1).body.kind,'PRODUCT_VIEW');assert.equal(calls.at(-1).body.product,'DEPOSIT');
assert.equal(tree.root.findByProps({id:'customer-message'}).props.value,'Explain Term deposit discussion and the access, term and fee information I should check.');
assert.equal(tree.root.findByProps({className:'mvp-chat-view'}).props.hidden,false);
console.log('PASS actual product exploration emits observed telemetry and composes an AI question without creating a bank application');
const contactButton=tree.root.findAllByType('button').find(n=>n.props['aria-label']==='Contact your RM');
await act(async()=>contactButton.props.onClick());assert.equal(calls.at(-1).body.kind,'RM_CONTACT_VIEW');
assert.ok(labelText(tree.root).includes('Maya Putri'));
assert.ok(tree.root.findAllByType('button').find(n=>labelText(n)==='Email unavailable').props.disabled);
assert.ok(tree.root.findAllByType('button').find(n=>labelText(n)==='Call unavailable').props.disabled);
assert.equal(tree.root.findAllByType('a').filter(n=>n.props.href?.startsWith('mailto:')||n.props.href?.startsWith('tel:')).length,0);
await act(async()=>tree.unmount());console.log('PASS RM contact sheet keeps official unconfigured channels unavailable and records a view, not a delivered message');
const presentation=load('lib/engagement-presentation.ts');
assert.equal(presentation.insightValue('gain_loss_percent','-0.96','IDR'),'-0.96%');
assert.equal(presentation.insightValue('current_spend','1150000.00','IDR'),'IDR 1,150,000');
const customerInsightsSrc=fs.readFileSync(path.resolve(root,'components/rm/CustomerInsights.tsx'),'utf8');
for(const key of ['safe_to_spend','goal_progress','debt','portfolio','net_worth','next_actions','spending_breakdown']){
  assert.ok(customerInsightsSrc.includes(key),`Missing key ${key} in CustomerInsights.tsx`);
}
assert.ok(customerInsightsSrc.includes('Information, not advice'),'Missing "Information, not advice" line in CustomerInsights.tsx');
const composed=[];
const {CustomerInsights}=load('components/rm/CustomerInsights.tsx');
const planningFeed={
  profile:{version:1,commercial_allowed:true},
  nudges:[],
  comparisons:[],
  insights:[
    {key:'safe_to_spend',title:'Safe to spend',status:'AVAILABLE',currency:'IDR',values:{headroom_until_payday:'2500000.00',payday:'2026-10-31',days_to_payday:'13',expected_spending_until_payday:'1200000.00',projected_30d_balance:'5000000.00',monthly_surplus_estimate:'800000.00',buffer_months:'3'},method:'FIN-PLAN-1'},
    {key:'goal_progress',title:'Goal progress',status:'AVAILABLE',currency:'IDR',values:{goal_name:'Emergency Fund',target_amount:'50000000.00',saved_amount:'30000000.00',progress_percent:'60.00',goal_status:'ON_TRACK'},rows:[{label:'Emergency Fund',target:'IDR 50,000,000',saved:'IDR 30,000,000',progress_percent:'60.00%',status:'ON_TRACK'}],method:'FIN-PLAN-2'},
    {key:'debt',title:'Credit card debt',status:'AVAILABLE',currency:'IDR',values:{outstanding_total:'4500000.00',monthly_interest_cost:'125000.00',card_rate_percent:'24.00',minimum_payment_total:'450000.00'},rows:[{label:'Platinum Card',outstanding:'IDR 4,500,000',rate_percent:'24.00%',minimum_payment:'IDR 450,000',due_day:'25'}],method:'FIN-PLAN-3'},
    {key:'portfolio',title:'Portfolio',status:'AVAILABLE',currency:'IDR',values:{total_value:'85000000.00',gain_loss_percent:'12.50',change_30d_percent:'-2.40',equity_percent:'70.00',bond_percent:'30.00',as_of:'2026-10-15'},rows:[{label:'Equity Index',asset_class:'Equity',value:'IDR 59,500,000',share_percent:'70%'}],method:'FIN-PLAN-4'},
    {key:'net_worth',title:'Net worth',status:'AVAILABLE',currency:'IDR',values:{net_worth:'120000000.00',assets_total:'150000000.00',liabilities_total:'30000000.00',buffer_months:'6'},rows:[{label:'Savings & Deposits',amount:'IDR 65,000,000'}],method:'FIN-PLAN-5'},
    {key:'spending_breakdown',title:'Spending breakdown',status:'AVAILABLE',currency:'IDR',values:{total_spend:'6200000.00'},rows:[{label:'Groceries',amount:'IDR 2,400,000',share_percent:'38.7%'}],method:'FIN-PLAN-6'},
    {key:'recurring',title:'Recurring charges',status:'AVAILABLE',currency:'IDR',values:{amount:'1850000.00',discretionary_total:'650000.00',merchant_count:'5'},rows:[{label:'Gym',category:'Health',type:'Discretionary',monthly_estimate:'IDR 450,000'}],method:'FIN-PLAN-7'},
    {key:'next_actions',title:'Next steps',status:'AVAILABLE',currency:'IDR',values:{},rows:[{rank:'1',topic:'Debt',action:'Pay high-interest card first',reason:'Saves IDR 125,000 monthly'}],method:'FIN-PLAN-8'}
  ]
};
overrides.set('@/components/rm/shared',{...shared,useRM:path=>({data:path.endsWith('/engagement')?planningFeed:feed,error:'',refresh,pending:false})});
cache.delete(path.resolve(root,'components/rm/CustomerInsights.tsx'));
const {CustomerInsights:PlanningInsights}=load('components/rm/CustomerInsights.tsx');
let planningTree;
await act(async()=>{planningTree=Renderer.create(React.createElement(PlanningInsights,{personId:'customer-one',active:true,compose:text=>composed.push(text),viewProduct:()=>{}}));});
const planningText=labelText(planningTree.root);
assert.ok(planningText.includes('Safe to spend'));
assert.ok(planningText.includes('Your goals'));
assert.ok(planningText.includes('Credit card cost'));
assert.ok(planningText.includes('Investments'));
assert.ok(planningText.includes('Net worth and financial health'));
assert.ok(planningText.includes('Where your money went'));
assert.ok(planningText.includes('Recurring payments'));
assert.ok(planningText.includes('Suggested next steps'));
assert.ok(planningText.includes('Snapshot as of 15 Oct 2026. Information, not advice.'));
const progressBars=planningTree.root.findAll(n=>n.props.role==='progressbar');
assert.ok(progressBars.length>=1);
assert.equal(progressBars[0].props['aria-valuenow'],60);
for(const question of [
  'How much can I safely spend this month?',
  'Am I on track for my goals?',
  'Should I pay down my credit card or save more?',
  'How are my investments doing?',
  'Why did my fund drop?',
  'How is my overall financial health?',
  'Where is my money going and how can I spend less?',
  'Are there subscriptions or recurring costs I can cut?',
  'What should I do next to improve my finances?'
]){
  const btn=planningTree.root.findAllByType('button').find(b=>labelText(b).includes(question));
  assert.ok(btn,`Button for "${question}" not found`);
  await act(async()=>btn.props.onClick());
  assert.equal(composed.at(-1),question);
}
await act(async()=>planningTree.unmount());
console.log('PASS planning insights render, progress bar accessibility, disclosure, and 9 compose question buttons');
