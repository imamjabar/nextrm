export type RMPosition = {
  latitude: number; longitude: number; mode: 'DEMO' | 'DEVICE';
  label: string; accuracy?: number;
};
export const DEMO_OFFICE: RMPosition = {latitude: -6.250, longitude: 106.981, mode: 'DEMO', label: 'Bekasi demo office'};
export function distanceKm(a: {latitude:number;longitude:number}, b: {latitude:number;longitude:number}) {
  const radians = Math.PI / 180;
  const lat = (b.latitude - a.latitude) * radians, lng = (b.longitude - a.longitude) * radians;
  const h = Math.sin(lat / 2) ** 2 + Math.cos(a.latitude * radians) * Math.cos(b.latitude * radians) * Math.sin(lng / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0, 1-h)));
}
export function distanceLabel(km: number) {
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`;
}
