import hashlib
import json
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser, get_current_user
from ..models.banking import PoiPlace, BankCustomer
from ..models.relationships import Party, Source, Prospect, ReviewEvent
from ..models.entities import utc_now
from ..schemas.rm import (
    RMPoiNearby,
    RMGeocode,
    RMProspect,
    RMPoiPlace,
    RMPoiCreateProspect,
    RMPoiMatchReview,
)
from ..services.poi_provider import get_poi_provider, format_poi_dto
from ..services.rm import require_rm, uid, j, review_event
from .rm import prospects_data

router = APIRouter(prefix="/v1/rm/poi", tags=["relationship-workspace"])


@router.get("/nearby", response_model=RMPoiNearby)
def poi_nearby(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(default=1500, ge=100, le=5000),
    type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    include_existing: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
):
    require_rm(user)
    provider = get_poi_provider()
    return provider.search_nearby(
        db,
        user,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        place_type=type,
        q=q,
        include_existing=include_existing,
        limit=limit
    )


@router.get("/geocode", response_model=RMGeocode)
def poi_geocode(
    q: str = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
):
    require_rm(user)
    provider = get_poi_provider()
    return provider.geocode(db, user, q=q)


@router.post("/{id}/prospect", response_model=RMProspect)
def create_poi_prospect(
    id: str,
    req: RMPoiCreateProspect,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
):
    require_rm(user)
    poi = db.query(PoiPlace).filter_by(id=id, tenant_id=user.tenant_id).first()
    if not poi:
        raise HTTPException(404, "POI place not found.")

    if poi.prospect_id:
        prosp = db.query(Prospect).filter_by(id=poi.prospect_id, tenant_id=user.tenant_id).first()
        if prosp:
            return prospects_data(db, [prosp])[0]

    existing_prospect = db.query(Prospect).filter_by(
        tenant_id=user.tenant_id,
        import_key=f"poi:{poi.id}"
    ).first()
    if existing_prospect:
        poi.prospect_id = existing_prospect.id
        db.commit()
        return prospects_data(db, [existing_prospect])[0]

    if poi.match_status == "EXISTING_CUSTOMER":
        raise HTTPException(409, "Cannot create prospect for verified existing customer.")

    if poi.match_status == "POSSIBLE_MATCH":
        if not req.confirm_not_customer:
            raise HTTPException(400, "Possible existing customer match requires explicit confirmation (confirm_not_customer=True).")
        if not req.reason or len(req.reason.strip()) < 3:
            raise HTTPException(400, "Reason is required when overriding possible customer match.")
        review_event(
            db,
            user,
            poi.id,
            "POSSIBLE_MATCH_OVERRIDE",
            req.reason.strip(),
            {"match_status": poi.match_status, "request_key": req.request_key},
            {"confirm_not_customer": True, "request_key": req.request_key}
        )

    party_id = uid("PARTY")
    party_ctx = {
        "mode": "SIMULATED" if poi.provider == "SYNTHETIC_DATASET" else "LIVE",
        "products": [],
        "declared_goal": "",
        "notes": "",
        "contact_channel": "IN_APP",
        "contact_purpose": "Permission not confirmed"
    }
    party = Party(
        id=party_id,
        tenant_id=user.tenant_id,
        kind="ORGANIZATION",
        name=poi.name,
        segment="BUSINESS",
        owner_id=user.user_id,
        relationship="NO_MATCH_IN_AVAILABLE_DATA",
        identity="UNRESOLVED",
        contact="REQUIRES_CONFIRMATION",
        locality=poi.address or "Local",
        customer_ref=None,
        context_json=j(party_ctx)
    )
    db.add(party)
    db.flush()

    source_id = uid("SOURCE")
    source_content = j({
        "name": poi.name,
        "primary_type": poi.primary_type,
        "address": poi.address,
        "attribution": poi.attribution,
        "provider": poi.provider,
        "rating": str(poi.rating) if poi.rating is not None else None,
        "website": poi.website
    })
    source = Source(
        id=source_id,
        tenant_id=user.tenant_id,
        party_id=party.id,
        kind="POI_LISTING",
        title=f"POI listing · {poi.name}",
        content=source_content,
        content_hash=hashlib.sha256(source_content.encode()).hexdigest(),
        mode="SIMULATED" if poi.provider == "SYNTHETIC_DATASET" else "LIVE"
    )
    db.add(source)
    db.flush()

    prospect_id = uid("PROSPECT")
    reasons = [
        f"Listing type: {poi.primary_type}",
        f"Address: {poi.address}",
        f"Source attribution: {poi.attribution}",
        "Public listing only; contact and identity unconfirmed."
    ]
    prospect = Prospect(
        id=prospect_id,
        tenant_id=user.tenant_id,
        party_id=party.id,
        source_id=source.id,
        owner_id=user.user_id,
        latitude=poi.latitude,
        longitude=poi.longitude,
        need="Not yet confirmed: business listing only; discuss needs with an authorized contact.",
        need_reviewed=False,
        reasons_json=j(reasons),
        import_key=f"poi:{poi.id}"
    )
    db.add(prospect)
    db.flush()

    poi.prospect_id = prospect.id
    db.commit()

    return prospects_data(db, [prospect])[0]


@router.post("/{id}/match-review", response_model=RMPoiPlace)
def review_poi_match(
    id: str,
    req: RMPoiMatchReview,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user)
):
    require_rm(user)
    poi = db.query(PoiPlace).filter_by(id=id, tenant_id=user.tenant_id).first()
    if not poi:
        raise HTTPException(404, "POI place not found.")

    prior = db.query(ReviewEvent).filter_by(
        tenant_id=user.tenant_id,
        resource_id=poi.id,
        action="POI_MATCH_REVIEW"
    ).all()
    for ev in prior:
        try:
            after_data = json.loads(ev.after_json)
            if after_data.get("request_key") == req.request_key:
                return format_poi_dto(db, user, poi, 0)
        except Exception:
            pass

    before_state = {
        "match_status": poi.match_status,
        "matched_customer_id": poi.matched_customer_id,
        "match_score": str(poi.match_score) if poi.match_score is not None else None
    }

    reasons = json.loads(poi.match_reasons_json or "[]")
    if req.decision == "CONFIRM_EXISTING":
        poi.match_status = "EXISTING_CUSTOMER"
        poi.match_score = Decimal("1.000")
        if req.customer_id:
            cust = db.query(BankCustomer).filter_by(id=req.customer_id, tenant_id=user.tenant_id).first()
            if not cust:
                raise HTTPException(404, "Bank customer not found in this institution.")
            poi.matched_customer_id = cust.id
        if poi.prospect_id:
            prospect = db.query(Prospect).filter_by(id=poi.prospect_id, tenant_id=user.tenant_id).first()
            if prospect:
                prospect.disposition = "EXISTING_CUSTOMER"
                prospect.version += 1
        reasons.append(f"RM confirmed existing customer: {req.reason}")
    else:
        poi.match_status = "NO_MATCH_IN_AVAILABLE_DATA"
        poi.matched_customer_id = None
        poi.match_score = Decimal("0.000")
        reasons.append(f"RM confirmed not a customer: {req.reason}")

    poi.match_reasons_json = j(reasons)
    poi.matched_at = utc_now()

    after_state = {
        "match_status": poi.match_status,
        "matched_customer_id": poi.matched_customer_id,
        "match_score": str(poi.match_score) if poi.match_score is not None else None,
        "request_key": req.request_key
    }

    review_event(db, user, poi.id, "POI_MATCH_REVIEW", req.reason, before_state, after_state)
    db.commit()

    return format_poi_dto(db, user, poi, 0)
