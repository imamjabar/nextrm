import json
import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.banking import BankCustomer, PoiPlace
from app.models.relationships import Party, Source, Prospect, ReviewEvent
from app.services.identity_keys import phone_hash, npwp_hash, email_hash
from app.services.customer_match import match_place, match_all_pois

client = TestClient(app)


def rm_headers():
    return {"X-User-Id": "usr-maya", "X-Tenant-Id": "demo-bank"}


def customer_headers():
    return {"X-User-Id": "usr-dina", "X-Tenant-Id": "demo-bank"}


def admin_headers():
    return {"X-User-Id": "usr-aiadmin", "X-Tenant-Id": "demo-bank"}


def test_matcher_crafted_customers():
    with SessionLocal() as db:
        # Create crafted bank customers
        c1 = BankCustomer(
            id="cust-budi-1",
            tenant_id="demo-bank",
            cif="CIF-BUDI01",
            kind="PERSON",
            full_name="Budi Santoso",
            normalized_name="budi santoso",
            phone_hash=phone_hash("demo-bank", "088899990001"),
            phone_masked="+6288••••001",
            npwp_hash=npwp_hash("demo-bank", "09.876.543.2-111.000"),
            email_hash=email_hash("demo-bank", "budi.santoso.unique@example.invalid"),
            address="Jl. Ahmad Yani No. 10",
            city="Bekasi",
            latitude=Decimal("-6.238300"),
            longitude=Decimal("106.975600"),
            segment="MASS",
            opened_at=date(2023, 1, 15)
        )
        c2 = BankCustomer(
            id="cust-klinik-2",
            tenant_id="demo-bank",
            cif="CIF-KLINIK02",
            kind="ORGANIZATION",
            full_name="Klinik Medika Sehat",
            normalized_name="klinik medika sehat",
            address="Jl. Juanda No. 5",
            city="Bekasi",
            latitude=Decimal("-6.240000"),
            longitude=Decimal("106.970000"),
            segment="SME",
            opened_at=date(2022, 5, 20)
        )
        c3 = BankCustomer(
            id="cust-sinar-3",
            tenant_id="demo-bank",
            cif="CIF-SINAR03",
            kind="ORGANIZATION",
            full_name="PT Sinar Harapan",
            normalized_name="sinar harapan",
            address="Jl. Basuki Rahmat No. 1",
            city="Surabaya",
            latitude=Decimal("-7.257500"),
            longitude=Decimal("112.752100"),
            segment="CORPORATE",
            opened_at=date(2021, 3, 10)
        )
        db.add_all([c1, c2, c3])
        db.commit()

        # 1. Exact phone match
        res_phone = match_place(db, "demo-bank", name="Unrelated Name", phone="088899990001")
        assert res_phone["customer_id"] == "cust-budi-1"
        assert res_phone["score"] == Decimal("1.000")
        assert not any("081234567890" in r for r in res_phone["reasons"])
        assert any("phone match" in r.lower() for r in res_phone["reasons"])

        # 2. Exact NPWP match
        res_npwp = match_place(db, "demo-bank", name="Another Name", npwp="098765432111000")
        assert res_npwp["customer_id"] == "cust-budi-1"
        assert res_npwp["score"] == Decimal("1.000")
        assert not any("012345678123000" in r for r in res_npwp["reasons"])
        assert any("npwp match" in r.lower() for r in res_npwp["reasons"])

        # 3. Similar name nearby (< 300m)
        res_similar = match_place(
            db, "demo-bank",
            name="Klinik Medika Sehat Sentosa",
            latitude=-6.240100,
            longitude=106.970050
        )
        assert res_similar["status"] == "POSSIBLE_MATCH"
        assert res_similar["customer_id"] == "cust-klinik-2"
        assert res_similar["score"] >= Decimal("0.700")
        assert any("within" in r.lower() for r in res_similar["reasons"])

        # 4. Far same name (> 300m, different city) -> NO_MATCH_IN_AVAILABLE_DATA
        res_far = match_place(
            db, "demo-bank",
            name="PT Sinar Harapan",
            address="Bekasi, Jawa Barat",
            latitude=-6.238300,
            longitude=106.975600
        )
        assert res_far["status"] == "NO_MATCH_IN_AVAILABLE_DATA"
        assert res_far["customer_id"] is None

        # 5. Two candidates ambiguous match
        c4 = BankCustomer(
            id="cust-budi-2",
            tenant_id="demo-bank",
            cif="CIF-BUDI02",
            kind="PERSON",
            full_name="Budi Santoso",
            normalized_name="budi santoso",
            address="Jl. Cut Meutia No. 3",
            city="Bekasi",
            latitude=Decimal("-6.239000"),
            longitude=Decimal("106.976000"),
            segment="AFFLUENT",
            opened_at=date(2024, 2, 1)
        )
        db.add(c4)
        db.commit()

        res_two = match_place(
            db, "demo-bank",
            name="Budi Santoso",
            address="Bekasi"
        )
        assert res_two["status"] == "POSSIBLE_MATCH"
        assert res_two["customer_id"] is None
        assert "Multiple candidate customers found" in res_two["reasons"][0]
        assert "CIF-BUDI01" in res_two["reasons"][0]
        assert "CIF-BUDI02" in res_two["reasons"][0]


def test_poi_nearby_filtering_and_counts():
    with SessionLocal() as db:
        db.query(PoiPlace).filter_by(tenant_id="demo-bank").delete()
        poi_a = PoiPlace(
            id="poi-test-a",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-a",
            name="Kedai Kopi Nikmat",
            primary_type="cafe",
            address="Jl. Ahmad Yani No. 12, Bekasi",
            latitude=Decimal("-6.238500"),
            longitude=Decimal("106.975500"),
            attribution="Synthetic dataset",
            match_status="NO_MATCH_IN_AVAILABLE_DATA"
        )
        poi_b = PoiPlace(
            id="poi-test-b",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-b",
            name="Apotek Sehat Sejahtera",
            primary_type="pharmacy",
            address="Jl. Juanda No. 2, Bekasi",
            latitude=Decimal("-6.240000"),
            longitude=Decimal("106.975000"),
            attribution="Synthetic dataset",
            match_status="POSSIBLE_MATCH"
        )
        poi_c = PoiPlace(
            id="poi-test-c",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-c",
            name="Toko Elektronik Makmur",
            primary_type="retail",
            address="Jl. Sudirman No. 50, Bekasi",
            latitude=Decimal("-6.245000"),
            longitude=Decimal("106.975000"),
            attribution="Synthetic dataset",
            match_status="EXISTING_CUSTOMER"
        )
        existing_prosp = db.query(Prospect).filter_by(tenant_id="demo-bank").first()
        poi_d = PoiPlace(
            id="poi-test-d",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-d",
            name="Bengkel Auto Jaya",
            primary_type="auto_repair",
            address="Jl. Hasibuan No. 1, Bekasi",
            latitude=Decimal("-6.246000"),
            longitude=Decimal("106.975000"),
            attribution="Synthetic dataset",
            match_status="NO_MATCH_IN_AVAILABLE_DATA",
            prospect_id=existing_prosp.id if existing_prosp else None
        )
        poi_far = PoiPlace(
            id="poi-test-far",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-far",
            name="Warung Jauh",
            primary_type="restaurant",
            address="Jl. Jauh No. 99, Cikarang",
            latitude=Decimal("-6.350000"),
            longitude=Decimal("106.975000"),
            attribution="Synthetic dataset",
            match_status="NO_MATCH_IN_AVAILABLE_DATA"
        )
        db.add_all([poi_a, poi_b, poi_c, poi_d, poi_far])
        db.commit()

    # Query nearby with radius 1500m
    resp = client.get("/v1/rm/poi/nearby?lat=-6.2383&lng=106.9756&radius_m=1500", headers=rm_headers())
    assert resp.status_code == 200
    data = resp.json()

    assert data["provider"] == "SYNTHETIC_DATASET"
    assert data["counts"]["existing_customer"] == 1
    assert data["counts"]["possible_match"] == 1
    assert data["counts"]["new_lead"] == 1
    assert data["counts"]["prospect"] == 1

    # Far place is not counted and not returned
    place_ids = [p["id"] for p in data["places"]]
    assert "poi-test-far" not in place_ids

    # By default, existing customers excluded from places list
    assert "poi-test-c" not in place_ids
    assert "poi-test-a" in place_ids
    assert "poi-test-b" in place_ids
    assert "poi-test-d" in place_ids

    # Ordering is by distance ascending: poi_a closest, then poi_b, then poi_d
    assert place_ids == ["poi-test-a", "poi-test-b", "poi-test-d"]
    assert data["places"][0]["distance_m"] < data["places"][1]["distance_m"] < data["places"][2]["distance_m"]

    # Test include_existing=true
    resp_inc = client.get("/v1/rm/poi/nearby?lat=-6.2383&lng=106.9756&radius_m=1500&include_existing=true", headers=rm_headers())
    assert resp_inc.status_code == 200
    data_inc = resp_inc.json()
    place_ids_inc = [p["id"] for p in data_inc["places"]]
    assert "poi-test-c" in place_ids_inc
    assert len(place_ids_inc) == 4

    # Test type filter
    resp_type = client.get("/v1/rm/poi/nearby?lat=-6.2383&lng=106.9756&radius_m=1500&type=pharmacy", headers=rm_headers())
    assert resp_type.status_code == 200
    assert len(resp_type.json()["places"]) == 1
    assert resp_type.json()["places"][0]["id"] == "poi-test-b"


def test_rm_only_access():
    # Customer gets 403
    r_cust = client.get("/v1/rm/poi/nearby?lat=-6.2383&lng=106.9756", headers=customer_headers())
    assert r_cust.status_code == 403

    # Admin gets 403
    r_admin = client.get("/v1/rm/poi/nearby?lat=-6.2383&lng=106.9756", headers=admin_headers())
    assert r_admin.status_code == 403

    # RM gets 200
    r_rm = client.get("/v1/rm/poi/nearby?lat=-6.2383&lng=106.9756", headers=rm_headers())
    assert r_rm.status_code == 200


def test_prospect_creation_rules_and_idempotency():
    with SessionLocal() as db:
        poi_exist = PoiPlace(
            id="poi-exist-1",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-exist-1",
            name="Bank Pelanggan Lama",
            primary_type="finance",
            address="Jl. Ahmad Yani No. 1",
            latitude=Decimal("-6.238300"),
            longitude=Decimal("106.975600"),
            attribution="Synthetic dataset",
            match_status="EXISTING_CUSTOMER"
        )
        poi_pos = PoiPlace(
            id="poi-pos-1",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-pos-1",
            name="PT Ragu Ragu",
            primary_type="wholesale",
            address="Jl. Ahmad Yani No. 2",
            latitude=Decimal("-6.238400"),
            longitude=Decimal("106.975700"),
            attribution="Synthetic dataset",
            match_status="POSSIBLE_MATCH"
        )
        poi_clean = PoiPlace(
            id="poi-clean-1",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-clean-1",
            name="Bengkel Baru Segar",
            primary_type="auto_repair",
            address="Jl. Ahmad Yani No. 3",
            latitude=Decimal("-6.238500"),
            longitude=Decimal("106.975800"),
            attribution="Synthetic dataset",
            match_status="NO_MATCH_IN_AVAILABLE_DATA"
        )
        db.add_all([poi_exist, poi_pos, poi_clean])
        db.commit()

    # Rule 1: 409 if EXISTING_CUSTOMER
    r_409 = client.post(
        "/v1/rm/poi/poi-exist-1/prospect",
        json={"request_key": "req-key-exist-01"},
        headers=rm_headers()
    )
    assert r_409.status_code == 409

    # Rule 2: POSSIBLE_MATCH requires confirm_not_customer=True and reason
    r_pos_no_conf = client.post(
        "/v1/rm/poi/poi-pos-1/prospect",
        json={"request_key": "req-key-pos-01", "confirm_not_customer": False},
        headers=rm_headers()
    )
    assert r_pos_no_conf.status_code == 400

    r_pos_no_reason = client.post(
        "/v1/rm/poi/poi-pos-1/prospect",
        json={"request_key": "req-key-pos-02", "confirm_not_customer": True, "reason": ""},
        headers=rm_headers()
    )
    assert r_pos_no_reason.status_code == 400

    r_pos_ok = client.post(
        "/v1/rm/poi/poi-pos-1/prospect",
        json={"request_key": "req-key-pos-03", "confirm_not_customer": True, "reason": "Verified legally distinct entity with legal team."},
        headers=rm_headers()
    )
    assert r_pos_ok.status_code == 200
    pos_data = r_pos_ok.json()
    assert pos_data["party"]["kind"] == "ORGANIZATION"
    assert pos_data["party"]["relationship"] == "NO_MATCH_IN_AVAILABLE_DATA"
    assert pos_data["party"]["contact"] == "REQUIRES_CONFIRMATION"
    assert "business listing only" in pos_data["need"]

    # Rule 3: Clean prospect creation and idempotency
    r_clean = client.post(
        "/v1/rm/poi/poi-clean-1/prospect",
        json={"request_key": "req-key-clean-01"},
        headers=rm_headers()
    )
    assert r_clean.status_code == 200
    clean_data = r_clean.json()
    prospect_id = clean_data["id"]

    # Calling again with same request_key returns identical prospect
    r_clean_repeat = client.post(
        "/v1/rm/poi/poi-clean-1/prospect",
        json={"request_key": "req-key-clean-01"},
        headers=rm_headers()
    )
    assert r_clean_repeat.status_code == 200
    assert r_clean_repeat.json()["id"] == prospect_id

    # Calling with different request_key on already-converted poi returns same prospect
    r_clean_diff_key = client.post(
        "/v1/rm/poi/poi-clean-1/prospect",
        json={"request_key": "req-key-clean-02"},
        headers=rm_headers()
    )
    assert r_clean_diff_key.status_code == 200
    assert r_clean_diff_key.json()["id"] == prospect_id

    with SessionLocal() as db:
        poi_record = db.query(PoiPlace).filter_by(id="poi-clean-1").first()
        assert poi_record.prospect_id == prospect_id


def test_match_review_endpoint():
    with SessionLocal() as db:
        poi = PoiPlace(
            id="poi-rev-1",
            tenant_id="demo-bank",
            provider="SYNTHETIC_DATASET",
            provider_place_id="syn-rev-1",
            name="Toko Roti Sedap",
            primary_type="bakery",
            address="Jl. Juanda No. 10",
            latitude=Decimal("-6.238300"),
            longitude=Decimal("106.975600"),
            attribution="Synthetic dataset",
            match_status="POSSIBLE_MATCH"
        )
        db.add(poi)
        db.commit()

    # RM confirms not a customer
    r = client.post(
        "/v1/rm/poi/poi-rev-1/match-review",
        json={
            "request_key": "key-rev-01",
            "decision": "NOT_A_CUSTOMER",
            "reason": "Different owner and taxpayer registration."
        },
        headers=rm_headers()
    )
    assert r.status_code == 200
    data = r.json()
    assert data["match_status"] == "NO_MATCH_IN_AVAILABLE_DATA"

    with SessionLocal() as db:
        poi_check = db.query(PoiPlace).filter_by(id="poi-rev-1").first()
        assert poi_check.match_status == "NO_MATCH_IN_AVAILABLE_DATA"
        # Check ReviewEvent recorded
        rev = db.query(ReviewEvent).filter_by(resource_id="poi-rev-1", action="POI_MATCH_REVIEW").first()
        assert rev is not None
        assert "Different owner" in rev.reason


def test_google_provider_without_key_yields_503(monkeypatch):
    monkeypatch.setenv("NEXTRM_POI_PROVIDER", "google")
    monkeypatch.delenv("GOOGLE_MAPS_SERVER_KEY", raising=False)

    r_nearby = client.get("/v1/rm/poi/nearby?lat=-6.2383&lng=106.9756", headers=rm_headers())
    assert r_nearby.status_code == 503
    assert "GOOGLE_MAPS_SERVER_KEY" in r_nearby.json()["detail"]

    r_geo = client.get("/v1/rm/poi/geocode?q=Bekasi", headers=rm_headers())
    assert r_geo.status_code == 503


def test_geocode_synthetic():
    r = client.get("/v1/rm/poi/geocode?q=Bekasi", headers=rm_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "SYNTHETIC_DATASET"
    assert len(data["results"]) > 0
    assert "latitude" in data["results"][0]
    assert "longitude" in data["results"][0]


def test_csv_import_marks_existing_customer():
    with SessionLocal() as db:
        cust = BankCustomer(
            id="cust-csv-match-1",
            tenant_id="demo-bank",
            cif="CIF-CSV01",
            kind="PERSON",
            full_name="Dewi Sartika",
            normalized_name="dewi sartika",
            phone_hash=phone_hash("demo-bank", "081999888777"),
            email_hash=email_hash("demo-bank", "dewi.sartika@example.invalid"),
            address="Jl. Melati No. 5",
            city="Bekasi",
            latitude=Decimal("-6.238300"),
            longitude=Decimal("106.975600"),
            segment="MASS",
            opened_at=date(2023, 6, 1)
        )
        db.add(cust)
        db.commit()

    csv_data = (
        "external_id,kind,name,need,latitude,longitude,contact_email\n"
        "imp-1,PERSON,Dewi Sartika,Modal usaha warung sembako,-6.2383,106.9756,dewi.sartika@example.invalid\n"
        "imp-2,PERSON,Bambang Pamungkas,Tabungan pensiun dan deposito,-6.2390,106.9760,bambang.p@example.invalid\n"
    )

    r = client.post(
        "/v1/rm/imports",
        json={"csv_text": csv_data, "request_key": "import-test-match-01"},
        headers=rm_headers()
    )
    assert r.status_code == 200
    receipt = r.json()

    # Row 1 matched existing bank customer, so it was NOT imported as a prospect
    # Row 2 was imported
    assert receipt["matched_existing"] == 1
    assert receipt["imported"] == 1
    assert len(receipt["prospect_ids"]) == 1

    with SessionLocal() as db:
        imported_prospect = db.query(Prospect).filter_by(id=receipt["prospect_ids"][0]).first()
        imported_party = db.query(Party).filter_by(id=imported_prospect.party_id).first()
        assert imported_party.name == "Bambang Pamungkas"
