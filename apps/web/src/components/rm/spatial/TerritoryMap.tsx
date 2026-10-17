"use client";

import {MapPin} from 'lucide-react';
import type {RMProspect} from '@/lib/rm.generated';
import {distanceKm, distanceLabel, type RMPosition} from './geo';
import {GoogleTerritoryMap} from './GoogleTerritoryMap';

export function TerritoryMap({
  items,
  allItems,
  selected,
  onSelect,
  origin,
  radius,
  onOpenBrief
}: {
  items: RMProspect[];
  allItems: RMProspect[];
  selected: string;
  onSelect: (id: string) => void;
  origin: RMPosition;
  radius: number;
  onOpenBrief: () => void;
}) {
  const current = items.find(p => p.id === selected);

  return (
    <div className="territory-map-wrapper">
      <GoogleTerritoryMap
        center={{lat: origin.latitude, lng: origin.longitude}}
        radiusM={radius > 0 ? radius * 1000 : 0}
        prospects={items}
        selectedProspectId={selected}
        onSelectProspect={onSelect}
      />
      {current && (
        <div className="selected-map-caption">
          <MapPin size={17} />
          <div>
            <strong>{current.party.name}</strong>
            <span>
              {distanceLabel(distanceKm(origin, current))} from{' '}
              {origin.mode === 'DEMO' ? 'demo office' : 'device location'} · Approximate locality
            </span>
          </div>
          <button type="button" className="text-link" onClick={onOpenBrief}>
            Open brief ↗
          </button>
        </div>
      )}
    </div>
  );
}
