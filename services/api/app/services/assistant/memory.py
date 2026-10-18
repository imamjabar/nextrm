import re
from datetime import timedelta
from ...models.entities import utc_now
from ...models.relationships import Turn, SessionTurn, ChatSession
from .engine import redact_message

TOPIC_VOCABULARY = [
    ('transport', ('transport', 'transportation', 'commute', 'ojek', 'taxi', 'fuel', 'bensin', 'toll', 'parking')),
    ('Gojek', ('gojek', 'gocar', 'goride')),
    ('Grab', ('grab', 'grabcar', 'grabbike')),
    ('Shopee', ('shopee',)),
    ('Tokopedia', ('tokopedia',)),
    ('Spotify', ('spotify',)),
    ('Netflix', ('netflix',)),
    ('IndiHome', ('indihome',)),
    ('electricity', ('pln', 'electricity', 'listrik')),
    ('groceries', ('groceries', 'grocery', 'supermarket', 'belanja')),
    ('dining', ('dining', 'restaurant', 'cafe', 'eating out')),
    ('school fees', ('school', 'tuition', 'sekolah')),
    ('credit card', ('credit card', 'kartu kredit')),
    ('debt', ('debt', 'pinjaman', 'cicilan', 'hutang')),
    ('emergency fund', ('emergency fund', 'dana darurat', 'buffer')),
    ('goals', ('goal', 'goals')),
    ('savings', ('savings', 'saving', 'tabungan')),
    ('time deposit', ('deposit', 'deposito')),
    ('investments', ('investment', 'investments', 'investasi', 'portfolio', 'reksadana', 'mutual fund', 'saham', 'stocks')),
    ('salary', ('salary', 'gaji', 'payday')),
    ('subscriptions', ('subscription', 'subscriptions', 'langganan')),
    ('bills', ('bill', 'bills', 'tagihan', 'utilities')),
    ('budget', ('budget', 'budgeting', 'anggaran')),
]
PATTERNS = [(label, re.compile(r'\b(?:' + '|'.join(re.escape(k) for k in keys) + r')\b', re.I)) for label, keys in TOPIC_VOCABULARY]
EMPTY = {'topics': [], 'items': []}


def topics_in(text: str) -> list[str]:
    found = sorted((m.start(), label) for label, pattern in PATTERNS if (m := pattern.search(text)))
    return [label for _, label in found]

def follow_up_anchor(message: str, memory: dict) -> dict | None:
    """A short topicless follow-up in a new chat continues the customer's latest earlier question that had a topic."""
    if topics_in(message) or len(message.split()) > 7:
        return None
    topical = [item for item in memory['items'] if topics_in(item['message'])]
    if not topical:
        return None
    same = [item['message'] for item in topical if item['session_id'] == topical[0]['session_id']][:2]
    return {'message': ' '.join(same), 'route': topical[0]['route']}



def chat_memory(db, user, party_id: str, exclude_session_id: str | None = None, limit: int = 6, days: int = 30) -> dict:
    """The customer's own recent questions from other chats, for continuity only. Answers and figures are never carried over."""
    turns = (db.query(Turn).filter(Turn.tenant_id == user.tenant_id, Turn.party_id == party_id, Turn.actor_id == user.user_id,
                                   Turn.status == 'COMPLETED', Turn.created_at >= utc_now() - timedelta(days=days))
             .order_by(Turn.created_at.desc(), Turn.id.desc()).limit(60).all())
    if not turns:
        return EMPTY
    linked = dict(db.query(SessionTurn.id, SessionTurn.session_id).filter(SessionTurn.tenant_id == user.tenant_id, SessionTurn.id.in_([t.id for t in turns])).all())
    sessions = {s.id: s for s in db.query(ChatSession).filter(ChatSession.tenant_id == user.tenant_id, ChatSession.party_id == party_id,
                                                               ChatSession.actor_id == user.user_id).all()}
    items = []
    for t in turns:
        sid = linked.get(t.id) or 'LEGACY-' + t.conversation_id
        session = sessions.get(sid)
        if sid == exclude_session_id or (session and session.archived) or (not session and not sid.startswith('LEGACY-')):
            continue
        items.append({'session_id': sid, 'title': session.title if session else 'Earlier conversation', 'date': t.created_at.date().isoformat(), 'message': redact_message(t.message)[:160], 'route': t.route or ''})
        if len(items) == limit:
            break
    recent = list(dict.fromkeys(x for item in items for x in topics_in(item['message'])))[:6]
    in_order = list(dict.fromkeys(x for item in reversed(items) for x in topics_in(item['message']) if x in recent))
    return {'topics': in_order, 'items': items}
