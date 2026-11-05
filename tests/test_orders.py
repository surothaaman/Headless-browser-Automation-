from app.automation.browser import BrowserManager
from playwright.sync_api import Error as PlaywrightError

from tests.test_browser_launch import save_screenshot

# Keep the original simulator URL exactly unchanged.
SIMULATOR_URL = (
    "https://lemon-forest-0915c3c1e.6.azurestaticapps.net/?next=%2Fallconnect%2F"
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


def fill_basic_information(page):
    print("\n========== FILLING BASIC INFORMATION ==========")

    page.locator("#namePrefixList").select_option(label=TEST_DATA["prefix"])
    page.locator("#firstName").fill(TEST_DATA["first_name"])
    page.locator("#middleName").fill(TEST_DATA["middle_name"])
    page.locator("#lastName").fill(TEST_DATA["last_name"])

    print("Customer name entered.")

    # ZIP lookup
    page.locator("#ssZipCode").fill(TEST_DATA["zip_code"])
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

    print("ZIP Code lookup completed.")

    # Address and unit details
    page.locator("#address1").fill(TEST_DATA["address"])

    page.locator("#unitTypeList").select_option(label=TEST_DATA["unit_type"])

    page.locator("#unitNumber").fill(TEST_DATA["unit_number"])

    page.locator("#city").fill(TEST_DATA["city"])

    page.locator("#stateList").select_option(value=TEST_DATA["state"])

    print("Address and unit details entered.")

    # Dwelling and ownership
    page.locator("#serviceAddressTypeList").select_option(
        label=TEST_DATA["dwelling_type"]
    )

    page.locator("#rentOwnList").select_option(label=TEST_DATA["ownership"])

    page.locator("#customerMove").select_option(label=TEST_DATA["moving"])

    print("Dwelling and moving details entered.")

    # Verify all entered fields
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

    print("\n========== FIELD VALIDATION ==========")

    all_valid = True

    for selector, expected in expected_values.items():
        actual = page.locator(selector).input_value()
        valid = actual == expected

        print(
            f"{selector} | Expected: {expected} | " f"Actual: {actual} | Valid: {valid}"
        )

        if not valid:
            all_valid = False

    page.screenshot(
        path="tests/basic_information_filled.png",
        full_page=True,
    )

    print("Screenshot saved: tests/basic_information_filled.png")

    return all_valid


def proceed_to_valid_address(page):
    """Validate the address and click the actual Forward control."""

    print("\n========== VALID ADDRESS ==========")

    # Confirm that the Valid Address page has loaded.
    page.wait_for_url(
        "**/valid-address/",
        timeout=60000,
    )

    print("Valid Address page loaded.")

    # Wait for the successful address message.
    matched_message = page.locator("p.green").filter(
        has_text="Proceed to the next screen"
    )

    matched_message.first.wait_for(
        state="visible",
        timeout=60000,
    )

    print("Address Matched successfully.")

    save_screenshot(
        page,
        "valid_address_page.png",
    )

    # Inspect visible controls that contain Forward.
    forward_controls = page.locator(
        "button:visible, "
        "input[type='button']:visible, "
        "input[type='submit']:visible, "
        "a:visible"
    )

    matching_controls = []

    for index in range(forward_controls.count()):
        control = forward_controls.nth(index)

        details = control.evaluate("""element => ({
                tag: element.tagName,
                id: element.id,
                text: (
                    element.innerText ||
                    element.value ||
                    element.getAttribute("aria-label") ||
                    ""
                ).trim(),
                disabled: element.disabled,
                visible: !!(
                    element.offsetWidth ||
                    element.offsetHeight ||
                    element.getClientRects().length
                )
            })""")

        if "forward" in details["text"].lower():
            matching_controls.append((index, details))

    print("\n========== FORWARD CONTROL INSPECTION ==========")

    for index, details in matching_controls:
        print(
            f"Index: {index} | "
            f"Tag: {details['tag']} | "
            f"ID: {details['id']} | "
            f"Text: {details['text']} | "
            f"Disabled: {details['disabled']}"
        )

    if not matching_controls:
        raise RuntimeError("No visible Forward control was found on Valid Address.")

    # Use the last matching visible Forward control.
    index, details = matching_controls[-1]

    forward_button = forward_controls.nth(index)

    if details["disabled"]:
        raise RuntimeError("The Valid Address Forward control is disabled.")

    forward_button.scroll_into_view_if_needed()
    forward_button.click(timeout=15000)

    print("\nValid Address Forward clicked successfully.")

    # Wait for the application to leave Valid Address.
    page.wait_for_function(
        """() => !window.location.pathname.endsWith('/valid-address/')""",
        timeout=60000,
    )

    print("Navigation completed.")
    print("Next page URL:", page.url)

    save_screenshot(
        page,
        "next_page_after_valid_address.png",
    )

    return True


def main():
    manager = BrowserManager()

    try:
        # Launch browser using the original URL.
        page = manager.start()
        manager.open_page(SIMULATOR_URL)

        print("\nComplete login manually.")
        print("Waiting for Idle Page...")

        page.locator('body[data-ac-page="idle"]').wait_for(
            state="attached",
            timeout=300000,
        )

        print("Idle Page detected.")

        # Start session.
        page.locator("#startCall").click()

        print("Start Session clicked.")

        # Greetings page.
        page.locator("#content_header").get_by_text(
            "Greetings",
            exact=True,
        ).wait_for(
            state="visible",
            timeout=60000,
        )

        print("Greetings page detected.")

        # Navigate to Basic Information.
        page.get_by_role(
            "button",
            name="Forward",
            exact=False,
        ).click()

        page.locator('body[data-ac-page="basic-information"]').wait_for(
            state="attached",
            timeout=30000,
        )

        print("Basic Information page detected.")

        # Fill and validate the form.
        validation_passed = fill_basic_information(page)

        if not validation_passed:
            print("\nBASIC INFORMATION VALIDATION FAILED.")
            print("Forward was NOT clicked.")

            input("\nPress Enter to close the browser...")
            return

        print("\nBASIC INFORMATION VALIDATION PASSED.")

        # Proceed to Valid Address.
        proceed_to_valid_address(page)

        input("\nPress Enter to close the browser...")

    except PlaywrightError as error:
        print("\nPlaywright error:", error)

        if manager.page and not manager.page.is_closed():
            manager.page.screenshot(
                path="tests/automation_error.png",
                full_page=True,
            )

    except Exception as error:
        print("\nUnexpected error:", error)

        if manager.page and not manager.page.is_closed():
            manager.page.screenshot(
                path="tests/automation_error.png",
                full_page=True,
            )

    finally:
        manager.close()
        print("Browser closed.")


if __name__ == "__main__":
    main()
