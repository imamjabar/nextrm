"use client";
import React,{useEffect,useState,useCallback,useRef} from 'react';
import Link from 'next/link';
import {fetchApi,subscribeSession,getUserContext,getMutationEpoch} from '@/lib/api';
import type {UserContext} from '@/lib/api';
import {Status,Notice,Loading,ErrorState,Empty} from '@/components/ui/Workspace';
import {dateLabel,label} from '@/lib/presentation';
import type {RMSource,RMSignal,RMParty,RMJourney,RMParties} from '@/lib/rm.generated';
const lastData=new Map<string,unknown>();
const pendingReads=new Map<string,{epoch:number;promise:Promise<unknown>}>();
function keyFor(ctx:UserContext,path:string){return `${ctx.userId||''}|${ctx.tenantId||''}|${path}`;}
function cacheKey(path:string):string{return keyFor(getUserContext(),path);}
export function prefetchRM(paths:string[],ctx:UserContext=getUserContext()):Promise<unknown[]>{
 const epoch=getMutationEpoch();
 return Promise.all(paths.map(path=>{const key=keyFor(ctx,path);if(lastData.has(key))return Promise.resolve(lastData.get(key));const shared=pendingReads.get(key);if(shared&&shared.epoch===epoch)return shared.promise;
  const promise=fetchApi<unknown>(path,{cache:'no-store'},ctx).then(d=>{if(lastData.size>200)lastData.clear();lastData.set(key,d);return d;}).catch(()=>undefined).finally(()=>{if(pendingReads.get(key)?.promise===promise)pendingReads.delete(key);});
  pendingReads.set(key,{epoch,promise});return promise;}));
}
export function prefetchRelationship(partyId:string){const base='/v1/rm/parties/'+partyId;return prefetchRM([base,base+'/snapshot',base+'/brief',base+'/behavior']);}
export async function prefetchCustomerHome(ctx:UserContext){const [parties]=await prefetchRM(['/v1/rm/parties'],ctx) as [RMParties|undefined];const p=parties?.parties.find(x=>x.kind==='PERSON'&&x.relationship==='EXISTING_CUSTOMER');if(!p)return;const base='/v1/rm/chat/'+p.id;await prefetchRM([base,base+'/sessions',base+'/engagement',base+'/requests'],ctx);}
export function useRM<T>(path:string,interval=0){
 const [data,setData]=useState<T|null>(()=>(lastData.get(cacheKey(path)) as T)??null),[error,setError]=useState(''),[pending,setPending]=useState(false);const generation=useRef(0),alive=useRef(true),inflight=useRef<{epoch:number;path:string;promise:Promise<void>}|null>(null);
 const refresh=useCallback(()=>{const epoch=getMutationEpoch();if(inflight.current?.epoch===epoch&&inflight.current.path===path)return inflight.current.promise;const turn=++generation.current;const key=cacheKey(path);setPending(true);const shared=pendingReads.get(key);const promise=(shared&&shared.epoch===epoch?shared.promise.then(d=>d===undefined?fetchApi<T>(path,{cache:'no-store'}):d as T):fetchApi<T>(path,{cache:'no-store'})).then(d=>{if(alive.current&&turn===generation.current){if(lastData.size>200)lastData.clear();lastData.set(key,d);setData(d);setError('');}}).catch(e=>{if(alive.current&&turn===generation.current)setError(e.message);}).finally(()=>{if(alive.current&&turn===generation.current)setPending(false);if(inflight.current?.promise===promise)inflight.current=null;});inflight.current={epoch,path,promise};return promise;},[path]);
 useEffect(()=>{alive.current=true;const c=lastData.get(cacheKey(path)) as T|undefined;if(c!==undefined)setData(c);setError('');refresh();const unsub=subscribeSession(refresh);return()=>{alive.current=false;generation.current++;inflight.current=null;unsub();};},[refresh]);
 useEffect(()=>{if(!interval)return;const timer=setInterval(()=>{if(document.visibilityState==='visible')refresh();},interval);return()=>clearInterval(timer);},[refresh,interval]);
 return {data,error,pending,refresh};
}
export function RequestState({error,data,retry}:{error:string;data:unknown;retry:()=>void}){return error?<ErrorState error={error} retry={retry}/>:!data?<Loading/>:null;}
export function PersonMark({name,kind='PERSON'}:{name:string;kind?:string}){return <span className={'person-mark '+(kind==='ORGANIZATION'?'business-mark':'')} aria-hidden="true">{kind==='ORGANIZATION'?'B':name.split(' ').map(x=>x[0]).slice(0,2).join('')}</span>;}
export function PersonName({party}:{party:RMParty}){return <div className="person-name"><PersonMark name={party.name} kind={party.kind}/><div><strong>{party.name}</strong><small>{party.kind==='PERSON'?'Person':'Business'} · {party.locality}</small></div></div>;}
export function Mode({provider}:{provider?:string}){return <div className="rm-mode"><span className="mode-dot"/><span>{provider==='local'?'Local prototype · Governed simulation':provider?'Google provider selected · Verify live status':'Synthetic prototype sources'} · Synthetic institution data</span></div>;}
export function SourceExcerpt({source}:{source:RMSource}){return <details className="source-excerpt"><summary>{source.title}<span className="text-xs text-muted">{dateLabel(source.event_at)} · {source.mode.toLowerCase()}</span></summary><p>{source.content}</p><small>Source {source.id} · v{source.version} · SHA-256 {source.hash.slice(0,12)}…</small></details>;}
export function SignalRows({signals}:{signals:RMSignal[]}){return !signals.length?<Empty title="No signals in this view">A permitted customer conversation or authorized event can create a sourced item here.</Empty>:<div className="relationship-rows">{signals.map(s=><Link className="relationship-row" key={s.id} href={`/relationships/${s.party_id}?signal=${s.id}#signal-${s.id}`}><PersonMark name={s.name}/><div className="row-content"><div className="row-top"><strong>{s.name}</strong><Status tone={s.urgency==='URGENT'?'bad':s.urgency==='TIME_SENSITIVE'?'warn':'neutral'}>{s.urgency==='URGENT'?'Urgent':s.urgency==='TIME_SENSITIVE'?'Time-sensitive':'Routine'}</Status></div><h3>{s.title}</h3><p>{s.need}</p><div className="row-meta"><span>{s.display_label}</span><span>{label(s.evidence)}</span><span>{dateLabel(s.created_at)}</span></div></div><span className="row-next-action">{s.workflow==='IN_PROGRESS'?'Continue follow-up':['COMPLETED','DISMISSED'].includes(s.workflow)?'View history':s.review==='PROPOSED'?'Review need':'Prepare follow-up'} <span aria-hidden="true">↗</span></span></Link>)}</div>;}
export const requestKey=()=>crypto.randomUUID();
export function CurrentRole(){const [role,setRole]=useState(getUserContext().role||'');useEffect(()=>subscribeSession(()=>setRole(getUserContext().role||'')),[]);return <span>{label(role)}</span>;}
export function JourneyLink({journey}:{journey:RMJourney}){return <Link className="journey-row" href={`/follow-ups/${journey.id}`}><div><strong>RM follow-up</strong><p>{journey.need}</p><small>{journey.due_at?'Due '+dateLabel(journey.due_at):'No due date set'} · RM work only</small></div><Status tone={journey.status==='DONE'?'good':'neutral'}>{label(journey.status)}</Status></Link>;}
