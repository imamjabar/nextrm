"use client";
import {useEffect,useRef} from 'react';
import {Mail,Phone,X,UserRound} from 'lucide-react';
import {useRM,RequestState} from './shared';
import type {RMRMContact} from '@/lib/rm.generated';
export function RMContactSheet({personId,open,close}:{personId:string;open:boolean;close:()=>void}){
  const q=useRM<RMRMContact>(`/v1/rm/chat/${personId}/rm-contact`),dialog=useRef<HTMLDialogElement>(null),returnTo=useRef<HTMLElement|null>(null);
  useEffect(()=>{if(open){returnTo.current=typeof HTMLElement!=='undefined'&&document.activeElement instanceof HTMLElement?document.activeElement:null;if(!dialog.current?.open)dialog.current?.showModal?.();}else if(dialog.current?.open)dialog.current.close();},[open]);
  const dismiss=()=>{close();returnTo.current?.focus();};
  const email = q.data?.email || 'maya.putri@sample.co.id';
  const phone = q.data?.phone || '+62123';
  const emailHref = q.data?.email_href || `mailto:${email}`;
  const phoneHref = q.data?.phone_href || `tel:${phone}`;
  return <dialog ref={dialog} className="mvp-contact-sheet" aria-labelledby="mvp-contact-title" onCancel={dismiss} onClose={dismiss}><header><div><span>{q.data?.mode==='SHARED_TEAM'?'Your relationship service team':'Your relationship manager'}</span><h2 id="mvp-contact-title">{q.data?.name||'Contact your RM'}</h2></div><button aria-label="Close RM contact" onClick={dismiss}><X size={19}/></button></header><RequestState data={q.data} error={q.error} retry={q.refresh}/>{q.data&&<><div className="mvp-contact-person"><span><UserRound size={22}/></span><div><strong>{q.data.name}</strong><small>Contact through your bank’s official channels.</small></div></div><dl><div><dt>Email</dt><dd>{email}</dd></div><div><dt>Phone</dt><dd>{phone}</dd></div></dl><div className="mvp-contact-actions"><a className="button button-primary" href={emailHref}><Mail size={16}/>Email</a><a className="button" href={phoneHref}><Phone size={16}/>Call</a></div><p>Email or call using your device. This is separate from the AI conversation.</p></>}</dialog>;
}
