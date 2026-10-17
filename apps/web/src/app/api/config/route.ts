import { NextResponse } from 'next/server';
export const dynamic = 'force-dynamic';
export async function GET() { return NextResponse.json({ authProvider: process.env.NEXTRM_AUTH_PROVIDER || 'firebase', demoMode: process.env.NEXTRM_DEMO_MODE === 'true', firebaseApiKey: process.env.FIREBASE_WEB_API_KEY || null, firebaseAuthDomain:process.env.FIREBASE_AUTH_DOMAIN||null, firebaseProjectId:process.env.FIREBASE_PROJECT_ID||null, googleMapsApiKey: process.env.GOOGLE_MAPS_BROWSER_KEY || null, googleMapsMapId: process.env.GOOGLE_MAPS_MAP_ID || null }, { headers: { 'Cache-Control': 'no-store' } }); }
