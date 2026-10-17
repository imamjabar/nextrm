"use client";
import React from 'react';
import { AlertCircle, ArrowRight, CheckCircle2 } from 'lucide-react';
import Link from 'next/link';
export function PageTitle({title,description,action}:{title:string;description?:string;action?:React.ReactNode}) {return <div className="page-title"><div><h1>{title}</h1>{description&&<p>{description}</p>}</div>{action}</div>;}
export function Status({children,tone='neutral'}:{children:React.ReactNode;tone?:'neutral'|'good'|'warn'|'bad'}) {return <span className={`status status-${tone}`}>{children}</span>;}
export function Notice({children,tone='neutral'}:{children:React.ReactNode;tone?:'neutral'|'good'|'warn'|'bad'}) {return <div className={`notice notice-${tone}`} role={tone==='bad'?'alert':'status'}>{tone==='good'?<CheckCircle2 size={18}/>:<AlertCircle size={18}/>}<div>{children}</div></div>;}
export function ErrorState({error,retry}:{error:string;retry?:()=>void}) {return <Notice tone="bad"><p>{error}</p>{retry&&<button className="text-link" onClick={retry}>Try again</button>}</Notice>;}
export function Loading(){return <div className="loading-block" role="status"><span>Loading current records…</span><div/><div/><div/></div>;}
export function Empty({title,children}:{title:string;children?:React.ReactNode}) {return <div className="empty-state"><h2>{title}</h2><div>{children}</div></div>;}
export function NextStep({title,description,href,action}:{title:string;description:string;href?:string;action?:string}) {return <section className="next-step"><div><span className="eyebrow">Next step</span><h2>{title}</h2><p>{description}</p></div>{href&&<Link className="button button-primary" href={href}>{action||'Continue'}<ArrowRight size={16}/></Link>}</section>;}
export function Field({label:caption,children,hint}:{label:string;children:React.ReactNode;hint?:string}) {return <label className="field"><span>{caption}</span>{children}{hint&&<small>{hint}</small>}</label>;}
