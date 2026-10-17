"use client";
import {getAppConfig} from '@/lib/app-config';
import React,{createContext,useContext,useEffect,useState} from 'react';


import {getUserContext,setUserContext} from '@/lib/api';
import {restoreDemoAccount} from '@/lib/demo-accounts';
const Ready=createContext(false);
export const useIdentityReady=()=>useContext(Ready);
export function AuthBootstrap({children}:{children:React.ReactNode}){const [ready,setReady]=useState(false);useEffect(()=>{let live=true,stop:undefined|(()=>void),generation=0;getAppConfig().then(async c=>{if(!live)return;if(c.demoMode&&c.authProvider==='synthetic_demo'){restoreDemoAccount();setReady(true);return;}if(!c.firebaseApiKey){if(c.demoMode)restoreDemoAccount();setReady(true);return;}const {identity,memberships,enterWorkspace}=await import('@/lib/identity');const {onIdTokenChanged}=await import('firebase/auth');const auth=await identity();if(!live)return;stop=onIdTokenChanged(auth,async user=>{const turn=++generation;try{if(user){const token=await user.getIdToken();const m=await memberships(token);if(!live||turn!==generation)return;const saved=sessionStorage.getItem('nextrm-membership');const chosen=m.memberships.find(x=>x.tenant_id===saved)||(m.memberships.length===1?m.memberships[0]:undefined);if(chosen)await enterWorkspace(token,user.uid,chosen.tenant_id);else setUserContext({userId:user.uid,tenantId:'',idToken:token});}else setUserContext({userId:'',tenantId:''});}catch{if(live&&turn===generation)setUserContext({userId:'',tenantId:''});}finally{if(live)setReady(true);}});}).catch(()=>{if(live)setReady(true);});return()=>{live=false;generation++;stop?.();};},[]);return <Ready.Provider value={ready}>{children}</Ready.Provider>;}
