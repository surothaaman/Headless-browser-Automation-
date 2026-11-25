from pathlib import Path
from tests.test_data import load_json_scenario, build_test_data

def test_ez_enroll_scenario_maps_to_existing_automation():
    path = Path(__file__).parents[1] / "scenario-04-ez-enroll(2).json"
    raw = load_json_scenario(path)
    data = build_test_data(raw)
    assert data["provider"] == "ProviderXX"
    assert data["internet_speed_mbps"] == 300
    assert data["pricing_term"] == "1_YEAR"
    assert data["ez_enroll"] is True
    assert data["autopay_paperless_discount"] is True
    assert data["equipment_type"] == "LEASED_GATEWAY"
    assert data["installation_type"] == "STANDARD_SHIPPING"
    assert data["billing_address_same_as_service"] is True
    assert data["card_type"] == "Visa"
    assert data["lead_id"] == "1111111111"
    assert data["moving"] == "No"

def test_scenario_does_not_contain_payment_secrets():
    path = Path(__file__).parents[1] / "scenario-04-ez-enroll(2).json"
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "sensitive_data" not in data
