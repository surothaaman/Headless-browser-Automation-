# Provider XX Order Automation

## API Field Documentation

## 1. API Overview

**Method:** POST  
**Suggested endpoint:** `/api/orders/`  
**Purpose:** Receive customer, address, product and installation details and initiate the authorised Allconnect browser workflow.

The endpoint validates the request before starting browser automation.

## 2. Customer Information

| Field       | Data type | Required  | Description            |
| ----------- | --------- | --------- | ---------------------- |
| first_name  | string    | Yes       | Customer first name    |
| last_name   | string    | Yes       | Customer last name     |
| title       | string    | To verify | Customer title         |
| email       | string    | Yes       | Customer email         |
| phone       | string    | Yes       | Customer phone number  |
| prefix      | string    | To verify | Account-holder prefix  |
| middle_name | string    | No        | Middle name or initial |
| suffix      | string    | No        | Account-holder suffix  |

## 3. Service Address

| Field            | Data type | Required    | Description                                    |
| ---------------- | --------- | ----------- | ---------------------------------------------- |
| zip_code         | string    | Yes         | Service ZIP code                               |
| address_line_1   | string    | Yes         | Main address                                   |
| address_line_2   | string    | No          | Apartment, unit or additional address          |
| city             | string    | Yes         | City                                           |
| state            | string    | Yes         | State                                          |
| property_type    | string    | To verify   | Apartment, condo, duplex, house or mobile home |
| ownership_status | string    | To verify   | Own or rent                                    |
| moving_status    | string    | To verify   | Moving or already living at the address        |
| move_date        | date      | Conditional | Applicable moving date                         |

## 4. Customer Qualification

| Field            | Data type | Required    | Description                     |
| ---------------- | --------- | ----------- | ------------------------------- |
| customer_type    | string    | Yes         | `new` or `transfer`             |
| current_provider | string    | Conditional | Required for transfer customers |

## 5. Product Selection

| Field                       | Data type | Required  | Description                                |
| --------------------------- | --------- | --------- | ------------------------------------------ |
| provider                    | string    | Yes       | Provider XX                                |
| internet_speed_mbps         | integer   | Yes       | Requested internet speed                   |
| pricing_term                | string    | To verify | Pricing term selected                      |
| video_plan                  | string    | No        | Selected video package or none             |
| phone_plan                  | string    | No        | Selected phone package or none             |
| equipment_choice            | string    | To verify | Leased gateway or customer-owned equipment |
| now_tv                      | boolean   | No        | Whether NOW TV is requested                |
| broadband_fact_label_choice | string    | To verify | Requested or not requested                 |
| broadband_fact_label_read   | boolean   | Yes       | Disclosure acknowledgement                 |

The available plans and prices must be read from the simulator. Do not hardcode prices as permanent values.

## 6. Account Holder Qualification

| Field                              | Data type | Required    | Description                                       |
| ---------------------------------- | --------- | ----------- | ------------------------------------------------- |
| account_holder_id                  | string    | To verify   | Selected account holder                           |
| is_account_holder_verified         | boolean   | Yes         | Agent verification response                       |
| is_existing_provider_customer      | boolean   | Yes         | Whether customer currently uses Provider XX       |
| ez_enroll                          | boolean   | To verify   | EZ-Enroll selection                               |
| automatic_payments_paperless       | boolean   | To verify   | Automatic payment and paperless billing selection |
| automatic_payments_disclosure_read | boolean   | Conditional | Required acknowledgement when applicable          |
| mailing_address_same_as_service    | boolean   | Yes         | Mailing address preference                        |
| shipping_address_same_as_service   | boolean   | Yes         | Shipping address preference                       |
| mailing_address                    | object    | Conditional | Separate mailing address if required              |
| shipping_address                   | object    | Conditional | Separate shipping address if required             |

## 7. Installation Selection

| Field                                  | Data type | Required    | Description                                   |
| -------------------------------------- | --------- | ----------- | --------------------------------------------- |
| installation_type                      | string    | Yes         | `standard_shipping` or `professional`         |
| adult_presence_acknowledged            | boolean   | Conditional | Required for professional installation        |
| installation_date                      | date      | Conditional | Required for professional installation        |
| preferred_installation_time            | string    | Conditional | Morning, afternoon or evening                 |
| installation_availability_acknowledged | boolean   | Conditional | Required installation availability disclosure |

## 8. Sensitive Information Handling

The simulator displays SSN and date of birth in the credit-check section. Payment information is also part of the broader checkout process.

These values require a separate security and authorisation design.

**Do not:**

- Store raw SSNs in SQLite order records.
- Print SSNs or dates of birth in application logs.
- Commit credentials or sensitive customer information to GitHub.
- Store CVV or full payment-card details.
- Send sensitive customer data to external AI services.

Use only synthetic test information during development.

## 9. API Response

Suggested successful response:

```json
{
  "order_id": "generated-order-id",
  "status": "completed",
  "provider": "Provider XX",
  "selected_plan": "300 Mbps",
  "monthly_total": 45.0,
  "installation_total": 100.0,
  "checkout_status": "CHECKOUT_COMPLETED",
  "verification_status": "passed",
  "message": "Order summary verified successfully"
}
```

This is a proposed API response structure, not a response captured from the simulator.

## 10. Implementation Notes

- Validate all required fields before launching Playwright.
- Validate conditional fields based on customer type and installation type.
- Check provider and plan availability in the simulator.
- Use the simulator's actual displayed price and order summary for verification.
- Prevent duplicate order execution when a request is retried.
- Return structured errors when the workflow fails.
- Do not report completion until the final Order Summary is verified.

## 11. Items Requiring Further Inspection

- Exact property type and ownership field values.
- Exact pricing-term options and plan identifiers.
- Separate mailing and shipping address fields.
- Complete Authorization step fields.
- Exact payment-card workflow and permitted handling.
- Whether order submission creates a unique final order reference.
