"use client";

import {useEffect, useMemo, useState} from 'react';
import {
  Search,
  MapPin,
  Navigation,
  LocateFixed,
  Flame,
  ArrowUpRight,
  Users,
  FileText,
  SlidersHorizontal,
  Upload,
  Compass,
  RotateCcw,
  Building2,
  AlertTriangle,
  UserCheck,
  CheckCircle2
} from 'lucide-react';
import {fetchApi} from '@/lib/api';
import {PageTitle, Notice, Empty, Status} from '@/components/ui/Workspace';
import {useRM, RequestState, PersonName, requestKey, Mode} from '@/components/rm/shared';
import {TerritoryMap} from '@/components/rm/spatial/TerritoryMap';
import {GoogleTerritoryMap} from '@/components/rm/spatial/GoogleTerritoryMap';
import {PlaceCard} from '@/components/rm/spatial/PlaceCard';
import {ProspectBrief} from '@/components/rm/spatial/ProspectBrief';
import {LeadCoverage, type DiscoveryQueue} from '@/components/rm/spatial/LeadCoverage';
import {DEMO_OFFICE, distanceKm, distanceLabel, type RMPosition} from '@/components/rm/spatial/geo';
import {dateLabel, label} from '@/lib/presentation';
import type {RMProspects, RMProspect, RMImportReceipt, RMPoiNearby, RMPoiPlace, RMGeocode} from '@/lib/rm.generated';
const permitted = (p: RMProspect) =>
  ['READY_FOR_DISCUSSION', 'REVIEW_FIRST', 'REVIEW'].includes(p.priority_tier);

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

export default function Acquisition() {
  const q = useRM<RMProspects>('/v1/rm/prospects', 5000);

  // Mode: assigned prospects vs nearby businesses
  const [mode, setMode] = useState<'assigned' | 'nearby'>('assigned');

  // Prospect shortlist state
  const [search, setSearch] = useState('');
  const [kind, setKind] = useState('all');
  const [queue, setQueue] = useState<DiscoveryQueue>('recommended');
  const [selected, setSelected] = useState('');
  const [sort, setSort] = useState('priority');
  const [mobileView, setMobileView] = useState('list');
  const [origin, setOrigin] = useState<RMPosition>(DEMO_OFFICE);
  const [radius, setRadius] = useState(5);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState('');
  const [narrow, setNarrow] = useState(false);

  // Nearby POI state
  const [poiCenter, setPoiCenter] = useState<{lat: number; lng: number}>({
    lat: DEMO_OFFICE.latitude,
    lng: DEMO_OFFICE.longitude
  });
  const [poiRadius, setPoiRadius] = useState(1500);
  const [poiData, setPoiData] = useState<RMPoiNearby | null>(null);
  const [poiLoading, setPoiLoading] = useState(false);
  const [poiError, setPoiError] = useState('');
  const [selectedPoiId, setSelectedPoiId] = useState('');
  const [showExisting, setShowExisting] = useState(false);
  const [geocodeQuery, setGeocodeQuery] = useState('');
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeNotice, setGeocodeNotice] = useState('');
  const [poiFilterSearch, setPoiFilterSearch] = useState('');
  const [poiSort, setPoiSort] = useState<'nearest' | 'name'>('nearest');

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('selected');
    if (id) {
      setSelected(id);
      setQueue('all');
    }
  }, []);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)');
    const update = () => setNarrow(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);

  const fetchNearby = async (
    lat: number,
    lng: number,
    radiusM: number,
    incExisting: boolean
  ) => {
    setPoiLoading(true);
    setPoiError('');
    try {
      const url = `/v1/rm/poi/nearby?lat=${lat}&lng=${lng}&radius_m=${radiusM}&include_existing=${incExisting}`;
      const data = await fetchApi<RMPoiNearby>(url);
      setPoiData(data);
      if (data.places.length > 0) {
        if (!data.places.some(p => p.id === selectedPoiId)) {
          setSelectedPoiId(data.places[0].id);
        }
      } else {
        setSelectedPoiId('');
      }
    } catch (err: unknown) {
      setPoiError(err instanceof Error ? err.message : 'Failed to search nearby businesses');
    } finally {
      setPoiLoading(false);
    }
  };

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
        const devOrigin: RMPosition = {
          latitude,
          longitude,
          accuracy,
          mode: 'DEVICE',
          label: 'Your device location'
        };
        setOrigin(devOrigin);
        setLocating(false);

        // Also update POI center if in nearby mode or switching
        setPoiCenter({lat: latitude, lng: longitude});
        if (mode === 'nearby') {
          fetchNearby(latitude, longitude, poiRadius, showExisting);
        }
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

  const resetToDemo = () => {
    setOrigin(DEMO_OFFICE);
    setRadius(5);
    setLocationError('');
    setPoiCenter({lat: DEMO_OFFICE.latitude, lng: DEMO_OFFICE.longitude});
    if (mode === 'nearby') {
      fetchNearby(DEMO_OFFICE.latitude, DEMO_OFFICE.longitude, poiRadius, showExisting);
    }
  };

  const handleGeocode = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!geocodeQuery.trim()) return;
    setGeocoding(true);
    setGeocodeNotice('');
    try {
      const data = await fetchApi<RMGeocode>(
        `/v1/rm/poi/geocode?q=${encodeURIComponent(geocodeQuery.trim())}`
      );
      if (data.results && data.results.length > 0) {
        const first = data.results[0];
        const newCenter = {lat: Number(first.latitude), lng: Number(first.longitude)};
        setPoiCenter(newCenter);
        setGeocodeNotice(`Centered on: ${first.label}`);
        await fetchNearby(newCenter.lat, newCenter.lng, poiRadius, showExisting);
      } else {
        setGeocodeNotice(`No location results found for "${geocodeQuery}".`);
      }
    } catch (err: unknown) {
      setGeocodeNotice(err instanceof Error ? err.message : 'Address geocoding failed');
    } finally {
      setGeocoding(false);
    }
  };

  const handleSearchThisArea = async (center: {lat: number; lng: number}, radiusM: number) => {
    setPoiCenter(center);
    setPoiRadius(radiusM);
    await fetchNearby(center.lat, center.lng, radiusM, showExisting);
  };

  const handleToggleExisting = (val: boolean) => {
    setShowExisting(val);
    fetchNearby(poiCenter.lat, poiCenter.lng, poiRadius, val);
  };

  // Prospect rows filtering & sorting
  const all = q.data?.prospects || [];
  const area = useMemo(
    () => all.filter(p => radius === 0 || distanceKm(origin, p) <= radius),
    [all, origin, radius]
  );
  const rows = useMemo(
    () =>
      area
        .filter(p => {
          const allowed =
            (queue === 'refresh' && p.priority_tier === 'SOURCE_REVIEW') ||
            queue === 'all' ||
            (queue === 'recommended' && permitted(p)) ||
            (queue === 'review' && permitted(p) && !p.hot_lead) ||
            (queue === 'hot' && p.hot_lead) ||
            (queue === 'followup' &&
              ['FOLLOWUP_PLANNED', 'FOLLOWUP_RECORDED'].includes(p.priority_tier)) ||
            (queue === 'held' &&
              !permitted(p) &&
              !['FOLLOWUP_PLANNED', 'FOLLOWUP_RECORDED'].includes(p.priority_tier));
          return (
            allowed &&
            (kind === 'all' || p.party.kind === kind) &&
            (
              p.party.name +
              ' ' +
              p.party.locality +
              ' ' +
              p.need +
              ' ' +
              p.party.contacts.map(c => c.name).join(' ')
            )
              .toLowerCase()
              .includes(search.toLowerCase())
          );
        })
        .sort((a, b) => (sort === 'nearest' ? distanceKm(origin, a) - distanceKm(origin, b) : 0)),
    [area, queue, kind, search, sort, origin]
  );

  useEffect(() => {
    if (!rows.some(p => p.id === selected)) setSelected(rows[0]?.id || '');
  }, [rows, selected]);

  const current = rows.find(p => p.id === selected);
  const choose = (id: string) => {
    setSelected(id);
    if (narrow) setMobileView('brief');
    window.history.replaceState(null, '', '/acquisition?selected=' + encodeURIComponent(id));
  };

  // Nearby places filtering & sorting
  const poiPlaces = poiData?.places || [];
  const filteredPois = useMemo(() => {
    const list = poiPlaces.filter(p => {
      const matchText = (p.name + ' ' + p.address + ' ' + p.primary_type)
        .toLowerCase()
        .includes(poiFilterSearch.toLowerCase());
      return matchText;
    });
    if (poiSort === 'nearest') {
      return [...list].sort((a, b) => a.distance_m - b.distance_m);
    }
    return [...list].sort((a, b) => a.name.localeCompare(b.name));
  }, [poiPlaces, poiFilterSearch, poiSort]);

  const currentPoi = poiPlaces.find(p => p.id === selectedPoiId);
  const choosePoi = (id: string) => {
    setSelectedPoiId(id);
    if (narrow) setMobileView('brief');
  };

  const handlePoiUpdated = (updated: RMPoiPlace) => {
    if (!poiData) return;
    setPoiData({
      ...poiData,
      places: poiData.places.map(p => (p.id === updated.id ? updated : p))
    });
  };

  const queueName =
    queue === 'refresh'
      ? 'Sources needing refresh'
      : queue === 'hot'
      ? 'Hot discussions'
      : queue === 'held'
      ? 'Held source records'
      : queue === 'followup'
      ? 'RM follow-up records'
      : queue === 'all'
      ? 'All assigned prospects'
      : 'Your prospect shortlist';

  return (
    <div className="discovery-page">
      <div className="discovery-heading">
        <div>
          <span className="eyebrow">
            <Compass size={14} /> Acquisition · Territory desk
          </span>
          <h1>
            Good relationships
            <br />
            start with a reason.
          </h1>
          <p>
            Discover the people and businesses nearby. See the source, the person to speak to,
            and the next useful step.
          </p>
        </div>
        <div className="discovery-location-action">
          <button
            type="button"
            className="button button-primary"
            disabled={locating}
            onClick={locate}
          >
            <LocateFixed size={17} />
            {locating ? 'Finding your location…' : 'Use my location'}
          </button>
          <span>Opt-in · Position stays in this page</span>
        </div>
      </div>

      <Mode />

      {/* Mode switcher tabs */}
      <div className="discovery-mode-bar" role="tablist" aria-label="Acquisition workspace modes">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'assigned'}
          className={`discovery-mode-tab ${mode === 'assigned' ? 'active' : ''}`}
          onClick={() => setMode('assigned')}
        >
          <Users size={16} /> Assigned prospects ({all.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'nearby'}
          className={`discovery-mode-tab ${mode === 'nearby' ? 'active' : ''}`}
          onClick={() => {
            setMode('nearby');
            if (!poiData && !poiLoading) {
              fetchNearby(poiCenter.lat, poiCenter.lng, poiRadius, showExisting);
            }
          }}
        >
          <Compass size={16} /> Nearby businesses
        </button>
      </div>

      <div className="discovery-location-bar">
        <div className="location-anchor">
          <span className="location-icon">
            <Navigation size={17} />
          </span>
          <div>
            <strong>{origin.label}</strong>
            <small>
              {origin.mode === 'DEMO'
                ? 'Synthetic RM office · Not your detected location'
                : `Device position · ${
                    origin.accuracy
                      ? `±${Math.round(origin.accuracy)} m accuracy`
                      : 'accuracy unavailable'
                  } · Not sent to the server`}
            </small>
          </div>
          {origin.mode === 'DEVICE' && (
            <button
              type="button"
              className="button button-subtle"
              style={{marginLeft: 'auto'}}
              onClick={resetToDemo}
            >
              Use demo area
            </button>
          )}
        </div>

        {mode === 'assigned' ? (
          <div className="discovery-radius">
            <label htmlFor="discovery-radius">Search around</label>
            <select
              id="discovery-radius"
              value={radius}
              onChange={e => setRadius(Number(e.target.value))}
            >
              <option value={0.5}>500 m</option>
              <option value={2}>2 km</option>
              <option value={5}>5 km</option>
              <option value={10}>10 km</option>
              <option value={0}>All source areas</option>
            </select>
          </div>
        ) : (
          <div className="discovery-radius">
            <label htmlFor="poi-radius-select">Search radius</label>
            <select
              id="poi-radius-select"
              value={poiRadius}
              onChange={e => {
                const r = Number(e.target.value);
                setPoiRadius(r);
                fetchNearby(poiCenter.lat, poiCenter.lng, r, showExisting);
              }}
            >
              <option value={500}>500 m</option>
              <option value={1500}>1.5 km</option>
              <option value={3000}>3 km</option>
              <option value={5000}>5 km</option>
            </select>
          </div>
        )}
      </div>

      {locationError && <Notice tone="warn">{locationError}</Notice>}
      {origin.mode === 'DEVICE' && mode === 'assigned' && area.length === 0 && (
        <Notice tone="neutral">
          Your detected device location is outside this example area. Use demo area to explore the
          assigned prospects.
        </Notice>
      )}

      {/* MODE 1: Assigned Prospects Mode */}
      {mode === 'assigned' && (
        <>
          <RequestState data={q.data} error={q.error} retry={q.refresh} />
          {q.data && (
            <>
              <div className="discovery-filter-row">
                <div className="discovery-tabs">
                  {[
                    {key: 'recommended', title: 'Prioritized', icon: Compass},
                    {key: 'hot', title: 'Hot leads', icon: Flame},
                    {key: 'refresh', title: 'Refresh sources', icon: FileText},
                    {key: 'all', title: 'All assigned', icon: Users}
                  ].map(t => (
                    <button
                      type="button"
                      key={t.key}
                      aria-pressed={queue === t.key}
                      onClick={() => setQueue(t.key as DiscoveryQueue)}
                    >
                      <t.icon size={15} />
                      {t.title}
                      {t.key === 'hot' && <span>{area.filter(p => p.hot_lead).length}</span>}
                    </button>
                  ))}
                </div>
                <label className="discovery-search">
                  <Search size={16} />
                  <input
                    aria-label="Search prospects and contacts"
                    placeholder="Name, business, contact, or need"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                  />
                </label>
                <label className="discovery-select">
                  <SlidersHorizontal size={15} />
                  <select
                    aria-label="Filter prospect kind"
                    value={kind}
                    onChange={e => setKind(e.target.value)}
                  >
                    <option value="all">All kinds</option>
                    <option value="ORGANIZATION">Businesses</option>
                    <option value="PERSON">Individual</option>
                  </select>
                </label>
              </div>

              <div className={'discovery-workbench view-' + mobileView}>
                <section className="discovery-shortlist">
                  <header>
                    <div>
                      <h2>{queueName}</h2>
                      <span>
                        {rows.length} matching · {area.length} in area
                      </span>
                    </div>
                    <select
                      aria-label="Prospect ordering"
                      value={sort}
                      onChange={e => setSort(e.target.value)}
                    >
                      <option value="priority">By priority</option>
                      <option value="nearest">Nearest first</option>
                    </select>
                  </header>

                  <div className="discovery-prospect-rows">
                    {rows.length ? (
                      rows.map((p, i) => (
                        <button
                          type="button"
                          key={p.id}
                          className={
                            'discovery-prospect ' +
                            (selected === p.id ? 'selected ' : '') +
                            (p.hot_lead ? 'is-hot' : '')
                          }
                          aria-pressed={selected === p.id}
                          onClick={() => choose(p.id)}
                        >
                          <div className="discovery-prospect-top">
                            <span className="prospect-order">{String(i + 1).padStart(2, '0')}</span>
                            <span className="discovery-distance">
                              {distanceLabel(distanceKm(origin, p))}
                            </span>
                          </div>
                          <PersonName party={p.party} />
                          <p>{p.need}</p>
                          <div className="discovery-prospect-footer">
                            <Status tone={p.hot_lead ? 'good' : permitted(p) ? 'neutral' : 'warn'}>
                              {p.hot_lead ? (
                                <>
                                  <Flame size={12} /> Hot lead
                                </>
                              ) : (
                                label(p.priority_tier)
                              )}
                            </Status>
                            <small>{p.party.locality}</small>
                          </div>
                        </button>
                      ))
                    ) : (
                      <Empty title="No prospects match">
                        Try clearing filters or changing distance.
                      </Empty>
                    )}
                  </div>
                </section>

                <div className="discovery-territory">
                  {(!narrow || mobileView === 'map') && (
                    <>
                      <TerritoryMap
                        items={rows}
                        allItems={all}
                        selected={selected}
                        onSelect={choose}
                        origin={origin}
                        radius={radius}
                        onOpenBrief={() => {
                          setMobileView('brief');
                          if (!narrow) {
                            document.getElementById('prospect-brief')?.scrollIntoView({block: 'nearest'});
                          }
                        }}
                      />
                      <LeadCoverage items={area} queue={queue} onQueue={setQueue} />
                    </>
                  )}
                </div>

                <div className="discovery-brief-column">
                  {current ? (
                    <ProspectBrief
                      key={current.id}
                      p={current}
                      origin={origin}
                      reload={q.refresh}
                    />
                  ) : (
                    <section className="brief-empty">
                      <MapPin size={24} />
                      <h2>A source before a sales pitch.</h2>
                      <p>
                        Select a prospect in the list or map to see why now, who to speak to and what
                        remains to confirm.
                      </p>
                    </section>
                  )}
                </div>
              </div>

              <details className="discovery-method">
                <summary>How discovery, proximity and hot leads work</summary>
                <p>{q.data.priority_method}</p>
                <p>
                  Hot discussion label: explicit opt-in source statement, unchanged need reviewed
                  by the RM, current identity/contact/freshness checks and approved educational
                  knowledge. No purchase probability, creditworthiness or private-person contact
                  permission is inferred.
                </p>
                <p>
                  Device location is requested only when you choose Use my location. It is held in
                  page memory for straight-line distance filtering, never sent to the API or
                  persisted.
                </p>
              </details>
              <SyntheticImport reload={q.refresh} />
            </>
          )}
        </>
      )}

      {/* MODE 2: Nearby Businesses Mode */}
      {mode === 'nearby' && (
        <div className="nearby-discovery-workbench">
          {/* Address search bar */}
          <form className="address-search-row" onSubmit={handleGeocode}>
            <input
              type="text"
              aria-label="Search address or locality"
              placeholder="Search address or place (e.g. Bekasi Cyber Park, Harapan Indah)"
              value={geocodeQuery}
              onChange={e => setGeocodeQuery(e.target.value)}
            />
            <button
              type="submit"
              className="button button-primary"
              disabled={geocoding || !geocodeQuery.trim()}
              onClick={handleGeocode}
            >
              <Search size={15} />
              {geocoding ? 'Locating…' : 'Search address'}
            </button>
          </form>

          {geocodeNotice && (
            <Notice tone={geocodeNotice.startsWith('No') ? 'warn' : 'neutral'}>
              {geocodeNotice}
            </Notice>
          )}
          {poiError && <Notice tone="warn">{poiError}</Notice>}

          <div className={'discovery-workbench view-' + mobileView}>
            {/* Column 1: Shortlist of Places */}
            <section className="discovery-shortlist">
              <header>
                <div>
                  <h2>Nearby establishments</h2>
                  <span aria-live="polite">
                    {filteredPois.length} businesses
                    {!showExisting && (poiData?.counts.existing_customer ?? 0) > 0
                      ? ` (${poiData?.counts.existing_customer} existing customers filtered out)`
                      : ''}
                  </span>
                </div>
                <select
                  aria-label="Sort establishments"
                  value={poiSort}
                  onChange={e => setPoiSort(e.target.value as 'nearest' | 'name')}
                >
                  <option value="nearest">Nearest first</option>
                  <option value="name">By name</option>
                </select>
              </header>

              <div className="shortlist-filter" style={{padding: '8px 14px', borderBottom: '1px solid var(--stroke)'}}>
                <label className="discovery-search" style={{width: '100%', maxWidth: 'none'}}>
                  <Search size={15} />
                  <input
                    aria-label="Filter results by name or type"
                    placeholder="Filter results…"
                    value={poiFilterSearch}
                    onChange={e => setPoiFilterSearch(e.target.value)}
                  />
                </label>
              </div>

              <div className="discovery-prospect-rows" role="list" aria-label="Nearby establishments">
                {poiLoading ? (
                  <div className="spatial-loading" style={{height: '240px'}}>
                    <Compass size={24} />
                    <span>Searching area establishments…</span>
                  </div>
                ) : filteredPois.length ? (
                  filteredPois.map((p, i) => {
                    const isSelected = selectedPoiId === p.id;
                    const isExisting = p.match_status === 'EXISTING_CUSTOMER';
                    const isPossible = p.match_status === 'POSSIBLE_MATCH';
                    const isProspect = Boolean(p.prospect_id || p.match_status === 'PROSPECT');

                    return (
                      <button
                        type="button"
                        key={p.id}
                        className={'discovery-prospect ' + (isSelected ? 'selected ' : '')}
                        aria-pressed={isSelected}
                        onClick={() => choosePoi(p.id)}
                      >
                        <div className="discovery-prospect-top">
                          <span className="prospect-order">{String(i + 1).padStart(2, '0')}</span>
                          <span className="discovery-distance">
                            {distanceLabel(p.distance_m / 1000)}
                          </span>
                        </div>
                        <div className="person-name">
                          <strong>{p.name}</strong>
                          <small>{p.primary_type.replaceAll('_', ' ')}</small>
                        </div>
                        <p style={{fontSize: '12px', color: 'var(--secondary)'}}>{p.address}</p>
                        <div className="discovery-prospect-footer">
                          {isExisting && (
                            <span className="status-badge status-existing">
                              <UserCheck size={11} /> Existing
                            </span>
                          )}
                          {isPossible && (
                            <span className="status-badge status-possible">
                              <AlertTriangle size={11} /> Possible match
                            </span>
                          )}
                          {isProspect && (
                            <span className="status-badge status-prospect">
                              <CheckCircle2 size={11} /> Prospect
                            </span>
                          )}
                          {!isExisting && !isPossible && !isProspect && (
                            <span className="status-badge status-new">
                              <CheckCircle2 size={11} /> New lead
                            </span>
                          )}
                          {p.rating != null && (
                            <small>★ {p.rating.toFixed(1)}</small>
                          )}
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <Empty title="No establishments found">
                    Try searching a different location or expanding your radius.
                  </Empty>
                )}
              </div>
            </section>

            {/* Column 2: Google Territory Map */}
            <div className="discovery-territory">
              {(!narrow || mobileView === 'map') && (
                <GoogleTerritoryMap
                  center={poiCenter}
                  radiusM={poiRadius}
                  places={poiPlaces}
                  selectedPlaceId={selectedPoiId}
                  onSelectPlace={choosePoi}
                  showExisting={showExisting}
                  onToggleExisting={handleToggleExisting}
                  counts={poiData?.counts}
                  onSearchThisArea={handleSearchThisArea}
                  isSearchingArea={poiLoading}
                />
              )}
            </div>

            {/* Column 3: PlaceCard */}
            <div className="discovery-brief-column">
              {currentPoi ? (
                <PlaceCard
                  key={currentPoi.id}
                  place={currentPoi}
                  origin={{latitude: poiCenter.lat, longitude: poiCenter.lng}}
                  onUpdate={handlePoiUpdated}
                  onProspectCreated={async () => {
                    await q.refresh();
                  }}
                />
              ) : (
                <section className="brief-empty">
                  <Building2 size={24} />
                  <h2>Select a business establishment</h2>
                  <p>
                    Select an establishment pin on the map or in the shortlist to inspect customer
                    matching facts, reviews, and relationship actions.
                  </p>
                </section>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
