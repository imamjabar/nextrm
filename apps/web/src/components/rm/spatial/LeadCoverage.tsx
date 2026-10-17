"use client";
import {useEffect, useRef} from 'react';
import type {RMProspect} from '@/lib/rm.generated';
export type DiscoveryQueue = 'recommended' | 'review' | 'hot' | 'followup' | 'held' | 'refresh' | 'all';
export function LeadCoverage({items, queue, onQueue}: {items: RMProspect[]; queue: DiscoveryQueue; onQueue: (queue:DiscoveryQueue)=>void}) {
  const el = useRef<HTMLDivElement>(null);
  const callback = useRef(onQueue); callback.current = onQueue;
  const ready = items.filter(p=>['READY_FOR_DISCUSSION','REVIEW_FIRST','REVIEW'].includes(p.priority_tier));
  const counts = [ready.filter(p=>!p.hot_lead).length, ready.filter(p=>p.hot_lead).length, items.filter(p=>['FOLLOWUP_PLANNED','FOLLOWUP_RECORDED'].includes(p.priority_tier)).length, items.filter(p=>!['READY_FOR_DISCUSSION','REVIEW_FIRST','REVIEW','FOLLOWUP_PLANNED','FOLLOWUP_RECORDED'].includes(p.priority_tier)).length];
  const signature = counts.join('|');
  useEffect(()=>{
    let stopped = false, cleanup: (()=>void)|undefined;
    Promise.all([import('echarts/core'),import('echarts/charts'),import('echarts/components'),import('echarts/renderers')]).then(([core,charts,components,renderers])=>{
      if(stopped||!el.current)return;
      core.use([charts.BarChart,components.GridComponent,components.TooltipComponent,components.AriaComponent,renderers.SVGRenderer]);
      const chart = core.init(el.current, undefined, {renderer:'svg'});
      const names=['Needs review','Hot discussion','RM follow-ups','Held / matched'];
      const colors=['#789887','#bb7138','#346650','#bdc4b8'];
      chart.setOption({animation:!window.matchMedia('(prefers-reduced-motion: reduce)').matches,animationDuration:250,aria:{enabled:true,description:`Assigned source records within the selected area: ${counts[0]} need review, ${counts[1]} hot discussion opportunities, ${counts[2]} with RM follow-up records, ${counts[3]} held or matched. Counts are not conversion scores.`},grid:{top:0,bottom:0,left:0,right:0},xAxis:{show:false,type:'value',max:Math.max(1,items.length)},yAxis:{show:false,type:'category',data:['Sources']},tooltip:{trigger:'item',formatter:(p: any)=>`${p.seriesName}: ${p.value} assigned records`},series:names.map((name,i)=>({name,type:'bar',stack:'records',data:[counts[i]],barWidth:12,itemStyle:{color:colors[i]},emphasis:{itemStyle:{opacity:.8}}}))});
      chart.on('click', (event: any)=>{const index=names.indexOf(event.seriesName);callback.current((['review','hot','followup','held'] as DiscoveryQueue[])[index]||'all');});
      const observer=new ResizeObserver(()=>chart.resize());observer.observe(el.current);
      cleanup=()=>{observer.disconnect();chart.dispose();};
    }).catch(()=>{/* The semantic count controls remain useful if the optional chart cannot load. */});
    return()=>{stopped=true;cleanup?.();};
  },[signature]);
  const groups = [{title:'For review',count:counts[0],key:'review'},{title:'Hot leads',count:counts[1],key:'hot'},{title:'Follow-up',count:counts[2],key:'followup'},{title:'Held / matched',count:counts[3],key:'held'}];
  return <section className="lead-coverage" aria-label="Assigned source coverage"><div className="coverage-title"><strong>In this area</strong><span>{items.length} assigned source records</span></div><div ref={el} className="coverage-chart" role="img" aria-label={counts.map((n,i)=>`${groups[i].title}: ${n}`).join(', ')}/><div className="coverage-legend">{groups.map((g,i)=><button key={g.key} aria-pressed={queue===g.key} onClick={()=>onQueue(g.key as DiscoveryQueue)}><i className={'coverage-dot dot-'+i}/>{g.title}<strong>{g.count}</strong></button>)}</div></section>;
}
