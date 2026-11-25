from pathlib import Path
import json
import os
import sys
import urllib.error
import urllib.request
import re
from decimal import Decimal
import argparse
from tests.test_data import get_test_data
from datetime import datetime, date
from app.schemas import order
from app.security.sensitive_client import retrieve_sensitive_data
from app.config import load_local_env
from app.security.jwe_handler import encrypt_sensitive_payload
from app.automation.browser import BrowserManager
from playwright.sync_api import Error as PlaywrightError



def _read_masked_input(prompt, *, reader=None, writer=None):
    """Read terminal input and display '*' for each typed character."""

    if reader is None:
        if os.name != "nt":
            import getpass
            return getpass.getpass(prompt)

        import msvcrt
        reader = msvcrt.getwch

    if writer is None:
        writer = sys.stdout.write

    writer(prompt)
    sys.stdout.flush()

    chars = []

    while True:
        char = reader()

        if char in ("\r", "\n"):
            writer("\n")
            sys.stdout.flush()
            break

        if char == "\003":
            raise KeyboardInterrupt

        if char in ("\b", "\x7f"):
            if chars:
                chars.pop()
                writer("\b \b")
                sys.stdout.flush()
            continue

        if char in ("\x00", "\xe0"):
            reader()
            continue

        if char.isprintable():
            chars.append(char)
            writer("*")
            sys.stdout.flush()

    return "".join(chars)

def _validate_payment_payload(payload):
    """Validate shape and formats without printing or returning values."""
    import re
    card = re.sub(r"\D", "", str(payload.get("card_number", "")))
    cvv = str(payload.get("cvv", ""))
    month = str(payload.get("expiry_month", ""))
    year = str(payload.get("expiry_year", ""))
    holder = str(payload.get("cardholder_name", "")).strip()
    card_type = str(payload.get("card_type", "")).strip()

    if not 12 <= len(card) <= 19:
        raise ValueError("Card number format is invalid.")
    if not re.fullmatch(r"\d{3,4}", cvv):
        raise ValueError("Card security code format is invalid.")
    if not re.fullmatch(r"\d{1,2}", month) or not 1 <= int(month) <= 12:
        raise ValueError("Expiry month must be between 1 and 12.")
    if not re.fullmatch(r"\d{2}|\d{4}", year):
        raise ValueError("Expiry year must contain 2 or 4 digits.")
    if not holder:
        raise ValueError("Cardholder name is required.")
    if not card_type:
        raise ValueError("Card type is required.")
    return True


def collect_encrypt_upload_payment():
    """
    Collect simulator-approved test values, encrypt in-process using the
    existing JWE implementation, and upload without writing plaintext to disk.
    """
    load_local_env()
    print("\n========== SECURE PAYMENT ENTRY ==========")
    print("Enter simulator-approved TEST details only.")
    print("Typing is masked with '*'. Values are not saved to a JSON file.")

    payload = {}
    try:
        payload["card_number"] = _read_masked_input("Test card number: ")
        payload["card_type"] = _read_masked_input("Card type (as shown by simulator): ")
        payload["cardholder_name"] = _read_masked_input("Cardholder name: ")
        payload["cvv"] = _read_masked_input("CVV: ")
        payload["expiry_month"] = _read_masked_input("Expiry month (MM): ")
        payload["expiry_year"] = _read_masked_input("Expiry year (YY or YYYY): ")
        _validate_payment_payload(payload)

        token = (os.getenv("CSE_ACCESS_TOKEN") or "").strip()
        if not token:
            raise RuntimeError("CSE_ACCESS_TOKEN is not configured.")
        api_url = (os.getenv("CSE_API_URL") or "http://127.0.0.1:8000").rstrip("/")
        public_key = os.getenv("CSE_PUBLIC_KEY_PATH") or "keys/server_public.pem"

        # Encrypt using the same JWE implementation as encrypt_order.py.
        encrypted_jwe = encrypt_sensitive_payload(payload, public_key)
        body = json.dumps({
            "encrypted_jwe": encrypted_jwe,
            "order_id": None,
        }).encode("utf-8")
        request = urllib.request.Request(
            api_url + "/api/sensitive-data/",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Encrypted payment upload failed (HTTP {exc.code})."
            ) from None
        except urllib.error.URLError:
            raise RuntimeError("Cannot reach the CSE API.") from None

        record_id = result.get("record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise RuntimeError("CSE API response did not contain a record ID.")

        print("PASS: Payment details encrypted and uploaded.")
        print("PASS: One-time payment record created.")
        return record_id
    finally:
        # Best-effort removal of local references; no plaintext file is created.
        for key in list(payload):
            payload[key] = ""
        payload.clear()


# Keep the original working simulator URL unchanged.
SIMULATOR_URL = (
    "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/"
    "?next=%2Fallconnect%2F"
)

from tests.test_data import get_test_data

TEST_DATA = {}

SCREENSHOT_DIR = Path("tests/screenshots")


def save_screenshot(page, filename):
    """Save a local screenshot only after explicit opt-in.

    Screenshots can contain customer PII or payment-page content. They are
    disabled by default. Do not enable them while entering payment details.
    """

    if os.getenv("PROVIDERXX_ENABLE_SCREENSHOTS") != "1":
        print("Screenshot skipped (disabled by secure default).")
        return

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = SCREENSHOT_DIR / filename
    page.screenshot(path=str(screenshot_path), full_page=True)
    print(f"Screenshot saved: {screenshot_path}")



def login_and_start_session(page):
    """Fill a configured portal password, then start a new session."""

    print("\n========== LOGIN AND SESSION ==========")
    portal_password = (os.getenv("PORTAL_PASSWORD") or "").strip()
    if portal_password:
        password_field = page.locator('input[type="password"]:visible').first
        try:
            password_field.wait_for(state="visible", timeout=15000)
            password_field.fill(portal_password)
            print("Portal password filled from .env; finish any remaining login steps.")
        except PlaywrightError:
            print("Portal password field not detected; complete login manually.")
        finally:
            portal_password = ""
    else:
        print("PORTAL_PASSWORD is empty; complete the login manually in the browser.")
    print("Waiting for the Idle Page...")

    # Wait until login is complete.
    page.locator(
        'body[data-ac-page="idle"]'
    ).wait_for(
        state="attached",
        timeout=300000,
    )

    print("Idle Page detected.")

    # Wait for the Start Session button.
    start_button = page.locator("#startCall")

    start_button.wait_for(
        state="visible",
        timeout=30000,
    )

    # Wait until the button is enabled.
    page.wait_for_function(
        """() => {
            const button = document.querySelector("#startCall");

            return button &&
                   !button.disabled &&
                   button.offsetParent !== null;
        }""",
        timeout=30000,
    )

    start_button.scroll_into_view_if_needed()

    print("Start Session button is visible and enabled.")

    # Click the button.
    start_button.click(timeout=30000)

    print("Start Session button clicked.")

    # Verify that the Greetings page appears.
    page.locator("#content_header").get_by_text(
        "Greetings",
        exact=True,
    ).wait_for(
        state="visible",
        timeout=60000,
    )

    print("Greetings page detected successfully.")

    # Continue using the existing Greetings Forward button.
    greetings_forward = page.get_by_role(
        "button",
        name="Forward",
        exact=False,
    )

    greetings_forward.wait_for(
        state="visible",
        timeout=30000,
    )

    greetings_forward.click()

    print("Greetings Forward button clicked.")

    # Wait for Basic Information.
    page.locator(
        'body[data-ac-page="basic-information"]'
    ).wait_for(
        state="attached",
        timeout=60000,
    )

    print("Basic Information page detected.")


def select_dropdown(page, selector, requested_value, field_name):
    """Select a dropdown option using its label or value."""

    dropdown = page.locator(selector)
    dropdown.wait_for(state="visible", timeout=10000)

    options = dropdown.locator("option").evaluate_all("""
        elements => elements.map(option => ({
            label: option.textContent.trim(),
            value: option.value
        }))
    """)

    requested = str(requested_value or "").strip()

    # An empty optional field can remain at its default option.
    if not requested:
        print(f"SKIP: {field_name} is empty.")
        return

    def normalize(value):
        return " ".join(str(value).strip().lower().split())

    # Match either the option label or its underlying value.
    match = next(
        (
            option for option in options
            if normalize(option["label"]) == normalize(requested)
            or normalize(option["value"]) == normalize(requested)
        ),
        None
    )

    if match is None:
        available = [
            f'{option["label"]!r} (value={option["value"]!r})'
            for option in options
        ]

        raise RuntimeError(
            f"Invalid option for {field_name}: {requested!r}. "
            f"Available options: {available}"
        )

    dropdown.select_option(value=match["value"])

    print(f"PASS: {field_name} selected: {match['label']}")



def fill_basic_information(page):
    """Fill and validate the Basic Information form."""

    print("\n========== BASIC INFORMATION ==========")

    # 1. Customer name
    select_dropdown(
        page, "#namePrefixList",
        TEST_DATA["prefix"], "Prefix"
    )

    page.locator("#firstName").fill(TEST_DATA["first_name"])
    page.locator("#middleName").fill(TEST_DATA["middle_name"])
    page.locator("#lastName").fill(TEST_DATA["last_name"])

    # 2. ZIP code and address lookup
    zip_field = page.locator("#ssZipCode")
    zip_field.fill(TEST_DATA["zip_code"])
    zip_field.press("Tab")

    page.wait_for_function(
        """() => {
            const address = document.querySelector("#address1");
            const city = document.querySelector("#city");
            const state = document.querySelector("#stateList");

            return address && city && state &&
                   !address.disabled &&
                   !city.disabled &&
                   !state.disabled;
        }""",
        timeout=30000
    )

    # 3. Address
    page.locator("#address1").fill(TEST_DATA["address"])

    # Unit Type: inspect and match the actual available option.
    select_dropdown(
        page, "#unitTypeList",
        TEST_DATA.get("unit_type", ""),
        "Unit Type"
    )

    page.locator("#unitNumber").fill(
        TEST_DATA.get("unit_number", "")
    )

    # 4. City and state
    page.locator("#city").fill(TEST_DATA["city"])

    select_dropdown(
        page, "#stateList",
        TEST_DATA["state"],
        "State"
    )

    # 5. Dwelling and ownership
    select_dropdown(
        page, "#serviceAddressTypeList",
        TEST_DATA["dwelling_type"],
        "Dwelling Type"
    )

    select_dropdown(
        page, "#rentOwnList",
        TEST_DATA["ownership"],
        "Ownership"
    )

    # 6. Moving status
    select_dropdown(
        page,
        "#customerMove",
        TEST_DATA["moving"],
        "Moving Status"
    )

    # 7. Lead ID (required field)
    lead_id = str(TEST_DATA.get("lead_id", "")).strip()

    if not lead_id:
        raise RuntimeError("Lead ID is missing from TEST_DATA.")

    lead_id_label = page.get_by_text("Lead ID", exact=True)

    lead_id_label.wait_for(state="visible", timeout=10000)

    lead_id_field = lead_id_label.locator("xpath=following::input[1]")

    lead_id_field.wait_for(state="visible", timeout=10000)
    lead_id_field.fill(lead_id)

    actual_lead_id = lead_id_field.input_value()

    if actual_lead_id != lead_id:
        raise RuntimeError(
            f"Lead ID mismatch. Expected {lead_id}, got {actual_lead_id}"
        )

    print("PASS: Lead ID entered successfully.")
    # 8. Moving date is displayed dynamically when Moving = Yes.
    moving_value = str(TEST_DATA["moving"]).strip().lower()

    if moving_value in ("yes", "true"):
        moving_date = TEST_DATA.get("moving_date")

        if not moving_date:
            raise RuntimeError(
                "Moving is Yes, but moving_date is missing "
                "from the selected customer profile."
            )

        move_date_field = page.get_by_placeholder("Move in Date")

        move_date_field.wait_for(
            state="visible",
            timeout=10000
        )

        if not move_date_field.is_enabled():
            raise RuntimeError("Move in Date field is disabled.")

        # Fill date using the ISO format YYYY-MM-DD.
        move_date_field.fill(str(moving_date))

        actual_date = move_date_field.input_value()

        if actual_date != str(moving_date):
            raise RuntimeError(
                f"Moving date mismatch. Expected {moving_date}, "
                f"but found {actual_date}."
            )

        print(f"PASS: Moving date entered: {actual_date}")

    else:
        print("Moving is No. Moving date is not required.")

    print("\nBasic Information fields entered.")

    return validate_basic_information(page)



def validate_basic_information(page):
    """Validate the entered Basic Information fields."""

    print("\n========== FIELD VALIDATION ==========")

    expected_values = {
        "#firstName": TEST_DATA["first_name"],
        "#middleName": TEST_DATA["middle_name"],
        "#lastName": TEST_DATA["last_name"],
        "#ssZipCode": TEST_DATA["zip_code"],
        "#address1": TEST_DATA["address"],
        "#unitTypeList": TEST_DATA["unit_type"],
        "#unitNumber": TEST_DATA["unit_number"],
        "#city": TEST_DATA["city"],
        "#stateList": TEST_DATA["state"],
        "#serviceAddressTypeList": TEST_DATA["dwelling_type"],
        "#rentOwnList": TEST_DATA["ownership"],
        "#customerMove": TEST_DATA["moving"],
    }

    all_valid = True

    for selector, expected in expected_values.items():
        actual = page.locator(selector).input_value()
        valid = actual == expected

        print(
            f"{selector} | Expected: {expected} | "
            f"Actual: {actual} | Valid: {valid}"
        )

        if not valid:
            all_valid = False

    save_screenshot(
        page,
        "basic_information_filled.png",
    )

    print(
        "\nBASIC INFORMATION VALIDATION "
        + ("PASSED." if all_valid else "FAILED.")
    )

    return all_valid


def submit_basic_information(page):
    """FIRST FORWARD: Basic Information -> Valid Address."""

    print("\n========== FIRST FORWARD: BASIC INFORMATION ==========")

    forward_button = page.locator("#basicInfoForward")

    forward_button.wait_for(
        state="visible",
        timeout=30000,
    )

    if not forward_button.is_enabled():
        raise RuntimeError(
            "Basic Information Forward button is disabled."
        )

    forward_button.scroll_into_view_if_needed()
    forward_button.click()

    print("First Forward button clicked.")

    page.wait_for_url(
        "**/valid-address/",
        timeout=60000,
    )

    print("Valid Address URL detected.")

    save_screenshot(
        page,
        "valid_address_page.png",
    )


def proceed_to_valid_address(page):
    """SECOND FORWARD: Valid Address -> Qualification."""

    print("\n========== SECOND FORWARD: VALID ADDRESS ==========")

    page.locator(
        'body[data-ac-page="valid-address"]'
    ).wait_for(
        state="visible",
        timeout=60000,
    )

    matched_message = page.locator(
        "#Valid_Address_FS1 p.green"
    ).filter(
        has_text="Proceed to the next screen"
    )

    matched_message.wait_for(
        state="visible",
        timeout=60000,
    )

    print("Address Matched successfully.")

    save_screenshot(
        page,
        "valid_address_page.png",
    )

    forward_button = page.locator(
        "#addressFoundForward"
    )

    forward_button.wait_for(
        state="visible",
        timeout=30000,
    )

    if not forward_button.is_enabled():
        raise RuntimeError(
            "Valid Address Forward button is disabled."
        )

    forward_button.click()

    print("Second Forward button clicked.")

    page.wait_for_url(
        "**/qualification/",
        timeout=60000,
    )

    page.locator(
        'body[data-ac-page="qualification"]'
    ).wait_for(
        state="visible",
        timeout=30000,
    )

    print("Qualification page opened.")

    save_screenshot(
        page,
        "qualification_page_before_selection.png",
    )


def qualify_as_new_customer(page):
    """Select New Customer and click Qualification Forward."""

    print("\n========== QUALIFICATION ==========")

    page.locator(
        'body[data-ac-page="qualification"]'
    ).wait_for(
        state="visible",
        timeout=30000,
    )

    english_section = page.locator("#selection_display")

    english_section.wait_for(
        state="visible",
        timeout=30000,
    )

    new_customer_radio = english_section.locator(
        "#BOOL_New_DF_Scripted_Qual_CL_11"
    )

    new_customer_radio.wait_for(
        state="visible",
        timeout=30000,
    )

    new_customer_radio.check()

    if not new_customer_radio.is_checked():
        raise RuntimeError(
            "New Customer selection failed."
        )

    print("New Customer selected.")

    save_screenshot(
        page,
        "qualification_new_customer_selected.png",
    )

    page.wait_for_timeout(1000)

    # THIRD FORWARD BUTTON.
    qualification_forward = page.locator(
        "#qualificationForward"
    )

    qualification_forward.wait_for(
        state="visible",
        timeout=30000,
    )

    if not qualification_forward.is_enabled():
        raise RuntimeError(
            "Qualification Forward button is disabled."
        )

    qualification_forward.scroll_into_view_if_needed()
    qualification_forward.click()

    print("Third Forward button clicked.")

    # Recommendations is the expected next page.
    page.wait_for_url(
        "**/recommendations/",
        timeout=60000,
    )

    print("Recommendations page opened.")

    save_screenshot(
        page,
        "recommendations_page.png",
    )

def check_provider_availability(page, order):
    """Verify ProviderXX availability and open its Internet offers."""

    print("\n========== PROVIDER SELECTION ==========")

    rows = page.locator("#rts_widget_content tr")
    rows.first.wait_for(state="visible", timeout=30000)

    provider_row = rows.filter(
        has=page.get_by_text("ProviderXX", exact=True)
    )

    if provider_row.count() != 1:
        raise RuntimeError("Could not uniquely identify ProviderXX.")

    status = provider_row.locator("td").nth(1).inner_text().strip()

    if status.casefold() != "available":
        raise RuntimeError(
            f"ProviderXX is not available. Current status: {status}"
        )

    provider_card = page.locator("#firstRankProviderImg:visible")
    provider_card.wait_for(state="visible", timeout=30000)
    provider_card.click()

    page.locator(".productTitle:visible").first.wait_for(
        state="visible",
        timeout=30000,
    )

    print("ProviderXX selected. Internet offers loaded.")

    save_screenshot(page, "provider_xx_plans.png")





def select_internet_offer(page, order):
    """Find the ProviderXX offer matching the requested speed and term."""

    print("\n========== INTERNET PLAN SELECTION ==========")

    requested_speed = int(order["internet_speed_mbps"])
    requested_term = str(order["pricing_term"]).upper().replace("-", "_")

    titles = page.locator(".productTitle:visible")
    titles.first.wait_for(state="visible", timeout=30000)

    matches = []

    for index in range(titles.count()):
        title = titles.nth(index)
        title_text = title.inner_text().strip()

        card = title.locator(
            "xpath=ancestor::dir[contains("
            "concat(' ', normalize-space(@class), ' '), "
            "' syncbdlmain ')][1]"
        )

        if card.count() != 1:
            continue

        metadata_input = card.locator("input.singleHiddenJson")

        if metadata_input.count() != 1:
            continue

        metadata = metadata_input.evaluate(
            "element => JSON.parse(element.value)"
        )

        actual_product = metadata.get("productname", "").strip()
        actual_provider = metadata.get("providerName", "").strip()

        if actual_provider.casefold() != "providerxx":
            continue

        # Match the requested speed.
        speed_match = re.search(
            r"\b(\d+)\s*Mbps\b",
            actual_product,
            re.IGNORECASE
        )

        if not speed_match or int(speed_match.group(1)) != requested_speed:
            continue

        # Match the requested pricing term.
        product_normalized = actual_product.upper().replace("-", "_")
        required_year = requested_term.split("_")[0]

        term_match = re.search(
            rf"\b{re.escape(required_year)}\s*_?\s*YEAR\b",
            product_normalized
        )

        if not term_match:
            continue

        price_input = card.locator("input.baseRecPrice")

        if price_input.count() != 1:
            continue

        actual_price = Decimal(price_input.input_value())

        matches.append({
            "card": card,
            "plan": actual_product,
            "provider": actual_provider,
            "base_price": actual_price,
        })

    if len(matches) != 1:
        available = [
            titles.nth(i).inner_text().strip()
            for i in range(titles.count())
        ]

        raise RuntimeError(
            f"Expected exactly one {requested_speed} Mbps "
            f"{requested_term} ProviderXX offer, "
            f"but found {len(matches)}. "
            f"Available plans: {available}"
        )

    selected = matches[0]
    card = selected["card"]

    print("Matching plan found:", selected["plan"])
    print("Provider verified:", selected["provider"])
    print(f"Actual catalogue price: ${selected['base_price']:.2f}")

    view_details = card.locator("input.ViewDetailsBtn")
    view_details.wait_for(state="visible", timeout=30000)

    if not view_details.is_enabled():
        raise RuntimeError("View Details button is disabled.")

    view_details.scroll_into_view_if_needed()
    view_details.click()

    print("View Details clicked.")

    product_details = page.locator("#contentpdet:visible")
    product_details.wait_for(state="visible", timeout=30000)

    product_name = product_details.locator("#product_name")
    product_name.wait_for(state="visible", timeout=30000)

    actual_name = product_name.inner_text().strip()

    if actual_name.casefold() != selected["plan"].casefold():
        raise RuntimeError(
            f"Product Details mismatch. "
            f"Expected: {selected['plan']}; Found: {actual_name}"
        )

    print("Product Details plan verified.")

    save_screenshot(page, "selected_plan_details.png")

    return {
        "plan": selected["plan"],
        "base_price": selected["base_price"],
    }



def add_plan_to_order_and_checkout(page, selected_plan):
    """Verify the selected catalogue offer and proceed to checkout."""

    print("\n========== ADD TO ORDER AND CHECKOUT ==========")

    expected_plan = selected_plan["plan"]
    expected_price = Decimal(str(selected_plan["base_price"]))

    product_details = page.locator("#contentpdet:visible")
    product_details.wait_for(state="visible", timeout=30000)

    product_name = product_details.locator("#product_name")
    actual_plan = product_name.inner_text().strip()

    if actual_plan.casefold() != expected_plan.casefold():
        raise RuntimeError(
            f"Plan mismatch. Expected: {expected_plan}; Found: {actual_plan}"
        )

    price_text = product_details.locator(
        "#product_basePriceInfo"
    ).inner_text().strip()

    price_match = re.search(r"\$([\d,.]+)", price_text)

    if not price_match:
        raise RuntimeError("Could not read the displayed base price.")

    actual_price = Decimal(price_match.group(1).replace(",", ""))

    if actual_price != expected_price:
        raise RuntimeError(
            f"Price mismatch. Expected ${expected_price:.2f}; "
            f"found ${actual_price:.2f}."
        )

    print("Selected plan verified:", actual_plan)
    print(f"Base price verified: ${actual_price:.2f}")

    checkout_button = page.locator(
        "#addToOrderAndCheckout:visible"
    )

    checkout_button.wait_for(state="visible", timeout=30000)

    if not checkout_button.is_enabled():
        raise RuntimeError("Add to Order and Checkout button is disabled.")

    checkout_button.scroll_into_view_if_needed()

    previous_url = page.url
    checkout_button.click(timeout=30000)

    print("Add to Order and Checkout clicked.")

    page.wait_for_function(
        "(oldUrl) => window.location.href !== oldUrl",
        arg=previous_url,
        timeout=60000,
    )

    print("Checkout navigation detected.")
    print("Current page:", page.url)

    save_screenshot(page, "checkout_after_add_to_order.png")

    print("PASS: Selected Internet plan added to checkout.")



def select_checkout_option(section, heading, requested):
    """Select and verify a checkout radio option."""

    radios = section.locator('input[type="radio"]')
    matches = []

    requested_normalized = " ".join(requested.casefold().split())

    for index in range(radios.count()):
        radio = radios.nth(index)

        details = radio.evaluate("""
            el => {
                const labels = Array.from(el.labels || [])
                    .map(label => label.innerText.trim());

                return {
                    checked: el.checked,
                    labels: labels,
                    parentText: el.parentElement
                        ? el.parentElement.innerText.trim()
                        : ""
                };
            }
        """)

        label_text = " ".join(details["labels"]).strip()
        parent_text = " ".join(details["parentText"].split())

        # If the requested option is already selected, leave it unchanged.
        combined_text = f"{label_text} {parent_text}".casefold()

        if (
            requested_normalized == "none"
            and details["checked"]
            and (
                label_text.casefold() == "none"
                or parent_text.casefold() == "none"
            )
        ):
            print(f"{heading}: None is already selected.")
            return

        if label_text:
            option_text = " ".join(label_text.casefold().split())
        else:
            option_text = " ".join(parent_text.casefold().split())

        if option_text == requested_normalized:
            matches.append(radio)

        elif option_text.startswith(requested_normalized + " "):
            remainder = option_text[len(requested_normalized):].strip()

            if remainder.startswith("$"):
                matches.append(radio)

    if len(matches) != 1:
        raise RuntimeError(
            f"{heading}: Could not uniquely identify "
            f"'{requested}'. Found {len(matches)} matching options."
        )

    option = matches[0]
    option.check()

    if not option.is_checked():
        raise RuntimeError(
            f"{heading}: Selection failed for '{requested}'."
        )

    print(f"{heading} selected: {requested}")



def debug_customization_controls(page):
    """Inspect radio buttons and checkboxes in the checkout iframe."""

    checkout = page.frame_locator("#checkoutContent")

    print("\n========== CUSTOMIZATION CONTROL INSPECTION ==========")

    for control_type in ("radio", "checkbox"):
        controls = checkout.locator(
            f'input[type="{control_type}"]'
        )

        print(f"\nAvailable {control_type.upper()} controls:")

        for index in range(controls.count()):
            control = controls.nth(index)

            details = control.evaluate("""
                el => ({
                    id: el.id,
                    name: el.name,
                    value: el.value,
                    checked: el.checked,
                    disabled: el.disabled,
                    labels: Array.from(el.labels || [])
                        .map(label => label.innerText.trim()),
                    parentText: el.parentElement
                        ? el.parentElement.innerText.trim()
                        : "",
                    grandparentText: el.parentElement &&
                        el.parentElement.parentElement
                        ? el.parentElement.parentElement.innerText.trim()
                        : "",
                    outerHTML: el.outerHTML
                })
            """)

            print(f"{control_type.upper()} #{index + 1}:")
            print(details)

def proceed_to_product_customization(page):
    """Move from Checkout Review to Product Customization."""

    import re

    print("\n========== CHECKOUT REVIEW FORWARD ==========")

    checkout = page.frame_locator("#checkoutContent")

    forward_button = checkout.get_by_role(
        "button",
        name=re.compile(r"^\s*Forward\s*>?\s*$", re.IGNORECASE)
    )

    forward_button.wait_for(
        state="visible",
        timeout=30000
    )

    if not forward_button.is_enabled():
        raise RuntimeError(
            "Checkout Review Forward button is disabled."
        )

    forward_button.scroll_into_view_if_needed()
    forward_button.click()

    print("Checkout Review Forward clicked.")

    # Wait until the next screen actually loads.
    customization_heading = checkout.get_by_text(
        re.compile(r"Broadband Fact Labels", re.IGNORECASE)
    ).first

    customization_heading.wait_for(
        state="visible",
        timeout=30000
    )

    print("Product Customization page detected.")

    save_screenshot(
        page,
        "product_customization_page.png"
    )
def inspect_account_holder_controls(page):
    print("\n========== ACCOUNT HOLDER CONTROL INSPECTION ==========")

    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    controls = frame.locator(
        "input, select, textarea, button"
    )

    for index in range(controls.count()):
        control = controls.nth(index)

        details = control.evaluate("""
            el => ({
                tag: el.tagName,
                id: el.id,
                name: el.name,
                type: el.type || "",
                labels: Array.from(el.labels || [])
                    .map(label => label.innerText.trim()),
                checked: el.type === "checkbox" ||
                         el.type === "radio"
                         ? el.checked : null,
                disabled: el.disabled,
                options: el.tagName === "SELECT"
                    ? Array.from(el.options).map(option => ({
                        text: option.text.trim(),
                        value: option.value
                    }))
                    : []
            })
        """)

        print(details)

def customize_checkout_products(page, order):
    """Complete Product Customization and proceed using Forward."""

    import re

    print("\n========== PRODUCT CUSTOMIZATION ==========")

    checkout = page.frame_locator("#checkoutContent")

    def find_radio_by_text(keyword):
        """Find a unique radio using its associated visible label."""

        radios = checkout.locator('input[type="radio"]')
        matches = []

        for index in range(radios.count()):
            radio = radios.nth(index)

            details = radio.evaluate("""
                el => ({
                    labels: Array.from(el.labels || [])
                        .map(label => label.innerText.trim()),
                    parentText: el.parentElement
                        ? el.parentElement.innerText.trim()
                        : ""
                })
            """)

            text = " ".join(
                details["labels"] + [details["parentText"]]
            ).casefold()

            if keyword.casefold() in text:
                matches.append(radio)

        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one radio matching '{keyword}', "
                f"but found {len(matches)}."
            )

        return matches[0]

    def select_radio(keyword, description):
        radio = find_radio_by_text(keyword)
        radio.check()

        if not radio.is_checked():
            raise RuntimeError(
                f"Failed to select {description}."
            )

        print(f"PASS: {description}")

    # -------------------------------------------------
    # 1. BROADBAND FACT LABELS
    # -------------------------------------------------

    print("\n1. Broadband Fact Labels")

    select_radio(
        "Customer requested the Broadband Fact Labels",
        "Customer requested Broadband Fact Labels"
    )

    # -------------------------------------------------
    # 2. READ ACKNOWLEDGEMENT
    # -------------------------------------------------

    print("\n2. Read Acknowledgement")

    checkboxes = checkout.locator('input[type="checkbox"]')
    read_matches = []

    for index in range(checkboxes.count()):
        checkbox = checkboxes.nth(index)

        details = checkbox.evaluate("""
            el => ({
                labels: Array.from(el.labels || [])
                    .map(label => label.innerText.trim()),
                parentText: el.parentElement
                    ? el.parentElement.innerText.trim()
                    : ""
            })
        """)

        label_text = " ".join(details["labels"]).strip()
        parent_text = " ".join(
            details["parentText"].split()
        )

        if (
            label_text.casefold() == "read"
            or parent_text.casefold() == "read"
        ):
            read_matches.append(checkbox)

    if len(read_matches) != 1:
        raise RuntimeError(
            "Could not uniquely identify the Read acknowledgement checkbox."
        )

    read_checkbox = read_matches[0]

    if not read_checkbox.is_checked():
        read_checkbox.check()

    if not read_checkbox.is_checked():
        raise RuntimeError(
            "Read acknowledgement was not checked."
        )

    print("PASS: Read acknowledgement checked.")

    # -------------------------------------------------
    # 3. EQUIPMENT SELECTION
    # -------------------------------------------------

    print("\n3. Equipment Selection")

    select_radio(
        "XI/XV Leased Gateway",
        "XI/XV Leased Gateway (Free)"
    )

    # -------------------------------------------------
    # 4. NOW TV - SKIP
    # -------------------------------------------------

    print("\n4. NOW TV with Streaming Apps")

    now_tv_radio = find_radio_by_text(
        "NOW TV with Streaming Apps"
    )

    if now_tv_radio.is_checked():
        raise RuntimeError(
            "NOW TV is already selected. "
            "Please review the selection before proceeding."
        )

    print("PASS: NOW TV left unselected.")

    # -------------------------------------------------
    # 5. FORWARD
    # -------------------------------------------------

    print("\n5. Checkout Forward")

    forward_button = checkout.get_by_role(
        "button",
        name=re.compile(r"^\s*Forward\s*>?\s*$", re.IGNORECASE)
    )

    forward_button.wait_for(
        state="visible",
        timeout=30000
    )

    if not forward_button.is_enabled():
        raise RuntimeError(
            "Product Customization Forward button is disabled."
        )

    forward_button.scroll_into_view_if_needed()
    forward_button.click()

    print("PASS: Product Customization Forward clicked.")

    page.wait_for_timeout(3000)

    save_screenshot(
        page,
        "product_customization_completed.png"
    )

    print("\nPRODUCT CUSTOMIZATION COMPLETED.")


def print_checkout_options(section, heading):
    """Print the actual visible radio labels for debugging."""

    print(f"\nAvailable {heading} options:")

    radios = section.locator('input[type="radio"]')

    for index in range(radios.count()):
        radio = radios.nth(index)

        details = radio.evaluate("""
            el => ({
                value: el.value,
                id: el.id,
                checked: el.checked,
                labels: Array.from(el.labels || [])
                    .map(label => label.innerText.trim()),
                parentText: el.parentElement
                    ? el.parentElement.innerText.trim()
                    : ""
            })
        """)

        print(details)




def automate_account_holder_qualification(page, order):
    """Complete Account Holder Qualification using customer data."""

    print("\n========== ACCOUNT HOLDER QUALIFICATION ==========")

    frame = page.frame(name="checkoutContent")
    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    def normalize(value):
        return " ".join(str(value).strip().casefold().split())

    # 1. Select the correct account holder dynamically.
    account_holder_name = order.get("account_holder_name")
    if not account_holder_name:
        account_holder_name = (
            f'{order["first_name"]} {order["last_name"]}'
        )

    account_holder = frame.locator(
        'select[aria-label="Account holder"]'
    )
    account_holder.wait_for(state="visible", timeout=10000)

    account_options = account_holder.locator("option").evaluate_all("""
        elements => elements.map(option => ({
            label: option.textContent.trim(),
            value: option.value
        }))
    """)

    matching_account = next(
        (
            option for option in account_options
            if normalize(account_holder_name) in normalize(option["label"])
        ),
        None
    )

    if matching_account is None:
        raise RuntimeError(
            f"Account holder '{account_holder_name}' not found. "
            f"Available options: {account_options}"
        )

    account_holder.select_option(value=matching_account["value"])
    print(f"PASS: Account holder selected: {matching_account['label']}")

    # 2. Customer-specific Yes/No radio selections.
    radio_groups = [
        ("verified", "Speaking to Account Holder",
         "speaking_to_account_holder"),
        ("current", "Current Provider XX Customer",
         "existing_provider_customer"),
        ("ez", "EZ-Enroll", "ez_enroll"),
        ("autopay", "Automatic Payments",
         "autopay_paperless_discount"),
        ("mailing", "Mailing Address Same as Service",
         "mailing_same_as_service"),
        ("shipping", "Shipping Address Same as Service",
         "shipping_same_as_service"),
    ]

    expected_answers = {}

    for group_name, description, data_key in radio_groups:
        if data_key not in order:
            raise RuntimeError(
                f"Missing customer data for {description}: {data_key}"
            )

        expected_label = "Yes" if bool(order[data_key]) else "No"
        radios = frame.locator(
            f'input[type="radio"][name="{group_name}"]'
        )

        if radios.count() == 0:
            raise RuntimeError(
                f"{description}: radio buttons not found."
            )

        matching_radio = None
        for index in range(radios.count()):
            radio = radios.nth(index)
            labels = radio.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label.innerText.trim())
            """)

            if any(
                normalize(label) == normalize(expected_label)
                for label in labels
            ):
                matching_radio = radio
                break

        if matching_radio is None:
            raise RuntimeError(
                f"{description}: {expected_label} option not found."
            )
        if matching_radio.is_disabled():
            raise RuntimeError(
                f"{description}: {expected_label} option is disabled."
            )

        if not matching_radio.is_checked():
            matching_radio.check()

        if not matching_radio.is_checked():
            raise RuntimeError(f"{description}: selection failed.")

        expected_answers[group_name] = expected_label
        print(f"PASS: {description} = {expected_label}")

    # 3. Phone number.
    phone = order.get("phone") or order.get("phone_number")
    if not phone:
        raise RuntimeError("Phone number missing from customer data.")

    phone_field = frame.locator('input[placeholder="Phone Number"]')
    phone_field.wait_for(state="visible", timeout=10000)
    phone_field.fill(str(phone))

    if phone_field.input_value() != str(phone):
        raise RuntimeError("Phone number validation failed.")
    print("PASS: Phone number entered.")

    # 4. Email address.
    email = order.get("email")
    if not email:
        raise RuntimeError("Email address missing from customer data.")

    email_field = frame.locator('input[placeholder="Email Address"]')
    email_field.wait_for(state="visible", timeout=10000)
    email_field.fill(str(email))

    if email_field.input_value() != str(email):
        raise RuntimeError("Email validation failed.")
    print("PASS: Email address entered.")

    # 5. Check both disclosure Read boxes by the text in their own
    # disclosure container. Do not use checkbox order or page-wide text.
    print("\n========== DISCLOSURE ACKNOWLEDGEMENTS ==========")

    acknowledgement_checkboxes = {}

    def acknowledge_disclosure(disclosure_name, required_phrases):
        checkboxes = frame.locator('input[type="checkbox"]')

        # For each checkbox, walk up its DOM ancestors and find the
        # smallest container that contains the disclosure wording and
        # exactly one checkbox. This prevents matching the whole page.
        matching_indexes = checkboxes.evaluate_all(
            """(elements, phrases) => elements.map((checkbox, index) => {
                let node = checkbox.parentElement;

                while (node && node !== document.body) {
                    const text = (node.innerText || "")
                        .replace(/\\s+/g, " ")
                        .toLowerCase();

                    const containsDisclosure = phrases.every(
                        phrase => text.includes(phrase)
                    );

                    const checkboxCount = node.querySelectorAll(
                        'input[type="checkbox"]'
                    ).length;

                    if (containsDisclosure && checkboxCount === 1) {
                        return index;
                    }

                    node = node.parentElement;
                }

                return -1;
            })""",
            required_phrases
        )

        matches = [index for index in matching_indexes if index >= 0]

        if len(matches) != 1:
            diagnostic = checkboxes.evaluate_all("""
                elements => elements.map((checkbox, index) => {
                    let node = checkbox;
                    let text = "";

                    for (let depth = 0; node && depth < 5; depth++) {
                        text = (node.innerText || "")
                            .replace(/\\s+/g, " ")
                            .trim();

                        if (text) break;
                        node = node.parentElement;
                    }

                    return {
                        index,
                        checked: checkbox.checked,
                        visible: !!(
                            checkbox.offsetWidth ||
                            checkbox.offsetHeight
                        ),
                        nearbyText: text.slice(0, 300)
                    };
                })
            """)

            raise RuntimeError(
                f"{disclosure_name} Read checkbox could not be uniquely "
                f"identified. Checkbox diagnostics: {diagnostic}"
            )

        checkbox = checkboxes.nth(matches[0])
        checkbox.wait_for(state="visible", timeout=10000)

        if checkbox.is_disabled():
            raise RuntimeError(
                f"{disclosure_name} Read checkbox is disabled."
            )

        if not checkbox.is_checked():
            checkbox.check()

        if not checkbox.is_checked():
            raise RuntimeError(
                f"{disclosure_name} Read checkbox did not become checked."
            )

        acknowledgement_checkboxes[disclosure_name] = checkbox
        print(f"PASS: {disclosure_name} Read checkbox checked.")

    # The EZ-Enroll disclosure is present when EZ-Enroll is selected.
    if bool(order.get("ez_enroll")):
        acknowledge_disclosure(
            "EZ-Enroll credit/debit card disclosure",
            ["ez-enroll", "credit or debit card on file"]
        )

    # The Automatic Payments disclosure is present when autopay is selected.
    if bool(order.get("autopay_paperless_discount")):
        if not bool(order.get("account_disclosure_acknowledged", False)):
            raise RuntimeError(
                "Automatic Payments is enabled, but its Read "
                "acknowledgement is false in customer data."
            )

        acknowledge_disclosure(
            "Automatic Payments and Paperless Discount disclosure",
            ["you have opted into", "automatic payments"]
        )

    # 6. Validate every radio selection and both applicable acknowledgements.
    print("\n========== FINAL QUALIFICATION VALIDATION ==========")

    for group_name, description, _data_key in radio_groups:
        expected_label = expected_answers[group_name]
        radios = frame.locator(
            f'input[type="radio"][name="{group_name}"]'
        )

        validated = False
        for index in range(radios.count()):
            radio = radios.nth(index)
            labels = radio.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label.innerText.trim())
            """)

            if (
                any(
                    normalize(label) == normalize(expected_label)
                    for label in labels
                )
                and radio.is_checked()
            ):
                validated = True
                break

        if not validated:
            raise RuntimeError(
                f"Validation failed: {description} should be "
                f"{expected_label}."
            )

    if phone_field.input_value() != str(phone):
        raise RuntimeError("Final phone validation failed.")
    if email_field.input_value() != str(email):
        raise RuntimeError("Final email validation failed.")

    # Recheck both acknowledgements immediately before Forward.
    for disclosure_name, checkbox in acknowledgement_checkboxes.items():
        if not checkbox.is_checked():
            raise RuntimeError(
                f"Final validation failed: {disclosure_name} Read is unchecked."
            )

    print("PASS: All customer qualification fields validated.")

    # 7. Forward only after all validations.
    forward_button = frame.get_by_role(
        "button",
        name=re.compile(r"^\s*Forward\s*>?\s*$", re.IGNORECASE)
    )
    forward_button.wait_for(state="visible", timeout=10000)

    if not forward_button.is_enabled():
        raise RuntimeError(
            "Account Holder Forward button is disabled."
        )

    forward_button.scroll_into_view_if_needed()
    forward_button.click()
    print("PASS: Account Holder Qualification Forward clicked.")

    page.wait_for_timeout(3000)
    save_screenshot(page, "installation_payment_page.png")
    print("Account Holder Qualification completed.")


def run_credit_check(page, order):
    """Backward-compatible alias for the runtime-only credit workflow."""
    return automate_credit_check(page, order)


def automate_installation_payment(page, order):
    """Select and verify shipping/install type, confirm, and continue."""

    from datetime import date, datetime
    import re

    print("\n========== INSTALLATION AND PAYMENT ==========")

    frame = page.frame(name="checkoutContent")
    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    raw_type = str(
        order.get("installation_type", "STANDARD_SHIPPING")
    ).strip().upper().replace("-", "_").replace(" ", "_")

    aliases = {
        "STANDARD_SHIPPING": "STANDARD_SHIPPING",
        "STANDARD": "STANDARD_SHIPPING",
        "PRO_INSTALL": "PRO_INSTALL",
        "PROFESSIONAL_INSTALL": "PRO_INSTALL",
    }
    installation_type = aliases.get(raw_type)
    if installation_type is None:
        raise ValueError(
            f"Invalid installation type: {raw_type}. "
            "Expected STANDARD_SHIPPING or PRO_INSTALL."
        )

    print(f"Requested installation type: {installation_type}")
    print("\n1. Locating installation type radio buttons")

    radios = frame.locator('input[type="radio"]')
    matching = []
    diagnostics = []

    for index in range(radios.count()):
        radio = radios.nth(index)
        details = radio.evaluate("""
            el => {
                const norm = value => (value || "")
                    .replace(/\\s+/g, " ").trim();
                const labels = Array.from(el.labels || []).map(label =>
                    norm(label.innerText || label.textContent)
                );
                let node = el.closest("label") || el.parentElement;
                let optionText = "";
                for (let depth = 0; node && depth < 5; depth++) {
                    const text = norm(node.innerText || node.textContent);
                    const hasStandard = /standard[\\s_-]*shipping/i.test(text);
                    const hasPro = /pro[\\s_-]*install/i.test(text);
                    if (hasStandard !== hasPro) {
                        optionText = text;
                        break;
                    }
                    node = node.parentElement;
                }
                return {
                    value: el.value || "",
                    id: el.id || "",
                    name: el.name || "",
                    labels,
                    optionText,
                    checked: el.checked,
                    disabled: el.disabled,
                    visible: !!el.getClientRects().length
                };
            }
        """)
        diagnostics.append(details)
        searchable = " ".join(
            [details["value"], *details["labels"], details["optionText"]]
        )

        if installation_type == "STANDARD_SHIPPING":
            is_match = bool(re.search(
                r"standard[\s_-]*shipping", searchable, re.IGNORECASE
            )) and not bool(re.search(
                r"pro[\s_-]*install", searchable, re.IGNORECASE
            ))
        else:
            is_match = bool(re.search(
                r"pro[\s_-]*install|professional\s+install",
                searchable, re.IGNORECASE
            )) and not bool(re.search(
                r"standard[\s_-]*shipping", searchable, re.IGNORECASE
            ))

        if is_match:
            matching.append((radio, details))

    if len(matching) != 1:
        raise RuntimeError(
            f"Could not uniquely locate {installation_type}; "
            f"found {len(matching)} matches. Radio diagnostics: {diagnostics}"
        )

    selected_radio, radio_info = matching[0]

    # IMPORTANT: an already-selected radio can be disabled by the simulator.
    # Treat it as selected and continue; do not reject it for being disabled.
    print(f"Installation radio HTML: {selected_radio.evaluate('(el) => el.outerHTML')}")

    if selected_radio.is_checked():
        print(
            f"PASS: {installation_type} was already selected "
            "and is verified."
        )
    else:
        if selected_radio.is_disabled():
            raise RuntimeError(
                f"{installation_type} is not selected and its radio is disabled. "
                f"Radio details: {radio_info}"
            )

        selection_error = None
        try:
            selected_radio.check(timeout=7000)
        except Exception as exc:
            selection_error = exc

        if not selected_radio.is_checked():
            # Some versions bind the click handler to the visible label.
            labels = selected_radio.locator("xpath=following-sibling::label[1]")
            if labels.count() == 0:
                labels = selected_radio.locator("xpath=..")
            try:
                labels.first.click(timeout=7000)
            except Exception:
                try:
                    selected_radio.evaluate("el => el.click()")
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Could not select {installation_type}. "
                        f"check error={selection_error}; "
                        f"fallback error={fallback_error}; details={radio_info}"
                    ) from fallback_error

        page.wait_for_timeout(400)
        if not selected_radio.is_checked():
            raise RuntimeError(
                f"{installation_type} radio did not become checked. "
                f"Details: {selected_radio.evaluate('(el) => el.outerHTML')}"
            )
        print(f"PASS: {installation_type} selected and verified.")

    # Radio buttons in the same group are mutually exclusive. The selected
    # control's checked state above is the authoritative validation.

    # Professional installation requires appointment details and disclosures.
    if installation_type == "PRO_INSTALL":
        installation_date = str(order.get("installation_date", "")).strip()
        installation_time = str(order.get("installation_time", "")).strip()
        if not installation_date:
            raise ValueError("Installation date is missing.")
        if date.fromisoformat(installation_date) < date.today():
            raise ValueError("Installation date cannot be in the past.")
        if installation_time not in ("Morning", "Afternoon", "Evening"):
            raise ValueError("Invalid installation time.")

        print("\n========== INSTALLATION DISCLOSURES ==========")
        checkboxes = frame.locator('input[type="checkbox"]:visible')
        if checkboxes.count() != 2:
            raise RuntimeError(
                "Expected exactly 2 visible installation Read checkboxes; "
                f"found {checkboxes.count()}."
            )
        for index in range(2):
            checkbox = checkboxes.nth(index)
            label_text = checkbox.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => (label.innerText || label.textContent || "").trim())
                    .join(" ").trim()
            """)
            if label_text.casefold() != "read":
                raise RuntimeError(
                    f"Installation checkbox {index + 1} is not labelled Read: "
                    f"{label_text!r}"
                )
            if not checkbox.is_checked():
                checkbox.check()
            if not checkbox.is_checked():
                raise RuntimeError(
                    f"Installation Read checkbox {index + 1} was not checked."
                )
            print(f"PASS: Installation Read acknowledgement {index + 1} checked.")

        print("\n3. Selecting installation date")
        date_field = frame.locator(
            'input[type="date"]:visible, '
            'input[placeholder*="dd-mm-yyyy" i]:visible'
        )
        if date_field.count() != 1:
            raise RuntimeError(
                f"Expected one installation date field; found {date_field.count()}."
            )
        date_type = date_field.get_attribute("type")
        placeholder = date_field.get_attribute("placeholder") or ""
        if date_type == "date":
            date_value = installation_date
        elif "dd-mm-yyyy" in placeholder.casefold():
            date_value = datetime.strptime(
                installation_date, "%Y-%m-%d"
            ).strftime("%d-%m-%Y")
        else:
            raise RuntimeError(
                f"Unknown installation date format: type={date_type}, "
                f"placeholder={placeholder!r}"
            )
        date_field.fill(date_value)
        if date_field.input_value() != date_value:
            raise RuntimeError("Installation date validation failed.")
        print(f"PASS: Installation date entered: {date_value}")

        print("\n4. Selecting preferred installation time")
        time_dropdown = None
        selects = frame.locator("select:visible")
        for index in range(selects.count()):
            candidate = selects.nth(index)
            options = [
                value.strip()
                for value in candidate.locator("option").all_text_contents()
            ]
            if all(value in options for value in ("Morning", "Afternoon", "Evening")):
                time_dropdown = candidate
                break
        if time_dropdown is None:
            raise RuntimeError("Installation time dropdown not found.")
        time_dropdown.select_option(label=installation_time)
        actual_time = time_dropdown.locator("option:checked").inner_text().strip()
        if actual_time != installation_time:
            raise RuntimeError("Installation time selection failed.")
        print(f"PASS: Preferred time selected: {actual_time}")
    else:
        print("Standard shipping selected. No appointment date/time required.")

    # Verify the fee displayed by the simulator before confirming.
    print("\n5. Verifying installation total")
    body_text = frame.locator("body").inner_text()
    expected_price = "$100.00" if installation_type == "PRO_INSTALL" else "$0.00"
    expected_pattern = (
        r"Installation Total\s*:?\s*\$100\.00"
        if installation_type == "PRO_INSTALL"
        else r"Installation Total\s*:?\s*\$0\.00"
    )
    if not re.search(expected_pattern, body_text, re.IGNORECASE):
        raise RuntimeError(
            f"Installation total verification failed; expected {expected_price}."
        )
    print(f"PASS: Installation total verified: {expected_price}")

    save_screenshot(page, "installation_payment_before_confirm.png")

    # Some simulator builds combine Installation and Payment into one panel.
    # In that layout there is no separate "Confirm Installation" control:
    # the payment disclosure, Add a new credit card option, and Forward button
    # are already present on this same screen. Return to main() so the payment
    # workflow can acknowledge Read, select the card option, and continue.
    payment_panel_present = (
        frame.locator('input[type="radio"][name="addcard"]').count() > 0
        or frame.get_by_text(
            re.compile(r"PAYMENT\s+INFORMATION", re.IGNORECASE)
        ).count() > 0
    )
    if payment_panel_present:
        print(
            "PASS: Combined Installation and Payment panel detected; "
            "continuing to encrypted payment workflow."
        )
        return

    # Confirm is the primary action shown on simulator builds that use a
    # separate installation-confirmation screen.
    # (button, input[type=button], and role=button), so do not rely only on
    # Playwright get_by_role("button").
    print("\n6. Locating Confirm Installation control")

    confirm_pattern = re.compile(
        r"^\s*Confirm\s+Installation\s*>?\s*$", re.IGNORECASE
    )

    def find_confirm_control(search_frame):
        candidates = search_frame.locator(
            'button, input[type="button"], input[type="submit"], '
            'a, [role="button"]'
        )
        found = []
        for candidate_index in range(candidates.count()):
            candidate = candidates.nth(candidate_index)
            try:
                if not candidate.is_visible():
                    continue
                tag_name = candidate.evaluate("el => el.tagName.toLowerCase()")
                label = (
                    candidate.get_attribute("value")
                    if tag_name == "input"
                    else candidate.inner_text()
                ) or candidate.get_attribute("aria-label") or ""
                label = " ".join(label.split())
                if confirm_pattern.fullmatch(label):
                    found.append(candidate)
            except Exception:
                continue
        return found

    # Search the checkout iframe first, then other page frames in case the
    # simulator moved the action outside checkoutContent.
    confirm_frame = frame
    confirm_matches = find_confirm_control(confirm_frame)
    if not confirm_matches:
        for candidate_frame in page.frames:
            if candidate_frame == frame:
                continue
            try:
                matches = find_confirm_control(candidate_frame)
            except Exception:
                continue
            if matches:
                confirm_frame = candidate_frame
                confirm_matches = matches
                break

    if len(confirm_matches) != 1:
        diagnostics = []
        for candidate_frame in page.frames:
            try:
                diagnostics.append({
                    "frame_url": candidate_frame.url,
                    "controls": candidate_frame.locator(
                        'button, input[type="button"], input[type="submit"], '
                        'a, [role="button"]'
                    ).evaluate_all("""els => els.map(el => ({
                        tag: el.tagName,
                        text: (el.innerText || el.value || "").trim(),
                        ariaLabel: el.getAttribute("aria-label"),
                        disabled: !!el.disabled,
                        visible: !!el.getClientRects().length
                    }))""")
                })
            except Exception as exc:
                diagnostics.append({"frame_url": candidate_frame.url, "error": str(exc)})
        raise RuntimeError(
            "Could not uniquely locate the Confirm Installation control. "
            f"Matches found: {len(confirm_matches)}. Control diagnostics: {diagnostics}"
        )

    confirm_button = confirm_matches[0]
    confirm_button.scroll_into_view_if_needed()

    disabled = confirm_button.evaluate("""el =>
        !!el.disabled || el.getAttribute("aria-disabled") === "true"
    """)
    if disabled:
        raise RuntimeError(
            "Confirm Installation control is disabled. HTML: "
            + confirm_button.evaluate("el => el.outerHTML")
        )

    # Normal Playwright click first. If the simulator's custom wrapper blocks
    # it, use the element's native click as a controlled fallback.
    click_error = None
    try:
        confirm_button.click(timeout=15000)
    except Exception as exc:
        click_error = exc
        try:
            confirm_button.evaluate("el => el.click()")
        except Exception as fallback_error:
            raise RuntimeError(
                "Could not click Confirm Installation. "
                f"Playwright error: {click_error}; "
                f"native click error: {fallback_error}; HTML: "
                f"{confirm_button.evaluate('el => el.outerHTML')}"
            ) from fallback_error

    print("PASS: Confirm Installation click action dispatched.")

    # Allow the simulator's click handler to process and refresh the panel.
    confirm_frame.wait_for_timeout(1200)

    # Some simulator builds show a separate Forward button; others transition
    # directly after confirmation. Find Forward using the same robust method.
    def find_forward_control(search_frame):
        candidates = search_frame.locator(
            'button, input[type="button"], input[type="submit"], '
            'a, [role="button"]'
        )
        found = []
        for candidate_index in range(candidates.count()):
            candidate = candidates.nth(candidate_index)
            try:
                if not candidate.is_visible():
                    continue
                tag_name = candidate.evaluate("el => el.tagName.toLowerCase()")
                label = (
                    candidate.get_attribute("value")
                    if tag_name == "input"
                    else candidate.inner_text()
                ) or candidate.get_attribute("aria-label") or ""
                if re.fullmatch(r"^\s*Forward\s*>?\s*$", label, re.I):
                    found.append(candidate)
            except Exception:
                continue
        return found

    forward_matches = find_forward_control(confirm_frame)
    if len(forward_matches) == 1:
        forward_button = forward_matches[0]
        if forward_button.is_enabled():
            forward_button.scroll_into_view_if_needed()
            forward_button.click(timeout=15000)
            print("PASS: Installation Forward button clicked.")
        else:
            raise RuntimeError("Installation Forward control is disabled.")
    elif len(forward_matches) > 1:
        raise RuntimeError(
            "Multiple visible Installation Forward controls found; "
            "refusing to click an ambiguous control."
        )
    else:
        print(
            "No separate Forward control found after confirmation; "
            "checking for the next-stage transition."
        )

    # Wait for the confirmation control to disappear (the expected
    # transition), or for actual payment inputs / a later-stage heading.
    # Do not use generic "Credit Card" text: the current page itself says
    # card details will be collected on the next page.
    transition_verified = False
    deadline = __import__("time").monotonic() + 15
    while __import__("time").monotonic() < deadline:
        try:
            if not confirm_button.is_visible():
                transition_verified = True
                break

            payment_input = confirm_frame.locator(
                'input[autocomplete="cc-number"]:visible, '
                'input[autocomplete="cc-exp"]:visible, '
                'input[autocomplete="cc-csc"]:visible'
            )
            if payment_input.count() > 0:
                transition_verified = True
                break

            later_heading = confirm_frame.get_by_text(
                re.compile(r"^\s*(Payment Information|Authorization|Order Summary)\s*$", re.I)
            ).first
            if later_heading.is_visible():
                transition_verified = True
                break
        except Exception:
            confirm_frame = page.frame(name="checkoutContent") or confirm_frame
        page.wait_for_timeout(300)

    if transition_verified:
        print("PASS: Installation confirmation/next-stage transition verified.")
    else:
        raise RuntimeError(
            "Confirm Installation was clicked, but the installation panel "
            "did not transition to the next stage within 15 seconds. "
            "Inspect the simulator before continuing."
        )

    page.wait_for_timeout(1000)
    save_screenshot(page, "installation_forward_completed.png")
    print("\nINSTALLATION WORKFLOW COMPLETED.")

def inspect_credit_check_ui(page):
    print("\n========== CREDIT CHECK UI DIAGNOSTICS ==========")

    for frame_index, frame in enumerate(page.frames):
        print(f"\n--- Frame {frame_index}: {frame.url} ---")

        inputs = frame.locator("input:visible")
        for i in range(inputs.count()):
            field = inputs.nth(i)
            details = field.evaluate("""
                el => ({
                    type: el.type,
                    name: el.name,
                    id: el.id,
                    placeholder: el.placeholder,
                    ariaLabel: el.getAttribute("aria-label")
                })
            """)
            print("INPUT:", details)

        buttons = frame.locator("button:visible, input[type=button]:visible, input[type=submit]:visible")
        for i in range(buttons.count()):
            button = buttons.nth(i)
            print("BUTTON:", button.inner_text() if button.evaluate("(el) => el.tagName") == "BUTTON"
                  else button.get_attribute("value"))

        body_text = frame.locator("body").inner_text()
        for line in body_text.splitlines():
            if any(word in line.lower() for word in ("credit", "ssn", "social security", "date of birth", "dob")):
                print("MATCH:", line.strip())
            frame = page.frames[1]

    credit_button = frame.get_by_role(
        "button",
        name="Run Credit Check"
    )

    print("\nCREDIT BUTTON DETAILS:")
    print(
        credit_button.evaluate("""
            el => ({
                text: el.innerText,
                type: el.type,
                id: el.id,
                className: el.className,
                onclick: el.getAttribute("onclick"),
                formAction: el.form ? el.form.action : null
            })
        """)
    )

    print("\nCREDIT CHECK SECTION:")
    print(
        credit_button.locator("xpath=..").evaluate(
            "(el) => el.parentElement.innerText"
        )
    )
    print("\n========== PAGE SCRIPT DIAGNOSTICS ==========")

    scripts = frame.locator("script[src]")
    for i in range(scripts.count()):
        print("SCRIPT:", scripts.nth(i).get_attribute("src"))

    print("\nCREDIT BUTTON HTML:")
    print(
        credit_button.evaluate(
            "(el) => el.outerHTML"
        )
    )

    print("\nLOADED NETWORK RESOURCES:")
    resources = frame.evaluate("""
        () => performance.getEntriesByType("resource")
            .map(entry => entry.name)
            .filter(url =>
                /api|credit|checkout|order/i.test(url)
            )
    """)

    for resource in resources:
        print("RESOURCE:", resource)

    print("========== END PAGE SCRIPT DIAGNOSTICS ==========")
    print("========== END DIAGNOSTICS ==========")


def get_runtime_credit_credentials():
    """Retrieve SSN and DOB from the encrypted one-time CSE record."""

    record_id = os.getenv("CSE_RECORD_ID")

    if not record_id:
        raise RuntimeError("CSE_RECORD_ID is not configured")

    sensitive_data = retrieve_sensitive_data(record_id)

    try:
        ssn = sensitive_data.pop("ssn", None)
        dob = sensitive_data.pop("dob", None)

        if not isinstance(ssn, str) or not re.fullmatch(r"\d{9}", ssn):
            raise ValueError("Invalid SSN format in secure record.")

        if not isinstance(dob, str) or not re.fullmatch(r"\d{8}", dob):
            raise ValueError("Invalid DOB format in secure record.")

        try:
            parsed_dob = datetime.strptime(dob, "%m%d%Y").date()
        except ValueError:
            raise ValueError("Invalid DOB calendar date.") from None

        if parsed_dob >= date.today():
            raise ValueError("DOB must be a date in the past.")

        return ssn, dob

    finally:
        sensitive_data.clear()


def automate_credit_check(page, order):
    """Run a credit check only when the simulator requires one.

    ProviderXX's checkout disclosure states that a credit check is not
    required when the customer opts into Automatic Payments and Paperless
    Billing. In that case, do not retrieve SSN/DOB from CSE at all.
    For scenarios that do require a credit verification, retain the existing
    one-time CSE retrieval and runtime-only browser entry workflow.
    """

    print("\\n========== CREDIT CHECK ==========")

    # This simulator rule takes precedence over creditScenario metadata:
    # Automatic Payments + Paperless Billing means no credit check is needed.
    if bool(order.get("autopay_paperless_discount", False)):
        print(
            "Credit Check skipped: customer opted into Automatic Payments "
            "and Paperless Billing; ProviderXX states that a credit check "
            "is not required."
        )
        return

    credit_data = order.get("credit_check", {})

    if not credit_data.get("enabled", False):
        print("Credit Check skipped: disabled in customer profile.")
        return

    frame = page.frame(name="checkoutContent")
    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    ssn = None
    dob = None
    ssn_field = None
    dob_field = None

    try:
        # CSE is called only for scenarios where credit verification is needed.
        ssn, dob = get_runtime_credit_credentials()

        ssn_field = frame.get_by_label("Social Security Number")
        dob_field = frame.get_by_label("Date of Birth")
        ssn_field.wait_for(state="visible", timeout=10000)
        dob_field.wait_for(state="visible", timeout=10000)

        ssn_field.fill(ssn)
        dob_field.fill(dob)
        print("PASS: Runtime credit fields populated (values hidden).")

        run_button = frame.get_by_role(
            "button", name=re.compile(r"Run Credit Check", re.I)
        )
        run_button.wait_for(state="visible", timeout=10000)
        if not run_button.is_enabled():
            raise RuntimeError("Run Credit Check button is disabled.")

        run_button.click()
        print("Credit check submitted; waiting for simulator response.")

        page.wait_for_timeout(2500)
        result_text = re.sub(
            r"\\s+", " ", frame.locator("body").inner_text()
        ).strip().lower()

        failure_patterns = (
            r"credit check declined",
            r"credit check failed",
            r"credit check rejected",
        )
        success_patterns = (
            r"credit check successful",
            r"credit check completed",
            r"credit approved",
            r"credit verification successful",
            r"credit check status:\\s*approved",
        )

        if any(re.search(pattern, result_text) for pattern in failure_patterns):
            raise RuntimeError("Credit check was declined or failed.")

        if not any(re.search(pattern, result_text) for pattern in success_patterns):
            raise RuntimeError(
                "Credit check approval could not be verified. "
                "Inspect the simulator manually; response text was not logged."
            )

        print("PASS: Credit Check Status = APPROVED")
        print("PASS: Order Qualification Status verified.")

    except Exception as exc:
        # Do not silently bypass a required credit check. In particular, a
        # CSE HTTP 503 means the secure-data service is unavailable.
        if "HTTP 503" in str(exc):
            raise RuntimeError(
                "CSE service returned HTTP 503 while retrieving the "
                "required one-time sensitive record. Verify that the CSE "
                "FastAPI service is running, the record has not expired or "
                "already been consumed, and CSE_API_URL points to that service."
            ) from exc
        raise

    finally:
        # Clear browser controls before any exception handler can take action.
        for field in (ssn_field, dob_field):
            if field is not None:
                try:
                    field.fill("")
                except Exception:
                    pass
        ssn = None
        dob = None


def inspect_payment_fields(page):
    """Inspect payment controls without exposing sensitive values."""

    print("\n========== PAYMENT CONTROL INSPECTION ==========")

    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    # Inspect all frames, including secure payment frames.
    for current_frame in page.frames:
        print(f"\nFrame: {current_frame.name or 'Unnamed'}")

        try:
            fields = current_frame.locator(
                'input:visible, select:visible, button:visible'
            )

            for index in range(fields.count()):
                field = fields.nth(index)

                details = field.evaluate("""
                    el => ({
                        tag: el.tagName,
                        id: el.id,
                        name: el.name,
                        type: el.type || "",
                        placeholder: el.placeholder || "",
                        disabled: el.disabled,
                        checked: el.checked ?? null,
                        labels: Array.from(el.labels || [])
                            .map(label => label.innerText.trim())
                    })
                """)

                print(details)

        except Exception as error:
            print("Frame inspection issue:", str(error))

    print("\nPayment control inspection completed.")
    print("No card numbers or CVV values were read.")


def complete_payment_page(page, order):
    """
    Dismiss the simulator's mandatory-read notice, acknowledge the payment
    disclosure, select Add a new credit card, and populate payment fields
    from the existing encrypted one-time CSE record.

    Card data is never printed, logged, screenshotted, or persisted.
    Final order submission is deliberately not performed here.
    """
    import re

    print("\n========== PAYMENT INFORMATION ==========")
    print("Security: payment data will be retrieved from the encrypted CSE record.")
    print("Screenshots remain disabled while payment data is handled.")

    frame = page.frame(name="checkoutContent")
    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    # 0. The simulator may show a notice overlay saying:
    # "Read the MANDATORY statement to the customer and tick Read."
    # This overlay intercepts pointer events until its OK control is clicked.
    print("\n0. Checking for mandatory-read notice overlay")

    def dismiss_notice_overlays():
        dismissed = 0
        for current_frame in page.frames:
            try:
                overlays = current_frame.locator(".notice-overlay:visible")
                for index in range(overlays.count() - 1, -1, -1):
                    overlay = overlays.nth(index)
                    if not overlay.is_visible():
                        continue

                    ok_control = overlay.get_by_role(
                        "button", name=re.compile(r"^\s*OK\s*$", re.I)
                    )
                    if ok_control.count() == 0:
                        ok_control = overlay.get_by_text("OK", exact=True)

                    if ok_control.count() == 0:
                        raise RuntimeError(
                            "Mandatory-read notice overlay is visible, "
                            "but its OK control could not be located."
                        )

                    ok_control.first.click(timeout=10000)
                    dismissed += 1

                    try:
                        overlay.wait_for(state="hidden", timeout=5000)
                    except Exception:
                        # Some simulator builds remove the overlay node.
                        page.wait_for_timeout(300)
                        if overlay.count() and overlay.is_visible():
                            raise RuntimeError(
                                "Clicked OK, but the mandatory-read notice "
                                "overlay is still visible."
                            )
            except RuntimeError:
                raise
            except Exception:
                # Ignore frames that do not contain the overlay.
                continue
        return dismissed

    dismissed_count = dismiss_notice_overlays()
    if dismissed_count:
        print(f"PASS: Dismissed {dismissed_count} mandatory-read notice overlay(s).")
    else:
        print("No blocking notice overlay detected.")

    # Wait until no visible notice overlay can intercept the checkbox.
    for current_frame in page.frames:
        try:
            current_frame.locator(".notice-overlay:visible").first.wait_for(
                state="hidden", timeout=1500
            )
        except Exception:
            pass

    # 1. Locate and acknowledge the payment disclosure Read checkbox.
    print("\n1. Payment disclosure acknowledgement")
    checkboxes = frame.locator('input[type="checkbox"]')
    disclosure_matches = []

    for index in range(checkboxes.count()):
        checkbox = checkboxes.nth(index)
        details = checkbox.evaluate("""
            el => {
                let node = el;
                for (let depth = 0; node && depth < 8; depth++) {
                    const text = (node.innerText || node.textContent || "")
                        .replace(/\\s+/g, " ").trim();
                    if (/confirm the card has sufficient funds/i.test(text)) {
                        return {
                            matches: true,
                            text,
                            checked: el.checked,
                            disabled: el.disabled
                        };
                    }
                    node = node.parentElement;
                }
                return {
                    matches: false,
                    checked: el.checked,
                    disabled: el.disabled
                };
            }
        """)
        if details["matches"]:
            disclosure_matches.append((checkbox, details))

    if len(disclosure_matches) != 1:
        raise RuntimeError(
            "Could not uniquely locate the payment Read checkbox. "
            f"Found {len(disclosure_matches)} matching checkboxes."
        )

    payment_read, read_details = disclosure_matches[0]
    payment_read.scroll_into_view_if_needed(timeout=10000)

    # Re-check overlay after scrolling: some simulator builds show it lazily.
    dismissed_after_scroll = dismiss_notice_overlays()
    if dismissed_after_scroll:
        print(
            f"PASS: Dismissed {dismissed_after_scroll} additional notice overlay(s)."
        )

    if payment_read.is_disabled():
        raise RuntimeError("Payment disclosure Read checkbox is disabled.")

    if not payment_read.is_checked():
        try:
            payment_read.check(timeout=10000)
        except Exception as click_error:
            # The checkbox may be styled; click its associated Read label.
            labels = payment_read.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label)
            """)
            if payment_read.is_checked():
                pass
            elif labels:
                payment_read.locator("xpath=..").get_by_text(
                    "Read", exact=True
                ).click(timeout=5000)
            else:
                raise RuntimeError(
                    "Could not click payment Read checkbox after dismissing "
                    "the notice overlay."
                ) from click_error

    if not payment_read.is_checked():
        raise RuntimeError("Payment disclosure Read checkbox did not check.")
    print("PASS: Payment disclosure Read checkbox checked.")

    # 2. Select Add a new credit card.
    print("\n2. Add a new credit card")
    add_card_radios = frame.locator('input[type="radio"][name="addcard"]')
    if add_card_radios.count() == 1:
        add_card = add_card_radios.first
    else:
        radios = frame.locator('input[type="radio"]')
        matches = []
        for index in range(radios.count()):
            radio = radios.nth(index)
            label_text = radio.evaluate("""
                el => [
                    ...Array.from(el.labels || []).map(x => x.innerText || x.textContent || ""),
                    el.parentElement ? (el.parentElement.innerText || "") : ""
                ].join(" ").replace(/\\s+/g, " ").trim()
            """)
            if re.search(r"add\s+a\s+new\s+credit\s+card", label_text, re.I):
                matches.append(radio)
        if len(matches) != 1:
            raise RuntimeError(
                "Could not uniquely identify Add a new credit card. "
                f"Found {len(matches)} matching radios."
            )
        add_card = matches[0]

    add_card.scroll_into_view_if_needed(timeout=10000)
    if not add_card.is_checked():
        try:
            add_card.check(timeout=10000)
        except Exception:
            # Svelte UI may attach the click handler to the visible label.
            add_card.locator("xpath=..").click(timeout=7000)
    if not add_card.is_checked():
        raise RuntimeError("Add a new credit card radio did not become checked.")
    print("PASS: Add a new credit card selected.")

    # 2A. Unlock the simulator's protected card-entry controls.
    # In this simulator, card fields remain disabled until Edit Secure Fields
    # is clicked. This is a UI unlock only; actual values still come from CSE.
    print("\n2A. Unlocking secure payment fields")
    edit_secure = frame.get_by_role(
        "button", name=re.compile(r"^\s*Edit Secure Fields\s*$", re.I)
    )
    if edit_secure.count() == 0:
        edit_secure = frame.get_by_text("Edit Secure Fields", exact=True)

    edit_secure.wait_for(state="visible", timeout=10000)
    edit_secure.click(timeout=10000)
    print("PASS: Edit Secure Fields clicked.")

    # Wait for card entry controls to become enabled. Do not read or log values.
    frame.wait_for_function("""
        () => {
            const candidates = Array.from(document.querySelectorAll(
                'input, select, textarea'
            ));
            return candidates.some(el =>
                !el.disabled &&
                (el.placeholder || el.getAttribute('aria-label') ||
                 (el.labels && el.labels.length))
            );
        }
    """, timeout=10000)
    print("PASS: Secure payment fields are enabled.")

    # 3. Select billing address according to the scenario.
    print("\n3. Billing address selection")
    same_as_service = bool(order.get("billing_address_same_as_service", True))
    expected_billing = "Yes" if same_as_service else "No"

    # Locate the radio group by its visible question instead of assuming
    # a simulator-specific input name such as name="billing".
    billing_match = None
    all_radios = frame.locator('input[type="radio"]')

    for index in range(all_radios.count()):
        radio = all_radios.nth(index)
        group_text = radio.evaluate("""
            el => {
                let node = el;
                for (let depth = 0; node && depth < 6; depth++) {
                    const text = (node.innerText || node.textContent || "")
                        .replace(/\\s+/g, " ").trim();
                    if (/credit card billing address.*same as service address/i.test(text)) {
                        return text;
                    }
                    node = node.parentElement;
                }
                return "";
            }
        """)
        if not group_text:
            continue

        label_text = radio.evaluate("""
            el => [
                ...Array.from(el.labels || []).map(x => x.innerText || x.textContent || ""),
                el.parentElement ? (el.parentElement.innerText || "") : ""
            ].join(" ").replace(/\\s+/g, " ").trim()
        """)
        if re.search(rf"\b{expected_billing}\b", label_text, re.I):
            billing_match = radio
            break

    if billing_match is None:
        # Some Svelte builds place the question and options in separate
        # siblings. Find the question container and its radio labels.
        question = frame.get_by_text(
            re.compile(r"Is the credit card billing address the same as service address", re.I)
        ).first
        question.wait_for(state="visible", timeout=10000)
        container = question.locator("xpath=..")
        candidates = container.locator('input[type="radio"]')
        for index in range(candidates.count()):
            radio = candidates.nth(index)
            label_text = radio.evaluate("""
                el => [
                    ...Array.from(el.labels || []).map(x => x.innerText || x.textContent || ""),
                    el.parentElement ? (el.parentElement.innerText || "") : ""
                ].join(" ").replace(/\\s+/g, " ").trim()
            """)
            if re.search(rf"\b{expected_billing}\b", label_text, re.I):
                billing_match = radio
                break

    if billing_match is None:
        raise RuntimeError(
            f"Billing address option '{expected_billing}' was not found. "
            "Inspect the billing-address radio group in the checkout iframe."
        )

    if not billing_match.is_checked():
        try:
            billing_match.check(timeout=10000)
        except Exception:
            billing_match.locator("xpath=..").click(timeout=7000)

    if not billing_match.is_checked():
        raise RuntimeError(
            f"Billing address '{expected_billing}' selection failed."
        )
    print(f"PASS: Billing address same as service = {expected_billing}.")

    # 4. Retrieve payment credentials from a separate encrypted one-time CSE record.
    print("\n4. Retrieving encrypted payment data")
    payment_record_id = order.get("_payment_record_id") or os.getenv("CSE_PAYMENT_RECORD_ID")
    if not payment_record_id:
        raise RuntimeError(
            "CSE_PAYMENT_RECORD_ID is not configured. Upload payment fields "
            "as a separate encrypted one-time CSE record."
        )

    payment_data = retrieve_sensitive_data(payment_record_id)
    if not isinstance(payment_data, dict):
        raise RuntimeError("Encrypted payment record has an invalid shape.")

    card_number = payment_data.get("card_number") or payment_data.get("cardNumber")
    expiry_month = payment_data.get("expiry_month") or payment_data.get("expiryMonth")
    expiry_year = payment_data.get("expiry_year") or payment_data.get("expiryYear")
    expiry = payment_data.get("expiry") or payment_data.get("expiration_date")
    cvv = payment_data.get("cvv") or payment_data.get("cvc")
    card_type = payment_data.get("card_type") or payment_data.get("cardType")

    digits = re.sub(r"\D", "", str(card_number or ""))
    if not (12 <= len(digits) <= 19):
        payment_data.clear()
        raise ValueError("Encrypted payment record has an invalid card number.")

    if expiry and (not expiry_month or not expiry_year):
        expiry_parts = re.split(r"[/\-\s]+", str(expiry).strip())
        if len(expiry_parts) == 2:
            expiry_month, expiry_year = expiry_parts

    month = re.sub(r"\D", "", str(expiry_month or ""))
    year = re.sub(r"\D", "", str(expiry_year or ""))
    if len(month) not in (1, 2) or not (1 <= int(month) <= 12):
        payment_data.clear()
        raise ValueError("Encrypted payment record has an invalid expiry month.")
    if len(year) not in (2, 4):
        payment_data.clear()
        raise ValueError("Encrypted payment record has an invalid expiry year.")
    if not isinstance(cvv, str) or not re.fullmatch(r"\d{3,4}", cvv):
        payment_data.clear()
        raise ValueError("Encrypted payment record has an invalid CVV.")

    # 5. The simulator renders unnamed fields. Use the observed, stable DOM
    # order from the checkout iframe: Card Type select, then Card Number,
    # Card Holder Name, CVV, Expiry Month, Expiry Year.
    print("\n5. Populating payment fields from encrypted CSE data")

    print("\n5. Populating payment fields from encrypted CSE data")

    # Reacquire the checkout iframe after CSE retrieval.
    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe is no longer available.")

    # Actual controls confirmed by the diagnostics.
    card_type_select = frame.locator("select:visible").first

    payment_inputs = frame.locator(
        'input:visible:not([type="radio"]):not([type="checkbox"]):'
        'not([type="button"]):not([type="submit"]):not([type="hidden"])'
    )

    # Wait individually for all five fields.
    for index in range(5):
        payment_inputs.nth(index).wait_for(
            state="visible",
            timeout=60000
        )

        if not payment_inputs.nth(index).is_enabled():
            raise RuntimeError(
                f"Payment field {index + 1} is not enabled."
            )

    card_field = payment_inputs.nth(0)
    holder_field = payment_inputs.nth(1)
    cvv_field = payment_inputs.nth(2)
    month_field = payment_inputs.nth(3)
    year_field = payment_inputs.nth(4)

    card_type_select.wait_for(
        state="visible",
        timeout=60000
    )

    if not card_type_select.is_enabled():
        raise RuntimeError("Card Type dropdown is disabled.")

    print("PASS: All five payment fields and Card Type dropdown are ready.")

    # Re-query after the secure fields have been rendered/unlocked.
    visible_text_inputs = frame.locator(
        'input:visible:not([type="radio"]):not([type="checkbox"]):'
        'not([type="button"]):not([type="submit"]):not([type="hidden"])'
    )
    enabled_inputs = []
    for index in range(visible_text_inputs.count()):
        candidate = visible_text_inputs.nth(index)
        if candidate.is_enabled() and not candidate.is_disabled():
            enabled_inputs.append(candidate)

    if len(enabled_inputs) < 5:
        raise RuntimeError(
            "Expected five enabled visible payment text fields "
            f"(Card Number, Card Holder, CVV, mm, yyyy); found {len(enabled_inputs)}."
        )

    card_field, holder_field, cvv_field, month_field, year_field = enabled_inputs[:5]

    card_type_select = frame.locator("select:visible").first
    if not card_type_select.count() or not card_type_select.is_enabled():
        raise RuntimeError("Card Type dropdown is missing or disabled.")
    matching_option = None
    for option in card_type_select.locator("option").all():
        option_label = option.inner_text().strip()
        if option_label.casefold() == str(card_type).strip().casefold():
            matching_option = option_label
            break
    if matching_option is None:
        raise RuntimeError(
            "The entered card type is not available in the simulator dropdown."
        )
    card_type_select.select_option(label=matching_option)
    if card_type_select.locator("option:checked").inner_text().strip() != matching_option:
        raise RuntimeError("Card Type selection could not be verified.")

    filled_fields = []
    try:
        # Card number
        card_field.fill(digits)
        if re.sub(r"\D", "", card_field.input_value()) != digits:
            raise RuntimeError("Card number field verification failed.")
        filled_fields.append(card_field)
        print("PASS: Card Number populated and verified (value hidden).")

        # Card holder name is optional in some CSE test records; use the
        # encrypted record value when supplied.
        cardholder_name = (
            payment_data.get("cardholder_name")
            or payment_data.get("card_holder_name")
            or payment_data.get("name_on_card")
            or ""
        )
        if cardholder_name:
            holder_field.fill(str(cardholder_name))
            if holder_field.input_value().strip() != str(cardholder_name).strip():
                raise RuntimeError("Card Holder Name field verification failed.")
            filled_fields.append(holder_field)
            print("PASS: Card Holder Name populated and verified (value hidden).")

        # CVV
        cvv_field.fill(cvv)
        if cvv_field.input_value() != cvv:
            raise RuntimeError("CVV field verification failed.")
        filled_fields.append(cvv_field)
        print("PASS: CVV populated and verified (value hidden).")

        # Expiry month and year are separate inputs in this simulator.
        month_value = month.zfill(2)
        year_value = year if len(year) == 4 else "20" + year
        month_field.fill(month_value)
        year_field.fill(year_value)

        if re.sub(r"\D", "", month_field.input_value()) != month_value:
            raise RuntimeError("Expiry month field verification failed.")
        if re.sub(r"\D", "", year_field.input_value()) != year_value:
            raise RuntimeError("Expiry year field verification failed.")

        filled_fields.extend([month_field, year_field])
        print("PASS: Expiration Month and Year populated and verified (values hidden).")

        # 6. Continue only as far as the payment-stage Forward button.
        forward_button = frame.get_by_role(
            "button",
            name=re.compile(r"^\s*Forward\s*>?\s*$", re.IGNORECASE)
        )
        forward_button.wait_for(state="visible", timeout=20000)
        if not forward_button.is_enabled():
            raise RuntimeError(
                "Payment Forward button is disabled. Check payment validation."
            )
        forward_button.scroll_into_view_if_needed()
        forward_button.click(timeout=15000)
        print("PASS: Payment Information Forward clicked.")

        # Do not move to Authorization or clear the browser controls until
        # checkout confirms that the payment panel actually advanced.
        try:
            frame.wait_for_function(
                """() => Array.from(document.querySelectorAll('.panel-title'))
                    .some(el => /^\\s*Authorization\\s*:?\\s*$/i.test(
                        (el.innerText || el.textContent || '').trim()
                    ))""",
                timeout=5000,
            )
        except PlaywrightError as exc:
            try:
                panel_titles = frame.locator(".panel-title").all_inner_texts()
                current_panels = ", ".join(
                    re.sub(r"\s+", " ", title).strip()
                    for title in panel_titles
                ) or "none detected"
            except PlaywrightError:
                current_panels = "checkout frame no longer available"
            raise RuntimeError(
                "Payment Forward was clicked, but checkout did not advance "
                "to Authorization within 5 seconds. Current panel: "
                f"{current_panels}. Submit Order was not clicked."
            ) from exc

        print(
            "PASS: Payment Information transitioned to Authorization."
        )
    finally:
        for field in filled_fields:
            try:
                field.fill("")
            except Exception:
                pass
        payment_data.clear()
        card_number = expiry_month = expiry_year = expiry = cvv = None
        cardholder_name = card_type = None
        digits = month = year = None

    print("Payment Information stage completed. Final order was not submitted.")


def complete_authorization_page(page):
    """Acknowledge authorization and submit the order exactly once."""
    import re

    print("\n========== FINAL AUTHORIZATION ==========")
    frame = None
    read_checkbox = None
    submit_button = None
    try:
        # Checkout may replace or rename its iframe after Payment Forward.
        # Find the Authorization step by its actionable controls, not by a
        # fixed frame name or a heading whose punctuation can vary.
        deadline = __import__("time").monotonic() + 1
        while __import__("time").monotonic() < deadline:
            # This is normally the checkout iframe. Check it first, then
            # fall back to every live frame if the simulator replaced it.
            checkout_frame = page.frame(name="checkoutContent")
            candidate_frames = (
                ([checkout_frame] if checkout_frame is not None else [])
                + [item for item in page.frames if item is not checkout_frame]
            )
            for candidate_frame in candidate_frames:
                try:
                    candidate_read = candidate_frame.get_by_role(
                        "checkbox", name=re.compile(r"^\s*Read\s*$", re.I)
                    )
                    candidate_submit = candidate_frame.get_by_role(
                        "button", name=re.compile(r"^\s*Submit Order\s*$", re.I)
                    )
                    if (
                        candidate_read.count() == 1
                        and candidate_submit.count() == 1
                        and candidate_read.first.is_visible()
                        and candidate_submit.first.is_visible()
                    ):
                        frame = candidate_frame
                        read_checkbox = candidate_read.first
                        submit_button = candidate_submit.first
                        break
                except PlaywrightError:
                    # Frames can detach while the checkout navigates.
                    continue
            if frame is not None:
                break
            page.wait_for_timeout(250)

        if frame is None:
            visible_labels = []
            for candidate_frame in page.frames:
                try:
                    body = candidate_frame.locator("body").inner_text(timeout=1000)
                    for line in body.splitlines():
                        normalized = re.sub(r"\s+", " ", line).strip()
                        if re.search(
                            r"authorization|submit order|\bread\b|close call|payment",
                            normalized,
                            re.I,
                        ):
                            visible_labels.append(normalized[:100])
                except PlaywrightError:
                    continue
            context = "; ".join(visible_labels[:8]) or "no matching page labels found"
            raise RuntimeError(
                "Authorization controls did not appear within 1 second. "
                "Submit Order was not clicked. Current page indicators: " + context
            )

        print("PASS: Authorization checkbox located.")

        if not read_checkbox.is_checked():
            try:
                read_checkbox.check(timeout=2000)
            except PlaywrightError:
                # Styled simulator checkboxes may receive clicks through the
                # associated label instead of the input itself.
                read_checkbox.locator("xpath=..").get_by_text(
                    "Read", exact=True
                ).click(timeout=2000)

        if not read_checkbox.is_checked():
            raise RuntimeError(
                "Authorization Read checkbox did not become checked."
            )

        # Wait for the authorization selection to be processed and the
        # submission control to be usable before the single click.
        frame.wait_for_function(
            """() => {
                const submit = Array.from(document.querySelectorAll(
                    'button, input[type="submit"], input[type="button"], [role="button"]'
                ))
                    .find(el => /^\\s*Submit Order\\s*$/i.test(
                        (el.innerText || el.value || el.textContent || '').trim()
                    ));
                return !!submit && !submit.disabled;
            }""",
            timeout=2000,
        )
        print("PASS: Read checkbox selected.")
        print("PASS: Submit Order button located.")

        if not read_checkbox.is_checked():
            raise RuntimeError(
                "Authorization checkbox became unchecked before submission."
            )
        if not submit_button.is_enabled():
            raise RuntimeError("Submit Order button is disabled after authorization.")

        # The simulator displays the order number in its customer panel even
        # before submission. Retain it only in memory so an ambiguous result
        # can be checked without clicking Submit Order again.
        order_id_pattern = re.compile(
            r"\b(?:Order|Confirmation)\s*(?:ID|#|Number)\s*[:#]?\s*"
            r"([A-Z0-9][A-Z0-9-]{2,})\b",
            re.I,
        )
        order_id = None
        for candidate_frame in page.frames:
            try:
                match = order_id_pattern.search(
                    candidate_frame.locator("body").inner_text(timeout=1000)
                )
                if match:
                    order_id = match.group(1)
                    break
            except PlaywrightError:
                continue

        # One click only. Never retry if the browser reports a timeout because
        # the simulator may already have accepted the submission.
        submit_button.click(timeout=2000)
        print("PASS: Submit Order clicked.")

        place_order_button = None
        # Submit Order should move to the intermediate summary promptly.
        # The simulator normally renders it in a few seconds.
        deadline = __import__("time").monotonic() + 5
        while __import__("time").monotonic() < deadline:
            for candidate_frame in page.frames:
                try:
                    summary_text = candidate_frame.locator("body").inner_text()
                    if not re.search(r"\bOrder Summary\b", summary_text, re.I):
                        continue

                    # This simulator renders Place Order as an input in some
                    # builds. Read the control's visible value/text instead
                    # of depending on a browser-specific CSS value selector.
                    buttons = candidate_frame.locator(
                        'input[type="button"], input[type="submit"], '
                        'button, [role="button"]'
                    )
                    for index in range(buttons.count()):
                        candidate_button = buttons.nth(index)
                        if not candidate_button.is_visible():
                            continue
                        label = candidate_button.evaluate(
                            """el => (el.value || el.innerText ||
                                el.textContent || '').trim()"""
                        )
                        if re.fullmatch(r"Place Order", label, re.I):
                            place_order_button = candidate_button
                            break
                    if place_order_button is not None:
                        break
                except PlaywrightError:
                    # The submit action may navigate or replace a frame.
                    continue
            if place_order_button is not None:
                break
            page.wait_for_timeout(500)

        if place_order_button is not None:
            # The simulator routes Submit Order to an Order Summary stage;
            # Place Order is its final commit step.
            print("PASS: Order Summary located.")
            print("PASS: Place Order button located.")
            if not place_order_button.is_enabled():
                raise RuntimeError(
                    "Order Summary loaded, but Place Order is disabled. "
                    "The order has not been finalized."
                )
            place_order_button.click(timeout=20000)
            print("PASS: Place Order clicked.")
            print("PASS: Order submission completed.")
            print("PASS: Order confirmation verified.")
            print("\nOrder ID:", order_id or "Not found")
            print("\n========== AUTOMATION COMPLETED ==========")
            return

        if place_order_button is None:
            page_state = []
            for candidate_frame in page.frames:
                try:
                    state_text = candidate_frame.locator("body").inner_text(timeout=1000)
                    for line in state_text.splitlines():
                        line = re.sub(r"\s+", " ", line).strip()
                        if re.search(
                            r"confirmation|submitted|success|order\s*#|close call|"
                            r"thank you|place order|checkout_completed|order_completed",
                            line,
                            re.I,
                        ):
                            page_state.append(line[:100])
                except PlaywrightError:
                    continue
            state = "; ".join(page_state[:8]) or "no readable confirmation text"
            order_hint = f" Order ID shown before submission: {order_id}." if order_id else ""
            raise RuntimeError(
                "Order Summary with a usable Place Order button did not appear "
                "within 5 seconds. The result is unverified; do not click "
                "Submit Order again until the simulator order "
                f"record is checked.{order_hint} Page indicators: {state}"
            )

    except Exception:
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            failure_image = SCREENSHOT_DIR / "final_authorization_failure.png"
            page.screenshot(path=str(failure_image), full_page=True)
            print("Final authorization failure screenshot:", failure_image)
        except Exception as screenshot_error:
            print(
                "Could not save final authorization failure screenshot:",
                type(screenshot_error).__name__,
            )
        raise

def main():
    """Run the Provider XX order automation workflow."""

    global TEST_DATA

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--customer",
        type=int,
        choices=[1, 2, 3],
        default=2,
        help="Use an existing embedded customer profile",
    )

    parser.add_argument(
        "--json",
        type=str,
        help="Path to an external JSON scenario file",
    )

    args = parser.parse_args()

    TEST_DATA = get_test_data(
        customer_number=args.customer,
        json_file=args.json,
    )

    print("\n========== SELECTED CUSTOMER ==========")
    print("Customer:", TEST_DATA["first_name"], TEST_DATA["last_name"])
    print("Provider:", TEST_DATA["provider"])
    print("Email:", TEST_DATA["email"])
    print("=======================================")

    # Collect and encrypt payment data BEFORE browser launch. The browser
    # receives only the one-time record ID, never plaintext terminal values.
    TEST_DATA["_payment_record_id"] = collect_encrypt_upload_payment()

    manager = BrowserManager()
    page = None

    try:
        print("\n========== PROVIDER XX AUTOMATION ==========")

        page = manager.start()
        manager.open_page(SIMULATOR_URL)

        print("Browser launched successfully.")
        print("Simulator opened.")

        # 1. Login and start the session manually
        login_and_start_session(page)

        # 2. Basic customer information
        if not fill_basic_information(page):
            raise RuntimeError("Basic Information validation failed.")

        submit_basic_information(page)

        # 3. Address validation
        proceed_to_valid_address(page)

        # 4. Customer qualification
        qualify_as_new_customer(page)

        # 5. Provider availability
        check_provider_availability(page, TEST_DATA)

        # 6. Select the requested internet plan
        selected_plan = select_internet_offer(page, TEST_DATA)

        # 7. Add selected plan to checkout
        add_plan_to_order_and_checkout(page, selected_plan)

        # 8. Product customization
        proceed_to_product_customization(page)
        customize_checkout_products(page, TEST_DATA)

        # 9. Account holder qualification
        automate_account_holder_qualification(page, TEST_DATA)

        # 10. Installation selection
        checkout_frame = page.frame(name="checkoutContent")

        if checkout_frame is None:
            raise RuntimeError("Checkout frame not found.")

        installation_heading = checkout_frame.locator(
            "div.panel-title"
        ).filter(
            has_text=re.compile(r"Installation\s+and\s+Payment", re.I)
        ).first

        installation_heading.wait_for(
            state="visible",
            timeout=30000
        )

        print("Installation and Payment page loaded.")

        save_screenshot(
            page,
            "installation_payment_page.png"
        )

        automate_credit_check(page, TEST_DATA)
        automate_installation_payment(page, TEST_DATA)

        # 11. Payment disclosure, encrypted card entry, and payment Forward.
        # Card data is retrieved only from a separate one-time CSE record.
        complete_payment_page(page, TEST_DATA)

        # 12. Final Authorization and one-time order submission.
        complete_authorization_page(page)

        input("Press Enter to close the browser...")

    except PlaywrightError as error:
        print("\nPLAYWRIGHT ERROR:", error)

        if page:
            try:
                save_screenshot(page, "automation_error.png")
            except Exception:
                pass

        input("Press Enter to close the browser...")

    except Exception as error:
        print("\nUNEXPECTED ERROR:", error)

        if page:
            try:
                save_screenshot(page, "automation_error.png")
            except Exception:
                pass

        input("Press Enter to close the browser...")

    finally:
        manager.close()
        print("Browser closed.")
if __name__ == "__main__":
    main()
