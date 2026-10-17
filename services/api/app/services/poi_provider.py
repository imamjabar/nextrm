import math
import os
import json
import httpx
from datetime import timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ..models.banking import PoiPlace, BankCustomer
from ..models.relationships import Party
from ..models.entities import utc_now
from .identity_keys import phone_hash, mask_phone
from .customer_match import haversine_distance, match_place
from .rm import uid


SYNTHETIC_ATTRIBUTION = "Synthetic locality dataset · illustrative banking and business points of interest"
GOOGLE_ATTRIBUTION = "Google Places API · Google Maps Platform"

GAZETTEER = [
    {"label": "Kantor Cabang Bekasi (Demo Office) - Jl. Ahmad Yani No. 1, Bekasi", "latitude": "-6.238300", "longitude": "106.975600"},
    {"label": "Summarecon Mall Bekasi - Jl. Bulevar Ahmad Yani, Bekasi", "latitude": "-6.225500", "longitude": "106.999800"},
    {"label": "Grand Galaxy City - Jl. Boulevard Raya, Jaka Setia, Bekasi", "latitude": "-6.265700", "longitude": "106.974800"},
    {"label": "Harapan Indah - Medan Satria, Kota Bekasi", "latitude": "-6.183300", "longitude": "106.980600"},
    {"label": "Mega Bekasi Hypermall - Jl. Jend. Ahmad Yani No. 1, Bekasi", "latitude": "-6.248300", "longitude": "106.994200"},
    {"label": "Metropolitan Mall Bekasi - Jl. KH. Noer Ali, Pekayon Jaya, Bekasi", "latitude": "-6.248800", "longitude": "106.990400"},
    {"label": "Kawasan Industri MM2100 - Cikarang Barat, Bekasi", "latitude": "-6.300000", "longitude": "107.100000"},
    {"label": "Jababeka Industrial Estate - Cikarang, Bekasi", "latitude": "-6.312000", "longitude": "107.145000"},
    {"label": "SCBD Sudirman - Senayan, Kebayoran Baru, Jakarta Selatan", "latitude": "-6.225300", "longitude": "106.809800"},
    {"label": "Kuningan Epicentrum - Setiabudi, Jakarta Selatan", "latitude": "-6.218500", "longitude": "106.832200"},
    {"label": "Kelapa Gading Boulevard - Jakarta Utara", "latitude": "-6.158200", "longitude": "106.908000"},
    {"label": "Pondok Indah Mall - Kebayoran Lama, Jakarta Selatan", "latitude": "-6.265200", "longitude": "106.784200"},
]


def format_poi_dto(db: Session, user, poi: PoiPlace, distance_m: int) -> dict:
    matched_cust = None
    if poi.matched_customer_id:
        cust = db.query(BankCustomer).filter_by(id=poi.matched_customer_id, tenant_id=user.tenant_id).first()
        if cust:
            owner_rm = False
            if cust.party_id:
                p = db.query(Party).filter_by(id=cust.party_id, tenant_id=user.tenant_id).first()
                if p and p.owner_id == user.user_id:
                    owner_rm = True
            matched_cust = {
                "id": cust.id,
                "cif": cust.cif,
                "name": cust.full_name,
                "segment": cust.segment,
                "relationship_owner_rm": owner_rm
            }

    return {
        "id": poi.id,
        "name": poi.name,
        "primary_type": poi.primary_type,
        "address": poi.address,
        "latitude": str(poi.latitude),
        "longitude": str(poi.longitude),
        "distance_m": distance_m,
        "phone_masked": poi.phone_masked,
        "website": poi.website,
        "rating": float(poi.rating) if poi.rating is not None else None,
        "rating_count": poi.rating_count,
        "match_status": poi.match_status,
        "match_score": str(poi.match_score) if poi.match_score is not None else None,
        "match_reasons": json.loads(poi.match_reasons_json or "[]"),
        "matched_customer": matched_cust,
        "prospect_id": poi.prospect_id,
        "provider": poi.provider,
        "attribution": poi.attribution,
        "fetched_at": poi.fetched_at.isoformat() if poi.fetched_at else utc_now().isoformat()
    }


class SyntheticProvider:
    provider_name = "SYNTHETIC_DATASET"

    def search_nearby(
        self,
        db: Session,
        user,
        lat: float,
        lng: float,
        radius_m: int = 1500,
        place_type: str | None = None,
        q: str | None = None,
        include_existing: bool = False,
        limit: int = 50
    ) -> dict:
        lat_delta = radius_m / 111000.0
        cos_factor = max(math.cos(math.radians(lat)), 0.01)
        lng_delta = radius_m / (111000.0 * cos_factor)

        min_lat = Decimal(str(lat - lat_delta))
        max_lat = Decimal(str(lat + lat_delta))
        min_lng = Decimal(str(lng - lng_delta))
        max_lng = Decimal(str(lng + lng_delta))

        query = db.query(PoiPlace).filter(
            PoiPlace.tenant_id == user.tenant_id,
            PoiPlace.provider == "SYNTHETIC_DATASET",
            PoiPlace.latitude >= min_lat,
            PoiPlace.latitude <= max_lat,
            PoiPlace.longitude >= min_lng,
            PoiPlace.longitude <= max_lng,
        )

        candidates = query.all()

        matching_with_dist = []
        for p in candidates:
            dist = int(round(haversine_distance(lat, lng, p.latitude, p.longitude)))
            if dist > radius_m:
                continue
            if place_type and place_type.strip():
                pt = place_type.strip().casefold()
                if pt != p.primary_type.casefold() and pt not in p.primary_type.casefold():
                    continue
            if q and q.strip():
                qs = q.strip().casefold()
                if qs not in p.name.casefold() and qs not in p.address.casefold():
                    continue
            matching_with_dist.append((p, dist))

        existing_customer_count = 0
        possible_match_count = 0
        new_lead_count = 0
        prospect_count = 0

        for p, _ in matching_with_dist:
            if p.prospect_id:
                prospect_count += 1
            if p.match_status == "EXISTING_CUSTOMER":
                existing_customer_count += 1
            elif p.match_status == "POSSIBLE_MATCH":
                possible_match_count += 1
            else:
                if not p.prospect_id:
                    new_lead_count += 1

        counts = {
            "existing_customer": existing_customer_count,
            "possible_match": possible_match_count,
            "new_lead": new_lead_count,
            "prospect": prospect_count
        }

        if not include_existing:
            filtered = [(p, d) for p, d in matching_with_dist if p.match_status != "EXISTING_CUSTOMER"]
        else:
            filtered = matching_with_dist

        filtered.sort(key=lambda item: item[1])
        selected = filtered[:limit]

        places_dtos = [format_poi_dto(db, user, p, d) for p, d in selected]

        return {
            "provider": self.provider_name,
            "attribution": SYNTHETIC_ATTRIBUTION,
            "center": {"lat": lat, "lng": lng},
            "radius_m": radius_m,
            "places": places_dtos,
            "counts": counts
        }

    def geocode(self, db: Session, user, q: str) -> dict:
        results = []
        qs = q.strip().casefold()
        if len(qs) < 2:
            return {"provider": self.provider_name, "results": []}

        # Search seeded places
        pois = db.query(PoiPlace).filter(
            PoiPlace.tenant_id == user.tenant_id,
            PoiPlace.provider == "SYNTHETIC_DATASET"
        ).all()

        seen_labels = set()
        for p in pois:
            if qs in p.name.casefold() or qs in p.address.casefold():
                label = f"{p.name} - {p.address}"
                if label not in seen_labels:
                    seen_labels.add(label)
                    results.append({
                        "label": label,
                        "latitude": str(p.latitude),
                        "longitude": str(p.longitude)
                    })

        # Search gazetteer
        for g in GAZETTEER:
            if qs in g["label"].casefold():
                if g["label"] not in seen_labels:
                    seen_labels.add(g["label"])
                    results.append({
                        "label": g["label"],
                        "latitude": g["latitude"],
                        "longitude": g["longitude"]
                    })

        return {
            "provider": self.provider_name,
            "results": results[:10]
        }


class GooglePlacesProvider:
    provider_name = "GOOGLE_PLACES"

    def _get_api_key(self) -> str:
        key = os.getenv("GOOGLE_MAPS_SERVER_KEY")
        if not key or not key.strip():
            raise HTTPException(
                status_code=503,
                detail="Google Maps server key is not configured. Set GOOGLE_MAPS_SERVER_KEY in environment."
            )
        return key.strip()

    def search_nearby(
        self,
        db: Session,
        user,
        lat: float,
        lng: float,
        radius_m: int = 1500,
        place_type: str | None = None,
        q: str | None = None,
        include_existing: bool = False,
        limit: int = 50
    ) -> dict:
        api_key = self._get_api_key()

        # Purge expired rows first
        db.query(PoiPlace).filter(
            PoiPlace.tenant_id == user.tenant_id,
            PoiPlace.expires_at != None,
            PoiPlace.expires_at < utc_now()
        ).delete()
        db.flush()

        headers = {
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,places.location,"
                "places.primaryType,places.nationalPhoneNumber,places.internationalPhoneNumber,"
                "places.websiteUri,places.rating,places.userRatingCount"
            ),
            "Content-Type": "application/json"
        }

        if q and q.strip():
            url = "https://places.googleapis.com/v1/places:searchText"
            payload = {
                "textQuery": q.strip(),
                "maxResultCount": min(limit, 20),
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius_m)
                    }
                }
            }
        else:
            url = "https://places.googleapis.com/v1/places:searchNearby"
            payload = {
                "maxResultCount": min(limit, 20),
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius_m)
                    }
                }
            }
            if place_type and place_type.strip():
                payload["includedTypes"] = [place_type.strip()]

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Google Places API returned status {res.status_code}: {res.text}"
                    )
                data = res.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Google Places API request failed: {exc}")

        places_data = data.get("places", [])

        # Upsert and run match_place
        upserted_pois = []
        for pdata in places_data:
            prov_id = pdata.get("id")
            if not prov_id:
                continue

            poi = db.query(PoiPlace).filter_by(
                tenant_id=user.tenant_id,
                provider="GOOGLE_PLACES",
                provider_place_id=prov_id
            ).first()

            name = pdata.get("displayName", {}).get("text") or prov_id
            primary_type = pdata.get("primaryType") or "establishment"
            address = pdata.get("formattedAddress") or ""
            loc = pdata.get("location", {})
            poi_lat = Decimal(str(loc.get("latitude", lat)))
            poi_lng = Decimal(str(loc.get("longitude", lng)))

            phone = pdata.get("internationalPhoneNumber") or pdata.get("nationalPhoneNumber")
            p_masked = mask_phone(phone) if phone else None
            p_hash = phone_hash(user.tenant_id, phone) if phone else None
            website = pdata.get("websiteUri")
            rating = Decimal(str(pdata["rating"])) if pdata.get("rating") is not None else None
            rating_count = pdata.get("userRatingCount")

            if not poi:
                poi = PoiPlace(
                    id=uid("POI"),
                    tenant_id=user.tenant_id,
                    provider="GOOGLE_PLACES",
                    provider_place_id=prov_id,
                    name=name,
                    primary_type=primary_type,
                    address=address,
                    latitude=poi_lat,
                    longitude=poi_lng,
                    phone_masked=p_masked,
                    phone_hash=p_hash,
                    website=website,
                    rating=rating,
                    rating_count=rating_count,
                    attribution=GOOGLE_ATTRIBUTION,
                    fetched_at=utc_now(),
                    expires_at=utc_now() + timedelta(days=30),
                )
                db.add(poi)
                db.flush()
            else:
                poi.name = name
                poi.primary_type = primary_type
                poi.address = address
                poi.latitude = poi_lat
                poi.longitude = poi_lng
                poi.phone_masked = p_masked
                poi.phone_hash = p_hash
                poi.website = website
                poi.rating = rating
                poi.rating_count = rating_count
                poi.attribution = GOOGLE_ATTRIBUTION
                poi.fetched_at = utc_now()
                poi.expires_at = utc_now() + timedelta(days=30)

            # Match against existing customers
            match = match_place(
                db,
                user.tenant_id,
                name=poi.name,
                phone=phone,
                latitude=poi.latitude,
                longitude=poi.longitude,
                address=poi.address
            )
            poi.match_status = match["status"]
            poi.matched_customer_id = match["customer_id"]
            poi.match_score = match["score"]
            poi.match_reasons_json = json.dumps(match["reasons"])
            poi.matched_at = utc_now()

            upserted_pois.append(poi)

        db.commit()

        # Calculate distances & filter
        matching_with_dist = []
        for p in upserted_pois:
            dist = int(round(haversine_distance(lat, lng, p.latitude, p.longitude)))
            matching_with_dist.append((p, dist))

        existing_customer_count = 0
        possible_match_count = 0
        new_lead_count = 0
        prospect_count = 0

        for p, _ in matching_with_dist:
            if p.prospect_id:
                prospect_count += 1
            if p.match_status == "EXISTING_CUSTOMER":
                existing_customer_count += 1
            elif p.match_status == "POSSIBLE_MATCH":
                possible_match_count += 1
            else:
                if not p.prospect_id:
                    new_lead_count += 1

        counts = {
            "existing_customer": existing_customer_count,
            "possible_match": possible_match_count,
            "new_lead": new_lead_count,
            "prospect": prospect_count
        }

        if not include_existing:
            filtered = [(p, d) for p, d in matching_with_dist if p.match_status != "EXISTING_CUSTOMER"]
        else:
            filtered = matching_with_dist

        filtered.sort(key=lambda item: item[1])
        selected = filtered[:limit]

        places_dtos = [format_poi_dto(db, user, p, d) for p, d in selected]

        return {
            "provider": self.provider_name,
            "attribution": GOOGLE_ATTRIBUTION,
            "center": {"lat": lat, "lng": lng},
            "radius_m": radius_m,
            "places": places_dtos,
            "counts": counts
        }

    def geocode(self, db: Session, user, q: str) -> dict:
        api_key = self._get_api_key()
        qs = q.strip()
        if len(qs) < 2:
            return {"provider": self.provider_name, "results": []}

        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
            "Content-Type": "application/json"
        }
        payload = {"textQuery": qs, "maxResultCount": 10}

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Google Places API returned status {res.status_code}: {res.text}"
                    )
                data = res.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Google Places API request failed: {exc}")

        results = []
        for p in data.get("places", []):
            label = p.get("displayName", {}).get("text", "")
            addr = p.get("formattedAddress", "")
            full_label = f"{label} - {addr}" if addr else label
            loc = p.get("location", {})
            results.append({
                "label": full_label,
                "latitude": str(loc.get("latitude", "")),
                "longitude": str(loc.get("longitude", ""))
            })

        return {
            "provider": self.provider_name,
            "results": results
        }


def get_poi_provider():
    selected = os.getenv("NEXTRM_POI_PROVIDER", "synthetic").strip().casefold()
    if selected == "google":
        return GooglePlacesProvider()
    return SyntheticProvider()
