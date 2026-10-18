import type {RMPoiPlace, RMProspect} from './rm.generated';
import {distanceKm, type RMPosition} from '@/components/rm/spatial/geo';

export type OppGroup = 'READY' | 'CHECK' | 'NEW' | 'FOLLOWUP' | 'LATER';
export type OppFilter = 'ALL' | OppGroup;
export type OppSort = 'best' | 'nearest';

export const OPP_GROUPS: {key: OppGroup; title: string; hint: string; color: string; border: string}[] = [
  {key: 'READY', title: 'Ready to talk', hint: 'Need checked and contact allowed. Prepare a follow-up.', color: '#285C3C', border: '#1A3D28'},
  {key: 'CHECK', title: 'To check', hint: 'Confirm the need, identity or source before any contact.', color: '#805015', border: '#5C390F'},
  {key: 'NEW', title: 'New nearby', hint: 'Businesses found around this area. Not customers or prospects yet.', color: '#285D86', border: '#1C415E'},
  {key: 'FOLLOWUP', title: 'In follow-up', hint: 'A follow-up is already prepared or recorded.', color: '#525D53', border: '#373E38'},
  {key: 'LATER', title: 'Not for now', hint: 'Contact restricted, on hold, or already a bank customer.', color: '#9AA397', border: '#7C877B'},
];

export type Opportunity = {
  key: string;
  kind: 'PROSPECT' | 'PLACE';
  name: string;
  subtitle: string;
  summary: string;
  status: string;
  group: OppGroup;
  hot: boolean;
  latitude: number;
  longitude: number;
  distanceKm: number;
  rank: number;
  search: string;
  prospect?: RMProspect;
  place?: RMPoiPlace;
};

export const PLACE_KEY = 'place:';

const PROSPECT_STATUS: Record<string, string> = {
  READY_FOR_DISCUSSION: 'Need checked',
  REVIEW_FIRST: 'Check the need',
  REVIEW: 'Check the need',
  IDENTITY_REVIEW: 'Check identity',
  SOURCE_REVIEW: 'Refresh source',
  FOLLOWUP_PLANNED: 'Follow-up planned',
  FOLLOWUP_RECORDED: 'Follow-up recorded',
  CONTACT_RESTRICTED: 'Contact restricted',
  ON_HOLD: 'On hold',
  EXISTING_RELATIONSHIP: 'Existing customer',
};

export function prospectGroup(p: RMProspect): OppGroup {
  if (p.hot_lead || p.priority_tier === 'READY_FOR_DISCUSSION') return 'READY';
  if (['REVIEW_FIRST', 'REVIEW', 'IDENTITY_REVIEW', 'SOURCE_REVIEW'].includes(p.priority_tier)) return 'CHECK';
  if (['FOLLOWUP_PLANNED', 'FOLLOWUP_RECORDED'].includes(p.priority_tier)) return 'FOLLOWUP';
  return 'LATER';
}

export function placeGroup(p: RMPoiPlace): OppGroup {
  if (p.match_status === 'EXISTING_CUSTOMER' || p.match_status === 'PROSPECT' || p.prospect_id) return 'LATER';
  if (p.match_status === 'POSSIBLE_MATCH') return 'CHECK';
  return 'NEW';
}

function placeStatus(p: RMPoiPlace): string {
  if (p.match_status === 'EXISTING_CUSTOMER') return 'Existing customer';
  if (p.match_status === 'PROSPECT' || p.prospect_id) return 'Prospect of another RM';
  if (p.match_status === 'POSSIBLE_MATCH') return 'Possible customer match';
  return 'New business';
}

export const placeType = (t: string) => t.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());

export function buildOpportunities(prospects: RMProspect[], places: RMPoiPlace[], center: RMPosition, radiusKm: number): Opportunity[] {
  const owned = new Set(prospects.map(p => p.id));
  const fromProspects = prospects.map((p, i): Opportunity => {
    const d = distanceKm(center, p);
    return {
      key: p.id, kind: 'PROSPECT', name: p.party.name,
      subtitle: `${p.party.kind === 'PERSON' ? 'Person' : 'Business'} · ${p.party.locality}`,
      summary: p.need, status: p.hot_lead ? 'Hot lead' : PROSPECT_STATUS[p.priority_tier] || 'Review the record',
      group: prospectGroup(p), hot: p.hot_lead, latitude: p.latitude, longitude: p.longitude, distanceKm: d, rank: i,
      search: [p.party.name, p.party.locality, p.need, ...p.party.contacts.map(c => c.name)].join(' ').toLowerCase(),
      prospect: p,
    };
  }).filter(o => radiusKm === 0 || o.distanceKm <= radiusKm);
  const fromPlaces = places.filter(p => !(p.prospect_id && owned.has(p.prospect_id))).map((p): Opportunity => ({
    key: PLACE_KEY + p.id, kind: 'PLACE', name: p.name, subtitle: placeType(p.primary_type), summary: p.address,
    status: placeStatus(p), group: placeGroup(p), hot: false, latitude: Number(p.latitude), longitude: Number(p.longitude),
    distanceKm: p.distance_m / 1000, rank: Number.MAX_SAFE_INTEGER,
    search: [p.name, p.address, p.primary_type.replaceAll('_', ' ')].join(' ').toLowerCase(), place: p,
  }));
  return [...fromProspects, ...fromPlaces];
}

export function sortOpportunities(rows: Opportunity[], sort: OppSort): Opportunity[] {
  const order = OPP_GROUPS.map(g => g.key);
  return [...rows].sort((a, b) =>
    order.indexOf(a.group) - order.indexOf(b.group) ||
    (sort === 'nearest' ? a.distanceKm - b.distanceKm : Number(b.hot) - Number(a.hot) || a.rank - b.rank || a.distanceKm - b.distanceKm) ||
    a.key.localeCompare(b.key));
}

export function filterOpportunities(rows: Opportunity[], filter: OppFilter, text: string): Opportunity[] {
  const needle = text.trim().toLowerCase();
  return rows.filter(o => (filter === 'ALL' || o.group === filter) && (!needle || o.search.includes(needle)));
}

export function countByGroup(rows: Opportunity[]): Record<OppGroup, number> {
  const counts: Record<OppGroup, number> = {READY: 0, CHECK: 0, NEW: 0, FOLLOWUP: 0, LATER: 0};
  rows.forEach(o => counts[o.group]++);
  return counts;
}
