/** React component and module contracts in Node for Google Maps acquisition workspace. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';

const require = createRequire(new URL('../apps/web/package.json',import.meta.url));
const React = require('react'), Renderer = require('react-test-renderer'), ts = require('typescript');
const {act} = Renderer;

const root = path.resolve('apps/web/src');
const cache = new Map(), overrides = new Map();
const storage = new Map();
const sessionStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: key => storage.delete(key)
};

let locationRequests = 0, located, pathname = '/acquisition';
const window = {
  matchMedia: () => ({matches: false, addEventListener() {}, removeEventListener() {}}),
  addEventListener() {},
  removeEventListener() {},
  history: {replaceState() {}},
  location: {search: '', assign(value) { pathname = value; }}
};
const navigator = {
  geolocation: {
    getCurrentPosition(success) {
      locationRequests++;
      located = success;
    }
  }
};
const document = {visibilityState: 'visible', getElementById: () => null};
const link = ({children, href, ...props}) => React.createElement('a', {href, ...props}, children);
const router = {push: href => { pathname = href; }, prefetch() {}};

function load(file) {
  const full = path.resolve(root, file);
  if (cache.has(full)) return cache.get(full).exports;
  const module = {exports: {}};
  cache.set(full, module);
  const source = fs.readFileSync(full, 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true
    }
  }).outputText;
  const resolve = id => {
    if (overrides.has(id)) return overrides.get(id);
    if (id === 'next/link') return {__esModule: true, default: link};
    if (id === 'next/navigation') return {useRouter: () => router, usePathname: () => pathname};
    if (id.startsWith('@/') || id.startsWith('.')) {
      let target = id.startsWith('@/')
        ? path.join(root, id.slice(2))
        : path.resolve(path.dirname(full), id);
      if (!path.extname(target)) {
        target = ['.ts', '.tsx'].map(ext => target + ext).find(fs.existsSync);
      }
      const alias = '@/' + path.relative(root, target).replace(/\.(tsx?|jsx?)$/, '');
      if (overrides.has(alias)) return overrides.get(alias);
      return load(target);
    }
    return require(id);
  };
  vm.runInNewContext(
    `(function(require,module,exports){${code}\n})`,
    {
      console,
      React,
      process: {env: {NODE_ENV: 'test'}},
      window,
      document,
      navigator,
      sessionStorage,
      Headers,
      URL,
      URLSearchParams,
      crypto: globalThis.crypto,
      fetch: (...args) => globalThis.fetch(...args),
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
      requestAnimationFrame: fn => setTimeout(fn, 0),
      cancelAnimationFrame: clearTimeout
    },
    {filename: full}
  )(resolve, module, module.exports);
  return module.exports;
}

const labelText = node =>
  typeof node === 'string'
    ? node
    : typeof node === 'number'
    ? String(node)
    : Array.isArray(node)
    ? node.map(labelText).join('')
    : node?.children
    ? labelText(node.children)
    : '';

const click = async (tree, name) => {
  const found = tree.root
    .findAllByType('button')
    .find(node => labelText(node).trim() === name.trim());
  assert.ok(found, `Missing button: ${name}`);
  assert.ok(!found.props.disabled, `Disabled button: ${name}`);
  await act(async () => {
    found.props.onClick();
  });
};

const options = {createNodeMock: () => ({scrollTo() {}, focus() {}, scrollHeight: 100})};

let config = {demoMode: true, authProvider: 'synthetic_demo', googleMapsApiKey: null, googleMapsMapId: null};
overrides.set('@/lib/app-config', {getAppConfig: async () => config});
overrides.set('./app-config', {getAppConfig: async () => config});

// Test fixtures
const samplePoiNew = {
  id: 'poi-pt-sejahtera',
  name: 'PT Sejahtera Logistik',
  primary_type: 'freight_forwarding_service',
  address: 'Jl. Ahmad Yani No. 88, Bekasi',
  latitude: '-6.2415',
  longitude: '106.9920',
  distance_m: 650,
  phone_masked: '+62 21 8899 ****',
  website: 'https://sejahtera.example.invalid',
  rating: 4.6,
  rating_count: 32,
  match_status: 'NEW_LEAD',
  match_score: '0.120',
  match_reasons: ['No matching customer records in tenant database'],
  matched_customer: null,
  prospect_id: null,
  provider: 'SYNTHETIC_DATASET',
  attribution: 'Synthetic Bekasi Commercial Gazetteer',
  fetched_at: '2026-10-17T06:00:00Z'
};

const samplePoiPossible = {
  id: 'poi-mitra-abadi',
  name: 'CV Mitra Abadi Mandiri',
  primary_type: 'wholesale_distributor',
  address: 'Jl. Cut Mutia No. 12, Bekasi',
  latitude: '-6.2520',
  longitude: '106.9850',
  distance_m: 1100,
  phone_masked: '+62 21 8240 ****',
  website: null,
  rating: 4.1,
  rating_count: 8,
  match_status: 'POSSIBLE_MATCH',
  match_score: '0.840',
  match_reasons: ['Name similarity 86% with customer CIF-10023 within 300 m'],
  matched_customer: {
    id: 'cust-10023',
    cif: 'CIF-10023',
    name: 'PT Mitra Abadi Utama',
    segment: 'COMMERCIAL',
    relationship_owner_rm: true
  },
  prospect_id: null,
  provider: 'SYNTHETIC_DATASET',
  attribution: 'Synthetic Bekasi Commercial Gazetteer',
  fetched_at: '2026-10-17T06:00:00Z'
};

const samplePoiExisting = {
  id: 'poi-dina-boutique',
  name: 'Dina Rahma Collections',
  primary_type: 'clothing_store',
  address: 'Ruko Summarecon Blok A-1, Bekasi',
  latitude: '-6.2280',
  longitude: '106.9980',
  distance_m: 1400,
  phone_masked: '+62 812 9988 ****',
  website: 'https://dinacollections.example.invalid',
  rating: 4.9,
  rating_count: 114,
  match_status: 'EXISTING_CUSTOMER',
  match_score: '1.000',
  match_reasons: ['Exact phone hash and NPWP hash match with active core-banking customer'],
  matched_customer: {
    id: 'cust-dina-01',
    cif: 'CIF-00842',
    name: 'Dina Rahma',
    segment: 'PRIORITY',
    relationship_owner_rm: true,
    party_id: 'party-dina'
  },
  prospect_id: null,
  provider: 'SYNTHETIC_DATASET',
  attribution: 'Synthetic Bekasi Commercial Gazetteer',
  fetched_at: '2026-10-17T06:00:00Z'
};

const sampleNearby = {
  provider: 'SYNTHETIC_DATASET',
  attribution: 'Synthetic Bekasi Commercial Gazetteer',
  center: {lat: -6.250, lng: 106.981},
  radius_m: 1500,
  places: [samplePoiNew, samplePoiPossible, samplePoiExisting],
  counts: {
    new_lead: 1,
    possible_match: 1,
    existing_customer: 1,
    prospect: 0
  }
};

let apiCalls = [];
const api = load('lib/api.ts');
overrides.set('@/lib/api', {
  ...api,
  fetchApi: async (endpoint, reqOpts = {}) => {
    apiCalls.push({endpoint, body: reqOpts.body ? JSON.parse(reqOpts.body) : null, method: reqOpts.method || 'GET'});
    if (endpoint.includes('/v1/rm/poi/nearby')) {
      return sampleNearby;
    }
    if (endpoint.includes('/v1/rm/poi/geocode')) {
      return {
        provider: 'SYNTHETIC_DATASET',
        results: [
          {label: 'Summarecon Mall Bekasi', latitude: '-6.2250', longitude: '106.9990'}
        ]
      };
    }
    if (endpoint.endsWith('/prospect')) {
      const placeId = endpoint.split('/')[4];
      return {
        id: 'prospect-from-' + placeId,
        party: {id: 'party-from-' + placeId, name: 'Created Prospect', kind: 'ORGANIZATION', locality: 'Bekasi', contact: 'REQUIRES_CONFIRMATION', identity: 'UNCONFIRMED', contacts: []},
        state: 'ASSIGNED',
        disposition: null,
        need: 'Business listing enquiry',
        need_reviewed: false,
        reasons: ['Converted from POI listing'],
        latitude: -6.2415,
        longitude: 106.9920,
        version: 1,
        priority_tier: 'REVIEW_FIRST',
        priority_reason: 'POI listing',
        next_action: 'Verify contact',
        priority_method: 'POI-1',
        hot_lead: false,
        hot_reason: 'Unreviewed'
      };
    }
    if (endpoint.endsWith('/match-review')) {
      const body = JSON.parse(reqOpts.body);
      return {
        ...samplePoiPossible,
        match_status: body.decision === 'CONFIRM_EXISTING' ? 'EXISTING_CUSTOMER' : 'NEW_LEAD',
        match_reasons: [body.reason]
      };
    }
    return {};
  }
});

// 1. Test PlaceCard: New Lead action 'Add as prospect'
const PlaceCard = load('components/rm/spatial/PlaceCard.tsx').PlaceCard;
let cardTree;
apiCalls = [];
let createdProspect = null;

await act(async () => {
  cardTree = Renderer.create(
    React.createElement(PlaceCard, {
      place: samplePoiNew,
      onProspectCreated: p => { createdProspect = p; }
    }),
    options
  );
});

assert.ok(labelText(cardTree.root).includes('PT Sejahtera Logistik'));
assert.ok(labelText(cardTree.root).includes('freight forwarding service'));
assert.ok(labelText(cardTree.root).includes('650 m away'));
assert.ok(labelText(cardTree.root).includes('4.6'));
assert.ok(labelText(cardTree.root).includes('New candidate lead'));

await click(cardTree, 'Add as prospect');
assert.equal(apiCalls.length, 1);
assert.equal(apiCalls[0].endpoint, '/v1/rm/poi/poi-pt-sejahtera/prospect');
assert.equal(apiCalls[0].body.confirm_not_customer, false);
assert.ok(apiCalls[0].body.request_key);
assert.ok(createdProspect);
assert.equal(createdProspect.id, 'prospect-from-poi-pt-sejahtera');

await act(async () => cardTree.unmount());
console.log('PASS PlaceCard: new lead displays metadata and adds prospect without override');

// 2. Test PlaceCard: Possible match requires confirmation and reason
apiCalls = [];
await act(async () => {
  cardTree = Renderer.create(
    React.createElement(PlaceCard, {
      place: samplePoiPossible
    }),
    options
  );
});

assert.ok(labelText(cardTree.root).includes('CV Mitra Abadi Mandiri'));
assert.ok(labelText(cardTree.root).includes('Possible existing match'));
assert.ok(labelText(cardTree.root).includes('CIF-10023'));

// "Add as prospect" button should be disabled initially for POSSIBLE_MATCH
const addBtn = cardTree.root.findAllByType('button').find(b => labelText(b).trim() === 'Add as prospect');
assert.ok(addBtn);
assert.equal(addBtn.props.disabled, true);

const checkbox = cardTree.root.findAllByType('input').find(i => i.props.type === 'checkbox');
assert.ok(checkbox);
await act(async () => {
  checkbox.props.onChange({target: {checked: true}});
});
// Still disabled because reason is empty
assert.equal(addBtn.props.disabled, true);

// Fill override reason
const reasonInput = cardTree.root.findAllByType('input').find(i => i.props.type === 'text');
await act(async () => {
  reasonInput.props.onChange({target: {value: 'Verified different trade registration and tax ID'}});
});
assert.equal(addBtn.props.disabled, false);

await click(cardTree, 'Add as prospect');
assert.equal(apiCalls.length, 1);
assert.equal(apiCalls[0].endpoint, '/v1/rm/poi/poi-mitra-abadi/prospect');
assert.equal(apiCalls[0].body.confirm_not_customer, true);
assert.equal(apiCalls[0].body.reason, 'Verified different trade registration and tax ID');

await act(async () => cardTree.unmount());
console.log('PASS PlaceCard: possible match enforces confirmation checkbox and audit reason');

// 3. Test PlaceCard: Match review submission
apiCalls = [];
await act(async () => {
  cardTree = Renderer.create(
    React.createElement(PlaceCard, {
      place: samplePoiPossible
    }),
    options
  );
});

await click(cardTree, 'Review match');
assert.ok(labelText(cardTree.root).includes('Record Match Audit Review'));

const textInputs = cardTree.root.findAllByType('input').filter(i => i.props.type === 'text');
const auditInput = textInputs.at(-1);
await act(async () => {
  auditInput.props.onChange({target: {value: 'Verified by credit manager'}});
});

await click(cardTree, 'Submit match decision');
assert.equal(apiCalls.length, 1);
assert.equal(apiCalls[0].endpoint, '/v1/rm/poi/poi-mitra-abadi/match-review');
assert.equal(apiCalls[0].body.decision, 'CONFIRM_EXISTING');
assert.equal(apiCalls[0].body.customer_id, 'cust-10023');
assert.equal(apiCalls[0].body.reason, 'Verified by credit manager');

await act(async () => cardTree.unmount());
console.log('PASS PlaceCard: review match records audit decision and links customer ID');

// 4. Test PlaceCard: Existing customer shows profile link and prevents duplicate prospect
await act(async () => {
  cardTree = Renderer.create(
    React.createElement(PlaceCard, {
      place: samplePoiExisting
    }),
    options
  );
});

assert.ok(labelText(cardTree.root).includes('Already a bank customer'));
const relLink = cardTree.root.findAllByType('a').find(a => a.props.href === '/relationships/party-dina');
assert.ok(relLink, 'Must link to /relationships/party-dina for existing customer with party ID');
const addProspectBtn = cardTree.root.findAllByType('button').find(b => labelText(b).trim() === 'Add as prospect');
assert.equal(addProspectBtn, undefined, 'Existing customer must not have Add as prospect action');

await act(async () => cardTree.unmount());
console.log('PASS PlaceCard: existing customer links to relationship and prohibits prospect addition');

// 5. GoogleTerritoryMap: honest missing-key notice, legend and usable area search
const GoogleTerritoryMap = load('components/rm/spatial/GoogleTerritoryMap.tsx').GoogleTerritoryMap;
let mapTree;
let searchedArea = null;
await act(async () => {
  mapTree = Renderer.create(
    React.createElement(GoogleTerritoryMap, {
      center: {lat: -6.250, lng: 106.981},
      radiusM: 1500,
      pins: [{id: 'a', lat: -6.24, lng: 106.99, title: 'A', color: '#285C3C', border: '#1A3D28'}],
      legend: [{key: 'READY', label: 'Ready to talk', color: '#285C3C', count: 1}, {key: 'NEW', label: 'New nearby', color: '#285D86', count: 2}],
      onSearchThisArea: (c, r) => { searchedArea = {c, r}; }
    }),
    options
  );
});
assert.ok(labelText(mapTree.root).includes('Google Maps is not configured (set GOOGLE_MAPS_BROWSER_KEY)'));
assert.ok(labelText(mapTree.root).includes('Ready to talk 1'));
assert.ok(labelText(mapTree.root).includes('New nearby 2'));
assert.ok(labelText(mapTree.root).includes('1.5 km around the centre'));
await click(mapTree, 'Search this area');
assert.deepEqual(searchedArea, {c: {lat: -6.250, lng: 106.981}, r: 1500});
await act(async () => mapTree.unmount());
console.log('PASS GoogleTerritoryMap: honest missing-key message, legend counts and usable area search without a fake map');

// 6. Acquisition page: one list for assigned prospects and nearby businesses
const shared = load('components/rm/shared.tsx');
const linkedPoi = {...samplePoiNew, id: 'poi-linked', name: 'Linked Prospect Shop', match_status: 'PROSPECT', prospect_id: 'prospect-ready'};
sampleNearby.places = [samplePoiNew, samplePoiPossible, samplePoiExisting, linkedPoi];
const assigned = (id, extra = {}) => ({id, party: {id: 'party-' + id, name: id, kind: 'ORGANIZATION', locality: 'Bekasi', contacts: [], relationship: 'PROSPECT', identity: 'CONFIRMED', contact: 'ALLOWED'}, source: {id: 'src-' + id}, state: 'ASSIGNED', disposition: null, need: 'Collections help', need_reviewed: false, reasons: ['Opt-in enquiry'], latitude: -6.251, longitude: 106.982, version: 1, map_mode: 'SIMULATED', priority_tier: 'REVIEW_FIRST', priority_reason: 'Permitted', next_action: 'Review', priority_method: 'ACQ-1', hot_lead: false, hot_reason: '', ...extra});
const assignedRows = [assigned('prospect-review'), assigned('prospect-ready', {priority_tier: 'READY_FOR_DISCUSSION', hot_lead: true}), assigned('prospect-far', {latitude: -6.9, longitude: 107.6})];
let pageMap, pageBrief, pagePlace;
overrides.set('@/components/rm/shared', {...shared, useRM: () => ({data: {prospects: assignedRows, map_label: '', priority_method: 'ACQ-1'}, error: '', refresh: async () => {}, pending: false})});
overrides.set('@/components/rm/spatial/GoogleTerritoryMap', {GoogleTerritoryMap: props => { pageMap = props; return null; }});
overrides.set('@/components/rm/spatial/ProspectBrief', {ProspectBrief: props => { pageBrief = props; return React.createElement('div', null, 'Brief ' + props.p.id); }});
overrides.set('@/components/rm/spatial/PlaceCard', {PlaceCard: props => { pagePlace = props; return React.createElement('div', null, 'Place ' + props.place.id); }});
const Acquisition = load('app/(workspace)/acquisition/page.tsx').default;
const pins = () => Array.from(pageMap.pins, p => p.id);
const chip = async (tree, title) => {
  const found = tree.root.findAllByType('button').find(n => labelText(n).startsWith(title));
  assert.ok(found, `Missing chip ${title}`);
  await act(async () => found.props.onClick());
};
let acqTree;
apiCalls = [];
await act(async () => { acqTree = Renderer.create(React.createElement(Acquisition), options); });
assert.equal(locationRequests, 0, 'Location is requested only on an explicit click');
assert.ok(apiCalls.some(c => c.endpoint.includes('/v1/rm/poi/nearby?lat=-6.25&lng=106.981&radius_m=5000&include_existing=true')));
assert.ok(!labelText(acqTree.root).includes('Nearby businesses'), 'No separate assigned/nearby modes');
assert.deepEqual(pins(), ['prospect-ready', 'prospect-review', 'place:poi-mitra-abadi', 'place:poi-pt-sejahtera'], 'Ready, then checks, then new businesses; linked place deduplicated; existing customer held back');
assert.equal(pageBrief.p.id, 'prospect-ready');
assert.ok(labelText(acqTree.root).includes('1 assigned prospect outside this area.'));
assert.ok(labelText(acqTree.root).includes('Show 1 not for now'));
await act(async () => pageMap.onSelect('place:poi-pt-sejahtera'));
assert.equal(pagePlace.place.id, 'poi-pt-sejahtera');
await chip(acqTree, 'Not for now');
assert.deepEqual(pins(), ['place:poi-dina-boutique']);
await chip(acqTree, 'All');
await click(acqTree, 'Show all my prospects');
assert.ok(pins().includes('prospect-far'));
const geocodeInput = acqTree.root.findAllByType('input').find(i => i.props['aria-label'] === 'Search an address or area');
await act(async () => geocodeInput.props.onChange({target: {value: 'Summarecon Mall'}}));
await act(async () => acqTree.root.findByType('form').props.onSubmit({preventDefault() {}}));
assert.ok(apiCalls.some(c => c.endpoint.includes('/v1/rm/poi/geocode?q=Summarecon%20Mall')));
assert.ok(apiCalls.some(c => c.endpoint.includes('/v1/rm/poi/nearby?lat=-6.225&lng=106.999')));
assert.ok(labelText(acqTree.root).includes('Summarecon Mall Bekasi'));
await act(async () => acqTree.unmount());
console.log('PASS Acquisition: one grouped list for prospects and nearby businesses, dedupe, held-back customers and area search');
