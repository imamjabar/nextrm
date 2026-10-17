import difflib
import json
import math
from decimal import Decimal
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..models.banking import BankCustomer, PoiPlace
from ..models.entities import utc_now
from .identity_keys import (
    normalize_name,
    phone_hash,
    npwp_hash,
    email_hash,
)


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def match_place(
    db: Session,
    tenant_id: str,
    *,
    name: str,
    phone: str | None = None,
    npwp: str | None = None,
    email: str | None = None,
    latitude: float | Decimal | str | None = None,
    longitude: float | Decimal | str | None = None,
    address: str | None = None,
    phone_hash_override: str | None = None
) -> dict:
    target_phone_hash = phone_hash_override if phone_hash_override else (phone_hash(tenant_id, phone) if phone else None)
    target_npwp_hash = npwp_hash(tenant_id, npwp) if npwp else None
    target_email_hash = email_hash(tenant_id, email) if email else None

    hash_queries = []
    if target_phone_hash:
        hash_queries.append(BankCustomer.phone_hash == target_phone_hash)
    if target_npwp_hash:
        hash_queries.append(BankCustomer.npwp_hash == target_npwp_hash)
    if target_email_hash:
        hash_queries.append(BankCustomer.email_hash == target_email_hash)

    if hash_queries:
        matched_records = db.query(BankCustomer).filter(
            BankCustomer.tenant_id == tenant_id,
            or_(*hash_queries)
        ).all()

        distinct_candidates = {c.id: c for c in matched_records}
        if len(distinct_candidates) == 1:
            c = next(iter(distinct_candidates.values()))
            reasons = []
            if target_phone_hash and c.phone_hash == target_phone_hash:
                reasons.append("Exact phone match with existing bank customer.")
            if target_npwp_hash and c.npwp_hash == target_npwp_hash:
                reasons.append("Exact NPWP match with existing bank customer.")
            if target_email_hash and c.email_hash == target_email_hash:
                reasons.append("Exact email match with existing bank customer.")
            return {
                "status": "EXISTING_CUSTOMER",
                "customer_id": c.id,
                "score": Decimal("1.000"),
                "reasons": reasons or ["Exact identifier match with existing bank customer."]
            }
        elif len(distinct_candidates) >= 2:
            candidates_list = list(distinct_candidates.values())
            cifs = ", ".join(c.cif for c in candidates_list)
            return {
                "status": "POSSIBLE_MATCH",
                "customer_id": None,
                "score": Decimal("1.000"),
                "reasons": [f"Multiple candidate bank customers matched ({cifs}). Requires RM review."]
            }

    target_norm = normalize_name(name)
    if not target_norm:
        return {
            "status": "NO_MATCH_IN_AVAILABLE_DATA",
            "customer_id": None,
            "score": Decimal("0.000"),
            "reasons": ["No identifier or name provided for matching."]
        }

    customers = db.query(BankCustomer).filter_by(tenant_id=tenant_id).all()
    candidates = []

    for c in customers:
        cust_norm = c.normalized_name or normalize_name(c.full_name)
        if not cust_norm:
            continue

        dist_m = None
        within_300m = False
        if latitude is not None and longitude is not None and c.latitude is not None and c.longitude is not None:
            try:
                lat_c = float(c.latitude)
                lng_c = float(c.longitude)
                lat_t = float(latitude)
                lng_t = float(longitude)
                if abs(lat_c - lat_t) <= 0.0035 and abs(lng_c - lng_t) <= 0.0035:
                    dist_m = haversine_distance(lat_t, lng_t, lat_c, lng_c)
                    within_300m = (dist_m <= 300.0)
            except (ValueError, TypeError):
                dist_m = None

        cust_city = (c.city or '').strip().casefold()
        addr = (address or '').strip().casefold()
        same_city = bool(cust_city and (cust_city in addr or addr in cust_city))

        if not within_300m and not same_city:
            continue

        exact_name = (target_norm == cust_norm)
        if exact_name:
            seq_ratio = 1.0
            strong_name = True
        else:
            if not within_300m:
                continue
            target_tokens = set(target_norm.split())
            cust_tokens = set(cust_norm.split())
            common_tokens = target_tokens & cust_tokens
            overlap = len(common_tokens) / max(len(target_tokens | cust_tokens), 1)
            seq_ratio = difflib.SequenceMatcher(None, target_norm, cust_norm).ratio()
            strong_name = (seq_ratio >= 0.85) or (seq_ratio >= 0.70 and overlap >= 0.60)
            if not strong_name:
                continue

        if within_300m:
            reason = f"Strong name similarity ({int(seq_ratio * 100)}%) and within {int(dist_m)}m of existing customer {c.cif}."
        else:
            reason = f"Exact normalized name match in same city ({c.city}) with existing customer {c.cif}."
        score = Decimal(f"{max(seq_ratio, 0.70):.3f}")
        candidates.append((c, score, reason))

    if not candidates:
        return {
            "status": "NO_MATCH_IN_AVAILABLE_DATA",
            "customer_id": None,
            "score": Decimal("0.000"),
            "reasons": ["No match found in available customer data."]
        }

    if len(candidates) == 1:
        c, score, reason = candidates[0]
        return {
            "status": "POSSIBLE_MATCH",
            "customer_id": c.id,
            "score": score,
            "reasons": [reason]
        }

    cifs = ", ".join(c.cif for c, _, _ in candidates)
    max_score = max(s for _, s, _ in candidates)
    reasons = [f"Multiple candidate customers found ({cifs}). Requires RM review."] + [r for _, _, r in candidates]
    return {
        "status": "POSSIBLE_MATCH",
        "customer_id": None,
        "score": max_score,
        "reasons": reasons
    }


def match_all_pois(db: Session, tenant_id: str) -> int:
    pois = db.query(PoiPlace).filter_by(tenant_id=tenant_id).all()
    count = 0
    for poi in pois:
        match = match_place(
            db,
            tenant_id,
            name=poi.name,
            latitude=poi.latitude,
            longitude=poi.longitude,
            address=poi.address,
            phone_hash_override=poi.phone_hash
        )
        poi.match_status = match["status"]
        poi.matched_customer_id = match["customer_id"]
        poi.match_score = match["score"]
        poi.match_reasons_json = json.dumps(match["reasons"])
        poi.matched_at = utc_now()
        count += 1
    db.commit()
    return count
