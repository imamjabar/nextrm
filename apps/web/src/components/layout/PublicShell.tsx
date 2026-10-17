import {APP_NAME} from '@/config/brand';
import Link from 'next/link';
export function PublicShell({children}:{children:React.ReactNode}){return <div className="public-site"><a className="skip-link" href="#public-main">Skip to content</a><header className="public-header"><Link href="/" className="wordmark">{APP_NAME}</Link></header><main id="public-main">{children}</main></div>;}
