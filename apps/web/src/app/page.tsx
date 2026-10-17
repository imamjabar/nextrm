import {redirect} from 'next/navigation';

export const dynamic = 'force-dynamic';

export default function RootPage() {
  if (process.env.NEXTRM_DEMO_MODE === 'true') {
    redirect('/demo');
  }
  redirect('/login');
}
