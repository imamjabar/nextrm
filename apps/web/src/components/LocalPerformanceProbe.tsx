"use client";
import {useEffect} from 'react';
import {usePathname} from 'next/navigation';
import {getAppConfig} from '@/lib/app-config';

/** Local synthetic-demo diagnostics only. No content, identities, tokens or telemetry export. */
export function LocalPerformanceProbe(){
 const path=usePathname();
 useEffect(()=>{
  let live=true,observer:MutationObserver|undefined,timer:ReturnType<typeof setTimeout>|undefined;
  const selectors:Record<string,string>={'/workspace':'.desk-summary','/pulse':'.rm-context-strip','/retention':'.rm-primary-section','/acquisition':'.discovery-shortlist','/follow-ups':'.rm-primary-section','/customer/chat':'.phone-bank-header','/settings/ai-quality':'.quality-health'};
  const selector=selectors[path];if(!selector)return;
  const navigation=performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming|undefined;
  const mounted=performance.now();
  getAppConfig().then(config=>{
   if(!live||!config.demoMode)return;
   document.body.removeAttribute('data-nextrm-performance');
   const capture=()=>{
    if(!live||!document.querySelector(selector))return;
    const resources=performance.getEntriesByType('resource') as PerformanceResourceTiming[];
    const api=resources.filter(x=>new URL(x.name).pathname.startsWith('/api/'));
    const group=(name:string)=>{const p=new URL(name).pathname;return p.replace(/(chat|nudges|parties|relationships|signals|sources|follow-ups)\/[^/]+/g,'$1/:record');};
    const counts:Record<string,number>={};for(const r of api)counts[group(r.name)]=(counts[group(r.name)]||0)+1;
    const paint=performance.getEntriesByName('first-contentful-paint')[0];
    document.body.setAttribute('data-nextrm-performance',JSON.stringify({
     method:'Browser Performance API and authorized data DOM marker; local synthetic demo only. No Lighthouse/CWV score.',
     route:path,ttfb_ms:navigation?Math.round(navigation.responseStart):null,
     dom_content_loaded_ms:navigation?.domContentLoadedEventEnd?Math.round(navigation.domContentLoadedEventEnd):null,
     first_contentful_paint_ms:paint?Math.round(paint.startTime):null,
     data_visible_ms:Math.round(performance.now()),observer_to_data_ms:Math.round(performance.now()-mounted),
     completed_api_reads:api.length,api_counts:counts,api_reads:api.map(r=>({route:group(r.name),start_ms:Math.round(r.startTime),duration_ms:Math.round(r.duration)})),
     slowest_api_read_ms:api.length?Math.round(Math.max(...api.map(r=>r.duration))):null,
     scripts:resources.filter(x=>x.initiatorType==='script').length
    }));
    observer?.disconnect();if(timer)clearTimeout(timer);
   };
   observer=new MutationObserver(capture);observer.observe(document.body,{childList:true,subtree:true});
   timer=setTimeout(()=>{observer?.disconnect();},30000);capture();
  }).catch(()=>{});
  return()=>{live=false;observer?.disconnect();if(timer)clearTimeout(timer);document.body.removeAttribute('data-nextrm-performance');};
 },[path]);
 return null;
}
