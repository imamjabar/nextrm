"use client";
import {useRM,RequestState,Mode} from '@/components/rm/shared';
import {AssistantDock,AssistantPanel} from '@/components/rm/AssistantPanel';
import {TodayDesk} from '@/components/rm/Today';
import type {RMToday} from '@/lib/rm.generated';

export default function Workspace(){
 const q=useRM<RMToday>('/v1/rm/today',4000);
 return (
  <AssistantDock label="Ask copilot" panel={(close,focus)=><AssistantPanel surface="RM" subject="your book" onClose={close} autoFocus={focus}/>}>
   <Mode provider={q.data?.provider}/>
   <RequestState error={q.error} data={q.data} retry={q.refresh}/>
   {q.data&&<TodayDesk data={q.data}/>}
  </AssistantDock>
 );
}
