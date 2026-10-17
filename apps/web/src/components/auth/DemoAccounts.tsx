"use client";
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import {Smartphone,Users,Activity,ArrowUpRight,ShieldCheck} from 'lucide-react';
import {getAppConfig} from '@/lib/app-config';
import {DEMO_ACCOUNTS,DEMO_REVIEWER,enterDemoAccount} from '@/lib/demo-accounts';
import {Notice} from '@/components/ui/Workspace';

export function DemoAccounts(){
  const router=useRouter();
  const [enabled,setEnabled]=useState<boolean|null>(null),[busy,setBusy]=useState(''),[error,setError]=useState('');
  useEffect(()=>{let live=true;getAppConfig().then(c=>{if(live)setEnabled(c.demoMode&&c.authProvider==='synthetic_demo');}).catch(()=>{if(live)setEnabled(false);});return()=>{live=false;};},[]);
  const enter=async(id:string)=>{setBusy(id);setError('');try{const destination=await enterDemoAccount(id);router.push(destination);}catch(e:any){setError(e.message);}finally{setBusy('');}};
  if(enabled===null)return <main className="demo-account-loading" role="status">Loading the demo accounts…</main>;
  if(!enabled)return <main className="demo-account-loading"><h1>Use your institution account</h1><p>The synthetic account chooser is available only in demo mode.</p><Link className="button button-primary" href="/login">Continue to sign-in</Link></main>;
  const icons=[Smartphone,Users,Activity];
  return <main className="demo-account-page"><header><Link href="/demo" className="wordmark">NextRM</Link><span className="demo-account-mode">Demo · Synthetic data only</span></header><section className="demo-account-intro"><span className="eyebrow">Three accounts. One connected relationship.</span><h1>Choose your experience.</h1><p>Customers get personal banking help. Relationship managers act on shared needs. AI administrators monitor the quality of the system.</p></section><div className="demo-account-options">{DEMO_ACCOUNTS.map((account,index)=>{const Icon=icons[index];return <section key={account.id} className={'demo-account-option account-'+account.role.toLowerCase()}><div className="account-icon"><Icon size={23}/></div><span className="eyebrow">0{index+1} / {account.title}</span><h2>{account.name}</h2><p>{account.description}</p><ul>{(account.role==='CUSTOMER'?['Bank assistant chat with history','Sourced insights and suggestions','Official RM contact']:account.role==='RM'?['Retention and customer needs','Nearby prospect acquisition','Reviewed RM follow-ups']:['AI health and monitoring','Rules: draft, test, publish','Authorized trace metadata']).map(text=><li key={text}>{text}</li>)}</ul><button className="button button-primary" disabled={!!busy} onClick={()=>enter(account.id)}>{busy===account.id?'Opening account…':'Enter '+account.title.toLowerCase()}<ArrowUpRight size={16}/></button><small>Separate {account.title.toLowerCase()} identity</small></section>;})}</div>{error&&<Notice tone="bad">{error}</Notice>}<footer className="demo-account-footer"><ShieldCheck size={17}/><p>Switching accounts clears the previous account’s cached data. Each API request checks the account’s institution, role and permitted records. These are synthetic demo identities, not production sign-in.</p></footer><details className="demo-reviewer-option"><summary>Additional authorized quality-review account</summary><p>Intan has a separate explicit grant to inspect conversation content. Arif’s administrator account has monitoring metadata access.</p><button className="button" disabled={!!busy} onClick={()=>enter(DEMO_REVIEWER.id)}>{busy===DEMO_REVIEWER.id?'Opening reviewer…':'Enter quality reviewer'}</button></details></main>;
}
