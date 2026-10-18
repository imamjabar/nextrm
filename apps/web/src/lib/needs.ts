import type {RMSignal} from './rm.generated';
export type NeedGroup=RMSignal['group'];
export const NEED_GROUPS:{key:NeedGroup;title:string;hint:string}[]=[
 {key:'PROBLEM',title:'Customer has a problem',hint:'Service issues. Handle these first.'},
 {key:'READY',title:'Ready to talk',hint:'Interest confirmed by the customer and checked by you.'},
 {key:'ASKED',title:'Asked for you',hint:'The customer sent you a message. They expect you to follow up.'},
 {key:'SPOTTED',title:'Spotted for you',hint:'Seen in their chat with the assistant, app activity or account data. The customer has not asked you yet.'},
];
export const SOURCE_PHRASE:Record<RMSignal['origin'],string>={REQUEST:'sent you a message',CHAT:'mentioned in chat',APP:'seen in app activity',INSIGHT:'seen in account data',EVENT:'from a bank record'};
export function urgencyChip(u:string):{text:string;tone:'bad'|'warn'}|null{return u==='URGENT'?{text:'Urgent',tone:'bad'}:u==='TIME_SENSITIVE'?{text:'Soon',tone:'warn'}:null;}
export function needStep(s:Pick<RMSignal,'review'|'workflow'>):{step:0|1|2|3|4;status:string;next:string}{
 if(s.workflow==='DISMISSED'||s.review==='REJECTED')return {step:0,status:'Dismissed',next:'No action needed.'};
 if(s.workflow==='COMPLETED')return {step:4,status:'Done',next:'Follow-up recorded.'};
 if(s.review==='PROPOSED')return {step:1,status:'New: check it',next:'Read what happened and confirm it is right.'};
 if(s.workflow==='IN_PROGRESS')return {step:3,status:'Follow-up in progress',next:'Continue the follow-up.'};
 return {step:2,status:'Checked',next:'Prepare a follow-up.'};
}
export function sortNeeds<T extends Pick<RMSignal,'group'|'created_at'|'id'>>(rows:T[]):T[]{const order=NEED_GROUPS.map(g=>g.key);return [...rows].sort((a,b)=>order.indexOf(a.group)-order.indexOf(b.group)||Date.parse(b.created_at)-Date.parse(a.created_at)||a.id.localeCompare(b.id));}
