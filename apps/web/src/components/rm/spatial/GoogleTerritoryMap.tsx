"use client";

import {Component, useEffect, useState, type ReactNode} from 'react';
import {
  APIProvider,
  Map,
  AdvancedMarker,
  Pin,
  Circle,
  useMap
} from '@vis.gl/react-google-maps';
import {MapPin as MapPinIcon, Search, Layers} from 'lucide-react';
import {getAppConfig} from '@/lib/app-config';
import {distanceKm, distanceLabel} from './geo';

export type MapPin = {
  id: string;
  lat: number;
  lng: number;
  title: string;
  color: string;
  border: string;
};

export type MapLegendItem = {
  key: string;
  label: string;
  color: string;
  count: number;
};

export interface GoogleTerritoryMapProps {
  center: {lat: number; lng: number};
  radiusM: number;
  pins: MapPin[];
  selectedId?: string;
  onSelect?: (id: string) => void;
  legend?: MapLegendItem[];
  onSearchThisArea?: (center: {lat: number; lng: number}, radiusM: number) => void;
  isSearchingArea?: boolean;
  className?: string;
}

class MapBoundary extends Component<{fallback: ReactNode; children: ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
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
  radiusM,
  pins,
  selectedId,
  onSelect,
  legend,
  onSearchThisArea,
  isSearchingArea = false,
  className = ''
}: GoogleTerritoryMapProps) {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [mapId, setMapId] = useState<string | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const w = window as Window & {gm_authFailure?: () => void};
    w.gm_authFailure = () => setFailed(true);
    return () => { delete w.gm_authFailure; };
  }, []);

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

  const validPins = (pins || []).filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lng));
  const unselectedPins = validPins.filter(p => p.id !== selectedId);
  const selectedPins = validPins.filter(p => p.id === selectedId);
  const orderedPins = [...unselectedPins, ...selectedPins];

  const hasLegend = Boolean(legend && legend.length > 0);
  const hasRadius = radiusM > 0;
  const fallback = (
    <div className="map-unconfigured-panel">
      <div className="maps-unconfigured-notice" role="alert">
        <MapPinIcon size={24} />
        <div>
          <strong>{apiKey ? 'The map could not load here' : 'Google Maps is not configured (set GOOGLE_MAPS_BROWSER_KEY)'}</strong>
          <p>The list and details still work. Search this area uses the current centre.</p>
        </div>
      </div>
      {onSearchThisArea && (
        <div className="unconfigured-actions-bar">
          <button type="button" className="button button-subtle" disabled={isSearchingArea} onClick={() => onSearchThisArea(center, radiusM || 1500)}>
            <Search size={14} />
            {isSearchingArea ? 'Searching area…' : 'Search this area'}
          </button>
        </div>
      )}
    </div>
  );
  return (
    <section className={`google-territory-map-container ${className}`.trim()} aria-label="Relationship territory map">
      <div className="sr-only" role="status" aria-live="polite">
        {`${pins?.length ?? 0} on the map.`}
      </div>

      <div className="territory-canvas-wrap">
        {!configLoaded ? (
          <div className="spatial-loading" role="status">
            <Layers size={26} />
            <span>Loading map…</span>
          </div>
        ) : !apiKey || failed ? (
          fallback
        ) : (
          <MapBoundary fallback={fallback}><APIProvider apiKey={apiKey} libraries={['places', 'geometry', 'marker']}>
            <div className="google-map-frame" style={{width: '100%', height: '100%', position: 'relative'}}>
              <Map
                mapId={mapId || 'DEMO_MAP_ID'}
                defaultCenter={center}
                defaultZoom={14}
                gestureHandling="greedy"
                mapTypeControl={false}
                streetViewControl={false}
                style={{width: '100%', height: '100%'}}
              >
                <MapController
                  center={center}
                  onSearchThisArea={onSearchThisArea}
                  isSearchingArea={isSearchingArea}
                />

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

                {orderedPins.map(pin => {
                  const isSelected = pin.id === selectedId;
                  return (
                    <AdvancedMarker
                      key={pin.id}
                      position={{lat: pin.lat, lng: pin.lng}}
                      title={pin.title}
                      zIndex={isSelected ? 10 : undefined}
                      onClick={() => onSelect?.(pin.id)}
                    >
                      <Pin
                        background={pin.color}
                        borderColor={pin.border}
                        glyphColor="#FFFFFF"
                        scale={isSelected ? 1.35 : 1}
                      />
                    </AdvancedMarker>
                  );
                })}
              </Map>
            </div>
          </APIProvider></MapBoundary>
        )}
      </div>

      {(hasLegend || hasRadius) && (
        <footer className="territory-map-footer">
          {hasLegend && (
            <ul className="map-legend" aria-label="Map legend">
              {legend!.map(item => (
                <li key={item.key}>
                  <i className="map-legend-dot" style={{background: item.color}} aria-hidden="true" />
                  {item.label} <b>{item.count}</b>
                </li>
              ))}
            </ul>
          )}
          {hasRadius && (
            <small>{distanceLabel(radiusM / 1000)} around the centre</small>
          )}
        </footer>
      )}
    </section>
  );
}

export default GoogleTerritoryMap;
