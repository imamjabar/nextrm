from datetime import datetime, timezone, timedelta
import hashlib
import logging
from typing import Literal, Optional

from ..models.relationships import Source
from .rm_seed import sid

logger = logging.getLogger(__name__)

WIB = timezone(timedelta(hours=7))

OPEN_MARKET_SNAPSHOT = {
    'session': 'OPEN',
    'as_of': '18 Oct 2026, 09:00 WIB',
    'index_name': 'Indonesian equities (IHSG)',
    'expected_open': 'cautious open around 7,650 level',
    'sentiment': 'regional Asian risk aversion and foreign capital repositioning ahead of MSCI index review',
    'macro_drivers': 'US Treasury yields steady and USD/IDR hovering near 15,620',
    'guidance': 'Opening market movements reflect short-term liquidity repositioning. Long-term investment goals and emergency buffers should guide portfolio strategy rather than opening bell volatility.',
}

CLOSE_MARKET_SNAPSHOT = {
    'session': 'CLOSE',
    'as_of': '18 Oct 2026, 16:00 WIB',
    'index_name': 'Indonesian equities (IHSG)',
    'change': '-3.4%',
    'period': 'over five trading days',
    'sentiment': 'foreign capital outflows following MSCI index rebalancing sentiment and global risk aversion',
    'yields': 'short-term money market yields were little changed',
    'closing_summary': 'IHSG closed lower alongside regional indices, pressured by foreign net selling in banking and large-cap leaders.',
    'guidance': 'A decline of this size is common for equity index funds; selling after a drop crystallizes a paper loss. Personal investment decisions require a suitability review with an advisor.',
}

OPEN_NOTE_TEMPLATE = (
    "Market Open Note, {as_of}: {index_name} is positioned for a {expected_open} amid {sentiment}. "
    "Macro context: {macro_drivers}. "
    "{guidance} "
    "A personal decision about buying, selling, or rebalancing needs the bank's suitability review with an advisor."
)

CLOSE_NOTE_TEMPLATE = (
    "Equity funds rise and fall, and a decline of several percent over a month is common; it does not by itself mean a fund is broken. "
    "What matters for any decision is the goal the money is for, how soon it is needed, whether essential spending is covered by cash, "
    "and how large the holding is relative to everything else. Selling after a fall turns a paper loss into a realized one, and trying to "
    "time the market is unreliable. These are general facts, not a recommendation. "
    "Market note, {as_of}: {index_name} fell {change} {period} amid {sentiment}, while {yields}. "
    "{closing_summary} {guidance}"
)


def determine_session(now: Optional[datetime] = None) -> Literal['OPEN', 'CLOSE']:
    t = now or datetime.now(WIB)
    return 'OPEN' if t.hour < 13 else 'CLOSE'


def fetch_market_snapshot(session: str = 'auto') -> dict:
    actual = determine_session() if session == 'auto' else session.upper()
    return dict(OPEN_MARKET_SNAPSHOT if actual == 'OPEN' else CLOSE_MARKET_SNAPSHOT)


def format_market_note(snapshot: dict) -> str:
    session = snapshot.get('session', 'CLOSE')
    if session == 'OPEN':
        merged = {**OPEN_MARKET_SNAPSHOT, **snapshot}
        return OPEN_NOTE_TEMPLATE.format(**merged)
    merged = {**CLOSE_MARKET_SNAPSHOT, **snapshot}
    return CLOSE_NOTE_TEMPLATE.format(**merged)


def sync_market_note_to_db(db, tenant_id: str = 'demo-bank', session: str = 'auto', snapshot: Optional[dict] = None) -> Source:
    data = snapshot or fetch_market_snapshot(session)
    actual_session = data.get('session') or (determine_session() if session == 'auto' else session.upper())
    data['session'] = actual_session
    content = format_market_note(data)
    digest = hashlib.sha256(content.encode()).hexdigest()
    source_id = sid(tenant_id, 'KB-market_moves')
    title = f"Falling markets · Bank market note ({data.get('as_of', '18 Oct 2026')})"

    source = db.get(Source, source_id)
    if not source:
        source = Source(
            id=source_id,
            tenant_id=tenant_id,
            kind='APPROVED_KNOWLEDGE',
            title=title,
            content=content,
            content_hash=digest,
            mode='SIMULATED',
            version=1,
        )
        db.add(source)
    else:
        if source.content_hash != digest:
            source.title = title
            source.content = content
            source.content_hash = digest
            source.version = (source.version or 1) + 1
    db.commit()
    db.refresh(source)
    return source
