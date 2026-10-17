"use client";

import {useEffect, useState, useRef} from 'react';
import {
  APIProvider,
  Map,
  AdvancedMarker,
  Pin,
  Circle,
  useMap
} from '@vis.gl/react-google-maps';
import {MapPin, Search, Navigation, AlertTriangle, Layers} from 'lucide-react';
import {getAppConfig} from '@/lib/app-config';
import {distanceKm, distanceLabel} from './geo';
import type {RMPoiPlace, RMPoiCounts} from './poi-types';
import type {RMProspect} from '@/lib/rm.generated';

export interface GoogleTerritoryMapProps {
  center: {lat: number; lng: number};
  radiusM?: number;
  onCenterChange?: (center: {lat: number; lng: number}) => void;

  // POI mode
  places?: RMPoiPlace[];
  selectedPlaceId?: string;
  onSelectPlace?: (id: string) => void;
  showExisting?: boolean;
  onToggleExisting?: (show: boolean) => void;
  counts?: RMPoiCounts;
  onSearchThisArea?: (center: {lat: number; lng: number}, radiusM: number) => void;
  isSearchingArea?: boolean;

  // Prospect mode
  prospects?: RMProspect[];
  selectedProspectId?: string;
  onSelectProspect?: (id: string) => void;

  className?: string;
}

function getStatusColor(status: string) {
  switch (status) {
    case 'EXISTING_CUSTOMER':
      return {bg: '#525D53', border: '#373E38'};
    case 'POSSIBLE_MATCH':
      return {bg: '#B45309', border: '#78350F'};
    case 'PROSPECT':
      return {bg: '#285D86', border: '#1C415E'};
    case 'NEW_LEAD':
    case 'NO_MATCH_IN_AVAILABLE_DATA':
    default:
      return {bg: '#285C3C', border: '#1A3D28'};
  }
}

function MapController({
  center,
  onSearchThisArea,
  isSearchingArea
}: {
  center: {lat: number; lng: number};
  onSearchThisArea?: (center: {lat: number; lng: number}, radiusM: number) => void;
  isSearchingArea?: boolean;
}) {
  const map = useMap();

  useEffect(() => {
    if (!map) return;
    map.panTo(center);
  }, [map, center.lat, center.lng]);

  const handleSearchClick = () => {
    if (!map || !onSearchThisArea) return;
    const mapCenter = map.getCenter();
    if (!mapCenter) return;
    const c = {lat: mapCenter.lat(), lng: mapCenter.lng()};
    const bounds = map.getBounds();
    let radiusM = 1500;
    if (bounds) {
      const ne = bounds.getNorthEast();
      const dist = distanceKm(
        {latitude: c.lat, longitude: c.lng},
        {latitude: ne.lat(), longitude: ne.lng()}
      );
      radiusM = Math.min(5000, Math.max(100, Math.round(dist * 1000)));
    }
    onSearchThisArea(c, radiusM);
  };

  return onSearchThisArea ? (
    <div className="google-map-floating-action">
      <button
        type="button"
        className="button button-search-area"
        disabled={isSearchingArea}
        onClick={handleSearchClick}
      >
        <Search size={14} />
        {isSearchingArea ? 'Searching area…' : 'Search this area'}
      </button>
    </div>
  ) : null;
}

export function GoogleTerritoryMap({
  center,
  radiusM = 1500,
  onCenterChange,
  places,
  selectedPlaceId,
  onSelectPlace,
  showExisting = false,
  onToggleExisting,
  counts,
  onSearchThisArea,
  isSearchingArea = false,
  prospects,
  selectedProspectId,
  onSelectProspect,
  className = ''
}: GoogleTerritoryMapProps) {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [mapId, setMapId] = useState<string | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    getAppConfig()
      .then(cfg => {
        if (!active) return;
        setApiKey(cfg.googleMapsApiKey || null);
        setMapId(cfg.googleMapsMapId || null);
        setConfigLoaded(true);
      })
      .catch(() => {
        if (!active) return;
        setConfigLoaded(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const visiblePlaces = (places || []).filter(
    p => showExisting || p.match_status !== 'EXISTING_CUSTOMER'
  );

  const ariaStatus = places
    ? `${visiblePlaces.length} businesses displayed. ${
        showExisting
          ? ''
          : `${counts?.existing_customer ?? 0} existing customers filtered out.`
      }`
    : prospects
    ? `${prospects.length} assigned prospects displayed.`
    : '';

  return (
    <section className={`google-territory-map-container ${className}`} aria-label="Relationship territory map">
      <div className="sr-only" role="status" aria-live="polite">
        {ariaStatus}
      </div>

      <header className="territory-map-header">
        <div>
          <span className="eyebrow">Relationship territory</span>
          <h2>
            {places
              ? 'Nearby business discovery'
              : 'Explore assigned prospect records'}
          </h2>
        </div>
        {radiusM > 0 && (
          <span className="map-mode-pill">
            {distanceLabel(radiusM / 1000)} discovery radius
          </span>
        )}
      </header>

      {/* Map or Missing Key Notice */}
      <div className="territory-canvas-wrap">
        {!configLoaded ? (
          <div className="spatial-loading">
            <Layers size={26} />
            <span>Loading map configuration…</span>
          </div>
        ) : !apiKey ? (
          <div className="map-unconfigured-panel">
            <div className="maps-unconfigured-notice" role="alert">
              <MapPin size={24} />
              <div>
                <strong>Google Maps is not configured (set GOOGLE_MAPS_BROWSER_KEY)</strong>
                <p>
                  Interactive map visualization is unavailable. Candidate discovery, address search,
                  and prospect actions remain fully functional in the shortlist.
                </p>
              </div>
            </div>
            {onSearchThisArea && (
              <div className="unconfigured-actions-bar">
                <button
                  type="button"
                  className="button button-subtle"
                  disabled={isSearchingArea}
                  onClick={() => onSearchThisArea(center, radiusM)}
                >
                  <Search size={14} />
                  {isSearchingArea ? 'Searching area…' : 'Search this area'}
                </button>
              </div>
            )}
          </div>
        ) : (
          <APIProvider apiKey={apiKey}>
            <div className="google-map-frame" style={{width: '100%', height: '100%', position: 'relative'}}>
              <Map
                mapId={mapId || 'DEMO_MAP_ID'}
                defaultCenter={center}
                defaultZoom={14}
                gestureHandling="greedy"
                disableDefaultUI={false}
                style={{width: '100%', height: '100%'}}
              >
                <MapController
                  center={center}
                  onSearchThisArea={onSearchThisArea}
                  isSearchingArea={isSearchingArea}
                />

                {/* Radius Circle */}
                {radiusM > 0 && (
                  <Circle
                    center={center}
                    radius={radiusM}
                    strokeColor="#285C3C"
                    strokeOpacity={0.8}
                    strokeWeight={2}
                    fillColor="#285C3C"
                    fillOpacity={0.06}
                  />
                )}

                {/* POI Markers */}
                {visiblePlaces.map(place => {
                  const lat = Number(place.latitude);
                  const lng = Number(place.longitude);
                  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
                  const isSelected = selectedPlaceId === place.id;
                  const colors = getStatusColor(place.match_status);

                  return (
                    <AdvancedMarker
                      key={place.id}
                      position={{lat, lng}}
                      title={`${place.name} · ${place.match_status.replaceAll('_', ' ')}`}
                      onClick={() => onSelectPlace?.(place.id)}
                    >
                      <Pin
                        background={colors.bg}
                        borderColor={colors.border}
                        glyphColor="#FFFFFF"
                        scale={isSelected ? 1.3 : 1.0}
                      />
                    </AdvancedMarker>
                  );
                })}

                {/* Prospect Markers (if used in assigned prospects mode) */}
                {(prospects || []).map(p => {
                  if (!Number.isFinite(p.latitude) || !Number.isFinite(p.longitude)) return null;
                  const isSelected = selectedProspectId === p.id;
                  const isHot = p.hot_lead;
                  const bg = isHot ? '#B45309' : p.priority_tier === 'REVIEW_FIRST' ? '#285C3C' : '#525D53';
                  const border = isHot ? '#78350F' : '#1A3D28';

                  return (
                    <AdvancedMarker
                      key={p.id}
                      position={{lat: p.latitude, lng: p.longitude}}
                      title={`${p.party.name} · ${p.priority_tier.replaceAll('_', ' ')}`}
                      onClick={() => onSelectProspect?.(p.id)}
                    >
                      <Pin
                        background={bg}
                        borderColor={border}
                        glyphColor="#FFFFFF"
                        scale={isSelected ? 1.3 : 1.0}
                      />
                    </AdvancedMarker>
                  );
                })}
              </Map>
            </div>
          </APIProvider>
        )}
      </div>

      {/* Legend and Counts Footer */}
      <footer className="territory-map-footer">
        {places ? (
          <div className="territory-map-legend" role="region" aria-label="Candidate counts and legend">
            <div className="legend-items">
              <span className="legend-chip">
                <i className="legend-dot new-lead" /> New lead ({counts?.new_lead ?? 0})
              </span>
              <span className="legend-chip">
                <i className="legend-dot possible-match" /> Possible match ({counts?.possible_match ?? 0})
              </span>
              <span className="legend-chip">
                <i className="legend-dot prospect" /> Prospect ({counts?.prospect ?? 0})
              </span>
              {showExisting && (
                <span className="legend-chip">
                  <i className="legend-dot existing" /> Existing ({counts?.existing_customer ?? 0})
                </span>
              )}
            </div>

            <div className="legend-side">
              {!showExisting && (counts?.existing_customer ?? 0) > 0 && (
                <span className="existing-filtered-note" aria-live="polite">
                  {counts?.existing_customer} existing customer{counts?.existing_customer === 1 ? '' : 's'} filtered out
                </span>
              )}
              {onToggleExisting && (
                <label className="show-existing-toggle">
                  <input
                    type="checkbox"
                    checked={showExisting}
                    onChange={e => onToggleExisting(e.target.checked)}
                  />
                  <span>Show existing customers</span>
                </label>
              )}
            </div>
          </div>
        ) : (
          <div className="territory-map-legend">
            <div className="legend-items">
              <span><i className="legend-dot permitted" /> For review</span>
              <span><i className="legend-dot hot" /> Hot discussion</span>
              <span><i className="legend-dot held" /> Held / matched</span>
            </div>
            <small>{prospects?.length ?? 0} source records</small>
          </div>
        )}
      </footer>
    </section>
  );
}
export default GoogleTerritoryMap;
