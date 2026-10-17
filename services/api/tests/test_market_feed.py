from datetime import datetime, timezone, timedelta
from app.core.database import SessionLocal
from app.services.market_feed import (
    WIB,
    determine_session,
    fetch_market_snapshot,
    format_market_note,
    sync_market_note_to_db,
)


def test_market_open_and_close_session_notes_contain_targeted_guidance():
    # Test Market Open session
    open_snap = fetch_market_snapshot(session='open')
    assert open_snap['session'] == 'OPEN'
    assert '7,650' in open_snap['expected_open']
    assert 'MSCI' in open_snap['sentiment']
    open_note = format_market_note(open_snap)
    assert 'Market Open Note' in open_note
    assert 'Indonesian equities (IHSG)' in open_note
    assert 'cautious open' in open_note
    assert 'suitability review with an advisor' in open_note

    # Test Market Close session
    close_snap = fetch_market_snapshot(session='close')
    assert close_snap['session'] == 'CLOSE'
    assert close_snap['change'] == '-3.4%'
    assert 'MSCI' in close_snap['sentiment']
    close_note = format_market_note(close_snap)
    assert 'Market note' in close_note
    assert 'Indonesian equities (IHSG) fell -3.4%' in close_note
    assert 'crystallizes a paper loss' in close_note
    assert 'suitability review with an advisor' in close_note


def test_determine_session_by_time():
    morning = datetime(2026, 10, 18, 9, 30, tzinfo=WIB)
    afternoon = datetime(2026, 10, 18, 16, 15, tzinfo=WIB)
    assert determine_session(morning) == 'OPEN'
    assert determine_session(afternoon) == 'CLOSE'

def test_sync_market_note_to_db_upserts_and_bumps_version():
    with SessionLocal() as db:
        source = sync_market_note_to_db(db, tenant_id='demo-bank')
        assert source.id.endswith('KB-market_moves')
        assert 'MSCI' in source.content
        v1 = source.version or 1
        h1 = source.content_hash

        # Idempotent call with same data
        source_same = sync_market_note_to_db(db, tenant_id='demo-bank')
        assert source_same.version == v1
        assert source_same.content_hash == h1

        # Updated sentiment bumps version
        updated_snapshot = fetch_market_snapshot()
        updated_snapshot['sentiment'] = 'global tech sector rally and domestic consumer strength'
        updated_source = sync_market_note_to_db(db, tenant_id='demo-bank', snapshot=updated_snapshot)
        assert updated_source.version == v1 + 1
        assert updated_source.content_hash != h1
        assert 'consumer strength' in updated_source.content

        # Restore original
        restored = sync_market_note_to_db(db, tenant_id='demo-bank')
        assert 'MSCI' in restored.content
