from pathlib import Path
import re
from decimal import Decimal

from app.automation.browser import BrowserManager
from playwright.sync_api import Error as PlaywrightError


# Keep the original working simulator URL unchanged.
SIMULATOR_URL = (
    "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/"
    "?next=%2Fallconnect%2F"
)

# Synthetic test data only.
TEST_DATA = {
    "prefix": "Mr",
    "first_name": "Phil",
    "middle_name": " ",
    "last_name": "Dunphy",
    "zip_code": "90064",
    "address": "10336 Dunleer Dr, Los Angeles, CA",
    "unit_type": "Suite",
    "unit_number": "123",
    "city": "Los Angeles",
    "state": "CA",
    "dwelling_type": "House",
    "ownership": "Own",
    "moving": "No",
    "customer_type": "New",
    "provider": "ProviderXX",
    "plan": "300 Mbps (1-YEAR PRICING)",
    "base_price": "40.00",
    "video": "None",
    "internet_plan": "300 Mbps (1-YEAR PRICING)",
    "phone": "5550101234",
    "email": "phil.test@example.com",
    "installation_type": "STANDARD_SHIPPING",
    "installation_date": "",
    "installation_time": "Afternoon",
}

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



def fill_basic_information(page):
    """Fill the Basic Information form."""

    print("\n========== BASIC INFORMATION ==========")

    page.locator("#namePrefixList").select_option(
        label=TEST_DATA["prefix"]
    )

    page.locator("#firstName").fill(
        TEST_DATA["first_name"]
    )

    page.locator("#middleName").fill(
        TEST_DATA["middle_name"]
    )

    page.locator("#lastName").fill(
        TEST_DATA["last_name"]
    )

    # ZIP lookup unlocks the address fields.
    page.locator("#ssZipCode").fill(
        TEST_DATA["zip_code"]
    )

    page.locator("#ssZipCode").press("Tab")

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
        timeout=30000,
    )

    page.locator("#address1").fill(
        TEST_DATA["address"]
    )

    page.locator("#unitTypeList").select_option(
        label=TEST_DATA["unit_type"]
    )

    page.locator("#unitNumber").fill(
        TEST_DATA["unit_number"]
    )

    page.locator("#city").fill(
        TEST_DATA["city"]
    )

    page.locator("#stateList").select_option(
        value=TEST_DATA["state"]
    )

    page.locator("#serviceAddressTypeList").select_option(
        label=TEST_DATA["dwelling_type"]
    )

    page.locator("#rentOwnList").select_option(
        label=TEST_DATA["ownership"]
    )

    page.locator("#customerMove").select_option(
        label=TEST_DATA["moving"]
    )

    print("Basic Information fields entered.")

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
    """Find the exact ProviderXX plan and open its View Details page."""

    print("\n========== INTERNET PLAN SELECTION ==========")

    requested_plan = order["plan"].strip()
    expected_price = Decimal(order["base_price"])

    # Wait for Internet offers to load.
    titles = page.locator(".productTitle:visible")

    titles.first.wait_for(
        state="visible",
        timeout=30000,
    )

    selected_title = None

    for index in range(titles.count()):
        current_title = titles.nth(index)
        title_text = current_title.inner_text().strip()

        if title_text.casefold() == requested_plan.casefold():
            selected_title = current_title
            break

    if selected_title is None:
        available = [
            titles.nth(i).inner_text().strip()
            for i in range(titles.count())
        ]

        raise RuntimeError(
            f"Requested plan not found: {requested_plan}. "
            f"Available plans: {available}"
        )

    print("Exact plan found:", requested_plan)

    # Find the nearest actual product card.
    card = selected_title.locator(
        "xpath=ancestor::dir[contains("
        "concat(' ', normalize-space(@class), ' '), "
        "' syncbdlmain ')][1]"
    )

    if card.count() != 1:
        raise RuntimeError(
            "Could not identify the product card for the selected plan."
        )

    # Read product metadata.
    metadata_input = card.locator(
        "input.singleHiddenJson"
    )

    metadata_input.wait_for(
        state="attached",
        timeout=15000,
    )

    metadata = metadata_input.evaluate(
        "element => JSON.parse(element.value)"
    )

    actual_product = metadata.get("productname", "").strip()
    actual_provider = metadata.get("providerName", "").strip()

    if actual_product.casefold() != requested_plan.casefold():
        raise RuntimeError(
            f"Product metadata mismatch: {actual_product}"
        )

    if actual_provider.casefold() != "providerxx":
        raise RuntimeError(
            f"Unexpected provider: {actual_provider}"
        )

    # Verify the base price.
    price_input = card.locator(
        "input.baseRecPrice"
    )

    actual_price = Decimal(
        price_input.input_value()
    )

    if actual_price != expected_price:
        raise RuntimeError(
            f"Price mismatch. Expected ${expected_price:.2f}; "
            f"found ${actual_price:.2f}."
        )

    print("Provider verified:", actual_provider)
    print(f"Base price verified: ${actual_price:.2f}")

    # Click the View Details input in this exact card.
    view_details = card.locator(
        "input.ViewDetailsBtn"
    )

    view_details.wait_for(
        state="visible",
        timeout=30000,
    )

    if not view_details.is_enabled():
        raise RuntimeError(
            "View Details button is disabled."
        )

    view_details.scroll_into_view_if_needed()
    view_details.click()

    print("View Details clicked.")

    # Verify Product Details.
    product_details = page.locator(
        "#contentpdet:visible"
    )

    product_details.wait_for(
        state="visible",
        timeout=30000,
    )

    product_name = product_details.locator(
        "#product_name"
    )

    product_name.wait_for(
        state="visible",
        timeout=30000,
    )

    actual_name = product_name.inner_text().strip()

    if actual_name.casefold() != requested_plan.casefold():
        raise RuntimeError(
            f"Product Details mismatch. "
            f"Expected: {requested_plan}; Found: {actual_name}"
        )

    print("Correct Product Details page opened.")

    save_screenshot(
        page,
        "selected_plan_details.png",
    )


def add_plan_to_order_and_checkout(page, order):
    """Verify the selected plan and click Add to Order and Checkout."""

    print("\n========== ADD TO ORDER AND CHECKOUT ==========")

    expected_plan = order["plan"].strip()
    expected_price = Decimal(order["base_price"])

    # Confirm Product Details is visible.
    product_details = page.locator("#contentpdet:visible")
    product_details.wait_for(
        state="visible",
        timeout=30000,
    )

    # Verify the exact selected plan.
    product_name = product_details.locator("#product_name")
    actual_plan = product_name.inner_text().strip()

    if actual_plan.casefold() != expected_plan.casefold():
        raise RuntimeError(
            f"Plan mismatch. Expected: {expected_plan}; "
            f"Found: {actual_plan}"
        )

    print("Selected plan verified:", actual_plan)

    # Verify the displayed base price.
    price_text = product_details.locator(
        "#product_basePriceInfo"
    ).inner_text().strip()

    price_match = re.search(r"\$([\d,.]+)", price_text)

    if not price_match:
        raise RuntimeError(
            "Could not read the plan's displayed base price."
        )

    actual_price = Decimal(
        price_match.group(1).replace(",", "")
    )

    if actual_price != expected_price:
        raise RuntimeError(
            f"Price mismatch. Expected ${expected_price:.2f}; "
            f"found ${actual_price:.2f}."
        )

    print(f"Base price verified: ${actual_price:.2f}")

    # Locate the Add to Order and Checkout button.
    checkout_button = page.locator(
        "#addToOrderAndCheckout:visible"
    )

    checkout_button.wait_for(
        state="visible",
        timeout=30000,
    )

    if not checkout_button.is_enabled():
        raise RuntimeError(
            "Add to Order and Checkout button is disabled."
        )

    checkout_button.scroll_into_view_if_needed()

    previous_url = page.url

    checkout_button.click(timeout=30000)

    print("Add to Order and Checkout clicked.")

    # Wait for the simulator to move to the next screen.
    page.wait_for_function(
        """(oldUrl) => window.location.href !== oldUrl""",
        arg=previous_url,
        timeout=60000,
    )

    print("Checkout navigation detected.")
    print("Current page:", page.url)

    save_screenshot(
        page,
        "checkout_after_add_to_order.png",
    )

    print("PASS: Selected Internet plan added to checkout.")



def get_checkout_product_section(checkout, heading):
    """Find a checkout product section. Return None if it is absent."""

    header = checkout.get_by_text(
        re.compile(rf"^\s*{re.escape(heading)}\s*$", re.IGNORECASE)
    )

    if header.count() == 0:
        print(f"{heading} section is not present. Skipping.")
        return None

    for index in range(header.count()):
        current_header = header.nth(index)

        if not current_header.is_visible():
            continue

        section = current_header.locator(
            'xpath=ancestor::*[.//input[@type="radio"]][1]'
        )

        if section.count() == 1:
            return section

    print(f"{heading} section is not visible. Skipping.")
    return None


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
    """Complete and validate Account Holder Qualification."""

    print("\n========== ACCOUNT HOLDER QUALIFICATION ==========")

    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    # 1. Select account holder.
    account_holder = frame.locator("select").first
    account_holder.select_option(label="Phil Dunphy(Customer)")

    print("PASS: Account holder selected.")

    # 2. Select Yes for confirmed test answers.
    radio_groups = [
        ("verified", "Speaking to Account Holder"),
        ("current", "Current Provider XX Customer"),
        ("ez", "EZ-Enroll"),
        ("autopay", "Automatic Payments"),
        ("mailing", "Mailing Address Same as Service"),
        ("shipping", "Shipping Address Same as Service"),
    ]

    for group_name, description in radio_groups:
        radios = frame.locator(
            f'input[type="radio"][name="{group_name}"]'
        )

        yes_radio = None

        for index in range(radios.count()):
            radio = radios.nth(index)

            labels = radio.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label.innerText.trim())
            """)

            if any(label.casefold() == "yes" for label in labels):
                yes_radio = radio
                break

        if yes_radio is None:
            raise RuntimeError(
                f"{description}: Yes option not found."
            )

        if yes_radio.is_disabled():
            raise RuntimeError(
                f"{description}: Yes option is disabled."
            )

        if not yes_radio.is_checked():
            yes_radio.check()

        if not yes_radio.is_checked():
            raise RuntimeError(
                f"{description}: Yes selection failed."
            )

        print(f"PASS: {description} = Yes")

    # 3. Enter phone number.
    phone = order.get("phone") or order.get("phone_number")

    if not phone:
        raise RuntimeError(
            "Phone number is missing from TEST_DATA."
        )

    phone_field = frame.locator(
        'input[placeholder="Phone Number"]'
    )

    if phone_field.count() != 1:
        raise RuntimeError(
            "Could not uniquely identify Phone Number field."
        )

    phone_field.fill(str(phone))

    if phone_field.input_value() != str(phone):
        raise RuntimeError("Phone number validation failed.")

    print("PASS: Phone number entered.")

    # 4. Enter email address.
    email = order.get("email")

    if not email:
        raise RuntimeError(
            "Email address is missing from TEST_DATA."
        )

    email_field = frame.locator(
        'input[placeholder="Email Address"]'
    )

    if email_field.count() != 1:
        raise RuntimeError(
            "Could not uniquely identify Email Address field."
        )

    email_field.fill(str(email))

    if email_field.input_value() != str(email):
        raise RuntimeError("Email address validation failed.")

    print("PASS: Email address entered.")

    # 5. Tick both mandatory Read acknowledgements.
    checkboxes = frame.locator('input[type="checkbox"]')
    read_checkboxes = []

    for index in range(checkboxes.count()):
        checkbox = checkboxes.nth(index)

        labels = checkbox.evaluate("""
            el => Array.from(el.labels || [])
                .map(label => label.innerText.trim())
        """)

        if any(label.casefold() == "read" for label in labels):
            read_checkboxes.append(checkbox)

    if len(read_checkboxes) < 2:
        raise RuntimeError(
            "Expected two mandatory Read acknowledgements, "
            f"but found {len(read_checkboxes)}."
        )

    for index, checkbox in enumerate(read_checkboxes, start=1):
        if checkbox.is_disabled():
            raise RuntimeError(
                f"Mandatory Read acknowledgement {index} is disabled."
            )

        if not checkbox.is_checked():
            checkbox.check()

        if not checkbox.is_checked():
            raise RuntimeError(
                f"Mandatory Read acknowledgement {index} failed."
            )

        print(
            f"PASS: Mandatory Read acknowledgement {index} checked."
        )

    # 6. Final validation.
    print("\n========== ACCOUNT HOLDER VALIDATION ==========")

    for group_name, description in radio_groups:
        radios = frame.locator(
            f'input[type="radio"][name="{group_name}"]'
        )

        yes_selected = False

        for index in range(radios.count()):
            radio = radios.nth(index)

            labels = radio.evaluate("""
                el => Array.from(el.labels || [])
                    .map(label => label.innerText.trim())
            """)

            if (
                any(label.casefold() == "yes" for label in labels)
                and radio.is_checked()
            ):
                yes_selected = True
                break

        if not yes_selected:
            raise RuntimeError(
                f"Validation failed: {description}."
            )

    if not phone_field.input_value():
        raise RuntimeError("Phone number is empty.")

    if not email_field.input_value():
        raise RuntimeError("Email address is empty.")

    print("All Account Holder Qualification fields validated.")

    save_screenshot(
        page,
        "account_holder_qualification_completed.png"
    )

    # 7. Click Forward.
    forward_button = frame.get_by_role(
        "button",
        name=re.compile(r"^\s*Forward\s*>?\s*$", re.IGNORECASE)
    )

    forward_button.wait_for(
        state="visible",
        timeout=30000
    )

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
    

def automate_installation_payment(page, order):
    """Handle Standard Shipping and Professional Installation."""

    from datetime import date
    import re

    print("\n========== INSTALLATION AND PAYMENT ==========")

    frame = page.frame(name="checkoutContent")

    if frame is None:
        raise RuntimeError("Checkout iframe not found.")

    installation_type = order.get(
        "installation_type", "STANDARD_SHIPPING"
    ).strip().upper()

    if installation_type not in ("STANDARD_SHIPPING", "PRO_INSTALL"):
        raise ValueError("Invalid installation type.")

    # Find the installation radio using its actual label/value.
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
            [details["value"]] +
            details["labels"] +
            [details["parent"]]
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
            f"Could not find installation option: {installation_type}"
        )

    selected_radio.check()

    if not selected_radio.is_checked():
        raise RuntimeError("Installation selection failed.")

    print(f"PASS: {installation_type} selected.")

    # Professional Installation requires additional details.
    if installation_type == "PRO_INSTALL":

        install_date = str(
            order.get("installation_date", "")
        ).strip()

        install_time = str(
            order.get("installation_time", "")
        ).strip()

        if not install_date:
            raise ValueError(
                "Enter the customer-selected installation_date "
                "in TEST_DATA."
            )

        parsed_date = date.fromisoformat(install_date)

        if parsed_date < date.today():
            raise ValueError("Installation date cannot be in the past.")

        if install_time not in (
            "Morning", "Afternoon", "Evening"
        ):
            raise ValueError(
                "Invalid installation time. Choose Morning, "
                "Afternoon, or Evening."
            )

        # Locate the date field.
        date_field = frame.locator(
            'input[type="date"]:visible, '
            'input[placeholder*="dd-mm-yyyy" i]:visible'
        )

        if date_field.count() != 1:
            raise RuntimeError(
                "Could not uniquely identify installation date field."
            )

        date_field.fill(install_date)

        if date_field.input_value() != install_date:
            raise RuntimeError("Installation date validation failed.")

        print("PASS: Installation date entered.")

        # Locate the dropdown by its actual options.
        selects = frame.locator("select:visible")
        time_dropdown = None

        for index in range(selects.count()):
            candidate = selects.nth(index)

            options = [
                value.strip()
                for value in candidate.locator(
                    "option"
                ).all_text_contents()
            ]

            if all(
                value in options
                for value in ("Morning", "Afternoon", "Evening")
            ):
                time_dropdown = candidate
                break

        if time_dropdown is None:
            raise RuntimeError(
                "Installation time dropdown not found."
            )

        time_dropdown.select_option(label=install_time)

        if time_dropdown.locator(
            "option:checked"
        ).inner_text().strip() != install_time:
            raise RuntimeError("Installation time selection failed.")

        print(f"PASS: Preferred time: {install_time}")

        # Tick the two mandatory installation disclosures.
        required_disclosures = [
            (
                "over the age of 18",
                "Adult availability acknowledgement"
            ),
            (
                "availability of installation dates",
                "Installation availability acknowledgement"
            ),
        ]

        checkboxes = frame.locator('input[type="checkbox"]')

        for phrase, description in required_disclosures:

            matching_checkbox = None

            for index in range(checkboxes.count()):
                checkbox = checkboxes.nth(index)

                surrounding_text = checkbox.evaluate("""
                    el => {
                        let node = el;

                        for (
                            let level = 0;
                            level < 5 && node;
                            level++, node = node.parentElement
                        ) {
                            const text = (node.innerText || "").trim();
                            if (text) return text;
                        }

                        return "";
                    }
                """)

                if phrase in " ".join(
                    surrounding_text.casefold().split()
                ):
                    matching_checkbox = checkbox
                    break

            if matching_checkbox is None:
                raise RuntimeError(
                    f"Mandatory acknowledgement not found: {description}"
                )

            if not matching_checkbox.is_checked():
                matching_checkbox.check()

            if not matching_checkbox.is_checked():
                raise RuntimeError(
                    f"Could not check: {description}"
                )

            print(f"PASS: {description} checked.")

    # Confirm the installation fee before proceeding.
    page_text = frame.locator("body").inner_text()

    if installation_type == "PRO_INSTALL":
        if not re.search(
            r"Installation Total\s*:\s*\$100\.00",
            page_text,
            re.I
        ):
            raise RuntimeError(
                "Expected $100.00 installation total was not verified."
            )
    else:
        if not re.search(
            r"Installation Total\s*:\s*\$0\.00",
            page_text,
            re.I
        ):
            raise RuntimeError(
                "Expected $0.00 standard shipping total was not verified."
            )

    print("PASS: Installation total verified.")

    save_screenshot(
        page,
        "installation_payment_before_confirm.png"
    )

    confirm_button = frame.get_by_role(
        "button",
        name=re.compile(
            r"^\s*Confirm Installation\s*>?\s*$",
            re.I
        )
    )

    confirm_button.wait_for(
        state="visible",
        timeout=30000
    )

    if not confirm_button.is_enabled():
        raise RuntimeError("Confirm Installation is disabled.")

    confirm_button.scroll_into_view_if_needed()
    confirm_button.click()

    print("PASS: Confirm Installation clicked.")

    page.wait_for_timeout(2000)

    save_screenshot(
        page,
        "installation_payment_after_confirm.png"
    )

    print("Installation workflow completed.")


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
    """Run the complete Provider XX order automation workflow."""

    manager = BrowserManager()

    try:
        print("\n========== PROVIDER XX ORDER AUTOMATION ==========")

        # -------------------------------------------------
        # 1. LAUNCH BROWSER
        # -------------------------------------------------

        page = manager.start()
        manager.open_page(SIMULATOR_URL)

        print("Chromium browser launched successfully.")
        print("Simulator opened.")

        # -------------------------------------------------
        # 2. LOGIN AND START SESSION
        # -------------------------------------------------

        login_and_start_session(page)

        # -------------------------------------------------
        # 3. BASIC INFORMATION
        # -------------------------------------------------

        validation_passed = fill_basic_information(page)

        if not validation_passed:
            raise RuntimeError(
                "Basic Information validation failed."
            )

        # FIRST FORWARD:
        # Basic Information -> Valid Address
        submit_basic_information(page)

        # -------------------------------------------------
        # 4. VALID ADDRESS
        # -------------------------------------------------

        # SECOND FORWARD:
        # Valid Address -> Qualification
        proceed_to_valid_address(page)

        # -------------------------------------------------
        # 5. CUSTOMER QUALIFICATION
        # -------------------------------------------------

        # THIRD FORWARD:
        # Qualification -> Recommendations
        qualify_as_new_customer(page)

        # -------------------------------------------------
        # 6. PROVIDER SELECTION
        # -------------------------------------------------

        check_provider_availability(
            page,
            TEST_DATA
        )

        # -------------------------------------------------
        # 7. INTERNET PLAN SELECTION
        # -------------------------------------------------

        select_internet_offer(
            page,
            TEST_DATA
        )

        # -------------------------------------------------
        # 8. ADD PLAN TO ORDER
        # -------------------------------------------------

        add_plan_to_order_and_checkout(
            page,
            TEST_DATA
        )

        # -------------------------------------------------
        # 9. CHECKOUT REVIEW
        # -------------------------------------------------

        proceed_to_product_customization(page)

        # -------------------------------------------------
        # 10. PRODUCT CUSTOMIZATION
        # -------------------------------------------------

        customize_checkout_products(
            page,
            TEST_DATA
        )

        # -------------------------------------------------
        # 11. ACCOUNT HOLDER QUALIFICATION
        # -------------------------------------------------

        automate_account_holder_qualification(
            page,
            TEST_DATA
        )

        # Wait for Installation & Payment to load.
        checkout_frame = page.frame(
            name="checkoutContent"
        )

        if checkout_frame is None:
            raise RuntimeError(
                "Checkout iframe not found after Account Holder Qualification."
            )

        installation_heading = checkout_frame.locator(
            "div.panel-title"
        ).filter(
            has_text=re.compile(
                r"Installation and Payment",
                re.IGNORECASE
            )
        ).first

        installation_heading.wait_for(
            state="visible",
            timeout=30000
        )

        print(
            "\nInstallation & Payment page detected successfully."
        )

        save_screenshot(
            page,
            "installation_payment_page.png"
        )

        # -------------------------------------------------
        # 12. INSTALLATION TYPE SELECTION
        # -------------------------------------------------

        # TEST_DATA controls the installation path:
        #
        # STANDARD_SHIPPING = Free
        # PRO_INSTALL       = $100
        #
        # Professional installation also requires
        # a customer-selected date, time and acknowledgements.

        automate_installation_payment(
            page,
            TEST_DATA
        )
        complete_payment_page(page)
        # -------------------------------------------------
        # 13. AUTOMATION RESULT
        # -------------------------------------------------
        inspect_payment_fields(page)
        
        print("\n========== AUTOMATION RESULT ==========")

        print("Manual Login: Completed")
        print("Basic Information: Passed")
        print("Address Validation: Passed")
        print("Customer Qualification: Passed")
        print("ProviderXX Selection: Passed")
        print("Internet Plan Selection: Passed")
        print("Checkout: Completed")
        print("Product Customization: Completed")
        print("Account Holder Qualification: Completed")

        print(
            "Installation Type:",
            TEST_DATA["installation_type"]
        )

        print("Installation Workflow: Completed")

        print(
            "\nAutomation stopped before Authorization "
            "and final order submission."
        )

        print(
            "\nScreenshot directory:",
            SCREENSHOT_DIR
        )

        input(
            "\nPress Enter to close the browser..."
        )

    except PlaywrightError as error:

        print("\n========== PLAYWRIGHT ERROR ==========")
        print(str(error))

        if manager.page and not manager.page.is_closed():
            save_screenshot(
                manager.page,
                "automation_error.png"
            )

        input(
            "\nPress Enter to close the browser..."
        )

    except Exception as error:

        print("\n========== UNEXPECTED ERROR ==========")
        print(str(error))

        if manager.page and not manager.page.is_closed():
            save_screenshot(
                manager.page,
                "automation_error.png"
            )

        input(
            "\nPress Enter to close the browser..."
        )

    finally:

        manager.close()

        print("\nBrowser closed successfully.")


if __name__ == "__main__":
    main()
