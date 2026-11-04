# Provider XX Order Automation

## Test Scenarios

## 1. Purpose

This document lists test scenarios for validating the Provider XX order automation workflow using the authorised Allconnect simulator.

Use synthetic customer information only.

## 2. Login and Session Tests

| Test ID | Scenario                                | Expected result                |
| ------- | --------------------------------------- | ------------------------------ |
| TS001   | Login with valid authorised credentials | Portal opens successfully      |
| TS002   | Login with invalid credentials          | Login failure is handled       |
| TS003   | Start a new session                     | New session begins             |
| TS004   | Session fails to start                  | Automation stops with an error |

## 3. Address Validation Tests

| Test ID | Scenario                                     | Expected result                               |
| ------- | -------------------------------------------- | --------------------------------------------- |
| TS005   | Enter a valid service address                | Address Matched is displayed                  |
| TS006   | Enter an invalid address                     | Address validation failure is handled         |
| TS007   | Enter an address with apartment/unit details | Additional address information is processed   |
| TS008   | Address is not matched                       | Automation does not proceed to plan selection |

## 4. Customer Qualification Tests

| Test ID | Scenario                                   | Expected result                   |
| ------- | ------------------------------------------ | --------------------------------- |
| TS009   | Select New customer                        | New customer workflow is selected |
| TS010   | Select Transfer customer                   | Transfer workflow is selected     |
| TS011   | Select a current provider for a transfer   | Selected provider is recorded     |
| TS012   | Transfer customer without current provider | Validation is handled             |

## 5. Provider and Internet Plan Tests

| Test ID | Scenario                                   | Expected result                             |
| ------- | ------------------------------------------ | ------------------------------------------- |
| TS013   | Provider XX is available                   | Provider XX plans are displayed             |
| TS014   | Provider XX is unavailable                 | Automation stops with an availability error |
| TS015   | Select a 300 Mbps plan                     | Correct plan details are displayed          |
| TS016   | Select a 500 Mbps plan                     | Correct plan details are displayed          |
| TS017   | Select a 1 Gbps plan                       | Correct plan details are displayed          |
| TS018   | Select a plan not available at the address | Automation does not continue with that plan |
| TS019   | Review product details                     | Plan and price are checked                  |
| TS020   | Add selected plan to order and checkout    | Selected plan appears in checkout           |

The speeds above are examples observed during simulator exploration. Confirm current plan availability before executing each test.

## 6. Product Customization Tests

| Test ID | Scenario                                       | Expected result                              |
| ------- | ---------------------------------------------- | -------------------------------------------- |
| TS021   | Select Broadband Fact Labels requested         | Correct option is selected                   |
| TS022   | Select Broadband Fact Labels not requested     | Correct option is selected                   |
| TS023   | Leave mandatory Read acknowledgement unchecked | Automation handles validation                |
| TS024   | Select leased gateway                          | Equipment selection is reflected in checkout |
| TS025   | Select customer-owned equipment                | Equipment selection is reflected in checkout |
| TS026   | Select NOW TV                                  | Optional service is added                    |
| TS027   | Do not select NOW TV                           | Optional service is not added                |
| TS028   | Review video and phone options                 | Selected services match the request          |

## 7. Account Holder Qualification Tests

| Test ID | Scenario                                               | Expected result                                                               |
| ------- | ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| TS029   | Verify the account holder                              | Verification is accepted                                                      |
| TS030   | Account-holder verification is No                      | Automation does not proceed as if verified                                    |
| TS031   | Enter account-holder contact details                   | Details are validated                                                         |
| TS032   | Select existing Provider XX customer                   | Correct response is recorded                                                  |
| TS033   | Select non-existing Provider XX customer               | Correct response is recorded                                                  |
| TS034   | Select EZ-Enroll Yes                                   | Correct option is selected                                                    |
| TS035   | Select EZ-Enroll No                                    | Correct option is selected                                                    |
| TS036   | Select automatic payments and paperless billing        | Correct option and acknowledgement are handled                                |
| TS037   | Select mailing address same as service address         | No separate mailing address should be required unless the portal requests it  |
| TS038   | Select mailing address different from service address  | Conditional address fields are investigated and completed                     |
| TS039   | Select shipping address same as service address        | No separate shipping address should be required unless the portal requests it |
| TS040   | Select shipping address different from service address | Conditional address fields are investigated and completed                     |

## 8. Installation Tests

| Test ID | Scenario                                                  | Expected result                       |
| ------- | --------------------------------------------------------- | ------------------------------------- |
| TS041   | Select STANDARD_SHIPPING                                  | Free standard option is selected      |
| TS042   | Select PRO_INSTALL                                        | Professional installation is selected |
| TS043   | Select PRO_INSTALL without adult-presence acknowledgement | Validation is handled                 |
| TS044   | Select a professional installation date                   | Date is accepted                      |
| TS045   | Select Morning                                            | Preferred time is recorded            |
| TS046   | Select Afternoon                                          | Preferred time is recorded            |
| TS047   | Select Evening                                            | Preferred time is recorded            |
| TS048   | Leave installation availability acknowledgement unchecked | Validation is handled                 |
| TS049   | Confirm professional installation                         | Installation selection is accepted    |

## 9. Order Summary Verification Tests

| Test ID | Scenario                        | Expected result                                      |
| ------- | ------------------------------- | ---------------------------------------------------- |
| TS050   | Complete a valid order workflow | Final Order Summary is displayed                     |
| TS051   | Verify provider name            | Provider XX is displayed                             |
| TS052   | Verify selected internet plan   | Plan matches the API request                         |
| TS053   | Verify account holder           | Account holder matches the request                   |
| TS054   | Verify monthly total            | Monthly total matches the simulator                  |
| TS055   | Verify installation total       | Installation total matches the selected installation |
| TS056   | Verify equipment and add-ons    | Summary matches selected configuration               |
| TS057   | Verify checkout status          | CHECKOUT_COMPLETED is displayed                      |
| TS058   | Detect a plan or price mismatch | Verification fails                                   |
| TS059   | Detect missing Order Summary    | Automation returns an incomplete result              |

## 10. API and Automation Tests

| Test ID | Scenario                                                              | Expected result                                    |
| ------- | --------------------------------------------------------------------- | -------------------------------------------------- |
| TS060   | Submit a valid POST order request                                     | Automation starts                                  |
| TS061   | Submit an invalid email                                               | API validation error is returned                   |
| TS062   | Submit missing required fields                                        | API rejects the request                            |
| TS063   | Submit an invalid installation type                                   | API validation error is returned                   |
| TS064   | Submit a professional installation without required scheduling fields | Conditional validation error is returned           |
| TS065   | Retry an existing order request                                       | Duplicate execution is prevented or safely handled |
| TS066   | Browser navigation timeout                                            | Structured automation error is returned            |
| TS067   | Browser session closes unexpectedly                                   | Failure is reported                                |
| TS068   | Complete the workflow successfully                                    | Final verified order result is returned            |

## 11. Security Tests

| Test ID | Scenario                                               | Expected result                                     |
| ------- | ------------------------------------------------------ | --------------------------------------------------- |
| TS069   | Inspect application logs after a test                  | No SSN, DOB, password or payment credentials appear |
| TS070   | Inspect Git staging area                               | No `.env` or sensitive test data is staged          |
| TS071   | Test with synthetic customer information               | No real customer information is used                |
| TS072   | Attempt to proceed without account-holder verification | Workflow is blocked                                 |
| TS073   | Test unauthorised portal access                        | Automation does not bypass access controls          |

## 12. Test Execution Record

Record the outcome when each test is executed.

| Test ID | Actual result | Status     | Remarks |
| ------- | ------------- | ---------- | ------- |
| TS001   |               | Not tested |         |
| TS005   |               | Not tested |         |
| TS009   |               | Not tested |         |
| TS015   |               | Not tested |         |
| TS020   |               | Not tested |         |
| TS029   |               | Not tested |         |
| TS041   |               | Not tested |         |
| TS050   |               | Not tested |         |
| TS057   |               | Not tested |         |

**Status values:** Not tested, Pass, Fail, Blocked.
