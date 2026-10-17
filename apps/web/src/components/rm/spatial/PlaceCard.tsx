"use client";

import {useState} from 'react';
import Link from 'next/link';
import {
  Building2,
  MapPin,
  Star,
  ExternalLink,
  Phone,
  CheckCircle2,
  AlertTriangle,
  UserCheck,
  ShieldAlert,
  ArrowRight,
  Info
} from 'lucide-react';
import {fetchApi} from '@/lib/api';
import {Notice, Status} from '@/components/ui/Workspace';
import {requestKey} from '@/components/rm/shared';
import {distanceLabel} from './geo';
import type {RMPoiPlace} from './poi-types';
import type {RMProspect} from '@/lib/rm.generated';

export interface PlaceCardProps {
  place: RMPoiPlace;
  origin?: {latitude: number; longitude: number};
  onClose?: () => void;
  onUpdate?: (updated: RMPoiPlace) => void;
  onProspectCreated?: (prospect: RMProspect) => void;
}

export function PlaceCard({place: initialPlace, origin, onClose, onUpdate, onProspectCreated}: PlaceCardProps) {
  const [place, setPlace] = useState<RMPoiPlace>(initialPlace);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // 'Add as prospect' for POSSIBLE_MATCH
  const [confirmNotCustomer, setConfirmNotCustomer] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');

  // 'Review match' drawer/form state
  const [showReviewMatch, setShowReviewMatch] = useState(false);
  const [reviewDecision, setReviewDecision] = useState<'CONFIRM_EXISTING' | 'NOT_A_CUSTOMER'>('CONFIRM_EXISTING');
  const [reviewReason, setReviewReason] = useState('');

  // Update place if parent passes a changed one
  if (initialPlace.id !== place.id) {
    setPlace(initialPlace);
    setError('');
    setSuccess('');
    setConfirmNotCustomer(false);
    setOverrideReason('');
    setShowReviewMatch(false);
    setReviewReason('');
  }

  const isExisting = place.match_status === 'EXISTING_CUSTOMER';
  const isPossibleMatch = place.match_status === 'POSSIBLE_MATCH';
  const isProspect = Boolean(place.prospect_id || place.match_status === 'PROSPECT');
  const isNewLead = !isExisting && !isPossibleMatch && !isProspect;

  const matchedCustomer = place.matched_customer;
  let partyId: string | undefined;
  if (matchedCustomer && 'party_id' in matchedCustomer && typeof matchedCustomer.party_id === 'string') {
    partyId = matchedCustomer.party_id;
  } else if ('party_id' in place && typeof place.party_id === 'string') {
    partyId = place.party_id;
  }

  const handleAddProspect = async () => {
    if (isPossibleMatch && (!confirmNotCustomer || !overrideReason.trim())) {
      setError('Confirmation and audit reason are required for candidate with a possible match.');
      return;
    }

    setBusy(true);
    setError('');
    setSuccess('');

    try {
      const body = {
        request_key: requestKey(),
        confirm_not_customer: isPossibleMatch ? confirmNotCustomer : false,
        reason: isPossibleMatch ? overrideReason.trim() : null
      };

      const created = await fetchApi<RMProspect>(`/v1/rm/poi/${place.id}/prospect`, {
        method: 'POST',
        body: JSON.stringify(body)
      });

      const updatedPlace: RMPoiPlace = {
        ...place,
        prospect_id: created.id,
        match_status: 'PROSPECT'
      };

      setPlace(updatedPlace);
      setSuccess(`Added "${place.name}" as an active relationship prospect.`);
      onUpdate?.(updatedPlace);
      onProspectCreated?.(created);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to add place as prospect';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleReviewMatch = async () => {
    if (reviewReason.trim().length < 3) {
      setError('Audit reason must be at least 3 characters.');
      return;
    }

    setBusy(true);
    setError('');
    setSuccess('');

    try {
      const body = {
        request_key: requestKey(),
        decision: reviewDecision,
        customer_id: reviewDecision === 'CONFIRM_EXISTING' ? (place.matched_customer?.id || null) : null,
        reason: reviewReason.trim()
      };

      const updated = await fetchApi<RMPoiPlace>(`/v1/rm/poi/${place.id}/match-review`, {
        method: 'POST',
        body: JSON.stringify(body)
      });

      setPlace(updated);
      setShowReviewMatch(false);
      setReviewReason('');
      setSuccess(
        reviewDecision === 'CONFIRM_EXISTING'
          ? 'Confirmed customer relationship. Candidate marked as existing customer.'
          : 'Match cleared. Candidate is marked as eligible new lead.'
      );
      onUpdate?.(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to record match review';
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const distanceKmVal = place.distance_m / 1000;

  return (
    <article className="place-card" aria-label={`Business details for ${place.name}`}>
      <header className="place-card-header">
        <div className="place-card-title-row">
          <span className="place-type-badge">
            <Building2 size={13} /> {place.primary_type.replaceAll('_', ' ')}
          </span>
          <span className="place-distance-badge">
            {distanceLabel(distanceKmVal)} away
          </span>
        </div>
        <h2 className="place-card-name">{place.name}</h2>
        <div className="place-card-address">
          <MapPin size={14} />
          <span>{place.address}</span>
        </div>
      </header>

      {/* Ratings and meta */}
      <div className="place-card-meta">
        {place.rating != null && (
          <div className="place-rating" aria-label={`Rating: ${place.rating} out of 5`}>
            <Star size={14} className="star-icon" fill="#eab308" color="#eab308" />
            <strong>{place.rating.toFixed(1)}</strong>
            {place.rating_count != null && <span>({place.rating_count} reviews)</span>}
          </div>
        )}
        {place.phone_masked && (
          <div className="place-phone">
            <Phone size={13} />
            <span>{place.phone_masked}</span>
          </div>
        )}
        {place.website && (
          <a
            href={place.website}
            target="_blank"
            rel="noopener noreferrer"
            className="place-website-link text-link"
          >
            <ExternalLink size={13} />
            <span>Website</span>
          </a>
        )}
      </div>

      {/* Status & Matching Section */}
      <section className="place-match-section" aria-label="Customer matching assessment">
        <div className="match-status-badge-row">
          {isExisting && (
            <span className="status-badge status-existing">
              <UserCheck size={14} /> Existing bank customer
            </span>
          )}
          {isPossibleMatch && (
            <span className="status-badge status-possible">
              <AlertTriangle size={14} /> Possible existing match
            </span>
          )}
          {isNewLead && (
            <span className="status-badge status-new">
              <CheckCircle2 size={14} /> New candidate lead
            </span>
          )}
          {isProspect && (
            <span className="status-badge status-prospect">
              <ShieldAlert size={14} /> Assigned prospect
            </span>
          )}
          {place.match_score && (
            <small className="match-score">Match score: {place.match_score}</small>
          )}
        </div>

        {place.matched_customer && (
          <div className="matched-customer-card">
            <h4>Matched Bank Record</h4>
            <div className="matched-customer-grid">
              <div>
                <span>Customer name</span>
                <strong>{place.matched_customer.name}</strong>
              </div>
              <div>
                <span>CIF Number</span>
                <strong>{place.matched_customer.cif}</strong>
              </div>
              <div>
                <span>Segment</span>
                <strong>{place.matched_customer.segment}</strong>
              </div>
              <div>
                <span>Portfolio</span>
                <strong>
                  {place.matched_customer.relationship_owner_rm
                    ? 'Your RM book'
                    : 'Other relationship manager'}
                </strong>
              </div>
            </div>
          </div>
        )}

        {place.match_reasons && place.match_reasons.length > 0 && (
          <div className="match-reasons-box">
            <strong>Match justification:</strong>
            <ul>
              {place.match_reasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* Notifications */}
      {error && <Notice tone="warn">{error}</Notice>}
      {success && <Notice tone="good">{success}</Notice>}

      {/* Actions Section */}
      <footer className="place-card-actions">
        {isExisting && (
          <div className="existing-customer-action">
            <p className="existing-note">
              <UserCheck size={16} />
              <span>Already a bank customer</span>
            </p>
            {partyId ? (
              <Link href={`/relationships/${partyId}`} className="button button-primary">
                View customer profile <ArrowRight size={14} />
              </Link>
            ) : null}
          </div>
        )}

        {isProspect && (
          <div className="prospect-action">
            <p className="prospect-note">
              <CheckCircle2 size={16} />
              <span>Already added to acquisition prospect queue.</span>
            </p>
            {place.prospect_id && (
              <Link
                href={`/acquisition?selected=${encodeURIComponent(place.prospect_id)}`}
                className="button button-subtle"
              >
                View in prospect shortlist
              </Link>
            )}
          </div>
        )}

        {isNewLead && (
          <button
            type="button"
            className="button button-primary"
            disabled={busy}
            onClick={handleAddProspect}
          >
            {busy ? 'Adding…' : 'Add as prospect'}
          </button>
        )}

        {isPossibleMatch && !isProspect && (
          <div className="possible-match-confirm-form">
            <div className="caution-callout">
              <AlertTriangle size={15} />
              <p>Potential duplicate customer. RM audit confirmation is required to create a new prospect.</p>
            </div>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={confirmNotCustomer}
                onChange={e => setConfirmNotCustomer(e.target.checked)}
              />
              <span>Confirm this candidate is NOT an existing bank customer</span>
            </label>
            <label className="field">
              <span>Override justification (audit trail)</span>
              <input
                type="text"
                placeholder="e.g. Tax ID and registration differ from existing CIF"
                value={overrideReason}
                onChange={e => setOverrideReason(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="button button-primary"
              disabled={busy || !confirmNotCustomer || !overrideReason.trim()}
              onClick={handleAddProspect}
            >
              {busy ? 'Adding…' : 'Add as prospect'}
            </button>
          </div>
        )}

        {/* Review match action for unconfirmed items */}
        {!isProspect && (
          <div className="review-match-container">
            <button
              type="button"
              className="button button-subtle review-match-toggle"
              onClick={() => setShowReviewMatch(!showReviewMatch)}
            >
              {showReviewMatch ? 'Cancel review' : 'Review match'}
            </button>

            {showReviewMatch && (
              <div className="match-review-panel">
                <h4>Record Match Audit Review</h4>
                <div className="review-decision-options">
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="decision"
                      value="CONFIRM_EXISTING"
                      checked={reviewDecision === 'CONFIRM_EXISTING'}
                      onChange={() => setReviewDecision('CONFIRM_EXISTING')}
                    />
                    <span>Confirm as existing customer</span>
                  </label>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="decision"
                      value="NOT_A_CUSTOMER"
                      checked={reviewDecision === 'NOT_A_CUSTOMER'}
                      onChange={() => setReviewDecision('NOT_A_CUSTOMER')}
                    />
                    <span>Clear match (not an existing customer)</span>
                  </label>
                </div>
                <label className="field">
                  <span>Review reason (required)</span>
                  <input
                    type="text"
                    placeholder="Enter verification notes from commercial registry or customer records"
                    value={reviewReason}
                    onChange={e => setReviewReason(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="button button-primary"
                  disabled={busy || reviewReason.trim().length < 3}
                  onClick={handleReviewMatch}
                >
                  {busy ? 'Saving…' : 'Submit match decision'}
                </button>
              </div>
            )}
          </div>
        )}
      </footer>

      {/* Attribution footer */}
      <div className="place-card-attribution">
        <Info size={12} />
        <span>Provider: {place.provider} · {place.attribution}</span>
      </div>
    </article>
  );
}
