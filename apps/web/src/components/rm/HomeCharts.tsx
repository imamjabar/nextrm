"use client";
import type {ReactNode} from 'react';
import {donutArcs} from '@/lib/home-model';
import type {GoalTone,Slice,Spark,Tick} from '@/lib/home-model';

export function Sparkline({spark,width,height,label}:{spark:Spark;width:number;height:number;label:string}){
  return <svg className="mvp-spark" role="img" aria-label={label} width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
    <path d={spark.area} fill="var(--primary-subtle)"/>
    <path d={spark.line} fill="none" stroke="var(--primary)" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx={spark.end[0]} cy={spark.end[1]} r={2.6} fill="var(--primary)"/>
  </svg>;
}

export function Donut({slices,size,children}:{slices:Slice[];size:number;children?:ReactNode}){
  const arcs=donutArcs(slices);
  return <div className="mvp-donut" style={{width:size,height:size}}>
    <svg viewBox="0 0 42 42" width={size} height={size} role="img" aria-label={'Spending by category: '+slices.map(slice=>slice.label+' '+slice.share).join(', ')}>
      <circle cx="21" cy="21" r="15.9155" fill="none" stroke="var(--surface-subtle)" strokeWidth="5.5"/>
      {arcs.map((arc,index)=><circle key={index} cx="21" cy="21" r="15.9155" fill="none" stroke={arc.color} strokeWidth="5.5" strokeDasharray={`${arc.length} ${100-arc.length}`} strokeDashoffset={arc.offset} transform="rotate(-90 21 21)"/>)}
    </svg>
    {children&&<div className="mvp-donut-center">{children}</div>}
  </div>;
}

export function StackBar({parts,label,height=8}:{parts:Array<{weight:number;color:string}>;label:string;height?:number}){
  return <div className="mvp-stack" role="img" aria-label={label} style={{height}}>
    {parts.map((part,index)=><span key={index} style={{flexGrow:part.weight,background:part.color}}/>)}
  </div>;
}

export function Progress({pct,tone,label,decorative}:{pct:number;tone:GoalTone;label:string;decorative?:boolean}){
  const semantics=decorative?{'aria-hidden':true}:{role:'progressbar','aria-valuenow':pct,'aria-valuemin':0,'aria-valuemax':100,'aria-label':label};
  return <div className="mvp-progress" {...semantics}>
    <span data-tone={tone} style={{transform:`scaleX(${pct/100})`}}/>
  </div>;
}

export function TickBars({ticks}:{ticks:Tick[]}){
  return <div className="mvp-tickbars" aria-hidden="true">
    {ticks.map(tick=><div key={tick.symbol} className="mvp-tickbar" data-direction={tick.direction}>
      <span className="mvp-tickplot"><i style={{height:`${tick.size*50}%`}}/></span>
      <small>{tick.symbol}</small>
    </div>)}
  </div>;
}

export function ChangeBar({tick}:{tick:Tick}){
  return <span className="mvp-changebar" data-direction={tick.direction} aria-hidden="true"><i style={{width:`${tick.size*50}%`}}/></span>;
}
