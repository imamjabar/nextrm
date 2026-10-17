export function label(value: unknown): string {
 if(value === null || value === undefined || value === '') return 'Not available';
 if(value==='RM') return 'Relationship manager'; if(value==='P2P') return 'P2P';
 const text=String(value).replaceAll('_',' ').toLowerCase(); return text.charAt(0).toUpperCase()+text.slice(1);
}
export function money(value: unknown, currency='IDR'): string {
 if(value === null || value === undefined || value === '') return 'Not available';
 const m=String(value).match(/^(-?)(\d+)(?:\.(\d+))?$/); if(!m)return 'Not available';
 const fraction=(m[3]||'').replace(/0+$/,'');
 return `${currency} ${m[1]}${m[2].replace(/\B(?=(\d{3})+(?!\d))/g,',')}${fraction?'.'+fraction:''}`;
}
export function dateLabel(value: unknown): string {
 if(!value)return 'Not available'; const raw=String(value); const timestamp=/^\d{4}-\d{2}-\d{2}[ T]\d{2}:/.test(raw)&&!/(Z|[+-]\d{2}:?\d{2})$/.test(raw)?raw.replace(' ','T')+'Z':raw; const d=new Date(timestamp);
 return Number.isNaN(d.getTime())?'Not available':new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'Asia/Jakarta'}).format(d);
}
