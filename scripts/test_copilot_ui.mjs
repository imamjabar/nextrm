/** Staff assistant panel contracts in Node: every visible state, keyboard and human-confirmed actions. */
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
const listeners=new Map();
const window={matchMedia:()=>({matches:true}),addEventListener:(type,fn)=>listeners.set(type,fn),removeEventListener(){}};
const document={visibilityState:'visible',getElementById:()=>null};
let pathname='/relationships/customer-one';
const router={push:href=>{pathname=href;},prefetch(){}};
function load(file){
 const full=path.resolve(root,file);if(cache.has(full))return cache.get(full).exports;
 const module={exports:{}};cache.set(full,module);
 const code=ts.transpileModule(fs.readFileSync(full,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 const resolve=id=>{
  if(overrides.has(id))return overrides.get(id);
  if(id==='next/navigation')return {useRouter:()=>router,usePathname:()=>pathname};
  if(id.startsWith('@/')||id.startsWith('.')){let target=id.startsWith('@/')?path.join(root,id.slice(2)):path.resolve(path.dirname(full),id);if(!path.extname(target))target=['.ts','.tsx'].map(ext=>target+ext).find(fs.existsSync);const alias='@/'+path.relative(root,target).replace(/\.(tsx?|jsx?)$/,'');if(overrides.has(alias))return overrides.get(alias);return load(target);}
  return require(id);
 };
 vm.runInNewContext(`(function(require,module,exports){${code}\n})`,{console,React,process:{env:{NODE_ENV:'test'}},window,document,URL,URLSearchParams,crypto:globalThis.crypto,setTimeout,clearTimeout,requestAnimationFrame:fn=>setTimeout(fn,0)},{filename:full})(resolve,module,module.exports);
 return module.exports;
}
const textOf=node=>typeof node==='string'?node:node?.children?node.children.map(textOf).join(''):'';
const buttons=tree=>tree.root.findAllByType('button');
const byLabel=(tree,label)=>{const found=buttons(tree).filter(b=>textOf(b)===label||b.props['aria-label']===label);assert.equal(found.length,1,`Expected one button: ${label}`);return found[0];};
const press=async(tree,label)=>{const b=byLabel(tree,label);assert.ok(!b.props.disabled,`Disabled: ${label}`);await act(async()=>{b.props.onClick();});};
const options={createNodeMock:()=>({scrollIntoView(){},focus(){},style:{},scrollHeight:40,scrollTop:0,querySelectorAll:()=>[]})};
const context={surface:'RM',scope:'PARTY',scope_label:'Dina Rahma · assigned to you',scope_detail:'Relationship v3 · sources, needs, follow-ups and your notes',access:'This relationship only. Other customers are outside the answer.',starters:['Why should I talk to Dina now?','What should my follow-up cover?','Which questions should I ask first?'],base_version:3,record_count:9,provider:'vertex',provider_ready:true,mode:'LIVE'};
const source={id:'SRC-1',title:'Customer message',content:'I want to discuss options for school fees.',kind:'CUSTOMER_MESSAGE',mode:'SIMULATED',version:1,hash:'a'.repeat(64),event_at:'2026-10-12T00:00:00Z',ingested_at:'2026-10-12T00:00:00Z'};
const turn={id:'COPILOT-1',question:'Why should I talk to Dina now?',answer:'She asked to discuss school fees, so lead with that goal.',points:[{text:'She wants to discuss options for school fees.',evidence:'CUSTOMER_SAID',evidence_label:'Customer said',refs:['SRC-1']},{text:'She may want access to the money before term starts.',evidence:'INFERENCE',evidence_label:'AI inference',refs:[]}],refs:[{id:'SRC-1',label:'Customer message',evidence:'Customer said',record_type:'source',record_id:'SRC-1',href:null,source},{id:'signal:SIG-1',label:'Need: School fees',evidence:'NextRM record',record_type:'signal',record_id:'SIG-1',href:'/relationships/customer-one?signal=SIG-1',source:null}],suggestions:['What should I ask first?'],action:{kind:'NOTE',label:'Insert into note',available:true,text:'Discuss school-fee timing with Dina.',record_type:'note'},mode:'LIVE',model:'gemini-test',prompt_version:'rm-copilot-v1',latency_ms:2140,created_at:'2026-10-18T00:00:00Z',scope_label:context.scope_label};
const calls=[];let reply=async()=>turn;
overrides.set('@/components/rm/shared',{useRM:()=>({data:context,error:'',pending:false,refresh:async()=>{}})});
overrides.set('@/lib/api',{fetchApi:async(endpoint,init)=>{calls.push({endpoint,body:JSON.parse(init.body)});return reply();}});
const {AssistantPanel}=load('components/rm/AssistantPanel.tsx');
const actions=[],refs=[];let reloaded=0,closed=0;
const props={surface:'RM',partyId:'customer-one',baseVersion:3,subject:'Dina',onAction:a=>{actions.push(a);return true;},onRef:r=>{refs.push(r);return true;},onReload:()=>{reloaded++;},onClose:()=>{closed++;}};
let tree;await act(async()=>{tree=Renderer.create(React.createElement(AssistantPanel,props),options);});
const shown=()=>textOf(tree.toJSON());

assert.ok(shown().includes('Dina Rahma · assigned to you')&&shown().includes('This relationship only.'),'scope header names what the answer can use');
assert.ok(shown().includes('Ask about Dina')&&shown().includes('9 records'),'empty state teaches the scope');
for(const s of context.starters)byLabel(tree,s);
assert.ok(shown().includes('AI can make mistakes. Always check important info.'));
console.log('PASS empty state: scope header, record count, three data-led starters, required footer');

let release;reply=()=>new Promise(r=>{release=r;});
await press(tree,'Why should I talk to Dina now?');
assert.ok(shown().includes('Reading the records in scope…'),'pending feedback appears at once');
assert.equal(tree.root.findAll(n=>n.props.role==='status').length>0,true);
await act(async()=>{release(turn);});
assert.deepEqual(calls[0],{endpoint:'/v1/rm/copilot/turns',body:{message:'Why should I talk to Dina now?',party_id:'customer-one',run_id:null,base_version:3,history:[]}});
console.log('PASS loading state and request carries the exact relationship version');

assert.ok(shown().includes('She asked to discuss school fees')&&shown().includes('Gemini · live'));
const items=tree.root.findAllByType('li');
assert.equal(items.length,2);
assert.equal(items[1].props.className,'is-inference','inference is styled apart from evidence');
assert.ok(textOf(items[0]).startsWith('Customer said')&&textOf(items[1]).startsWith('AI inference'));
assert.equal(actions.length,0,'nothing happens until the RM confirms');
await press(tree,'Insert into note');
assert.equal(actions[0].kind,'NOTE');
await press(tree,'Customer message');
assert.ok(shown().includes('I want to discuss options for school fees.'),'source chip expands the original excerpt inline');
assert.equal(refs.length,0);
console.log('PASS answer: lead first, labelled evidence vs inference, inline source, action only on click');

reply=async()=>turn;
const input=tree.root.findByType('textarea');
await act(async()=>{input.props.onChange({target:{value:'What changed?',style:{}}});});
let prevented=false;
await act(async()=>{input.props.onKeyDown({key:'Enter',shiftKey:true,nativeEvent:{},preventDefault(){prevented=true;}});});
assert.equal(prevented,false);assert.equal(calls.length,1,'Shift+Enter keeps writing');
await act(async()=>{input.props.onKeyDown({key:'Enter',shiftKey:false,nativeEvent:{},preventDefault(){prevented=true;}});});
assert.equal(calls.length,2);assert.deepEqual(calls[1].body.history,[{question:turn.question,answer:turn.answer}]);
let stopped=false;
await act(async()=>{tree.root.findByType('aside').props.onKeyDown({key:'Escape',stopPropagation(){stopped=true;}});});
assert.equal(closed,1);assert.ok(stopped);
console.log('PASS keyboard: Enter sends with history, Shift+Enter new line, Esc closes');

const failures=[[502,'Response contained an unsupported number: 9,999,999. No simulated fallback was used.','Answer withheld','Try again'],[503,'Configure the requested Google provider. No simulated fallback was used.','Gemini is not available','Try again'],[403,'This relationship is not assigned to you.','Outside your access',null],[409,'This relationship changed since you opened it.','This record changed','Reload record']];
for(const [status,message,title,control] of failures){
 await press(tree,'New chat');
 reply=async()=>{throw Object.assign(new Error(message),{status});};
 await press(tree,'Which questions should I ask first?');
 const alert=tree.root.findAll(n=>n.props.role==='alert');
 assert.equal(alert.length,1,`one alert for ${status}`);
 assert.ok(textOf(alert[0]).includes(title)&&textOf(alert[0]).includes(message),`state ${status} explains what happened`);
 if(control)byLabel(tree,control);
}
await press(tree,'Reload record');
assert.equal(reloaded,1);
assert.equal(tree.root.findAll(n=>n.props.role==='alert').length,0,'reload clears the stale answer request');
console.log('PASS states: validation-failed, provider-down, access-denied and stale-version each say what happened and the next step');
