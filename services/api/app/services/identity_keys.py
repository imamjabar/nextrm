"""Normalization and hashing for identifiers used in customer matching.

Raw identifiers (phone, NPWP, NIK, email) are never persisted. Every stored key is
sha256(tenant_id + ':' + kind + ':' + normalized value), so matches are only possible inside one tenant.
"""
import hashlib
import re
import unicodedata

LEGAL_FORMS = {'pt', 'cv', 'ud', 'tbk', 'persero', 'koperasi', 'fa', 'firma', 'toko', 'pd', 'yayasan'}


def normalize_name(name: str) -> str:
    text = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().casefold()
    tokens = re.findall(r'[a-z0-9]+', text)
    return ' '.join(t for t in tokens if t not in LEGAL_FORMS)


def normalize_phone(phone: str) -> str | None:
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('0'):
        digits = '62' + digits[1:]
    elif digits.startswith('8'):
        digits = '62' + digits
    return digits if digits.startswith('62') and 9 <= len(digits) <= 15 else None


def normalize_npwp(npwp: str) -> str | None:
    digits = re.sub(r'\D', '', npwp or '')
    return digits if len(digits) in (15, 16) else None


def normalize_email(email: str) -> str | None:
    value = (email or '').strip().casefold()
    return value if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value) else None


def identifier_hash(tenant_id: str, kind: str, normalized: str | None) -> str | None:
    if not normalized:
        return None
    return hashlib.sha256(f'{tenant_id}:{kind}:{normalized}'.encode()).hexdigest()


def phone_hash(tenant_id: str, phone: str) -> str | None:
    return identifier_hash(tenant_id, 'phone', normalize_phone(phone))


def npwp_hash(tenant_id: str, npwp: str) -> str | None:
    return identifier_hash(tenant_id, 'npwp', normalize_npwp(npwp))


def email_hash(tenant_id: str, email: str) -> str | None:
    return identifier_hash(tenant_id, 'email', normalize_email(email))


def mask_phone(phone: str) -> str | None:
    normalized = normalize_phone(phone)
    return '+' + normalized[:4] + '••••' + normalized[-3:] if normalized else None
