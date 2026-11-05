from pathlib import Path

from app.automation.browser import BrowserManager
from playwright.sync_api import Error as PlaywrightError

# Keep the original working simulator URL unchanged.
SIMULATOR_URL = (
    "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/" "?next=%2Fallconnect%2F"
)

# Synthetic test data only.
TEST_DATA = {
    "prefix": "Mr",
    "first_name": "Test",
    "middle_name": "A",
    "last_name": "Customer",
    "zip_code": "10001",
    "address": "123 Test Street",
    "unit_type": "Suite",
    "unit_number": "101",
    "city": "New York",
    "state": "NY",
    "dwelling_type": "House",
    "ownership": "Own",
    "moving": "No",
}

SCREENSHOT_DIR = Path("tests/screenshots")


def save_screenshot(page, filename):
    """Save screenshots locally for testing."""

    SCREENSHOT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    screenshot_path = SCREENSHOT_DIR / filename

    page.screenshot(
        path=str(screenshot_path),
        full_page=True,
    )

    print(f"Screenshot saved: {screenshot_path}")


def wait_for_basic_information(page):
    """Wait for the Basic Information page."""

    page.locator('body[data-ac-page="basic-information"]').wait_for(
        state="visible",
        timeout=60000,
    )

    print("Basic Information page detected.")


def login_and_start_session(page):
    """Wait for manual login and start the session."""

    print("\n========== LOGIN AND SESSION ==========")
    print("Complete login manually in the browser.")
    print("Waiting for Idle Page...")

    page.locator('body[data-ac-page="idle"]').wait_for(
        state="attached",
        timeout=300000,
    )

    print("Idle Page detected successfully.")

    # Start Session.
    page.locator("#startCall").click()

    print("Start Session clicked successfully.")

    # Wait for Greetings.
    page.locator("#content_header").get_by_text(
        "Greetings",
        exact=True,
    ).wait_for(
        state="visible",
        timeout=60000,
    )

    print("Greetings page detected.")

    # Forward: Greetings -> Basic Information.
    page.get_by_role(
        "button",
        name="Forward",
        exact=False,
    ).click()

    print("Greetings Forward button clicked.")

    wait_for_basic_information(page)


def fill_basic_information(page):
    """Fill the Basic Information form with synthetic data."""

    print("\n========== FILLING BASIC INFORMATION ==========")

    # Customer name.
    page.locator("#namePrefixList").select_option(label=TEST_DATA["prefix"])

    page.locator("#firstName").fill(TEST_DATA["first_name"])

    page.locator("#middleName").fill(TEST_DATA["middle_name"])

    page.locator("#lastName").fill(TEST_DATA["last_name"])

    print("Customer name entered.")

    # ZIP Code lookup.
    page.locator("#ssZipCode").fill(TEST_DATA["zip_code"])

    page.locator("#ssZipCode").press("Tab")

    page.wait_for_function(
        """() => {
            const address = document.querySelector("#address1");
            const city = document.querySelector("#city");
            const state = document.querySelector("#stateList");

            return (
                address &&
                city &&
                state &&
                !address.disabled &&
                !city.disabled &&
                !state.disabled
            );
        }""",
        timeout=30000,
    )

    print("ZIP Code lookup completed.")

    # Address details.
    page.locator("#address1").fill(TEST_DATA["address"])

    page.locator("#unitTypeList").select_option(label=TEST_DATA["unit_type"])

    page.locator("#unitNumber").fill(TEST_DATA["unit_number"])

    page.locator("#city").fill(TEST_DATA["city"])

    page.locator("#stateList").select_option(value=TEST_DATA["state"])

    print("Address and unit details entered.")

    # Dwelling and ownership.
    page.locator("#serviceAddressTypeList").select_option(
        label=TEST_DATA["dwelling_type"]
    )

    page.locator("#rentOwnList").select_option(label=TEST_DATA["ownership"])

    page.locator("#customerMove").select_option(label=TEST_DATA["moving"])

    print("Dwelling and moving details entered.")

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
            f"{selector} | "
            f"Expected: {expected} | "
            f"Actual: {actual} | "
            f"Valid: {valid}"
        )

        if not valid:
            all_valid = False

    save_screenshot(
        page,
        "basic_information_filled.png",
    )

    if all_valid:
        print("\nBASIC INFORMATION VALIDATION PASSED.")
    else:
        print("\nBASIC INFORMATION VALIDATION FAILED.")

    return all_valid


def submit_basic_information(page):
    """
    FIRST FORWARD BUTTON:
    Basic Information -> Valid Address.
    """

    print("\n========== FIRST FORWARD: BASIC INFORMATION ==========")

    forward_button = page.locator("#basicInfoForward")

    forward_button.wait_for(
        state="visible",
        timeout=30000,
    )

    if not forward_button.is_enabled():
        raise RuntimeError("Basic Information Forward button is disabled.")

    forward_button.scroll_into_view_if_needed()
    forward_button.click()

    print("First Forward button clicked.")

    # Wait for Valid Address page.
    page.wait_for_url(
        "**/valid-address/",
        timeout=60000,
    )

    page.locator('body[data-ac-page="valid-address"]').wait_for(
        state="visible",
        timeout=30000,
    )

    print("Valid Address page opened successfully.")

    save_screenshot(
        page,
        "valid_address_page.png",
    )


def proceed_to_valid_address(page):
    """
    SECOND FORWARD BUTTON:
    Valid Address -> Qualification.
    """

    print("\n========== SECOND FORWARD: VALID ADDRESS ==========")

    # Wait for the actual successful address message.
    page.locator("#Valid_Address_FS1").locator("p.green").wait_for(
        state="visible",
        timeout=60000,
    )

    print("Address Matched successfully.")

    # Exact button ID confirmed from the uploaded HTML.
    forward_button = page.locator("#addressFoundForward")

    forward_button.wait_for(
        state="visible",
        timeout=30000,
    )

    if not forward_button.is_enabled():
        raise RuntimeError("Valid Address Forward button is disabled.")

    forward_button.scroll_into_view_if_needed()
    forward_button.click()

    print("Second Forward button clicked.")

    # Verify actual navigation to Qualification.
    page.wait_for_url(
        "**/qualification/",
        timeout=60000,
    )

    print("Qualification URL detected.")

    page.locator('body[data-ac-page="qualification"]').wait_for(
        state="visible",
        timeout=60000,
    )

    print("Qualification page detected successfully.")

    save_screenshot(
        page,
        "qualification_page.png",
    )

    return True


def main():
    """Run the Provider XX browser automation."""

    manager = BrowserManager()

    try:
        print("\n========== PROVIDER XX ORDER AUTOMATION ==========")

        # Launch browser.
        page = manager.start()

        manager.open_page(SIMULATOR_URL)

        print("Chromium browser launched successfully.")
        print("Simulator opened successfully.")

        # Manual login and session start.
        login_and_start_session(page)

        # Fill Basic Information.
        validation_passed = fill_basic_information(page)

        if not validation_passed:
            print("\nBasic Information validation failed.")
            print("Automation stopped. Forward was not clicked.")

            input("\nPress Enter to close the browser...")
            return

        # FIRST FORWARD:
        # Basic Information -> Valid Address.
        submit_basic_information(page)

        # SECOND FORWARD:
        # Valid Address -> Qualification.
        proceed_to_valid_address(page)

        # Final result.
        print("\n========== AUTOMATION RESULT ==========")

        print("Manual Login: Completed")
        print("Session Start: Completed")
        print("Greetings: Completed")
        print("Basic Information: Completed")
        print("Field Validation: Passed")
        print("First Forward: Successful")
        print("Valid Address: Completed")
        print("Second Forward: Successful")
        print("Qualification: Opened successfully")

        print("\nScreenshots saved in:", SCREENSHOT_DIR)

        input("\nPress Enter to close the browser...")

    except PlaywrightError as error:
        print("\nPLAYWRIGHT ERROR:")
        print(str(error))

        if manager.page and not manager.page.is_closed():
            save_screenshot(
                manager.page,
                "automation_error.png",
            )

    except Exception as error:
        print("\nUNEXPECTED ERROR:")
        print(str(error))

        if manager.page and not manager.page.is_closed():
            save_screenshot(
                manager.page,
                "automation_error.png",
            )

    finally:
        manager.close()
        print("Browser closed.")


if __name__ == "__main__":
    main()
