
from datetime import date
import copy
import re


# ==================================================
# CUSTOMER TEST DATA
# ==================================================

CUSTOMERS = {

    # --------------------------------------------------
    # CUSTOMER 1 - DAVID MORGAN
    # --------------------------------------------------
    1: {
        "customer": {
            "prefix": "Mr",
            "first_name": "David",
            "middle_initial": "J",
            "last_name": "Morgan",
            "phone": "5125550142",
            "email": "david.morgan@example.com"
        },

        "service_address": {
            "zip_code": "78701",
            "address_line_1": "453 Church Street",
            "city": "Austin",
            "state": "TX",
            "dwelling_type": "HOUSE",
            "ownership": "OWN",
            "moving_status": False
        },

        "order": {
            "provider": "XFINITY",
            "customer_type": "NEW",
            "service_category": "INTERNET",
            "internet_speed_mbps": 300,
            "pricing_term": "1_YEAR",
            "video_service": False,
            "phone_service": False,
            "now_tv": False,
            "equipment_type": "LEASED_GATEWAY"
        },

        "qualification": {
            "account_holder_name": "David Morgan",
            "speaking_to_account_holder": True,
            "existing_provider_customer": False,
            "ez_enroll": False,
            "autopay_paperless_discount": True,
            "mailing_same_as_service": True,
            "shipping_same_as_service": True,
            "account_disclosure_acknowledged": True
        },

        "installation": {
            "installation_type": "PRO_INSTALL",
            "preferred_date": "2026-11-16",
            "preferred_time": "Evening",
            "installation_disclosure_acknowledged": True
        },

        "disclosures": {
            "broadband_label_choice": "NOT_REQUESTED",
            "broadband_label_acknowledged": True
        },

        "credit_check": {
            "ssn": "123456789",
            "dob": "04/09/1985",
            "enabled": True
        }
    },

    # --------------------------------------------------
    # CUSTOMER 2 - EMILY CARTER
    # --------------------------------------------------
    2: {
        "customer": {
            "prefix": "Ms",
            "first_name": "Emily",
            "middle_initial": "R",
            "last_name": "Carter",
            "phone": "5125550186",
            "email": "emily.carter@example.com"
        },

        "service_address": {
            "zip_code": "78704",
            "address_line_1": "825 South Lamar Boulevard",
            "city": "Austin",
            "state": "TX",
            "dwelling_type": "APARTMENT",
            "ownership": "RENT",
            "moving_status": True
        },

        "order": {
            "provider": "XFINITY",
            "customer_type": "NEW",
            "service_category": "INTERNET",
            "internet_speed_mbps": 500,
            "pricing_term": "5_YEAR",
            "video_service": False,
            "phone_service": False,
            "now_tv": False,
            "equipment_type": "CUSTOMER_OWNED"
        },

        "qualification": {
            "account_holder_name": "Emily Carter",
            "speaking_to_account_holder": True,
            "existing_provider_customer": False,
            "ez_enroll": False,
            "autopay_paperless_discount": True,
            "mailing_same_as_service": True,
            "shipping_same_as_service": True,
            "account_disclosure_acknowledged": True
        },

        "installation": {
            "installation_type": "PRO_INSTALL",
            "preferred_date": "2026-11-16",
            "preferred_time": "Evening",
            "installation_disclosure_acknowledged": True
        },

        "disclosures": {
            "broadband_label_choice": "REQUESTED",
            "broadband_label_acknowledged": True
        },

        "credit_check": {
            "ssn": "",
            "dob": "",
            "enabled": False
        }
    },

    # --------------------------------------------------
    # CUSTOMER 3 - MICHAEL BROOKS
    # --------------------------------------------------
    3: {
        "customer": {
            "prefix": "Mr",
            "first_name": "Michael",
            "middle_initial": "T",
            "last_name": "Brooks",
            "phone": "5125550129",
            "email": "michael.brooks@example.com"
        },

        "service_address": {
            "zip_code": "78745",
            "address_line_1": "1201 Westgate Boulevard",
            "city": "Austin",
            "state": "TX",
            "dwelling_type": "HOUSE",
            "ownership": "OWN",
            "moving_status": False
        },

        "order": {
            "provider": "XFINITY",
            "customer_type": "NEW",
            "service_category": "INTERNET",
            "internet_speed_mbps": 1000,
            "pricing_term": "1_YEAR",
            "video_service": True,
            "video_package": "POPULAR_TV",
            "phone_service": False,
            "now_tv": True,
            "equipment_type": "LEASED_GATEWAY"
        },

        "qualification": {
            "account_holder_name": "Michael Brooks",
            "speaking_to_account_holder": True,
            "existing_provider_customer": False,
            "ez_enroll": False,
            "autopay_paperless_discount": True,
            "mailing_same_as_service": True,
            "shipping_same_as_service": True,
            "account_disclosure_acknowledged": True
        },

        "installation": {
            "installation_type": "PRO_INSTALL",
            "preferred_date": "2026-11-16",
            "preferred_time": "Evening",
            "installation_disclosure_acknowledged": True
        },

        "disclosures": {
            "broadband_label_choice": "NOT_REQUESTED",
            "broadband_label_acknowledged": True
        },

        "credit_check": {
            "ssn": "123456789",
            "dob": "04/09/1985",
            "enabled": True
        }
    }
}


# ==================================================
# LOAD CUSTOMER DATA
# ==================================================

def load_customer(customer_number, file_path=None):
    """Load a customer profile from this Python file."""

    if file_path is not None:
        raise ValueError(
            "Customer data is embedded in test_data.py. "
            "External file paths are not supported."
        )

    try:
        return copy.deepcopy(CUSTOMERS[int(customer_number)])

    except (KeyError, ValueError, TypeError) as error:
        raise ValueError(
            f"Customer {customer_number} not found. "
            "Available customers: 1, 2, 3."
        ) from error


# ==================================================
# VALIDATE CUSTOMER DATA
# ==================================================

def validate_customer_data(data):
    """Validate all required customer information."""

    required_sections = [
        "customer",
        "service_address",
        "order",
        "qualification",
        "installation",
        "disclosures",
        "credit_check"
    ]

    for section in required_sections:
        if section not in data:
            raise ValueError(
                f"Missing required section: {section}"
            )

    required_fields = {
        "customer": [
            "prefix", "first_name", "last_name",
            "phone", "email"
        ],
        "service_address": [
            "zip_code", "address_line_1", "city",
            "state", "dwelling_type", "ownership",
            "moving_status"
        ],
        "order": [
            "provider", "customer_type", "service_category",
            "internet_speed_mbps", "pricing_term",
            "video_service", "phone_service", "now_tv",
            "equipment_type"
        ],
        "qualification": [
            "account_holder_name",
            "speaking_to_account_holder",
            "existing_provider_customer",
            "ez_enroll",
            "autopay_paperless_discount",
            "mailing_same_as_service",
            "shipping_same_as_service"
        ],
        "installation": [
            "installation_type", "preferred_date",
            "preferred_time"
        ],
        "disclosures": [
            "broadband_label_choice",
            "broadband_label_acknowledged"
        ],
        "credit_check": [
            "ssn", "dob", "enabled"
        ]
    }

    for section, fields in required_fields.items():
        for field in fields:
            if field not in data[section]:
                raise ValueError(
                    f"Missing field: {section}.{field}"
                )

    for section, fields in required_fields.items():
        for field in fields:
            value = data[section][field]

            if value is None or value == "":
                if section == "credit_check" and field in ("ssn", "dob"):
                    continue

                raise ValueError(
                    f"Empty required field: {section}.{field}"
                )

    customer = data["customer"]
    address = data["service_address"]
    order = data["order"]
    installation = data["installation"]
    credit_check = data["credit_check"]

    if not re.fullmatch(r"\d{10}", str(customer["phone"])):
        raise ValueError("Phone number must contain 10 digits.")

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        customer["email"]
    ):
        raise ValueError("Invalid email address.")

    if not re.fullmatch(r"\d{5}", str(address["zip_code"])):
        raise ValueError("ZIP code must contain 5 digits.")

    if not isinstance(address["moving_status"], bool):
        raise ValueError("Moving status must be True or False.")

    if (
        not isinstance(order["internet_speed_mbps"], int)
        or order["internet_speed_mbps"] <= 0
    ):
        raise ValueError("Internet speed must be a positive integer.")

    if order["equipment_type"] not in (
        "LEASED_GATEWAY",
        "CUSTOMER_OWNED"
    ):
        raise ValueError("Unsupported equipment type.")

    if installation["installation_type"] not in (
        "STANDARD_SHIPPING",
        "PRO_INSTALL"
    ):
        raise ValueError("Invalid installation type.")

    if order["provider"] != "XFINITY":
        raise ValueError("Unexpected source provider.")

    if not isinstance(credit_check["enabled"], bool):
        raise ValueError("Credit check enabled must be True or False.")

    # Credit check is disabled until approved simulator test data
    # and sandbox behavior are confirmed.
    if not isinstance(credit_check.get("enabled"), bool):
        raise ValueError("Credit Check enabled must be True or False.")

    if credit_check["enabled"]:
        if not credit_check.get("ssn"):
            raise ValueError("Dummy SSN is required when credit check is enabled.")

        if not credit_check.get("dob"):
            raise ValueError("Dummy DOB is required when credit check is enabled.")

    if installation["installation_type"] == "PRO_INSTALL":

        install_date = date.fromisoformat(
            installation["preferred_date"]
        )

        if install_date < date.today():
            raise ValueError("Installation date is in the past.")

        if installation["preferred_time"] not in (
            "Morning", "Afternoon", "Evening"
        ):
            raise ValueError("Invalid installation time.")

    print("Customer data validation: PASSED")

    return True


# ==================================================
# CONVERT CUSTOMER DATA FOR PLAYWRIGHT
# ==================================================

def build_test_data(data, moving_date="2026-11-10"):
    """Convert nested customer data into Playwright fields."""

    validate_customer_data(data)

    customer = data["customer"]
    address = data["service_address"]
    order = data["order"]
    qualification = data["qualification"]
    installation = data["installation"]
    disclosures = data["disclosures"]
    credit_check = data["credit_check"]

    resolved_moving_date = (
        moving_date if address["moving_status"] else ""
    )

    return {
        "prefix": customer["prefix"],
        "first_name": customer["first_name"],
        "middle_name": customer.get("middle_initial", ""),
        "last_name": customer["last_name"],

        "zip_code": address["zip_code"],
        "address": address["address_line_1"],
        "unit_type": "",
        "unit_number": "",
        "city": address["city"],
        "state": address["state"],
        "dwelling_type": address["dwelling_type"].title(),
        "ownership": address["ownership"].title(),
        "moving": (
            "Yes" if address["moving_status"] else "No"
        ),
        "moving_date": resolved_moving_date,

        "customer_type": order["customer_type"].title(),
        "provider": "ProviderXX",
        "internet_speed_mbps": order["internet_speed_mbps"],
        "pricing_term": order["pricing_term"],
        "service_category": order["service_category"],

        "video": (
            "Video" if order["video_service"] else "None"
        ),
        "video_service": order["video_service"],
        "video_package": order.get("video_package"),
        "phone_service": order["phone_service"],
        "now_tv": order["now_tv"],
        "equipment_type": order["equipment_type"],

        "phone": customer["phone"],
        "email": customer["email"],

        "account_holder_name": qualification["account_holder_name"],
        "speaking_to_account_holder":
            qualification["speaking_to_account_holder"],
        "existing_provider_customer":
            qualification["existing_provider_customer"],
        "ez_enroll": qualification["ez_enroll"],
        "autopay_paperless_discount":
            qualification["autopay_paperless_discount"],
        "mailing_same_as_service":
            qualification["mailing_same_as_service"],
        "shipping_same_as_service":
            qualification["shipping_same_as_service"],
        "account_disclosure_acknowledged":
            qualification.get("account_disclosure_acknowledged", False),

        "broadband_label_choice":
            disclosures["broadband_label_choice"],
        "broadband_label_acknowledged":
            disclosures["broadband_label_acknowledged"],

        "installation_type": installation["installation_type"],
        "installation_date": installation["preferred_date"],
        "installation_time": installation["preferred_time"],
        "installation_disclosure_acknowledged":
            installation.get("installation_disclosure_acknowledged", False),

        "credit_check": {
            "ssn": credit_check["ssn"],
            "dob": credit_check["dob"],
            "enabled": credit_check["enabled"]
        }
    }


# ==================================================
# CUSTOMER LOADING ENTRY POINT
# ==================================================

def get_test_data(customer_number=2, moving_date="2026-11-10"):
    """Main function used by test_browser_launch.py."""

    raw_data = load_customer(customer_number)

    test_data = build_test_data(
        raw_data,
        moving_date=moving_date
    )

    print("\n========== CUSTOMER LOADED ==========")

    print(
        "Customer:",
        test_data["first_name"],
        test_data["last_name"]
    )

    print("Provider:", test_data["provider"])

    print(
        "Internet Speed:",
        test_data["internet_speed_mbps"],
        "Mbps"
    )

    print("Pricing Term:", test_data["pricing_term"])
    print("Equipment:", test_data["equipment_type"])
    print("Moving:", test_data["moving"])
    print("Moving Date:", test_data["moving_date"])

    print(
        "Installation:",
        test_data["installation_date"],
        test_data["installation_time"]
    )

    print(
        "Credit Check Enabled:",
        test_data["credit_check"]["enabled"]
    )

    print("=====================================\n")

    return test_data


# ==================================================
# CUSTOMER LOADING ENTRY POINT
# ==================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--customer", type=int, choices=[1, 2, 3], default=2)
    args = parser.parse_args()

    get_test_data(args.customer)
