"use client";
import React, {useId, useState} from 'react';
import {fetchApi} from '@/lib/api';
import type {RMCustomerRequest} from '@/lib/rm.generated';

export const CONTACT_METHODS: Record<string, string> = {
  PHONE_CALL: 'Phone call',
  VIDEO_CALL: 'Video call',
  BRANCH_MEETING: 'Meet at a branch',
  EMAIL: 'Email',
};

export const CONTACT_WINDOWS: Record<string, string> = {
  MORNING: 'Morning',
  AFTERNOON: 'Afternoon',
  ANY_TIME: 'Any time',
};

export function contactSummary(method?: string | null, window?: string | null): string | null {
  if (!method) return null;
  const methodLabel = CONTACT_METHODS[method] || method;
  const windowLabel = window ? (CONTACT_WINDOWS[window] || window).toLowerCase() : null;
  return windowLabel ? `${methodLabel}, ${windowLabel}` : methodLabel;
}

export function methodVerb(method?: string | null): string {
  switch (method) {
    case 'PHONE_CALL': return 'call you';
    case 'VIDEO_CALL': return 'set up a video call with you';
    case 'BRANCH_MEETING': return 'meet you at a branch';
    case 'EMAIL': return 'email you';
    default: return 'contact you';
  }
}

export function contactPlanText(who: string, method?: string | null, window?: string | null): string {
  if (!method) return '';
  const Who = who ? who[0].toUpperCase() + who.slice(1) : 'Your RM';
  const win = window === 'MORNING' ? 'in the morning' : window === 'AFTERNOON' ? 'in the afternoon' : 'any time';
  switch (method) {
    case 'PHONE_CALL':
      return `${Who} will call you ${win}.`;
    case 'VIDEO_CALL':
      return `${Who} will set up a video call with you ${win}.`;
    case 'BRANCH_MEETING':
      return window === 'ANY_TIME'
        ? `${Who} will meet you at a branch.`
        : `${Who} will meet you at a branch ${win}.`;
    case 'EMAIL':
      return `${Who} will email you ${win}.`;
    default:
      return `${Who} will contact you ${win}.`;
  }
}

export interface ContactPreferenceChipsProps {
  method: string;
  onMethodChange: (method: string) => void;
  windowChoice: string;
  onWindowChange: (window: string) => void;
  who: string;
  disabled?: boolean;
}

export function ContactPreferenceChips({
  method,
  onMethodChange,
  windowChoice,
  onWindowChange,
  who,
  disabled = false,
}: ContactPreferenceChipsProps) {
  const methodGroup = useId();
  const windowGroup = useId();
  const Who = who ? who[0].toUpperCase() + who.slice(1) : 'Your RM';

  return (
    <>
      <div className="pref-group">
        <p id={methodGroup} className="pref-legend">How should {Who} reach you?</p>
        <div role="radiogroup" aria-labelledby={methodGroup} className="pref-chips">
          {Object.entries(CONTACT_METHODS).map(([val, label]) => (
            <button
              key={val}
              type="button"
              role="radio"
              aria-checked={method === val}
              disabled={disabled}
              className="pref-chip"
              onClick={() => onMethodChange(val)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="pref-group">
        <p id={windowGroup} className="pref-legend">When suits you?</p>
        <div role="radiogroup" aria-labelledby={windowGroup} className="pref-chips">
          {Object.entries(CONTACT_WINDOWS).map(([val, label]) => (
            <button
              key={val}
              type="button"
              role="radio"
              aria-checked={windowChoice === val}
              disabled={disabled}
              className="pref-chip"
              onClick={() => onWindowChange(val)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

export interface ContactPreferencePickerProps {
  personId: string;
  request: { id: string; contact_method?: string | null; contact_window?: string | null };
  who: string;
  onSaved: (updatedRequest: RMCustomerRequest) => void;
  onCancel?: () => void;
}

export function ContactPreferencePicker({
  personId,
  request,
  who,
  onSaved,
  onCancel,
}: ContactPreferencePickerProps) {
  const [method, setMethod] = useState<string>(request.contact_method || '');
  const [windowChoice, setWindowChoice] = useState<string>(request.contact_window || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const save = async () => {
    if (!method || !windowChoice || busy) return;
    setBusy(true);
    setError('');
    try {
      const key = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36);
      const res = await fetchApi<RMCustomerRequest>(
        `/v1/rm/chat/${personId}/requests/${request.id}/preference`,
        {
          method: 'POST',
          body: JSON.stringify({
            request_key: key,
            method,
            window: windowChoice,
          }),
        }
      );
      onSaved(res);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not save contact preference.';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pref-picker">
      <ContactPreferenceChips
        method={method}
        onMethodChange={setMethod}
        windowChoice={windowChoice}
        onWindowChange={setWindowChoice}
        who={who}
        disabled={busy}
      />
      <div className="pref-actions">
        <button
          type="button"
          className="button button-primary"
          disabled={busy || !method || !windowChoice}
          onClick={save}
        >
          {busy ? 'Saving…' : 'Save'}
        </button>
        {onCancel && (
          <button
            type="button"
            className="button button-quiet"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
        )}
      </div>
      {error && <p className="pref-error" role="alert">{error}</p>}
    </div>
  );
}
