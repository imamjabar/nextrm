export function accountHome(role:string) {
  return role==='CUSTOMER'?'/customer/chat': ['QUALITY_REVIEWER','INSTITUTION_AI_ADMIN'].includes(role)?'/settings/ai-quality':'/workspace';
}
export function accountCanOpen(role:string,raw:string) {
  if(!raw.startsWith('/')||raw.startsWith('//')||raw.includes('\\'))return false;
  let path:string;
  try{path=new URL(raw,'https://nextrm.invalid').pathname;}catch{return false;}
  if(role==='CUSTOMER')return path==='/customer/chat';
  if(role==='QUALITY_REVIEWER')return path==='/settings/ai-quality';
  if(role==='INSTITUTION_AI_ADMIN')return ['/settings/ai-quality','/settings/governance','/settings/assignments'].includes(path);
  return role==='RM'&&/^\/(workspace|pulse|retention|acquisition|follow-ups|relationships)(\/|$)/.test(path);
}
