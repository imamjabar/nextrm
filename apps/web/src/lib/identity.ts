export interface Membership {
  tenant_id: string;
  institution_name: string;
  role: string;
}

export interface MembershipsResponse {
  user_id: string;
  memberships: Array<Membership>;
}

import {accountHome,accountCanOpen} from './account-surfaces';
import {initializeApp,getApps} from 'firebase/app';
import {getAuth,setPersistence,browserSessionPersistence,signOut} from 'firebase/auth';
import {fetchApi,setUserContext,setTokenProvider} from './api';
let pending:Promise<ReturnType<typeof getAuth>>|undefined;
export function identity(){if(!pending)pending=(async()=>{const c=await fetch('/api/config',{cache:'no-store'}).then(r=>r.json());if(!c.firebaseApiKey)throw new Error('Account access is not configured yet. Please contact your POC coordinator.');const app=getApps()[0]||initializeApp({apiKey:c.firebaseApiKey,authDomain:c.firebaseAuthDomain||undefined,projectId:c.firebaseProjectId||undefined});const auth=getAuth(app);await setPersistence(auth,browserSessionPersistence);setTokenProvider(()=>auth.currentUser?.getIdToken()||Promise.resolve(undefined));return auth;})();return pending;}
export async function memberships(token:string){const r=await fetch('/api/v1/auth/memberships',{headers:{Authorization:`Bearer ${token}`},cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.detail||'No active workspace is assigned.');return d as MembershipsResponse;}
export async function enterWorkspace(token:string,uid:string,tenant:string){const ctx={userId:uid,tenantId:tenant,idToken:token};const r=await fetch('/api/v1/auth/me',{headers:{Authorization:`Bearer ${token}`,'X-Tenant-Id':tenant},cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Workspace unavailable');sessionStorage.setItem('nextrm-membership',tenant);setUserContext({...ctx,role:d.user.role});return d.user;}
export function safeDestination(raw:string|null,role:string){return raw&&accountCanOpen(role,raw)?raw:accountHome(role);}
export async function logout(){sessionStorage.removeItem('nextrm-membership');setUserContext({userId:'',tenantId:''});try{await signOut(await identity());}finally{window.location.assign('/login');}}
