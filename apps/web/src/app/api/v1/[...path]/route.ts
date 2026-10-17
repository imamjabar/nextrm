import { NextRequest, NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
async function proxy(req: NextRequest, { params }: { params: { path: string[] } }) {
  const segments = params.path;
  if(req.method==='POST' && Number(req.headers.get('content-length')||0)>16384)return NextResponse.json({detail:'Request too large'},{status:413});
  const allowed = new Set(['rm', 'auth']);
  if (!allowed.has(segments[0]) || segments.some(p => !/^[a-zA-Z0-9_-]+$/.test(p))) return NextResponse.json({ detail: 'Unsupported route' }, { status: 404 });
  const base = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';
  const headers = new Headers({ 'Content-Type': 'application/json' });
  for (const key of ['Authorization', 'X-Tenant-Id']) { const v = req.headers.get(key); if (v) headers.set(key, v); }
  const demo = process.env.NEXTRM_DEMO_MODE === 'true';
  if (demo) { const v = req.headers.get('X-User-Id'); if (v) headers.set('X-User-Id', v); }
  if (process.env.K_SERVICE) {
    const token = await fetch(`http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(base)}`, { headers: { 'Metadata-Flavor': 'Google' }, cache: 'no-store' });
    if (!token.ok) return NextResponse.json({ detail: 'Service authentication unavailable' }, { status: 503 });
    headers.set('X-Serverless-Authorization', `Bearer ${await token.text()}`);
  }
  try {
    const response = await fetch(`${base}/v1/${segments.join('/')}${req.nextUrl.search}`, { method: req.method, headers, body: ['GET','HEAD'].includes(req.method) ? undefined : await req.text(), cache: 'no-store', redirect: 'error' });
    return new NextResponse(await response.text(), { status: response.status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
  } catch { return NextResponse.json({ detail: 'API unavailable. Your action has not been confirmed; check operation status before retrying.' }, { status: 503 }); }
}
export { proxy as GET, proxy as POST };
