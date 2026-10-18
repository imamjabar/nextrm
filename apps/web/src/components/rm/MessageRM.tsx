"use client";
import React, {useEffect, useRef, useState} from 'react';
import {Check, X} from 'lucide-react';
import {fetchApi} from '@/lib/api';
import type {RMCustomerRequest} from '@/lib/rm.generated';
import {ContactPreferenceChips, contactPlanText} from './ContactPreference';

export interface MessageRMSheetProps {
  personId: string;
  who: string;
  open: boolean;
  initialMessage?: string;
  turnId?: string | null;
  onClose: () => void;
  onSent?: (request: RMCustomerRequest) => void;
}

export function MessageRMSheet({
  personId,
  who,
  open,
  initialMessage = '',
  turnId = null,
  onClose,
  onSent,
}: MessageRMSheetProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  const keyRef = useRef('');
  const keyBody = useRef('');
  const prevOpen = useRef(false);

  const [message, setMessage] = useState(initialMessage);
  const [method, setMethod] = useState('');
  const [windowChoice, setWindowChoice] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState<RMCustomerRequest | null>(null);

  const Who = who ? who[0].toUpperCase() + who.slice(1) : 'Your RM';

  useEffect(() => {
    if (open) {
      returnTo.current = typeof HTMLElement !== 'undefined' && document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (!prevOpen.current) {
        keyBody.current = '';
        setMessage(initialMessage || '');
        setMethod('');
        setWindowChoice('');
        setBusy(false);
        setError('');
        setSent(null);
      }
      if (!dialog.current?.open) dialog.current?.showModal?.();
    } else if (dialog.current?.open) {
      dialog.current.close();
    }
    prevOpen.current = open;
  }, [open, initialMessage]);

  const dismiss = () => {
    dialog.current?.close();
    onClose();
    returnTo.current?.focus();
  };

  const send = async () => {
    const trimmed = message.trim();
    if (busy || trimmed.length < 3 || !method || !windowChoice) return;
    setBusy(true);
    setError('');
    try {
      const fields = {message: trimmed, method, window: windowChoice, turn_id: turnId || null};
      const body = JSON.stringify(fields);
      if (keyBody.current !== body) {
        keyRef.current = crypto.randomUUID();
        keyBody.current = body;
      }
      const res = await fetchApi<RMCustomerRequest>(`/v1/rm/chat/${personId}/requests`, {
        method: 'POST',
        body: JSON.stringify({request_key: keyRef.current, ...fields}),
      });
      setSent(res);
      onSent?.(res);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not send message.';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const canSend = !busy && message.trim().length >= 3 && Boolean(method) && Boolean(windowChoice);

  return (
    <dialog
      ref={dialog}
      className="mvp-contact-sheet mvp-message-sheet"
      aria-labelledby="mvp-message-title"
      onCancel={dismiss}
      onClose={dismiss}
    >
      {open && (
        <>
          <header>
            <div>
              <h2 id="mvp-message-title">Message {Who}</h2>
            </div>
            <button type="button" aria-label="Close message form" onClick={dismiss}>
              <X size={19} />
            </button>
          </header>
      {sent ? (
        <div className="mvp-message-sent">
          <div className="mvp-message-sent-icon">
            <Check size={24} aria-hidden="true" />
          </div>
          <h3>Sent to {Who}.</h3>
          <p>{contactPlanText(who, sent.contact_method || method, sent.contact_window || windowChoice)}</p>
          <p className="mvp-message-sent-sub">You can follow it on Home.</p>
          <button type="button" className="button button-primary mvp-message-done" onClick={dismiss}>
            Done
          </button>
        </div>
      ) : (
        <>
          <p className="mvp-message-helper">{Who} replies by phone, video call, at a branch or by email. Not in this app.</p>
          <div className="mvp-message-form">
            <div className="mvp-message-field">
              <div className="mvp-message-label-row">
                <label htmlFor="rm-message-text" className="mvp-message-label">
                  Your message
                </label>
                <span className="mvp-message-counter tabular">{message.length}/1000</span>
              </div>
              <textarea
                id="rm-message-text"
                className="mvp-message-input"
                value={message}
                maxLength={1000}
                disabled={busy}
                onChange={e => setMessage(e.target.value)}
                rows={3}
              />
            </div>
            <ContactPreferenceChips
              method={method}
              onMethodChange={setMethod}
              windowChoice={windowChoice}
              onWindowChange={setWindowChoice}
              who={who}
              disabled={busy}
            />
            <button
              type="button"
              className="button button-primary mvp-message-submit"
              disabled={!canSend}
              onClick={send}
            >
              {busy ? 'Sending…' : `Send to ${Who}`}
            </button>
            {error && (
              <p className="pref-error" role="alert">
                {error}
              </p>
            )}
          </div>
        </>
      )}
        </>
      )}
    </dialog>
  );
}
