import {setUserContext,setTokenProvider,fetchApi} from './api';
import {getAppConfig} from './app-config';
import {accountHome} from './account-surfaces';

export const DEMO_ACCOUNT_KEY='nextrm-demo-account';
export const DEMO_ACCOUNTS=[
  {id:'usr-dina',name:'Dina Rahma',role:'CUSTOMER',title:'Customer',description:'Personal banking help, personalized suggestions and your requests.',tenant:'demo-bank'},
  {id:'usr-maya',name:'Maya Putri',role:'RM',title:'Relationship manager',description:'Existing relationships, prospect acquisition and RM follow-up.',tenant:'demo-bank'},
  {id:'usr-aiadmin',name:'Arif',role:'INSTITUTION_AI_ADMIN',title:'AI administrator',description:'AI monitoring, model traces, evaluation results and system health.',tenant:'demo-bank'},
] as const;
export const DEMO_REVIEWER={id:'usr-quality',name:'Intan',role:'QUALITY_REVIEWER',title:'Authorized quality reviewer',description:'Separately granted conversation content review.',tenant:'demo-bank'} as const;
const all=[...DEMO_ACCOUNTS,DEMO_REVIEWER];
export function restoreDemoAccount(){
  const saved=sessionStorage.getItem(DEMO_ACCOUNT_KEY);
  const account=all.find(a=>a.id===saved);
  setTokenProvider(undefined);
  setUserContext(account?{userId:account.id,tenantId:account.tenant,role:account.role}:{userId:'',tenantId:''});
}
export async function enterDemoAccount(id:string){
  const config=await getAppConfig();
  if(!config.demoMode||config.authProvider!=='synthetic_demo')throw new Error('Synthetic demo accounts are unavailable. Use your provisioned sign-in.');
  const account=all.find(a=>a.id===id);
  if(!account)throw new Error('Choose an available demo account.');
  // Reset the prior account and its cached data before resolving the next membership.
  sessionStorage.removeItem(DEMO_ACCOUNT_KEY);setTokenProvider(undefined);setUserContext({userId:'',tenantId:''});
  const context={userId:account.id,tenantId:account.tenant};
  const response=await fetchApi<{user:{user_id:string;tenant_id:string;role:string}}>('/v1/auth/me',{cache:'no-store'},context);
  const user=response.user;
  sessionStorage.setItem(DEMO_ACCOUNT_KEY,user.user_id);
  setUserContext({userId:user.user_id,tenantId:user.tenant_id,role:user.role});
  return accountHome(user.role);
}
