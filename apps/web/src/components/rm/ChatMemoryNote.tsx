"use client";
import {ArrowUpRight,History,X} from 'lucide-react';
import {useRM} from './shared';
import {shownDate} from '@/lib/home-model';
import type {RMChatMemory} from '@/lib/rm.generated';

export function memoryStarter(topics:string[]){
  return topics.length?`Can we continue on ${topics.slice(-2).join(' and ')}?`:'';
}

export function ChatMemoryNote({personId,sessionId,enabled,toggle,ask}:{personId:string;sessionId:string;enabled:boolean;toggle:()=>void;ask:(text:string)=>void}){
  const q=useRM<RMChatMemory>(`/v1/rm/chat/${personId}/memory?exclude=${encodeURIComponent(sessionId)}`);
  const topics=q.data?.topics||[],latest=(q.data?.items||[])[0];
  if(topics.length===0)return null;
  if(!enabled)return <p className="mvp-memory-off">This chat starts fresh without your earlier chats. <button type="button" className="text-link" onClick={toggle}>Use earlier chats</button></p>;
  return <section className="mvp-memory" aria-label="What the assistant remembers from your earlier chats">
    <header>
      <History size={14} aria-hidden="true"/>
      <span>From your earlier chats{latest?' · '+shownDate(latest.date):''}</span>
      <button type="button" aria-label="Start this chat without earlier chats" title="Start fresh" onClick={toggle}><X size={14} aria-hidden="true"/></button>
    </header>
    <ul>{topics.map(topic=><li key={topic}>{topic}</li>)}</ul>
    <button type="button" className="mvp-memory-continue" onClick={()=>ask(memoryStarter(topics))}><span>{memoryStarter(topics)}</span><ArrowUpRight size={14} aria-hidden="true"/></button>
  </section>;
}
