from pathlib import Path
import re
from decimal import Decimal
import argparse

from app.automation.browser import BrowserManager
from playwright.sync_api import Error as PlaywrightError


# Keep the original working simulator URL unchanged.
SIMULATOR_URL = ("")

from tests.test_data import get_test_data

TEST_DATA = {}

SCREENSHOT_DIR = Path("tests/screenshots")


def save_screenshot(page, filename):
    """Save screenshots locally."""

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    screenshot_path = SCREENSHOT_DIR / filename

    page.screenshot(
        path=str(screenshot_path),
        full_page=True,
    )

    print(f"Screenshot saved: {screenshot_path}")



def login_and_start_session(page):
    """Wait for manual login and reliably start a new session."""

    print("\n========== LOGIN AND SESSION ==========")
    print("Complete the login manually in the browser.")
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
        page, "#customerMove",
        TEST_DATA["moving"],
        "Moving Status"
    )

    # 7. Moving date is displayed dynamically when Moving = Yes.
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

    print(
        f"PASS: Account holder selected: "
        f"{matching_account['label']}"
    )

    # 2. Customer-specific Yes/No radio selections.
    radio_groups = [
        (
            "verified",
            "Speaking to Account Holder",
            "speaking_to_account_holder"
        ),
        (
            "current",
            "Current Provider XX Customer",
            "existing_provider_customer"
        ),
        (
            "ez",
            "EZ-Enroll",
            "ez_enroll"
        ),
        (
            "autopay",
            "Automatic Payments",
            "autopay_paperless_discount"
        ),
        (
            "mailing",
            "Mailing Address Same as Service",
            "mailing_same_as_service"
        ),
        (
            "shipping",
            "Shipping Address Same as Service",
            "shipping_same_as_service"
        ),
    ]

    expected_answers = {}

    for group_name, description, data_key in radio_groups:

        if data_key not in order:
            raise RuntimeError(
                f"Missing customer data for {description}: {data_key}"
            )

        expected = bool(order[data_key])
        expected_label = "Yes" if expected else "No"

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
            raise RuntimeError(
                f"{description}: selection failed."
            )

        expected_answers[group_name] = expected_label

        print(f"PASS: {description} = {expected_label}")

    # 3. Phone number.
    phone = order.get("phone") or order.get("phone_number")

    if not phone:
        raise RuntimeError("Phone number missing from customer data.")

    phone_field = frame.locator(
        'input[placeholder="Phone Number"]'
    )

    phone_field.wait_for(state="visible", timeout=10000)
    phone_field.fill(str(phone))

    if phone_field.input_value() != str(phone):
        raise RuntimeError("Phone number validation failed.")

    print("PASS: Phone number entered.")

    # 4. Email address.
    email = order.get("email")

    if not email:
        raise RuntimeError("Email address missing from customer data.")

    email_field = frame.locator(
        'input[placeholder="Email Address"]'
    )

    email_field.wait_for(state="visible", timeout=10000)
    email_field.fill(str(email))

    if email_field.input_value() != str(email):
        raise RuntimeError("Email validation failed.")

    print("PASS: Email address entered.")

    
        # 5. Mandatory disclosure acknowledgement
    print("\n========== DISCLOSURE ACKNOWLEDGEMENT ==========")

    checkboxes = frame.locator('input[type="checkbox"]')

    read_checkbox = None

    for index in range(checkboxes.count()):
        checkbox = checkboxes.nth(index)

        labels = checkbox.evaluate("""
            el => Array.from(el.labels || [])
                .map(label => label.innerText.trim())
        """)

        if any(label.casefold() == "read" for label in labels):
            read_checkbox = checkbox
            break

    if read_checkbox is None:
        raise RuntimeError("Mandatory Read checkbox not found.")

    if not read_checkbox.is_checked():
        read_checkbox.check()

    if not read_checkbox.is_checked():
        raise RuntimeError("Mandatory Read acknowledgement failed.")

    print("PASS: Automatic Payments disclosure acknowledged.")

    # 6. Validate all radio selections.
    print("\n========== FINAL QUALIFICATION VALIDATION ==========")

    for group_name, description, data_key in radio_groups:

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
                f"Validation failed: {description} "
                f"should be {expected_label}."
            )

    if phone_field.input_value() != str(phone):
        raise RuntimeError("Final phone validation failed.")

    if email_field.input_value() != str(email):
        raise RuntimeError("Final email validation failed.")

    print("PASS: All customer qualification fields validated.")

    save_screenshot(
        page,
        "account_holder_qualification_completed.png"
    )

    # 7. Forward only after validation.
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

    save_screenshot(
        page,
        "installation_payment_page.png"
    )

    print("Account Holder Qualification completed.")

    
def run_credit_check(page, order):
    """Run the credit check only when sandbox testing is enabled."""

    print("\n========== CREDIT CHECK ==========")

    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    credit_data = order.get("credit_check", {})

    if not credit_data.get("enabled", False):
        print("Credit Check skipped: sandbox execution is disabled.")
        return

    ssn = credit_data.get("ssn")
    dob = credit_data.get("dob")

    if not ssn or not dob:
        raise RuntimeError("Dummy SSN or DOB is missing.")

    ssn_field = frame.locator(
        'input[placeholder*="SSN"], input[name*="ssn" i]'
    )

    dob_field = frame.locator(
        'input[placeholder="MM/DD/YYYY"], input[name*="dob" i]'
    )

    if ssn_field.count() != 1 or dob_field.count() != 1:
        raise RuntimeError(
            "Could not uniquely identify SSN and DOB fields."
        )

    ssn_field.fill(str(ssn))
    dob_field.fill(str(dob))

    print("PASS: Dummy SSN entered.")
    print("PASS: Dummy DOB entered.")

    if ssn_field.input_value() != str(ssn):
        raise RuntimeError("SSN validation failed.")

    if dob_field.input_value() != str(dob):
        raise RuntimeError("DOB validation failed.")

    run_button = frame.get_by_role(
        "button",
        name=re.compile(r"Run Credit Check", re.I)
    )

    run_button.wait_for(state="visible", timeout=10000)

    if not run_button.is_enabled():
        raise RuntimeError("Run Credit Check button is disabled.")

    save_screenshot(page, "credit_check_before_run.png")

    run_button.click()

    print("PASS: Run Credit Check clicked.")

    page.wait_for_timeout(3000)

    save_screenshot(page, "credit_check_result.png")

    print("Credit Check response captured.")




def automate_installation_payment(page, order):
    """Select shipping or professional installation, confirm, and continue."""

    from datetime import date, datetime
    import re

    print("\n========== INSTALLATION AND PAYMENT ==========")

    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    installation_type = str(
        order.get("installation_type", "STANDARD_SHIPPING")
    ).strip().upper()

    if installation_type not in ("STANDARD_SHIPPING", "PRO_INSTALL"):
        raise ValueError(f"Invalid installation type: {installation_type}")

    # -------------------------------------------------
    # 1. SELECT INSTALLATION TYPE
    # -------------------------------------------------

    print("\n1. Selecting installation type")

    radios = frame.locator('input[type="radio"]')
    selected_radio = None

    for index in range(radios.count()):
        radio = radios.nth(index)

        details = radio.evaluate("""
            el => ({
                value: el.value || "",
                labels: Array.from(el.labels || [])
                    .map(label => label.innerText.trim()),
                parent: el.parentElement
                    ? el.parentElement.innerText.trim()
                    : ""
            })
        """)

        text = " ".join(
            [details["value"]] + details["labels"] + [details["parent"]]
        ).casefold()

        if installation_type == "STANDARD_SHIPPING":
            matched = (
                "standard_shipping" in text
                or "standard shipping" in text
            )
        else:
            matched = (
                "pro_install" in text
                or "pro install" in text
            )

        if matched:
            selected_radio = radio
            break

    if selected_radio is None:
        raise RuntimeError(
            f"Installation option not found: {installation_type}"
        )

    if not selected_radio.is_checked():
        selected_radio.check()

    if not selected_radio.is_checked():
        raise RuntimeError("Installation selection failed.")

    print(f"PASS: {installation_type} selected.")

    # -------------------------------------------------
    # 2. PROFESSIONAL INSTALLATION DETAILS
    # -------------------------------------------------

    if installation_type == "PRO_INSTALL":

        installation_date = str(
            order.get("installation_date", "")
        ).strip()

        installation_time = str(
            order.get("installation_time", "")
        ).strip()

        if not installation_date:
            raise ValueError("Installation date is missing.")

        parsed_date = date.fromisoformat(installation_date)

        if parsed_date < date.today():
            raise ValueError("Installation date cannot be in the past.")

        if installation_time not in ("Morning", "Afternoon", "Evening"):
            raise ValueError("Invalid installation time.")

        
        # 2A. Identify the two mandatory Read checkboxes
        print("\n========== INSTALLATION DISCLOSURES ==========")

        read_checkboxes = frame.locator(
            'input[type="checkbox"]:visible'
        )

        count = read_checkboxes.count()

        print(f"Visible installation checkboxes found: {count}")

        if count != 2:
            raise RuntimeError(
                f"Expected exactly 2 visible installation "
                f"acknowledgements, found {count}. "
                "Inspect the installation page."
            )

        # Verify both controls are labelled Read.
        for index in range(2):
            checkbox = read_checkboxes.nth(index)

            details = checkbox.evaluate("""
                el => ({
                    labels: Array.from(el.labels || [])
                        .map(label => label.innerText.trim()),
                    parentText: el.parentElement
                        ? el.parentElement.innerText.trim()
                        : ""
                })
            """)

            print(f"Disclosure checkbox {index + 1}: {details}")

            if not any(
                label.casefold() == "read"
                for label in details["labels"]
            ):
                raise RuntimeError(
                    f"Checkbox {index + 1} is not labelled Read."
                )

        # First checkbox: Adult availability
        adult_checkbox = read_checkboxes.nth(0)

        if not adult_checkbox.is_checked():
            adult_checkbox.check()

        if not adult_checkbox.is_checked():
            raise RuntimeError(
                "Adult availability acknowledgement failed."
            )

        print("PASS: Adult availability Read checked.")

        # Second checkbox: Installation date availability
        availability_checkbox = read_checkboxes.nth(1)

        if not availability_checkbox.is_checked():
            availability_checkbox.check()

        if not availability_checkbox.is_checked():
            raise RuntimeError(
                "Installation availability acknowledgement failed."
            )

        print("PASS: Installation availability Read checked.")

        # 2B. Installation date

        print("\n3. Selecting installation date")

        date_field = frame.locator(
            'input[type="date"]:visible, '
            'input[placeholder*="dd-mm-yyyy" i]:visible'
        )

        if date_field.count() != 1:
            raise RuntimeError(
                f"Expected one installation date field; "
                f"found {date_field.count()}."
            )

        date_input_type = date_field.get_attribute("type")
        date_placeholder = date_field.get_attribute("placeholder") or ""

        if date_input_type == "date":
            date_to_enter = installation_date
        elif "dd-mm-yyyy" in date_placeholder.casefold():
            date_to_enter = datetime.strptime(
                installation_date, "%Y-%m-%d"
            ).strftime("%d-%m-%Y")
        else:
            raise RuntimeError(
                "Unknown installation date field format. "
                f"Type={date_input_type}, "
                f"Placeholder={date_placeholder}"
            )

        date_field.fill(date_to_enter)

        if date_field.input_value() != date_to_enter:
            raise RuntimeError("Installation date validation failed.")

        print(f"PASS: Installation date entered: {date_to_enter}")

        # 2C. Preferred installation time

        print("\n4. Selecting preferred installation time")

        selects = frame.locator("select:visible")
        time_dropdown = None

        for index in range(selects.count()):
            candidate = selects.nth(index)

            options = [
                value.strip()
                for value in candidate.locator("option").all_text_contents()
            ]

            if all(
                value in options
                for value in ("Morning", "Afternoon", "Evening")
            ):
                time_dropdown = candidate
                break

        if time_dropdown is None:
            raise RuntimeError("Installation time dropdown not found.")

        time_dropdown.select_option(label=installation_time)

        actual_time = time_dropdown.locator(
            "option:checked"
        ).inner_text().strip()

        if actual_time != installation_time:
            raise RuntimeError("Installation time selection failed.")

        print(f"PASS: Preferred time selected: {actual_time}")

        # 2D. Second mandatory acknowledgement

        print("\n5. Installation availability acknowledgement")

        # Reuse the already identified second Read checkbox instead of
        # calling a nonexistent helper.
        if not availability_checkbox.is_checked():
            availability_checkbox.check()

        if not availability_checkbox.is_checked():
            raise RuntimeError(
                "Installation availability acknowledgement failed."
            )

        print("PASS: Installation availability Read checked.")

    else:
        print("Standard shipping selected. No appointment required.")

    # -------------------------------------------------
    # 3. VERIFY INSTALLATION TOTAL
    # -------------------------------------------------

    print("\n6. Verifying installation total")

    page_text = frame.locator("body").inner_text()

    expected_total = (
        r"Installation Total\s*:?\s*\$100\.00"
        if installation_type == "PRO_INSTALL"
        else r"Installation Total\s*:?\s*\$0\.00"
    )

    if not re.search(expected_total, page_text, re.IGNORECASE):
        raise RuntimeError(
            "Installation total verification failed. "
            f"Expected: {'$100.00' if installation_type == 'PRO_INSTALL' else '$0.00'}"
        )

    print("PASS: Installation total verified.")

    save_screenshot(
        page,
        "installation_payment_before_confirm.png"
    )

    # -------------------------------------------------
    # 4. CONFIRM INSTALLATION
    # -------------------------------------------------

    print("\n7. Confirming installation")

    confirm_button = frame.get_by_role(
        "button",
        name=re.compile(
            r"^\s*Confirm Installation\s*>?\s*$",
            re.IGNORECASE
        )
    )

    confirm_button.wait_for(state="visible", timeout=20000)

    if not confirm_button.is_enabled():
        raise RuntimeError("Confirm Installation is disabled.")

    confirm_button.scroll_into_view_if_needed()
    confirm_button.click()

    print("PASS: Confirm Installation clicked.")

    save_screenshot(
        page,
        "installation_payment_after_confirm.png"
    )

    # -------------------------------------------------
    # 5. WAIT FOR THE NEXT FORWARD BUTTON
    # -------------------------------------------------

    print("\n8. Waiting for next Forward button")

    forward_button = frame.get_by_role(
        "button",
        name=re.compile(
            r"^\s*Forward\s*>?\s*$",
            re.IGNORECASE
        )
    )

    forward_button.wait_for(
        state="visible",
        timeout=30000
    )

    if not forward_button.is_enabled():
        raise RuntimeError(
            "The next Forward button is disabled."
        )

    forward_button.scroll_into_view_if_needed()
    forward_button.click()

    print("PASS: Installation Forward button clicked.")

    page.wait_for_timeout(3000)

    save_screenshot(
        page,
        "installation_forward_completed.png"
    )

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

def automate_credit_check(page, order):
    print("\n========== CREDIT CHECK ==========")

    frame = page.frames[1]

    credit_data = order.get("credit_check", {})

    if not credit_data.get("enabled"):
        raise RuntimeError("Credit check is disabled in test data.")

    ssn = credit_data.get("ssn", "")
    dob = credit_data.get("dob", "")

    if not ssn or not dob:
        raise RuntimeError("Dummy credit-check values are missing.")

    # Fill the two fields using their accessible labels.
    frame.get_by_label("Social Security Number").fill(ssn)
    frame.get_by_label("Date of Birth").fill(dob)

    print("PASS: Dummy SSN and DOB entered.")

    # Click Run Credit Check.
    frame.get_by_role(
        "button",
        name="Run Credit Check"
    ).click()

    page.wait_for_timeout(2000)

    # Inspect visible result text.
    result_text = frame.locator("body").inner_text().lower()

    
    # Normalize the simulator response
    result_text = re.sub(r"\s+", " ", result_text).strip()

    success_patterns = [
        r"credit check successful",
        r"credit check completed",
        r"credit approved",
        r"credit verification successful",
        r"credit check status:\s*approved",
    ]

    failure_patterns = [
        r"credit check declined",
        r"credit check failed",
        r"credit check rejected",
    ]

    if any(re.search(pattern, result_text) for pattern in failure_patterns):
        raise RuntimeError("Credit check was declined or failed.")

    if not any(
        re.search(pattern, result_text)
        for pattern in success_patterns
    ):
        raise RuntimeError(
            "Credit check approval could not be verified. "
            "Inspect the simulator response."
        )

    print("PASS: Credit Check Status = APPROVED")
    print("PASS: Order Qualification Status verified.")

    save_screenshot(page, "credit_check_completed.png")

    
    
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


def complete_payment_page(page):
    """
    Prepare the payment page, allow manual secure card entry,
    validate non-sensitive controls and click Forward.

    Card number, CVV and expiry remain manually entered.
    """

    import re

    print("\n========== PAYMENT INFORMATION ==========")

    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    # 1. Select Add a new credit card.
    add_card = frame.locator(
        'input[type="radio"][name="addcard"]'
    )

    if add_card.count() != 1:
        raise RuntimeError(
            "Could not identify Add a new credit card."
        )

    if not add_card.is_checked():
        add_card.check()

    if not add_card.is_checked():
        raise RuntimeError(
            "Add a new credit card selection failed."
        )

    print("PASS: Add a new credit card selected.")

    # 2. Inspect the billing address selection.
    billing_radios = frame.locator(
        'input[type="radio"][name="billing"]'
    )

    print("\nBilling address options:")

    for index in range(billing_radios.count()):
        radio = billing_radios.nth(index)

        labels = radio.evaluate("""
            el => Array.from(el.labels || [])
                .map(label => label.innerText.trim())
        """)

        print({
            "label": labels,
            "checked": radio.is_checked(),
            "disabled": radio.is_disabled()
        })

    # Do not guess whether billing address is the same
    # as the service address. The customer's answer is required.

    # 3. Inspect payment disclosure acknowledgement.
    checkboxes = frame.locator(
        'input[type="checkbox"]:visible'
    )

    print("\nPayment acknowledgement controls:")

    for index in range(checkboxes.count()):
        checkbox = checkboxes.nth(index)

        labels = checkbox.evaluate("""
            el => Array.from(el.labels || [])
                .map(label => label.innerText.trim())
        """)

        print({
            "label": labels,
            "checked": checkbox.is_checked(),
            "disabled": checkbox.is_disabled()
        })

    # 4. Save a screenshot before manual payment entry.
    save_screenshot(
        page,
        "payment_information_ready.png"
    )

    print("\nPayment page is ready.")

    print(
        "Please enter the card details manually in the browser."
    )

    input(
        "After entering the card details and selecting the "
        "correct billing address, press Enter here to continue..."
    )

    # 5. Validate the non-sensitive billing selection.
    checked_billing = billing_radios.locator(
        "xpath=.."
    )

    selected_billing = []

    for index in range(billing_radios.count()):
        radio = billing_radios.nth(index)

        if radio.is_checked():
            labels = radio.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label.innerText.trim())
            """)

            selected_billing.extend(labels)

    if len(selected_billing) != 1:
        raise RuntimeError(
            "Select exactly one billing address option."
        )

    print(
        "PASS: Billing address option selected:",
        selected_billing[0]
    )

    # 6. Locate Forward.
    forward_button = frame.get_by_role(
        "button",
        name=re.compile(
            r"^\s*Forward\s*>?\s*$",
            re.IGNORECASE
        )
    )

    forward_button.wait_for(
        state="visible",
        timeout=30000
    )

    if not forward_button.is_enabled():
        raise RuntimeError(
            "Payment Information Forward button is disabled. "
            "Check the payment form in the browser."
        )

    save_screenshot(
        page,
        "payment_information_before_forward.png"
    )

    forward_button.scroll_into_view_if_needed()
    forward_button.click()

    print("PASS: Payment Information Forward clicked.")

    page.wait_for_timeout(3000)

    save_screenshot(
        page,
        "payment_information_after_forward.png"
    )

    print("Payment Information stage completed.")



def main():
    """Run the Provider XX order automation workflow."""

    global TEST_DATA

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--customer",
        type=int,
        choices=[1, 2, 3],
        default=2,
        help="Customer profile to test (1, 2, or 3)"
    )
    args = parser.parse_args()

    TEST_DATA = get_test_data(args.customer)

    print("\n========== SELECTED CUSTOMER ==========")
    print("Customer:", TEST_DATA["first_name"], TEST_DATA["last_name"])
    print("Provider:", TEST_DATA["provider"])
    print("Email:", TEST_DATA["email"])
    print("=======================================")

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

        # 11. Check for Order Summary without submitting payment
        print("\nChecking for Order Summary...")

        summary_found = False

        for frame in page.frames:
            try:
                summary = frame.get_by_text(
                    re.compile(r"Order Summary", re.I)
                ).first

                if summary.is_visible(timeout=3000):
                    summary_found = True
                    break
            except Exception:
                continue

        if summary_found:
            print("Order Summary detected.")
            save_screenshot(page, "order_summary.png")
        else:
            print("Order Summary not detected automatically.")
            print("Current URL:", page.url)
            print("Please inspect the browser before proceeding.")
            save_screenshot(page, "order_summary_check.png")

        print("\n========== AUTOMATION STOPPED ==========")
        print("No payment details entered.")
        print("No final order submitted.")
        print("========================================")

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
