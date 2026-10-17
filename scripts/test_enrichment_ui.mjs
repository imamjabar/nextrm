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
 vm.runInNewContext(`(function(require,module,exports){${code}\n})`,{console,React,Error,process:{env:{NODE_ENV:'test'}},window,document,navigator,sessionStorage,Headers,URL,URLSearchParams,crypto:globalThis.crypto,fetch:(...args)=>globalThis.fetch(...args),setTimeout,clearTimeout,setInterval,clearInterval,IntersectionObserver:class{constructor(callback){this.callback=callback;}observe(){this.callback([{isIntersecting:true,intersectionRatio:1}]);}disconnect(){}},requestAnimationFrame:fn=>setTimeout(fn,0),cancelAnimationFrame:clearTimeout},{filename:full})(resolve,module,module.exports);
 return module.exports;
}
const text=node=>typeof node==='string'||typeof node==='number'?String(node):Array.isArray(node)?node.map(text).join(''):node?.children?text(node.children):'';
const button=(tree,label)=>{const matches=tree.root.findAllByType('button').filter(node=>text(node.toJSON?node.toJSON():{children:node.children.map(c=>typeof c==='string'?c:c.toJSON?c.toJSON():c)})===label);if(matches.length!==1)throw new Error(`Expected one button ${label}; got ${matches.length}`);return matches[0];};
const labelText=node=>typeof node==='string'?node:node?.children?node.children.map(labelText).join(''):'';
const click=async(tree,name)=>{const found=tree.root.findAllByType('button').find(node=>labelText(node).trim()===name.trim());assert.ok(found,`Missing button: ${name}`);assert.ok(!found.props.disabled,`Disabled: ${name}`);await act(async()=>{found.props.onClick();});};
const options={createNodeMock:()=>({scrollTo(){},focus(){},scrollHeight:100})};
const api=load('lib/api.ts'),shared=load('components/rm/shared.tsx');
const source={id:'goal-source',kind:'CUSTOMER_DECLARED_CONTEXT',title:'Declared goal',content:'Education goal',mode:'SIMULATED',version:1,hash:'a'.repeat(64),event_at:'2026-10-03T00:00:00Z',ingested_at:'2026-10-03T00:00:00Z'};
let feed={profile:{version:1,goal:'Education goal',horizon:'Two years',interests:['goals'],share_context:false,topic_snoozes:{},commercial_allowed:true},nudges:[{id:'nudge-one',party_id:'person-one',route:'SAVINGS',title:'Plan your education goal',body:'Use your declared timeframe',prompt:'Help me plan my education goal.',state:'AVAILABLE',version:1,source,knowledge:{...source,kind:'APPROVED_KNOWLEDGE'},why:'Declared goal, not purchase intent',signal_id:null,mode:'SIMULATED',family:'E03',topic:'goals',category:'GUIDANCE',expires_at:'2026-11-03T00:00:00Z',primary:true,can_request_rm:true}],decisions:[],decision_id:'decision-one',method:'Care first',insights:[{key:'cash_flow',title:'Upcoming commitments',status:'UNAVAILABLE',explanation:'Fresh coverage unavailable.',currency:null,values:{},source:null,method:'Decimal only'}],comparisons:[]};
let calls=[],explored=[],requested=[],failNext=false;
const refresh=async()=>{};
overrides.set('@/components/rm/shared',{...shared,useRM:()=>({data:feed,error:'',refresh,pending:false})});
overrides.set('@/lib/api',{...api,fetchApi:async(endpoint,options)=>{const body=JSON.parse(options.body);calls.push({endpoint,body});if(failNext){failNext=false;throw new Error('Response unknown. Check original operation.');}if(endpoint.endsWith('/context'))return {...feed.profile,version:feed.profile.version+1,goal:body.goal,horizon:body.horizon,interests:body.interests,share_context:body.share_context};if(endpoint.includes('/follow-ups/'))return {...task,version:task.version+1,due_at:body.due_at,status:body.action==='COMPLETE'?'DONE':'PLANNED',snoozed_until:body.action==='SNOOZE'?body.due_at:null,outcome:body.outcome};if(body.action==='EXPLORE')return {...feed.nudges[0],state:'EXPLORED'};if(body.action==='REQUEST_RM')return {...feed.nudges[0],state:'REQUESTED',signal_id:'signal-one'};return {id:'choice-one',profile_version:feed.profile.version,action:body.action,message:'Choice saved; no purchase intent.'};}});
const Customer=load('components/rm/CustomerEngagement.tsx').CustomerEngagement;
let tree;await act(async()=>{tree=Renderer.create(React.createElement(Customer,{personId:'person-one',share:false,locked:false,explore:t=>explored.push(t),requested:id=>requested.push(id)}),options);});
assert.ok(labelText(tree.root).includes('Private context'));assert.ok(labelText(tree.root).includes('Fresh coverage unavailable.'));
assert.ok(tree.root.findAllByType('button').find(b=>labelText(b)==='Request RM help').props.disabled);
assert.equal(calls.filter(c=>c.body.action==='EXPOSED').length,1);
await click(tree,'Talk it through');assert.equal(explored[0],'Help me plan my education goal.');assert.equal(requested.length,0);assert.equal(calls.at(-1).body.action,'EXPLORE');
await click(tree,' Helpful');assert.equal(calls.at(-1).body.action,'HELPFUL');assert.equal(requested.length,0);
await act(async()=>tree.unmount());console.log('PASS real customer feed, unavailable insights, explicit display receipt and private exploration/feedback');

calls=[];await act(async()=>{tree=Renderer.create(React.createElement(Customer,{personId:'person-one',share:true,locked:false,explore:t=>explored.push(t),requested:id=>requested.push(id)}),options);});
await act(async()=>{tree.root.findByType('textarea').props.onChange({target:{value:''}});});
await click(tree,'Save context');assert.equal(calls.at(-1).endpoint,'/v1/rm/chat/person-one/context');assert.equal(calls.at(-1).body.goal,'');assert.equal(calls.at(-1).body.share_context,false);
await click(tree,'Request RM help');assert.equal(requested.at(-1),'signal-one');assert.equal(calls.at(-1).body.share_with_rm,true);
failNext=true;await click(tree,'Pause topic 7 days');const original=calls.at(-1).body;await click(tree,'Pause topic 7 days');assert.deepEqual(calls.at(-1).body,original);
await act(async()=>tree.unmount());console.log('PASS goal withdrawal, explicit shared RM request and same-operation retry after unknown response');

const brief={party_id:'person-one',why_now:'Customer asked for help',facts:[{kind:'CUSTOMER_STATEMENT',text:'Original words',source}],questions:['What timing matters?'],constraints:['No signing authority inferred'],next_action:'Review source',contacts:[],timeline:[],source_review:true,method:'Evidence first'};
overrides.set('@/components/rm/shared',{...shared,useRM:()=>({data:brief,error:'',refresh,pending:false})});
const Brief=load('components/rm/RelationshipBrief.tsx').RelationshipBrief;
await act(async()=>{tree=Renderer.create(React.createElement(Brief,{partyId:'person-one',partyVersion:1,reload:refresh}),options);});
assert.ok(labelText(tree.root).includes('Source refresh needed.'));assert.ok(labelText(tree.root).includes('Original words'));assert.ok(labelText(tree.root).includes('No signing authority inferred'));
await act(async()=>tree.root.findByType('textarea').props.onChange({target:{value:'Prepared a meeting, not sent.'}}));await click(tree,'Record activity');assert.equal(calls.at(-1).body.event,'PREPARED');assert.equal(calls.at(-1).body.base_version,1);
await act(async()=>tree.unmount());console.log('PASS actual RM brief, evidence distinctions, source refresh and human activity recording');

const task={id:'task-one',name:'Dina',party_id:'person-one',need:'Original reviewed need',status:'PLANNED',version:1,kind:'RM_FOLLOWUP',draft:'Not sent',source_id:'source-one',history:[],due_at:null,snoozed_until:null,outcome:null};
overrides.set('@/components/rm/shared',{...shared,useRM:endpoint=>({data:endpoint.includes('/sources/')?source:task,error:'',refresh,pending:false})});
overrides.set('@/components/rm/MenuLinks',{MenuLinks:()=>null});
const Followup=load('app/(workspace)/follow-ups/[id]/page.tsx').default;
await act(async()=>{tree=Renderer.create(React.createElement(Followup,{params:{id:'task-one'}}),{createNodeMock:node=>node.type==='input'?{value:'2026-12-01T12:00'}:{scrollTo(){},focus(){}}});});
assert.ok(tree.root.findAllByType('button').find(n=>labelText(n)==='Snooze until due date').props.disabled);
await act(async()=>{tree.root.findByType('textarea').props.onChange({target:{value:'Customer requested a later discussion.'}});tree.root.findByType('input').props.onChange({target:{value:'2026-12-01T12:00'}});});await click(tree,'Snooze until due date');assert.equal(calls.at(-1).body.action,'SNOOZE');assert.ok(calls.at(-1).body.due_at);assert.equal(calls.at(-1).body.outcome,null);
await act(async()=>{tree.root.findByType('select').props.onChange({target:{value:'NO_CURRENT_NEED'}});tree.root.findByType('textarea').props.onChange({target:{value:'Customer stated there is no current need.'}});});await click(tree,'Record follow-up done');assert.equal(calls.at(-1).body.outcome,'NO_CURRENT_NEED');assert.equal(calls.at(-1).body.action,'COMPLETE');
await act(async()=>tree.unmount());console.log('PASS actual follow-up snooze and structured human outcome controls');

const presentation=load('lib/engagement-presentation.ts');
assert.equal(presentation.insightValue('change_percent','27.78','IDR'),'27.78%');
assert.equal(presentation.insightValue('available','12500000.00','IDR'),'IDR 12,500,000');
assert.equal(presentation.insightValue('difference','-1500.25','USD'),'USD -1,500.25');
assert.equal(presentation.insightValue('available','10000000000000000.01','IDR'),'IDR 10,000,000,000,000,000.01');
assert.equal(presentation.insightValue('available','Unavailable','IDR'),'Unavailable');
assert.equal(presentation.localDateTimeValue('invalid'),'');
console.log('PASS faithful decimal-string display, percentage units, large values and invalid-date presentation');

feed={...feed,profile:{...feed.profile,version:1,goal:'Education goal',horizon:'Two years',share_context:false},nudges:[]};
overrides.set('@/components/rm/shared',{...shared,useRM:()=>({data:feed,error:'',refresh,pending:false})});
const props={personId:'person-one',share:false,locked:false,explore:t=>explored.push(t),requested:id=>requested.push(id)};
await act(async()=>{tree=Renderer.create(React.createElement(Customer,props),options);});
await act(async()=>tree.root.findByType('textarea').props.onChange({target:{value:'My unsaved travel plan'}}));
feed={...feed,profile:{...feed.profile,version:2}};
await act(async()=>tree.update(React.createElement(Customer,props)));
assert.equal(tree.root.findByType('textarea').props.value,'My unsaved travel plan');
feed={...feed,profile:{...feed.profile,version:3,goal:'A goal saved in another session'}};
await act(async()=>tree.update(React.createElement(Customer,props)));
assert.equal(tree.root.findByType('textarea').props.value,'My unsaved travel plan');
assert.ok(labelText(tree.root).includes('Your saved context changed. Your draft is retained.'));
assert.ok(tree.root.findAllByType('button').find(n=>labelText(n)==='Save context').props.disabled);
await click(tree,'Keep my draft for review');await click(tree,'Save context');
assert.equal(calls.at(-1).body.goal,'My unsaved travel plan');assert.equal(calls.at(-1).body.base_version,3);
feed={...feed,profile:{...feed.profile,version:4,goal:'My unsaved travel plan'}};
await act(async()=>tree.update(React.createElement(Customer,props)));
assert.ok(labelText(tree.root).includes('Your context is saved.'));
assert.equal(tree.root.findByType('textarea').props.value,'My unsaved travel plan');
await act(async()=>tree.unmount());console.log('PASS unsaved context survives refresh, conflicting server changes require review, saved receipt survives updated revision');

feed={...feed,profile:{...feed.profile,version:5,commercial_allowed:true}};let failPreference=true;
const apiFixture=overrides.get('@/lib/api');apiFixture.fetchApi=async(endpoint,options)=>{const body=JSON.parse(options.body);calls.push({endpoint,body});if(failPreference){failPreference=false;throw new Error('Response unknown; check current status.');}return {id:'preference-one',action:'OPT_OUT',profile_version:6,message:'Commercial follow-up is off. Service help remains available.'};};
await act(async()=>{tree=Renderer.create(React.createElement(Customer,props),options);});
await click(tree,'Turn off commercial follow-up');const firstPreference=calls.at(-1).body;
await click(tree,'Turn off commercial follow-up');assert.deepEqual(calls.at(-1).body,firstPreference);
assert.ok(labelText(tree.root).includes('Commercial follow-up is off. Service help remains available.'));
await act(async()=>tree.unmount());console.log('PASS preference has visible pending/result/error and stable original payload on unknown retry');

feed={...feed,profile:{...feed.profile,version:7},nudges:[{id:'removable-suggestion',party_id:'person-one',route:'SAVINGS',title:'Plan your education goal',body:'Use your declared timeframe',prompt:'Help with my goal',state:'AVAILABLE',version:1,source,knowledge:{...source,kind:'APPROVED_KNOWLEDGE'},why:'Declared goal',signal_id:null,mode:'SIMULATED',family:'E03',topic:'goals',category:'GUIDANCE',expires_at:'2026-11-03T00:00:00Z',primary:true,can_request_rm:true}]};
apiFixture.fetchApi=async(endpoint,options)=>{const body=JSON.parse(options.body);calls.push({endpoint,body});return {id:'dismiss-one',action:body.action,profile_version:8,message:'This suggestion was dismissed. Other topics remain available.'};};
await act(async()=>{tree=Renderer.create(React.createElement(Customer,props),options);});
await click(tree,'Dismiss this suggestion');
feed={...feed,profile:{...feed.profile,version:8},nudges:[]};
await act(async()=>tree.update(React.createElement(Customer,props)));
assert.ok(labelText(tree.root).includes('This suggestion was dismissed. Other topics remain available.'));
assert.ok(labelText(tree.root).includes('No relevant suggestion right now.'));
await act(async()=>tree.unmount());console.log('PASS dismissal receipt remains visible after the suggestion leaves the feed');
