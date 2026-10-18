"use client";
import React,{useEffect,useState} from 'react';
import Link from 'next/link';
import {usePathname,useRouter} from 'next/navigation';
import {Inbox,Users,Activity,Menu,Search,CalendarClock,ArrowLeftRight,ShieldCheck,Smartphone,GitBranch,SlidersHorizontal} from 'lucide-react';
import {getAppConfig} from '@/lib/app-config';
import {APP_NAME} from '@/config/brand';
import {fetchApi,getUserContext,subscribeSession} from '@/lib/api';
import {accountCanOpen,accountHome} from '@/lib/account-surfaces';
import {CommandPalette} from '@/components/ui/CommandPalette';
import {DemoAccounts} from '@/components/auth/DemoAccounts';
import {DEMO_CUSTOMERS,switchDemoCustomer} from '@/lib/demo-accounts';
import {prefetchCustomerHome} from '@/components/rm/shared';
import {useIdentityReady} from '@/components/auth/AuthBootstrap';
import {logout} from '@/lib/identity';
import {label} from '@/lib/presentation';

const rmNavigation=[{href:'/workspace',title:'Home & briefing',icon:Inbox},{href:'/retention',title:'Existing customers',icon:Users},{href:'/follow-ups',title:'Follow-ups',icon:CalendarClock},{href:'/acquisition',title:'Acquisition',icon:Search}];
const adminNavigation=[{href:'/settings/ai-quality',title:'AI monitoring',icon:Activity},{href:'/settings/governance',title:'Rules & governance',icon:GitBranch},{href:'/settings/assignments',title:'RM coverage',icon:Users}];
type Account={user_id:string;tenant_id:string;name:string;role:string;institution_name:string};

const accounts=new Map<string,Account>();
export function AppShell({children}:{children:React.ReactNode}){
  const ready=useIdentityReady(),pathname=usePathname(),router=useRouter();
  const [session,setSession]=useState(getUserContext()),[demo,setDemo]=useState<boolean|null>(null),[user,setUser]=useState<Account|null>(null);
  const [error,setError]=useState(''),[menu,setMenu]=useState(false),[commands,setCommands]=useState(false);
  useEffect(()=>subscribeSession(()=>{const next=getUserContext();setSession(current=>current.userId===next.userId&&current.tenantId===next.tenantId&&current.idToken===next.idToken&&current.role===next.role?current:{...next});}),[]);
  useEffect(()=>{getAppConfig().then(c=>setDemo(c.demoMode&&c.authProvider==='synthetic_demo')).catch(()=>setDemo(false));},[]);
  useEffect(()=>{
    let live=true;
    setUser(current=>current?.user_id===session.userId&&current?.tenant_id===session.tenantId?current:accounts.get(session.userId+'|'+session.tenantId)??null);setError('');
    if(ready&&demo!==null&&session.userId&&(demo||session.idToken))fetchApi<{user:Account}>('/v1/auth/me').then(data=>{if(live){accounts.set(session.userId+'|'+session.tenantId,data.user);setUser(data.user);}}).catch(e=>{if(live)setError(e.message);});
    return()=>{live=false;};
  },[ready,demo,session]);
  useEffect(()=>{
    if(!demo||user?.role!=='CUSTOMER'||session.idToken)return;
    const timer=setTimeout(()=>{
      for(const c of DEMO_CUSTOMERS){
        if(c.id===user.user_id)continue;
        const ctx={userId:c.id,tenantId:c.tenant};
        fetchApi<{user:Account}>('/v1/auth/me',{cache:'no-store'},ctx).then(d=>accounts.set(c.id+'|'+c.tenant,d.user)).catch(()=>{});
        prefetchCustomerHome(ctx);
      }
    },1200);
    return()=>clearTimeout(timer);
  },[user?.user_id,demo]);
  useEffect(()=>{
    const rm=user?.role==='RM',admin=['QUALITY_REVIEWER','INSTITUTION_AI_ADMIN'].includes(user?.role||'');
    if(!rm&&!admin)return;
    const nav=rm?rmNavigation:adminNavigation.filter(item=>user?.role==='INSTITUTION_AI_ADMIN'||item.href==='/settings/ai-quality');
    nav.forEach(item=>router.prefetch(item.href));
  },[user?.role]);
  useEffect(()=>{setMenu(false);setCommands(false);},[pathname,session.userId]);
  useEffect(()=>{const key=(e:KeyboardEvent)=>{if(user?.role==='RM'&&(e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();setCommands(value=>!value);}if(e.key==='Escape')setMenu(false);};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[user?.role]);
  if(!ready||demo===null)return <main className="empty-state" role="status">Loading your account…</main>;
  if(!session.userId||(!demo&&!session.idToken)||(session.idToken&&!session.tenantId))return demo?<DemoAccounts/>:<main className="empty-state"><h1>Sign in to your institution</h1><Link className="button button-primary" href="/login">Sign in</Link></main>;
  if(error)return <main className="empty-state"><h1>Account unavailable</h1><p role="alert">{error}</p><button className="button" onClick={()=>setSession({...getUserContext()})}>Reload account</button>{demo&&<Link className="text-link" href="/demo">Choose a demo account</Link>}</main>;
  if(!user)return <main className="empty-state" role="status">Opening your account…</main>;
  const customer=user.role==='CUSTOMER',rm=user.role==='RM',admin=['QUALITY_REVIEWER','INSTITUTION_AI_ADMIN'].includes(user.role);
  const home=accountHome(user.role),allowed=accountCanOpen(user.role,pathname);
  const accountLabel=customer?'Customer':rm?'Relationship manager':user.role==='QUALITY_REVIEWER'?'AI quality reviewer':'AI administrator';
  const targetName=pathname.startsWith('/customer/')?'customer':pathname.startsWith('/settings/')?'AI administration':'relationship-manager';
  const navigation=rm?rmNavigation:admin?adminNavigation.filter(item=>user.role==='INSTITUTION_AI_ADMIN'||item.href==='/settings/ai-quality'):[];
  const content=allowed?children:<section className="account-boundary"><ShieldCheck size={30}/><span className="eyebrow">Separate account access</span><h1>This is the {targetName} experience.</h1><p>You are signed in as {user.name}, using a {accountLabel.toLowerCase()} account.</p><Link className="button button-primary" href={home}>Open my {customer?'banking assistant':rm?'RM workspace':'AI monitoring'}</Link>{demo&&<Link className="button" href="/demo"><ArrowLeftRight size={16}/> Choose another demo account</Link>}</section>;
  return <div className={customer?'app-shell portal-shell customer-account-shell':'app-shell'}><a href="#main-content" className="skip-link">Skip to content</a>
    {!customer&&<aside className="app-sidebar"><Link className="wordmark" href={home}>{APP_NAME}</Link><div className="institution"><span className="eyebrow">{rm?'RM workspace':'AI administration'}</span><strong>{user.institution_name||user.tenant_id}</strong></div><button className="button mobile-menu" aria-expanded={menu} aria-controls="main-nav" onClick={()=>setMenu(!menu)}><Menu size={18}/>Menu</button><nav id="main-nav" aria-label="Main navigation" className={menu?'is-open':''}>{navigation.map(item=><Link key={item.href} href={item.href} aria-current={pathname===item.href||pathname.startsWith(item.href+'/')?'page':undefined}><item.icon size={18}/>{item.title}</Link>)}</nav></aside>}
    <div className="app-body"><header className="app-topbar">{customer?<Link href={home} className="customer-account-brand"><Smartphone size={18}/><strong>{user.institution_name||'Your bank'}</strong></Link>:rm?<button className="search-trigger" onClick={()=>setCommands(true)}><Search size={17}/><span>Go to…</span><kbd>⌘ K</kbd></button>:<span className="eyebrow">AI monitoring & quality</span>}<div className="identity"><span className="account-role-tag">{accountLabel}</span><strong>{user.name}</strong>{session.idToken&&<button className="text-link" onClick={logout}>Sign out</button>}</div></header>
      {demo&&!session.idToken&&<div className="demo-account-strip"><span><i/>Synthetic demo · {accountLabel} account</span>{customer&&<><label className="sr-only" htmlFor="demo-customer">Demo customer</label><select id="demo-customer" value={session.userId} onChange={e=>switchDemoCustomer(e.target.value)}>{DEMO_CUSTOMERS.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></>}<Link href="/demo"><ArrowLeftRight size={13}/> Switch demo account</Link></div>}
      <main id="main-content" className="app-content" tabIndex={-1}><React.Fragment key={session.userId+session.tenantId}>{content}</React.Fragment></main>{rm&&<CommandPalette role={user.role} isOpen={commands} onClose={()=>setCommands(false)}/>}
    </div>
  </div>;
}
