# Provider XX Order Automation

## Allconnect Order Workflow Documentation

## 1. Project Overview

**Objective:** Automate the authorised Allconnect simulator workflow for creating a Provider XX order.

**Automation tool:** Python Playwright  
**Backend:** FastAPI  
**Expected input:** A validated order request through one POST API endpoint.  
**Expected output:** Final order summary and order verification status.

The automation begins when a new order request is received and ends after the final Order Summary is displayed and verified.

---

## 2. End-to-End Workflow

1. Login to the authorised Allconnect simulator.
2. Start a new session.
3. Enter customer and service address information.
4. Verify the service address.
5. Select whether the customer is new or transferring from another provider.
6. Review available providers and select Provider XX.
7. Select the required internet plan.
8. Review product details and add the selected plan to the order.
9. Complete product customization.
10. Complete account-holder qualification.
11. Complete installation and payment-related steps.
12. Complete any remaining authorization requirements.
13. Display and verify the final Order Summary.
14. Return the order result through the FastAPI endpoint.

---

## 3. Screen-by-Screen Documentation

### Screen 1: Login and Start Session

**Purpose:** Start a new customer interaction.

**Observed actions:**

1. Open the authorised portal.
2. Authenticate using authorised credentials.
3. Click Start Session.
4. Review the greeting screen.
5. Click Forward.

**Buttons:** Login, Start Session, Forward.

**Automation requirement:** Confirm successful login and session creation before proceeding.

**Security:** Credentials must be stored securely and must never be hardcoded or committed to GitHub.

### Screen 2: Customer Address

**Purpose:** Collect the customer's service address and identify the service location.

**Fields identified from the workflow:**

- ZIP code
- Address line
- Additional address details, where applicable
- City
- Customer first name
- Customer last name
- Title
- Property type
- Own or rent
- Moving status
- Move date, where applicable

**Property type examples:**

- Apartment
- Condo
- Duplex
- House
- Mobile home

**Moving status:** Moving to a new place or already living at the address.

**Additional information:** A lead ID is generated dynamically by the simulator.

**Automation requirement:** Enter the supplied address and customer information, then proceed to address validation.

### Screen 3: Valid Address

**Purpose:** Confirm that the entered service address is matched.

**Observed result:**

- Address Matched
- Proceed to the next screen

**Action:** Click Forward after successful address matching.

**Automation requirement:** Verify the address-matched result before proceeding. If the address is not matched, stop and return an appropriate error.

### Screen 4: Qualification

**Purpose:** Identify the customer type and determine available service options.

**Question:** Is this a new or transfer customer?

**Options:**

- New
- Transfer

**For transfer customers:** The portal asks for the current service provider.

**Observed provider options include:**

- ProviderVZ 5G
- ProviderXX
- ProviderOP ST
- ProviderAT IG
- ProviderTM IG
- Others

**Other information:**

- Customer information is displayed in a side panel.
- Provider availability is displayed in the Real Time Status panel.
- The Forward button continues the workflow.

**Automation requirement:** Select the correct customer type and, for transfer customers, the current provider based on the request.

### Screen 5: Recommendations and Internet Plan Selection

**Purpose:** Display available providers and internet plans for the validated address.

**Observed information:**

- Provider name
- Internet speed
- Base monthly price
- Pricing term
- Product description
- Availability status

**Observed internet plan examples:**

- 300 Mbps
- 500 Mbps
- 1 Gbps
- 2 Gbps

These are examples observed in the simulator, not a fixed list of plans.

**Selection process:**

1. Open the Internet section from the product navigation menu.
2. Review available Provider XX plans.
3. Select the required internet plan.
4. Click View Details.
5. Review the product information, features, promotions and pricing.
6. Click Add to Order and Checkout.

**Important:** The selected plan and pricing must match the API request.

### Screen 6: Checkout – Product Selection

**Purpose:** Review and customize the products included in the order.

**Video options observed:**

- Ultimate TV
- Popular TV
- World Soccer Ticket
- None

**Internet:** The selected internet plan is displayed, with alternative plans available.

**Phone options observed:**

- ProviderXX Voice Premier
- None

**Action:** Verify the selected products and click Forward.

### Screen 7: Checkout – Product Customization

**Purpose:** Review product disclosures and configure optional equipment and services.

**Fields and controls observed:**

1. Broadband Fact Labels
   - Customer requested the Broadband Fact Labels
   - Customer did not request the Broadband Fact Labels
   - Read checkbox

2. Internet Features
   - SHOW_CONSENT is displayed.

3. HSD Equipment Auto Choice
   - XI/XV Leased Gateway (Free)
   - Internet/Voice Equipment Own (Free)

4. NOW TV with Streaming Apps
   - NOW TV with Streaming Apps
   - Monthly price displayed: $30.00

**Automation requirement:**

- Select the correct disclosure response.
- Complete mandatory Read acknowledgements.
- Select equipment according to the order request.
- Select optional streaming services only when requested.
- Verify the configured products and continue.

### Screen 8: Account Holder Qualification

**Purpose:** Verify the account holder and collect the required account information.

**Observed controls and questions:**

- Account holder selection dropdown
- Agent verification: Are you speaking to the Account Holder? Yes / No
- Customer currently a ProviderXX customer? Yes / No
- Continue with EZ-Enroll? Yes / No
- Continue with Automatic Payments and Paperless Billing Discount? Yes / No
- Read acknowledgement for the automatic payment disclosure
- Mailing address same as service address? Yes / No
- Shipping address same as service address? Yes / No

**Account-holder details observed when verification is selected:**

- Prefix
- First name
- Middle name or initial
- Last name
- Suffix
- Phone number
- Email address

**Conditional behaviour:**

- Selecting different mailing or shipping addresses may require additional address details. This must be verified during further testing.
- Account-holder verification is required before continuing.

**Automation requirement:** Validate the account-holder information, apply the correct Yes/No responses and complete mandatory acknowledgements.

### Screen 9: Installation and Payment

**Purpose:** Review credit-check results and configure installation.

**Credit-check information observed:**

- Social Security Number (SSN)
- Date of Birth
- Credit Check Status

**Order Qualification Status:**

- Processing Status
- LineItem Status
- Pre-Payment

**Important security requirement:** Use synthetic test data only. Never log, store in ordinary order records or commit raw SSNs, dates of birth or payment credentials.

**Installation type options observed:**

| Option            | Cost shown |
| ----------------- | ---------: |
| STANDARD_SHIPPING |       Free |
| PRO_INSTALL       |    $100.00 |

**When PRO_INSTALL is selected, additional controls appear:**

- Read acknowledgement: Someone over the age of 18 must be available at installation.
- Install Date
- Preferred time of day:
  - Morning
  - Afternoon
  - Evening
- Read acknowledgement: Installation dates and times may not be confirmed until the order is processed.

**Action:** Complete the required installation selections and click Confirm Installation.

### Screen 10: Authorization

The checkout sidebar displays Step 4 – Authorization.

**Status:** Not yet independently documented.

The exact fields, controls, validation messages and actions on this step must be inspected before implementing this section of the automation.

### Screen 11: Final Order Summary

**Purpose:** Display and verify the completed order.

**Information observed:**

- Provider
- Selected product/plan
- Account holder
- Base monthly price
- Selected product add-ons
- Equipment selection
- Installation selection
- Monthly total
- Installation total
- One-time fee
- Promotion information
- Checkout status

**Observed completion status:** CHECKOUT_COMPLETED

**Final verification requirements:**

1. Confirm that the Order Summary is displayed.
2. Confirm the provider is Provider XX.
3. Confirm the selected plan matches the requested plan.
4. Confirm the account holder matches the request.
5. Verify monthly and installation totals.
6. Verify relevant product add-ons and equipment.
7. Confirm the checkout completion status.

**Automation end condition:** Stop after successfully verifying the final Order Summary.

If any required value does not match, return a verification failure instead of reporting a successful order.

---

## 4. Error Handling Requirements

The automation must handle:

- Login failure
- Session creation failure
- Address not matched
- Provider unavailable
- Requested plan unavailable
- Invalid or incomplete customer information
- Missing mandatory acknowledgements
- Account-holder verification failure
- Credit-check or qualification failure
- Installation selection failure
- Checkout failure
- Order Summary mismatch
- Browser timeout or unexpected page navigation

The automation must not report success unless the final order status and required summary fields have been verified.

---

## 5. Automation Completion Criteria

The workflow is considered complete when:

- The order reaches the final Order Summary.
- The checkout status is verified as completed.
- The requested provider and plan are correct.
- Customer and account-holder details match.
- Monthly and installation totals are verified.
- The API receives a structured result containing the order status and verification outcome.
