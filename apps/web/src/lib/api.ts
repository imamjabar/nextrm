export interface UserContext { userId: string; tenantId: string; role?: string; idToken?: string; }
export const defaultUserContext: UserContext = { userId: '', tenantId: '' };
let activeContext: UserContext = defaultUserContext;
let tokenProvider: (() => Promise<string | undefined>) | undefined;
export function setTokenProvider(provider: typeof tokenProvider) { tokenProvider=provider; }
const listeners = new Set<() => void>();
export function getUserContext() { return activeContext; }
export function subscribeSession(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function setUserContext(ctx: UserContext) { activeContext = ctx; clearApiCache(); listeners.forEach(fn => fn()); }
const activeReads = new Map<string, Promise<unknown>>();
const apiCache = new Map<string, { data: unknown; timestamp: number }>();
let mutationEpoch = 0;
export function getMutationEpoch() { return mutationEpoch; }
export function getApiCacheSize() { return apiCache.size; }
export function clearApiCache(prefix?: string) {
  mutationEpoch++;
  activeReads.clear();
  for (const key of Array.from(apiCache.keys())) if (!prefix || key.includes(prefix)) apiCache.delete(key);
}
export async function fetchApi<T>(endpoint: string, options: RequestInit = {}, ctx: UserContext = activeContext): Promise<T> {
  if (!endpoint.startsWith('/v1/') || endpoint.includes('..')) throw new Error('Unsupported API path');
  const method = (options.method || 'GET').toUpperCase();
  const key = `${method}:${endpoint}:${ctx.userId}:${ctx.tenantId}`;
  // Credentialed reads are revalidated; never retain tokens in cache keys or credential-dependent results.
  const cacheable = method === 'GET' && !ctx.idToken && options.cache !== 'no-store';
  const cached = apiCache.get(key);
  if (cacheable && cached && Date.now() - cached.timestamp < 5000) return cached.data as T;
  const epoch = mutationEpoch;
  // Only share concurrent development reads for the exact active identity/epoch.
  // Credentialed/explicit-context/header/cancellable reads are always independent.
  const shareable = method === 'GET' && !ctx.idToken && ctx === activeContext && !options.headers && !options.signal && !options.body;
  const readKey = `${key}:${epoch}`;
  if (shareable && activeReads.has(readKey)) return activeReads.get(readKey) as Promise<T>;
  const perform = async ():Promise<T> => {
  const headers = new Headers(options.headers);
  for (const name of ['authorization', 'x-user-id', 'x-tenant-id', 'x-serverless-authorization', 'cookie']) headers.delete(name);
  headers.set('Content-Type', 'application/json');
  headers.set('X-Tenant-Id', ctx.tenantId);
  if (ctx.idToken) headers.set('Authorization', `Bearer ${(ctx===activeContext&&tokenProvider?await tokenProvider():undefined)||ctx.idToken}`);
  else headers.set('X-User-Id', ctx.userId);
  const res = await fetch(`/api${endpoint}`, { ...options, headers });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw Object.assign(new Error(typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail || `API request failed (${res.status})`)), {status: res.status});
  }
  const data = await res.json() as T;
  if (method !== 'GET') { clearApiCache(); listeners.forEach(fn => fn()); }
  else if (epoch !== mutationEpoch) throw new Error('The case or session changed while loading. Reload the current version.');
  else if (cacheable) {
    if (apiCache.size >= 100) apiCache.delete(apiCache.keys().next().value!);
    apiCache.set(key, { data, timestamp: Date.now() });
  }
  return data;
  };
  const request=perform();
  if(shareable){
    activeReads.set(readKey,request);
    request.then(()=>{if(activeReads.get(readKey)===request)activeReads.delete(readKey);},()=>{if(activeReads.get(readKey)===request)activeReads.delete(readKey);});
  }
  return request;
}
