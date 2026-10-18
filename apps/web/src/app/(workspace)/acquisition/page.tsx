"use client";

import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  MapPin,
  Search,
  LocateFixed,
  Building2,
  Flame,
  Upload,
} from 'lucide-react';
import {fetchApi} from '@/lib/api';
import {Notice, Empty, Status} from '@/components/ui/Workspace';
import {useRM, RequestState, PersonMark, requestKey} from '@/components/rm/shared';
import {GoogleTerritoryMap} from '@/components/rm/spatial/GoogleTerritoryMap';
import {PlaceCard} from '@/components/rm/spatial/PlaceCard';
import {ProspectBrief} from '@/components/rm/spatial/ProspectBrief';
import {DEMO_OFFICE, distanceLabel, type RMPosition} from '@/components/rm/spatial/geo';
import {
  buildOpportunities,
  sortOpportunities,
  filterOpportunities,
  countByGroup,
  OPP_GROUPS,
  type OppFilter,
  type OppSort,
  type Opportunity,
} from '@/lib/opportunities';
import type {
  RMProspects,
  RMProspect,
  RMPoiNearby,
  RMPoiPlace,
  RMGeocode,
  RMImportReceipt,
} from '@/lib/rm.generated';

function SyntheticImport({reload}: {reload: () => Promise<void>}) {
  const [csv, setCsv] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(requestKey);

  return (
    <details className="discovery-source-controls">
      <summary>
        <Upload size={15} /> Source controls · Synthetic CSV import
      </summary>
      <p>
        Supply assigned source records with external_id, kind, name, need, latitude, longitude.
        Optional business contact columns: contact_name, contact_role, contact_email. Use
        @example.invalid emails and a new source_version for changed evidence.
      </p>
      <label className="field">
        <span>Synthetic CSV file · Maximum 8KB / 25 rows</span>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={async e => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (file.size > 8000) {
              setError('Use a CSV no larger than 8KB.');
              return;
            }
            setCsv(await file.text());
            setKey(requestKey());
            setError('');
            setMessage('');
          }}
        />
      </label>
      {error && <Notice tone="warn">{error}</Notice>}
      {message && <Notice tone="good">{message}</Notice>}
      <button
        type="button"
        className="button button-primary"
        disabled={!csv || busy}
        onClick={async () => {
          setBusy(true);
          setError('');
          setMessage('');
          try {
            const res = await fetchApi<RMImportReceipt>('/v1/rm/prospects/import', {
              method: 'POST',
              body: JSON.stringify({csv_text: csv, request_key: requestKey()})
            });
            setMessage(
              `Import complete: ${res.imported} imported, ${res.reused} reused${
                res.matched_existing ? `, ${res.matched_existing} matched existing bank customers` : ''
              }.`
            );
            await reload();
          } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Import failed');
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? 'Importing…' : 'Import assigned CSV'}
      </button>
    </details>
  );
}

function OpportunityRow({
  o,
  selected,
  onChoose,
}: {
  o: Opportunity;
  selected: boolean;
  onChoose: (key: string) => void;
}) {
  const group = OPP_GROUPS.find(g => g.key === o.group)!;
  const statusTone = o.group === 'READY' ? 'good' : o.group === 'CHECK' ? 'warn' : 'neutral';

  return (
    <button
      type="button"
      className="acq-row"
      aria-pressed={selected}
      onClick={() => onChoose(o.key)}
    >
      <span className="acq-mark" style={{'--mark': group.color} as React.CSSProperties}>
        {o.kind === 'PLACE' ? (
          <Building2 size={16} aria-hidden />
        ) : (
          <PersonMark name={o.name} kind={o.prospect?.party.kind} />
        )}
      </span>
      <span className="acq-row-main">
        <span className="acq-row-top">
          <strong>{o.name}</strong>
          <span className="acq-dist">{distanceLabel(o.distanceKm)}</span>
        </span>
        <small>{o.subtitle}</small>
        <span className="acq-summary">{o.summary}</span>
        <span className="acq-tags">
          <Status tone={statusTone}>
            {o.hot && <Flame size={12} aria-hidden />}
            {o.status}
          </Status>
          <span className="acq-source">
            {o.kind === 'PROSPECT' ? 'Assigned to you' : 'Found nearby'}
          </span>
        </span>
      </span>
    </button>
  );
}

export default function Acquisition() {
  const q = useRM<RMProspects>('/v1/rm/prospects', 5000);
  const [center, setCenter] = useState<RMPosition>(DEMO_OFFICE);
  const [radius, setRadius] = useState<number>(5);
  const [places, setPlaces] = useState<RMPoiPlace[]>([]);
  const [poiLoading, setPoiLoading] = useState(false);
  const [poiError, setPoiError] = useState('');
  const [filter, setFilter] = useState<OppFilter>('ALL');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<OppSort>('best');
  const [selected, setSelected] = useState('');
  const [pending, setPending] = useState('');
  const [showLater, setShowLater] = useState(false);
  const [mobileView, setMobileView] = useState<'list' | 'map' | 'detail'>('list');
  const [narrow, setNarrow] = useState(false);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState('');
  const [address, setAddress] = useState('');
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeNotice, setGeocodeNotice] = useState('');

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)');
    const update = () => setNarrow(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);

  const poiRadiusM = Math.min(5000, (radius || 5) * 1000);
  const reqSeq = useRef(0);

  const loadPlaces = useCallback(async () => {
    const seq = ++reqSeq.current;
    setPoiLoading(true);
    setPoiError('');
    try {
      const data = await fetchApi<RMPoiNearby>(
        `/v1/rm/poi/nearby?lat=${center.latitude}&lng=${center.longitude}&radius_m=${poiRadiusM}&include_existing=true`
      );
      if (seq === reqSeq.current) {
        setPlaces(data.places || []);
      }
    } catch (err: unknown) {
      if (seq === reqSeq.current) {
        setPoiError(err instanceof Error ? err.message : 'Could not load places');
      }
    } finally {
      if (seq === reqSeq.current) {
        setPoiLoading(false);
      }
    }
  }, [center.latitude, center.longitude, poiRadiusM]);

  useEffect(() => {
    loadPlaces();
  }, [loadPlaces]);

  const all = useMemo(
    () => buildOpportunities(q.data?.prospects || [], places, center, radius),
    [q.data?.prospects, places, center, radius]
  );
  const counts = useMemo(() => countByGroup(all), [all]);
  const rows = useMemo(
    () => sortOpportunities(filterOpportunities(all, filter, search), sort),
    [all, filter, search, sort]
  );
  const hideLater = filter === 'ALL' && !search.trim() && !showLater;
  const listed = useMemo(
    () => (hideLater ? rows.filter(o => o.group !== 'LATER') : rows),
    [hideLater, rows]
  );

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const id = new URLSearchParams(window.location.search).get('selected');
      if (id) setPending(id);
    }
  }, []);

  useEffect(() => {
    if (!pending) return;
    const match = all.find(o => o.key === pending);
    if (match) {
      setFilter('ALL');
      if (match.group === 'LATER') setShowLater(true);
      setSelected(pending);
      setPending('');
    } else if (radius !== 0 && q.data?.prospects.some(p => p.id === pending)) {
      setRadius(0);
    } else if (q.data && !poiLoading) {
      setPending('');
    }
  }, [pending, all, q.data, poiLoading, radius]);

  useEffect(() => {
    if (!pending && q.data && !listed.some(o => o.key === selected)) {
      setSelected(listed[0]?.key || '');
    }
  }, [pending, q.data, listed, selected]);

  const choose = useCallback(
    (key: string) => {
      setSelected(key);
      if (narrow) setMobileView('detail');
      window.history.replaceState(null, '', '/acquisition?selected=' + encodeURIComponent(key));
    },
    [narrow]
  );

  const locate = () => {
    setLocationError('');
    if (!navigator.geolocation) {
      setLocationError('Device location is unavailable. The example office remains selected.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      position => {
        const {latitude, longitude, accuracy} = position.coords;
        if (
          !Number.isFinite(latitude) ||
          !Number.isFinite(longitude) ||
          Math.abs(latitude) > 90 ||
          Math.abs(longitude) > 180
        ) {
          setLocationError('The device returned an unavailable position. Choose the demo area.');
          setLocating(false);
          return;
        }
        setCenter({
          latitude,
          longitude,
          accuracy,
          mode: 'DEVICE',
          label: 'Your location',
        });
        setLocating(false);
      },
      error => {
        setLocationError(
          error.code === 1
            ? 'Location permission was declined. Use the demo office or allow location when you want nearby discovery.'
            : 'Your device location could not be refreshed. Choose the demo area or try again.'
        );
        setLocating(false);
      },
      {enableHighAccuracy: false, timeout: 10000, maximumAge: 0}
    );
  };

  const useDemoArea = () => {
    setCenter(DEMO_OFFICE);
    setRadius(5);
    setLocationError('');
  };

  const handleGeocode = async (e: React.FormEvent) => {
    e.preventDefault();
    const qStr = address.trim();
    if (!qStr) return;
    setGeocoding(true);
    setGeocodeNotice('');
    try {
      const data = await fetchApi<RMGeocode>(`/v1/rm/poi/geocode?q=${encodeURIComponent(qStr)}`);
      if (data.results && data.results.length > 0) {
        const r = data.results[0];
        setCenter({
          latitude: Number(r.latitude),
          longitude: Number(r.longitude),
          mode: 'PLACE',
          label: r.label,
        });
        setGeocodeNotice('');
      } else {
        setGeocodeNotice(`No place found for "${qStr}".`);
      }
    } catch (err: unknown) {
      setGeocodeNotice(err instanceof Error ? err.message : 'Address search failed.');
    } finally {
      setGeocoding(false);
    }
  };

  const handleSearchThisArea = (c: {lat: number; lng: number}, r: number) => {
    setCenter({latitude: c.lat, longitude: c.lng, mode: 'PLACE', label: 'Map area'});
    const km = r / 1000;
    const options = [0.5, 1.5, 3, 5];
    const matched = options.find(opt => opt >= km);
    setRadius(matched !== undefined ? matched : 5);
  };


  const handleProspectCreated = async (p: RMProspect) => {
    await q.refresh();
    loadPlaces();
    setPending(p.id);
  };

  const current = useMemo(
    () => all.find(o => o.key === selected) || null,
    [all, selected]
  );
  const currentGroup = OPP_GROUPS.find(g => g.key === filter);
  const outsideCount =
    (q.data?.prospects.length || 0) - all.filter(o => o.kind === 'PROSPECT').length;

  return (
    <div className="acq-page">
      <header className="acq-head">
        <h1>Acquisition</h1>
        <p>Prospects assigned to you and businesses around you, in one list.</p>
      </header>
      <section className="acq-area" aria-label="Area">
        <div className="acq-area-place">
          <MapPin size={18} aria-hidden />
          <div>
            <strong>{center.label}</strong>
            <small>
              {center.mode === 'DEMO'
                ? 'Example office in synthetic data'
                : center.mode === 'DEVICE'
                ? center.accuracy != null
                  ? `Your device, ±${Math.round(center.accuracy)} m · not sent to the server`
                  : 'Your device, accuracy unavailable · not sent to the server'
                : 'Searched area'}
            </small>
          </div>
        </div>
        <form className="acq-area-search" role="search" onSubmit={handleGeocode}>
          <Search size={16} aria-hidden />
          <input
            aria-label="Search an address or area"
            placeholder="Search an address or area"
            value={address}
            onChange={e => setAddress(e.target.value)}
          />
          <button type="submit" className="button" disabled={geocoding || !address.trim()}>
            {geocoding ? 'Searching…' : 'Search'}
          </button>
        </form>
        <button type="button" className="button" onClick={locate} disabled={locating}>
          <LocateFixed size={16} />
          {locating ? 'Finding you…' : 'Use my location'}
        </button>
        {center.mode !== 'DEMO' && (
          <button type="button" className="button button-subtle" onClick={useDemoArea}>
            Use demo area
          </button>
        )}
        <label className="acq-radius">
          <span>Within</span>
          <select
            id="discovery-radius"
            value={radius}
            onChange={e => setRadius(Number(e.target.value))}
          >
            <option value={0.5}>500 m</option>
            <option value={1.5}>1.5 km</option>
            <option value={3}>3 km</option>
            <option value={5}>5 km</option>
            <option value={0}>All my prospects</option>
          </select>
        </label>
      </section>

      {locationError && <Notice tone="warn">{locationError}</Notice>}
      {geocodeNotice && <Notice tone="warn">{geocodeNotice}</Notice>}
      {poiError && <Notice tone="warn">Nearby businesses could not load: {poiError}</Notice>}
      {center.mode === 'DEVICE' && q.data && !all.some(o => o.kind === 'PROSPECT') && (
        <Notice tone="neutral">
          Your location is outside this example area, so no assigned prospects are within reach. Businesses around you are still listed. Use demo area to see the example portfolio.
        </Notice>
      )}

      <RequestState data={q.data} error={q.error} retry={q.refresh} />

      {q.data && (
        <>
          <div className="acq-filters">
            <div className="acq-chips" role="group" aria-label="Show">
              {[{key: 'ALL' as const, title: 'All'}, ...OPP_GROUPS].map(g => (
                <button
                  type="button"
                  key={g.key}
                  aria-pressed={filter === g.key}
                  onClick={() => setFilter(g.key)}
                >
                  {g.key !== 'ALL' && (
                    <i
                      className="acq-dot"
                      style={{background: 'color' in g ? g.color : undefined}}
                      aria-hidden
                    />
                  )}
                  {g.title}
                  <span className="acq-count">{g.key === 'ALL' ? all.length : counts[g.key]}</span>
                </button>
              ))}
            </div>
            <label className="acq-search">
              <Search size={16} aria-hidden />
              <input
                aria-label="Search prospects and contacts"
                placeholder="Name, business, contact or need"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </label>
          </div>

          {narrow && (
            <div className="acq-switch" role="group" aria-label="View">
              <button
                type="button"
                aria-pressed={mobileView !== 'map'}
                onClick={() => setMobileView('list')}
              >
                List
              </button>
              <button
                type="button"
                aria-pressed={mobileView === 'map'}
                onClick={() => setMobileView('map')}
              >
                Map
              </button>
            </div>
          )}

          <div className={'acq-workbench view-' + mobileView}>
            <section className="acq-list" aria-label="Opportunities">
              <header>
                <div className="acq-list-title">
                  <div>
                    <h2>{filter === 'ALL' ? 'All opportunities' : currentGroup?.title}</h2>
                    <span aria-live="polite">
                      {listed.length} shown{poiLoading ? ' · finding businesses…' : ''}
                    </span>
                  </div>
                  <select
                    className="acq-sort"
                    aria-label="Prospect ordering"
                    value={sort}
                    onChange={e => setSort(e.target.value as OppSort)}
                  >
                    <option value="best">Best first</option>
                    <option value="nearest">Nearest first</option>
                  </select>
                </div>
                {filter !== 'ALL' && currentGroup && <p>{currentGroup.hint}</p>}
              </header>
              <div className="acq-list-body">
                {listed.length === 0 && poiLoading ? (
                  <div className="acq-skeleton" role="status" aria-label="Finding businesses nearby">
                    <span /><span /><span />
                  </div>
                ) : listed.length === 0 ? (
                  <Empty title="Nothing in this view">
                    {filter === 'ALL'
                      ? 'Widen the area or search another place.'
                      : 'Choose All or widen the area.'}
                  </Empty>
                ) : filter === 'ALL' ? (
                  OPP_GROUPS.map(g => {
                    const groupRows = listed.filter(o => o.group === g.key);
                    if (!groupRows.length) return null;
                    return (
                      <div className="acq-group" key={g.key}>
                        <h3>
                          <i className="acq-dot" style={{background: g.color}} aria-hidden />
                          {g.title}
                          <span className="acq-count">{groupRows.length}</span>
                        </h3>
                        {groupRows.map(o => (
                          <OpportunityRow key={o.key} o={o} selected={selected === o.key} onChoose={choose} />
                        ))}
                      </div>
                    );
                  })
                ) : (
                  listed.map(o => (
                    <OpportunityRow key={o.key} o={o} selected={selected === o.key} onChoose={choose} />
                  ))
                )}
                {counts.LATER > 0 && filter === 'ALL' && !search.trim() && (
                  <button
                    type="button"
                    className="acq-later"
                    onClick={() => setShowLater(v => !v)}
                  >
                    {showLater ? 'Hide not for now' : `Show ${counts.LATER} not for now`}
                  </button>
                )}
                {radius !== 0 && outsideCount > 0 && (
                  <p className="acq-outside">
                    {outsideCount} assigned prospect{outsideCount === 1 ? '' : 's'} outside this area.{' '}
                    <button type="button" className="text-link" onClick={() => setRadius(0)}>
                      Show all my prospects
                    </button>
                  </p>
                )}
              </div>
            </section>

            <div className="acq-map">
              {(!narrow || mobileView === 'map') && (
                <GoogleTerritoryMap
                  center={{lat: center.latitude, lng: center.longitude}}
                  radiusM={radius > 0 ? radius * 1000 : 0}
                  pins={listed.map(o => {
                    const g = OPP_GROUPS.find(x => x.key === o.group)!;
                    return {
                      id: o.key,
                      lat: o.latitude,
                      lng: o.longitude,
                      title: `${o.name} · ${o.status}`,
                      color: g.color,
                      border: g.border,
                    };
                  })}
                  selectedId={selected}
                  onSelect={choose}
                  legend={OPP_GROUPS.filter(g => listed.some(o => o.group === g.key)).map(g => ({
                    key: g.key,
                    label: g.title,
                    color: g.color,
                    count: listed.filter(o => o.group === g.key).length,
                  }))}
                  onSearchThisArea={handleSearchThisArea}
                  isSearchingArea={poiLoading}
                />
              )}
            </div>

            <div className="acq-detail" id="opportunity-detail">
              {narrow && (
                <button
                  type="button"
                  className="button button-subtle acq-back"
                  onClick={() => setMobileView('list')}
                >
                  Back to list
                </button>
              )}
              {current?.prospect ? (
                <ProspectBrief
                  key={current.key}
                  p={current.prospect}
                  origin={center}
                  reload={q.refresh}
                />
              ) : current?.place ? (
                <PlaceCard
                  key={current.key}
                  place={current.place}
                  origin={{latitude: center.latitude, longitude: center.longitude}}
                  onUpdate={updated => setPlaces(prev => prev.map(p => (p.id === updated.id ? updated : p)))}
                  onProspectCreated={handleProspectCreated}
                />
              ) : (
                <section className="acq-detail-empty">
                  <MapPin size={22} aria-hidden />
                  <h2>Pick someone to start</h2>
                  <p>Choose a row or a pin to see why they matter and what to do next.</p>
                </section>
              )}
            </div>
          </div>

          <details className="acq-method">
            <summary>How this list is built</summary>
            <p>{q.data.priority_method}</p>
            <p>
              Ready to talk means the need was checked by you, identity is confirmed, contact is allowed and the source is fresh. Hot lead adds an explicit opt-in statement from the person. No purchase probability or creditworthiness is inferred.
            </p>
            <p>
              New nearby businesses come from the map provider and are matched against bank customers before you can add one as a prospect. Possible matches need your identity check first.
            </p>
            <p>
              Your device location is requested only when you choose Use my location. It stays in this page for distance filtering and is never sent to the server or saved.
            </p>
          </details>

          <SyntheticImport reload={q.refresh} />
        </>
      )}
    </div>
  );
}
