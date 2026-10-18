"use client";
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import {Smartphone,Users,Activity,ArrowUpRight} from 'lucide-react';
import {getAppConfig} from '@/lib/app-config';
import {DEMO_ACCOUNTS,DEMO_CUSTOMERS,enterDemoAccount} from '@/lib/demo-accounts';
import {Notice} from '@/components/ui/Workspace';

export function DemoAccounts(){
  const router=useRouter();
  const [enabled,setEnabled]=useState<boolean|null>(null),[busy,setBusy]=useState(''),[error,setError]=useState('');
  const [customer,setCustomer]=useState('usr-dina');
  useEffect(()=>{let live=true;getAppConfig().then(c=>{if(live)setEnabled(c.demoMode&&c.authProvider==='synthetic_demo');}).catch(()=>{if(live)setEnabled(false);});return()=>{live=false;};},[]);
  const enter=async(id:string)=>{setBusy(id);setError('');try{const destination=await enterDemoAccount(id);router.push(destination);}catch(e:any){setError(e.message);}finally{setBusy('');}};
  if(enabled===null)return <main className="demo-account-loading" role="status">Loading the demo accounts…</main>;
  if(!enabled)return <main className="demo-account-loading"><h1>Use your institution account</h1><p>The synthetic account chooser is available only in demo mode.</p><Link className="button button-primary" href="/login">Continue to sign-in</Link></main>;
  const icons=[Smartphone,Users,Activity];
  return <main className="demo-account-page"><header><Link href="/demo" className="wordmark">NextRM</Link><span className="demo-account-mode">Demo · Synthetic data only</span></header><section className="demo-account-intro"><span className="eyebrow">Three roles. Three customers. One connected relationship.</span><h1>Choose your experience.</h1><p>Customers get personal banking help. Relationship managers act on shared needs. AI administrators monitor the quality of the system.</p></section><div className="demo-account-options">{DEMO_ACCOUNTS.map((account,index)=>{const Icon=icons[index];return <section key={account.id} className={'demo-account-option account-'+account.role.toLowerCase()}><div className="account-icon"><Icon size={23}/></div><span className="eyebrow">0{index+1} / {account.title}</span>{account.role==='CUSTOMER'?(<fieldset className="demo-persona-picker"><legend>Choose a customer</legend>{DEMO_CUSTOMERS.map(c=><label key={c.id} className={customer===c.id?'is-selected':''}><input type="radio" name="demo-customer" value={c.id} checked={customer===c.id} onChange={()=>setCustomer(c.id)}/><strong>{c.name}</strong><small>{c.persona}</small><span>{c.story}</span></label>)}</fieldset>):(<><h2>{account.name}</h2><p>{account.description}</p></>)}<ul>{(account.role==='CUSTOMER'?['Bank assistant chat with history','Sourced insights and suggestions','Official RM contact']:account.role==='RM'?['Retention and customer needs','Nearby prospect acquisition','Reviewed RM follow-ups']:['AI health and monitoring','Rules: draft, test, publish','Authorized trace metadata']).map(text=><li key={text}>{text}</li>)}</ul><button className="button button-primary" disabled={!!busy} onClick={()=>enter(account.role==='CUSTOMER'?customer:account.id)}>{busy===(account.role==='CUSTOMER'?customer:account.id)?'Opening account…':account.role==='CUSTOMER'?'Enter as '+(DEMO_CUSTOMERS.find(c=>c.id===customer)?.name.split(' ')[0]||'customer'):'Enter '+account.title.toLowerCase()}<ArrowUpRight size={16}/></button><small>Separate {account.title.toLowerCase()} identity</small></section>;})}</div>{error&&<Notice tone="bad">{error}</Notice>}</main>;
}
