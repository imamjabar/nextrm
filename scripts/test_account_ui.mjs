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
 vm.runInNewContext(`(function(require,module,exports){${code}\n})`,{console,React,process:{env:{NODE_ENV:'test'}},window,document,navigator,sessionStorage,Headers,URL,URLSearchParams,crypto:globalThis.crypto,fetch:(...args)=>globalThis.fetch(...args),setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame:fn=>setTimeout(fn,0),cancelAnimationFrame:clearTimeout},{filename:full})(resolve,module,module.exports);
 return module.exports;
}
const text=node=>typeof node==='string'||typeof node==='number'?String(node):Array.isArray(node)?node.map(text).join(''):node?.children?text(node.children):'';
const button=(tree,label)=>{const matches=tree.root.findAllByType('button').filter(node=>text(node.toJSON?node.toJSON():{children:node.children.map(c=>typeof c==='string'?c:c.toJSON?c.toJSON():c)})===label);if(matches.length!==1)throw new Error(`Expected one button ${label}; got ${matches.length}`);return matches[0];};
const labelText=node=>typeof node==='string'?node:node?.children?node.children.map(labelText).join(''):'';
const click=async(tree,name)=>{const found=tree.root.findAllByType('button').find(node=>labelText(node)===name);assert.ok(found,`Missing button: ${name}`);assert.ok(!found.props.disabled,`Disabled: ${name}`);await act(async()=>{found.props.onClick();});};
const options={createNodeMock:()=>({scrollTo(){},focus(){},scrollHeight:100})};
const api=load('lib/api.ts');
let config={demoMode:true,authProvider:'synthetic_demo'};
overrides.set('@/lib/app-config',{getAppConfig:async()=>config});
overrides.set('./app-config',{getAppConfig:async()=>config});
const accounts=load('lib/demo-accounts.ts'),routes=load('lib/account-surfaces.ts');
const users={
 'usr-dina':{user_id:'usr-dina',tenant_id:'demo-bank',role:'CUSTOMER',name:'Dina Rahma',institution_name:'Demo bank'},
 'usr-maya':{user_id:'usr-maya',tenant_id:'demo-bank',role:'RM',name:'Maya Putri',institution_name:'Demo bank'},
 'usr-aiadmin':{user_id:'usr-aiadmin',tenant_id:'demo-bank',role:'INSTITUTION_AI_ADMIN',name:'Arif',institution_name:'Demo bank'},
};
globalThis.fetch=async(_url,options)=>({ok:true,json:async()=>({user:users[options.headers.get('X-User-Id')]})});
assert.equal(await accounts.enterDemoAccount('usr-dina'),'/customer/chat');
assert.equal(api.getUserContext().role,'CUSTOMER');
api.setUserContext({userId:'',tenantId:''});accounts.restoreDemoAccount();assert.equal(api.getUserContext().userId,'usr-dina');
assert.equal(await accounts.enterDemoAccount('usr-maya'),'/workspace');assert.equal(api.getUserContext().role,'RM');
assert.equal(await accounts.enterDemoAccount('usr-aiadmin'),'/settings/ai-quality');
assert.equal(routes.accountCanOpen('RM','/customer/chat'),false);assert.equal(routes.accountCanOpen('RM','/settings/ai-quality'),false);
assert.equal(routes.accountCanOpen('CUSTOMER','/retention'),false);assert.equal(routes.accountCanOpen('INSTITUTION_AI_ADMIN','/acquisition'),false);
assert.equal(routes.accountCanOpen('RM','/workspace/../customer/chat'),false);
assert.equal(routes.accountCanOpen('CUSTOMER','//evil.invalid'),false);
config={demoMode:false,authProvider:'firebase'};await assert.rejects(accounts.enterDemoAccount('usr-dina'),/unavailable/);config={demoMode:true,authProvider:'synthetic_demo'};
console.log('PASS account selection, session restore, verified role and route isolation');

const party={id:'customer-one',name:'Dina Rahma',kind:'PERSON',relationship:'EXISTING_CUSTOMER',contact:'ALLOWED',identity:'CONFIRMED',owner_name:'Maya Putri',products:['Everyday savings'],declared_goal:'School expenses',version:1,locality:'Bekasi'};
const source={id:'source-one',kind:'APPROVED_KNOWLEDGE',title:'Savings help',content:'Approved savings education',mode:'SIMULATED',version:1,hash:'a'.repeat(64),event_at:'2026-10-03T00:00:00Z',ingested_at:'2026-10-03T00:00:00Z'};
let conv={id:'conv-one',party,institution_name:'Demo bank',version:1,turns:[],provider:'local',provider_ready:true};
let requestRows=[];const calls=[];
const shared=load('components/rm/shared.tsx');
overrides.set('@/components/rm/shared',{...shared,useRM:endpoint=>({data:endpoint==='/v1/rm/parties'?{parties:[party]}:endpoint.endsWith('/sessions')?{sessions:[{id:'chat-fixture',title:'Saved conversation',version:1,created_at:'2026-10-03T00:00:00Z',updated_at:'2026-10-03T00:00:00Z',turn_count:conv.turns.length}],next_cursor:null}:endpoint.includes('/sessions/')?{...conv,id:'chat-fixture'}:endpoint.endsWith('/rm-contact')?{name:'Maya Putri',email:null,phone:null,email_href:null,phone_href:null,status:'NOT_CONFIGURED',mode:'UNAVAILABLE'}:endpoint.endsWith('/engagement')?{profile:{version:1,goal:'School expenses',horizon:'',interests:[],share_context:false,topic_snoozes:{},commercial_allowed:true},nudges:[],insights:[],comparisons:[],decisions:[],decision_id:'fixture-decision',method:'Fixture decision'}:endpoint.endsWith('/requests')?{requests:requestRows,boundary:'RM work only'}:endpoint.endsWith('/nudges')?{nudges:[]}:endpoint==='/v1/rm/destinations'?{destinations:[]}:conv,error:'',refresh:async()=>{},pending:false})});
overrides.set('@/components/rm/CustomerNudges',{CustomerNudges:()=>null});
overrides.set('@/components/rm/MenuLinks',{MenuLinks:()=>null});
overrides.set('@/lib/api',{...api,fetchApi:async(endpoint,options)=>{const body=JSON.parse(options.body);calls.push({endpoint,body});if(endpoint.endsWith('/sessions'))return {id:'chat-fixture',title:'New conversation',version:1,created_at:'2026-10-03T00:00:00Z',updated_at:'2026-10-03T00:00:00Z',turn_count:0};const row={id:'turn-'+calls.length,message:body.message,answer:'Approved answer.',status:'COMPLETED',route:'SAVINGS',mode:'SIMULATED',model:'local',created_at:'2026-10-03T00:00:00Z',latency_ms:20,sources:[source],tools:[],signal_id:null,error_code:null,sharing_status:body.share_with_rm?'HELP_ONLY':'PRIVATE'};conv={...conv,version:conv.version+1,turns:[...conv.turns,row]};return row;}});
const Phone=load('app/(workspace)/customer/chat/page.tsx').default;
let phone;await act(async()=>{phone=Renderer.create(React.createElement(Phone),options);});
assert.equal(phone.root.findAllByType('select').length,0);
assert.equal(phone.root.findAllByType('a').filter(n=>['/retention','/acquisition','/settings/ai-quality'].includes(n.props.href)).length,0);
assert.equal(phone.root.findAllByType('input').filter(n=>n.props.type==='checkbox').length,0);
assert.ok(!labelText(phone.root).includes('Share relevant requests with my RM'));
assert.ok(labelText(phone.root).includes('AI can make mistakes. Always check important info.'));
await click(phone,'Chats');
await act(async()=>{phone.root.findByProps({id:'customer-message'}).props.onChange({target:{value:'What is a savings account?'}});});
await act(async()=>{await phone.root.findByType('form').props.onSubmit({preventDefault(){}});});
assert.equal(calls.find(c=>c.endpoint.endsWith('/turns')).body.message,'What is a savings account?');assert.equal('share_with_rm' in calls.find(c=>c.endpoint.endsWith('/turns')).body,false);
assert.ok(labelText(phone.root).includes('Approved answer.'));
await act(async()=>phone.root.findByProps({id:'customer-message'}).props.onChange({target:{value:'An unfinished cash-flow question'}}));
await click(phone,'Home');assert.ok(phone.root.findByProps({className:'mvp-chat-view'}).props.hidden);
await click(phone,'Chats');assert.equal(phone.root.findByProps({id:'customer-message'}).props.value,'An unfinished cash-flow question');
assert.equal(phone.root.findAllByType('button').filter(n=>labelText(n)==='Requests').length,0);
await act(async()=>phone.unmount());console.log('PASS focused customer phone, assistant/insights, no sharing/request controls, retained composer and AI caution');

// Render real account shell with resolved identities. This does not operate a browser.
overrides.set('@/lib/api',api);
overrides.set('@/components/auth/AuthBootstrap',{useIdentityReady:()=>true});
overrides.set('@/components/ui/CommandPalette',{CommandPalette:()=>null});
overrides.set('@/lib/identity',{logout:async()=>{}});
const Shell=load('components/layout/AppShell.tsx').AppShell;
for(const [id,url,expected,forbidden] of [
 ['usr-dina','/customer/chat',[],['/retention','/acquisition','/settings/ai-quality']],
 ['usr-maya','/retention',['/retention','/acquisition','/follow-ups'],['/customer/chat','/settings/ai-quality']],
 ['usr-aiadmin','/settings/ai-quality',['/settings/ai-quality'],['/customer/chat','/retention','/acquisition']],
]){
 pathname=url;api.setUserContext({userId:id,tenantId:'demo-bank',role:users[id].role});let tree;
 await act(async()=>{tree=Renderer.create(React.createElement(Shell,null,React.createElement('p',null,'Allowed surface')),options);});
 const hrefs=tree.root.findAllByType('a').map(a=>a.props.href);for(const link of expected)assert.ok(hrefs.includes(link));for(const link of forbidden)assert.ok(!hrefs.includes(link));assert.ok(labelText(tree.root).includes('Allowed surface'));await act(async()=>tree.unmount());
}
pathname='/customer/chat';api.setUserContext({userId:'usr-maya',tenantId:'demo-bank',role:'RM'});let denied;
await act(async()=>{denied=Renderer.create(React.createElement(Shell,null,React.createElement('p',null,'Forbidden customer content')),options);});
assert.ok(!labelText(denied.root).includes('Forbidden customer content'));assert.ok(labelText(denied.root).includes('This is the customer experience.'));await act(async()=>denied.unmount());
console.log('PASS role-specific shells and wrong-role bookmark denial');

const geo=load('components/rm/spatial/geo.ts');assert.equal(geo.distanceKm(geo.DEMO_OFFICE,geo.DEMO_OFFICE),0);
const oneDegree=geo.distanceKm({latitude:0,longitude:0},{latitude:0,longitude:1});assert.ok(oneDegree>111&&oneDegree<112);
const opposite=geo.distanceKm({latitude:0,longitude:0},{latitude:0,longitude:180});assert.ok(Number.isFinite(opposite)&&opposite>20000);
assert.equal(geo.distanceLabel(.25),'250 m');assert.equal(geo.distanceLabel(2.23),'2.2 km');
console.log('PASS distance calculations, zero-distance and antipodal handling');

// Unified acquisition desk: explicit location request, radius/nearest filters and synchronized list/map/brief.
const prospect=(id,latitude,longitude,extra={})=>({id,party:{...party,id:'party-'+id,name:id,contacts:[],contact_channel:'IN_APP',contact_purpose:'Opt-in discussion',email:id+'@example.invalid'},source,state:'ASSIGNED',disposition:null,need:'A savings discussion',need_reviewed:false,reasons:['Opt-in savings enquiry'],latitude,longitude,version:1,map_mode:'SIMULATED',priority_tier:'REVIEW_FIRST',priority_reason:'Permitted source',next_action:'Review need',priority_method:'ACQ-1',hot_lead:false,hot_reason:'Not reviewed',...extra});
const prospects=[prospect('Farther',-6.275,106.981),prospect('Nearer',-6.251,106.981),prospect('Held',-6.251,106.982,{priority_tier:'CONTACT_RESTRICTED'})];
let renderedMap,renderedBrief;const nearby=[];
overrides.set('@/lib/api',{...api,fetchApi:async endpoint=>{nearby.push(endpoint);return {provider:'SYNTHETIC_DATASET',attribution:'Synthetic',center:{lat:0,lng:0},radius_m:5000,places:[],counts:{}};}});
overrides.set('@/components/rm/spatial/GoogleTerritoryMap',{GoogleTerritoryMap:props=>{renderedMap=props;return null;}});
overrides.set('@/components/rm/spatial/ProspectBrief',{ProspectBrief:props=>{renderedBrief=props;return React.createElement('div',null,'Brief: '+props.p.id);}});
overrides.set('@/components/rm/shared',{...shared,useRM:()=>({data:{prospects,map_label:'',priority_method:'ACQ-1'},error:'',refresh:async()=>{},pending:false})});
const Acquisition=load('app/(workspace)/acquisition/page.tsx').default;let territory;const pins=()=>Array.from(renderedMap.pins,p=>p.id);
await act(async()=>{territory=Renderer.create(React.createElement(Acquisition),options);});
assert.equal(locationRequests,0);assert.deepEqual(pins(),['Farther','Nearer']);assert.equal(renderedBrief.p.id,'Farther');
await act(async()=>{territory.root.findAllByType('select').find(n=>n.props.id==='discovery-radius').props.onChange({target:{value:'.5'}});});
assert.deepEqual(pins(),['Nearer']);assert.equal(renderedBrief.p.id,'Nearer');assert.ok(nearby.at(-1).includes('radius_m=500&'));
await click(territory,'Use my location');assert.equal(locationRequests,1);
await act(async()=>located({coords:{latitude:0,longitude:0,accuracy:30}}));assert.equal(renderedMap.pins.length,0);assert.ok(labelText(territory.root).includes('outside this example area'));assert.ok(nearby.at(-1).includes('lat=0&lng=0'));
await click(territory,'Use demo area');assert.equal(renderedMap.center.lat,geo.DEMO_OFFICE.latitude);assert.equal(renderedMap.pins.length,2);
await act(async()=>{territory.root.findAllByType('select').find(n=>n.props['aria-label']==='Prospect ordering').props.onChange({target:{value:'nearest'}});});assert.equal(pins()[0],'Nearer');
await act(async()=>{territory.root.findAllByType('input').find(n=>n.props['aria-label']==='Search prospects and contacts').props.onChange({target:{value:'Held'}});});assert.deepEqual(pins(),['Held']);assert.equal(renderedMap.selectedId,'Held');assert.equal(renderedBrief.p.id,'Held');
await act(async()=>territory.unmount());console.log('PASS explicit location request, radius/nearest filters and synchronized list/map/brief');
