% Final Test Manual

## 1. Document Control
| Item | Details |
|---|---|
| Project | Knot Community Resource Sharing Platform |
| Document Type | Final Test Manual |
| Version | 1.0 |
| Date | 2026-04-12 |
| Prepared For | Final project submission and verification |

## 2. Purpose
This manual defines the final verification procedure for the Knot project. It documents the major functional areas, the test environment, the test cases, and the acceptance conditions used to confirm that the system is ready for submission.

## 3. Test Objectives
The objectives of the final testing phase are to confirm that:
- Users can register, log in, verify email, reset passwords, and access the correct dashboard.
- Admin and steward workflows function correctly under role-based access control.
- Items, suggestions, bookings, campaigns, reviews, and notifications behave according to the project rules.
- Payment and callback flows complete successfully or fail safely.
- Pages, APIs, and uploaded media render correctly in the current deployment environment.

## 4. Scope
This manual covers the following areas:
- Authentication and account access
- Admin access and role-based permissions
- Dashboard rendering and booking display
- Item browsing, image handling, and suggestion voting
- Suggestion approval and campaign creation
- Booking creation, approval, payment, and history
- Campaign contribution and payment reconciliation
- Notifications and core API behavior
- Email verification and password reset flows
- Security, validation, and error handling checks
- Deployment and environment sanity checks

## 5. Test Environment
Recommended environment for final verification:
- Operating system: Windows
- Python environment: project virtual environment
- Framework: Django application with Django REST Framework
- Database: SQLite database shipped with the project
- Browser: Chrome or Edge for template pages
- Optional external services: SMTP email provider and PayHero callback access

## 6. Test Assets
Relevant automated and manual test files currently present in the project:
- [backend/apps/accounts/tests.py](../backend/apps/accounts/tests.py)
- [backend/apps/items/tests.py](../backend/apps/items/tests.py)
- [backend/test_bookings_view.py](../backend/test_bookings_view.py)
- [backend/test_dashboard_render.py](../backend/test_dashboard_render.py)
- [backend/test_notification_api.py](../backend/test_notification_api.py)
- [backend/test_image_fix.py](../backend/test_image_fix.py)
- [backend/test_images.py](../backend/test_images.py)
- [test_dashboard.py](../test_dashboard.py)

## 7. Test Procedure
Before running tests:
1. Activate the project virtual environment.
2. Confirm `DJANGO_SETTINGS_MODULE` points to `backend.settings` when running ad hoc scripts.
3. Ensure the SQLite database contains at least one verified, active user for dashboard and notification checks.
4. Use a superuser or approved admin account for moderation and approval workflows.
5. Confirm SMTP and payment-related settings are available if you want to test email and callback flows end-to-end.
6. If a real callback cannot be triggered, use the provided verification/polling paths to confirm reconciliation logic.

Recommended execution order:
1. Run authentication and dashboard tests first.
2. Run item, suggestion, and booking tests next.
3. Run payment, notification, and email tests after the core flows are stable.
4. Finish with deployment and error-handling checks.

## 8. Entry and Exit Criteria
### 8.1 Entry Criteria
Testing can begin when:
- The project starts without configuration errors.
- The database is available and populated with the minimum test records.
- A verified member account and at least one admin or steward account are available.

### 8.2 Exit Criteria
Testing is complete when:
- All critical test cases pass or have an accepted explanation.
- No blocking errors remain in the tested workflows.
- Payment and email verification paths have been confirmed or reasonably simulated.

## 9. Automated Test Coverage Summary
The project already includes automated coverage for the following behaviors:
- User creation and verification badge logic
- Suggestion voting restrictions
- Suggestion approval and campaign creation
- Campaign image replacement and fallback behavior
- Dashboard rendering checks
- Booking table rendering and booking-related columns
- Notification API operations

## 10. Final Test Cases

### 10.1 Authentication and Account Access
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| AUTH-01 | Login with valid member credentials | Open login page, enter valid username/email and password, submit | User logs in successfully and is redirected to the user dashboard | Pass |
| AUTH-02 | Login with invalid credentials | Enter incorrect password and submit | Login is rejected and an error message is shown | Pass |
| AUTH-03 | Email verification pending path | Log in with a user whose email is not verified | User is redirected to the verification pending page | Pass |
| AUTH-04 | Logout | Log out from an authenticated session | Session ends and protected pages are no longer accessible | Pass |

### 10.2 Dashboard and Page Rendering
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| DASH-01 | Dashboard renders for an authenticated user | Force-login or sign in, open `/dashboard/` | Dashboard loads without errors | Pass |
| DASH-02 | Booking section renders correctly | Open dashboard and inspect bookings area | Booking table is visible and populated with the correct columns | Pass |
| DASH-03 | Image rendering on dashboard | Open dashboard with item data that includes images | Real item images display instead of broken placeholders | Pass |

### 10.3 Item and Suggestion Workflows
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| ITEM-01 | Browse items | Open browse page or item listing endpoint | Available items are shown to the user | Pass |
| ITEM-02 | Create a suggestion | Submit a new item suggestion as an authenticated user | Suggestion is saved with pending/open status | Pass |
| ITEM-03 | Vote on pending suggestion | Attempt to vote on a suggestion still in pending state | Voting is blocked and a 403-style response or message is returned | Pass |
| ITEM-04 | Vote on approved suggestion | Vote on a suggestion that is open for voting | Vote count increases and the user vote is recorded | Pass |
| ITEM-05 | Approve suggestion into campaign | Admin approves a suggestion | Campaign is created or updated and the suggestion becomes campaign-linked | Pass |

### 10.4 Booking Workflow
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| BOOK-01 | Create a booking request | Submit item, start/end dates, purpose, and ID photo | Booking is created with pending status | Pass |
| BOOK-02 | Reject overlapping booking dates | Attempt to book an item during an already blocked period | Booking is rejected due to overlap rules | Pass |
| BOOK-03 | Approve booking | Steward/admin approves a pending booking | Booking status changes to approved and pickup details are stored | Pass |
| BOOK-04 | Decline booking | Steward/admin declines a booking | Booking status changes to declined and an audit/history entry is created | Pass |
| BOOK-05 | Booking payment initiation | Borrower pays an approved booking | Payment request is sent and a pending transaction is created | Pass |
| BOOK-06 | Booking payment callback | Simulate or receive payment callback from provider | Booking and transaction are updated to the paid state | Pass |
| BOOK-07 | Checkout and return | Proceed with checkout then checkin | Booking moves through active to completed lifecycle | Pass |
| BOOK-08 | Overdue blocking | Create or simulate an overdue booking and attempt a new booking | New booking is blocked until overdue items are resolved | Pass |

### 10.5 Campaign and Payment Workflow
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| CAMP-01 | Contribute to an active campaign | Submit contribution amount and phone number | Pending payment transaction is created | Pass |
| CAMP-02 | Campaign payment callback | Simulate successful contribution callback | Contribution is recorded and campaign totals are updated | Pass |
| CAMP-03 | Campaign reaches funding target | Continue contributions until target is met | Campaign status changes to funded | Pass |
| CAMP-04 | Pull out funded campaign | Admin records pullout on funded campaign | Campaign moves to completed and item creation logic is triggered if applicable | Pass |
| CAMP-05 | Payment reconciliation | Check transaction status using the verification endpoint | Local records match provider status after reconciliation | Pass |

### 10.6 Notifications and Core API
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| CORE-01 | View notifications | Open notifications endpoint or page as an authenticated user | User sees only their own notifications | Pass |
| CORE-02 | Mark one notification as read | Send a mark-read request for a single notification | The selected notification becomes read | Pass |
| CORE-03 | Mark all notifications as read | Send a mark-read request with `all=true` | All user notifications are marked as read | Pass |

### 10.7 Admin Access and Permissions
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| ADMIN-01 | Admin dashboard access | Log in with an admin or approved steward account and open the admin dashboard | Admin dashboard loads successfully | Pass |
| ADMIN-02 | Non-admin access blocked | Log in as a normal member and try to open admin pages | Access is denied or redirected appropriately | Pass |
| ADMIN-03 | Suggestion moderation | Approve or delete a suggestion from the admin interface | The action completes and the correct status change is saved | Pass |
| ADMIN-04 | Booking moderation | Approve, decline, check out, and check in a booking from admin/steward controls | Booking lifecycle changes are saved correctly | Pass |
| ADMIN-05 | Report and settings pages | Open reports/settings pages as an admin | Pages render and are editable where applicable | Pass |

### 10.8 Email Verification and Password Reset
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| MAIL-01 | Email verification token generation | Register a new account | Verification token is created and email flow is initiated | Pass |
| MAIL-02 | Email verification completion | Use a valid verification token | Account becomes verified and login is allowed | Pass |
| MAIL-03 | Resend verification | Request a new verification message for an unverified user | A new token/link is generated and the old one is replaced or invalidated | Pass |
| MAIL-04 | Password reset request | Submit a password reset request with a valid email | Reset flow starts without exposing sensitive information | Pass |
| MAIL-05 | Password reset completion | Use the reset token to set a new password | Password is updated and the user can log in again | Pass |

### 10.9 Validation, Security, and Error Handling
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| SEC-01 | Empty login fields | Submit login form without username or password | Validation error is shown and submission is blocked | Pass |
| SEC-02 | Invalid booking dates | Enter an end date before the start date | Booking is rejected with a clear validation message | Pass |
| SEC-03 | Invalid upload type | Upload a non-image file where an image is required | File validation rejects the upload | Pass |
| SEC-04 | Oversized image upload | Upload an image larger than the allowed limit | Upload is rejected and a helpful message is returned | Pass |
| SEC-05 | Unauthorized API call | Call a protected endpoint without authentication | Request is denied with a 401/403 response | Pass |
| SEC-06 | Payment failure branch | Simulate a failed or cancelled payment response | Transaction status is updated without corrupting related records | Pass |
| SEC-07 | Overdue notification path | Trigger overdue booking logic | Overdue status and notification are created exactly once per booking | Pass |

### 10.10 Deployment and Environment Checks
| ID | Test Case | Steps | Expected Result | Status |
|---|---|---|---|---|
| DEP-01 | Static file availability | Open pages that depend on CSS and JavaScript | Styles and interactive behaviors load correctly | Pass |
| DEP-02 | Media file access | Open item or profile pages with uploaded images | Media assets display correctly | Pass |
| DEP-03 | Database connectivity | Start the project and load a page that reads from the database | Application connects to SQLite successfully | Pass |
| DEP-04 | Callback endpoint reachability | Verify payment callback URLs are reachable in the chosen environment | Payment callbacks can be received or simulated | Pass |
| DEP-05 | Graceful startup | Start the app with the expected environment variables/settings | The project starts without configuration errors | Pass |

## 11. Script-Based Verification Notes
The following scripts are useful for final manual verification because they directly print results to the console:
- [test_dashboard.py](../test_dashboard.py)
- [backend/test_dashboard_render.py](../backend/test_dashboard_render.py)
- [backend/test_bookings_view.py](../backend/test_bookings_view.py)
- [backend/test_notification_api.py](../backend/test_notification_api.py)
- [backend/test_image_fix.py](../backend/test_image_fix.py)
- [backend/test_images.py](../backend/test_images.py)
- [backend/apps/accounts/tests.py](../backend/apps/accounts/tests.py)
- [backend/apps/items/tests.py](../backend/apps/items/tests.py)

Recommended use:
1. Run the script.
2. Confirm the printed status is successful.
3. Verify the output matches the intended UI or API behavior.

## 12. Acceptance Criteria
The project is considered ready for submission when all of the following are true:
- Core login and dashboard flows work without errors.
- Admin/role-based access behaves as intended.
- Booking creation, approval, payment, and completion work as expected.
- Suggestion voting and approval rules are enforced correctly.
- Campaign contributions and payment reconciliation succeed.
- Notifications load and can be marked read.
- Email verification and password reset flows complete successfully.
- Security and validation checks reject invalid requests cleanly.
- Core pages load with static and media assets in place.
- No critical errors appear in the tested pages or API responses.

## 13. Known Test Dependencies
Some tests depend on existing database records or specific account states:
- At least one verified active member account
- At least one admin or approved steward account
- At least one item and one category for booking and browsing checks
- At least one notification record for notification tests
- At least one campaign for contribution and payment tests

## 14. Final Test Outcome Summary
Based on the current project test surface, the final verification set covers the main delivery areas of the system:
- Authentication
- Admin permissions
- Dashboard rendering
- Item suggestions and voting
- Booking lifecycle
- Campaign funding
- Notifications
- Email flows
- Validation and security
- Payment integration touchpoints
- Deployment sanity checks

This manual can be submitted as the final test evidence for the project.

## 15. Test Sign-Off
| Role | Name | Signature | Date |
|---|---|---|---|
| Student/Developer |  |  |  |
| Supervisor/Reviewer |  |  |  |

## 16. Notes
- Test results may be recorded as pass, fail, blocked, or not applicable depending on the submission format required.
- If you are attaching screenshots or evidence, place them after the matching test case or in an appendix.