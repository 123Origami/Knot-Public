# SOFTWARE REQUIREMENTS SPECIFICATION (SRS)
## For
## KNOT: TYING COMMUNITIES TOGETHER THROUGH SHARED RESOURCES

| Item | Details |
|---|---|
| Version | 2.0 (Detailed, Implementation-Aligned) |
| Prepared by | Sally Mukami Munga (updated to current build baseline) |
| Date | 2026-04-27 |
| Department | Computer Science |
| Institution | Egerton University |

---

## Contents
1. INTRODUCTION
1.1 Purpose
1.2 Document Conventions
1.3 Intended Audience and Reading Suggestions
1.4 Product Scope
1.5 References
2. OVERALL DESCRIPTION
2.1 Product Perspective
2.2 Product Functions
2.3 User Classes and Characteristics
2.4 Operating Environment
2.5 Design and Implementation Constraints
2.6 User Documentation
2.7 Assumptions and Dependencies
3. SYSTEM FEATURES
3.1 User Registration, Authentication, and Verification
3.2 Role and Access Control
3.3 Item Listing and Discovery
3.4 Booking and Reservation Management
3.5 Booking Payment Integration
3.6 Item Suggestion and Voting
3.7 Campaign and Contribution Management
3.8 Review and Reputation System
3.9 Dashboard and Notifications
3.10 Administrative Functions
3.11 Messaging and Booking Chat
4. EXTERNAL INTERFACE REQUIREMENTS
4.1 User Interfaces
4.2 Hardware Interfaces
4.3 Software Interfaces
4.4 Communication Interfaces
5. NON-FUNCTIONAL REQUIREMENTS
5.1 Performance Requirements
5.2 Safety and Reliability Requirements
5.3 Security Requirements
5.4 Software Quality Attributes
5.5 Business Rules (Current Enforcement)
6. OTHER REQUIREMENTS
6.1 Legal and Policy Requirements
6.2 Ethical Requirements
6.3 Accessibility Requirements
7. CURRENT LIMITATIONS AND GAP NOTES
APPENDIX A: GLOSSARY
APPENDIX B: PRIORITY DEFINITIONS
APPENDIX C: STATUS ENUMERATIONS

---

## 1. INTRODUCTION

### 1.1 Purpose
This document provides a detailed Software Requirements Specification for the currently implemented KNOT platform. It mirrors the depth and structure of the original SRS template while reflecting the actual behavior of the present codebase.

This SRS is intended to:
- Guide maintenance and future enhancements.
- Provide a traceable requirements baseline for testing.
- Clearly distinguish implemented behavior from planned behavior.

### 1.2 Document Conventions
| Convention | Meaning |
|---|---|
| MUST | Implemented mandatory requirement in current baseline |
| SHOULD | Recommended behavior, partially implemented or environment-dependent |
| MAY | Optional/future behavior not guaranteed in current baseline |
| [REQ-ID] | Unique requirement identifier |

Requirement identifiers use:
- Functional: [KNOT-FXX-XXX]
- Non-functional: [KNOT-NFXX-XXX]
- Interface: [KNOT-UI-XXX]
- Legal/Ethical/Accessibility: [KNOT-LXX-XXX], [KNOT-EXX-XXX], [KNOT-AXX-XXX]

### 1.3 Intended Audience and Reading Suggestions
| Audience | Purpose | Sections |
|---|---|---|
| Project Supervisor | Evaluate technical completeness and implementation fidelity | All |
| Developer/Maintainer | Understand implemented requirements and gaps | 2, 3, 4, 5, 7 |
| Tester/QA | Build test cases from current system behavior | 3, 4, 5, Appendix C |
| Examiners | Assess scope and implemented outcomes | 1, 2, 6, 7 |

### 1.4 Product Scope
KNOT is a web-based community resource sharing platform that supports:
- Shared inventory discovery and borrowing.
- Community suggestion and voting for future resources.
- Campaign contributions for item acquisition.
- Steward/admin moderation workflows.

The current implementation is centered on Django server-rendered pages plus JSON APIs, with SQLite as the default local database and PayHero integration for monetary transactions.

### 1.5 References
1. Current KNOT repository codebase (Django apps: accounts, bookings, campaigns, core, items, messaging, payments, reviews).
2. Existing user documentation in docs/.
3. IEEE SRS structuring style (adapted for project context).

---

## 2. OVERALL DESCRIPTION

### 2.1 Product Perspective
KNOT is implemented as a modular Django monolith with app-level separation of concerns. It includes:
- Template views for end-user/admin pages.
- DRF endpoints for core workflows.
- Shared domain models and business validation.

### 2.2 Product Functions
Major implemented functions:
1. Account registration, login, email verification, password reset.
2. Admin access request workflow with ID-photo submission and moderation.
3. Item browsing, filtering, details, category listing, and availability checks.
4. Booking creation, moderation, payment, checkout, return, overdue tracking.
5. Suggestion submission, admin approval/deletion, and vote toggling.
6. Campaign listing, contribution payments, callback reconciliation, pullout recording.
7. Reviews and reputation updates.
8. Dashboard analytics and in-app notifications.
9. Admin reporting and configuration pages.
10. Messaging models and booking-linked chat actions.

### 2.3 User Classes and Characteristics
| User Class | Description | Privileges | Technical Level |
|---|---|---|---|
| Visitor | Unauthenticated user | Public page access and limited public data views | Low-Medium |
| Member | Registered user with verified email | Browse, book, suggest, vote, contribute, review, dashboard access | Medium |
| Admin/Steward | Approved admin request, staff, or superuser | Manage users/items/bookings/suggestions/reports/settings | Medium-High |

### 2.4 Operating Environment
| Component | Technology | Current Baseline |
|---|---|---|
| Backend Framework | Django + DRF | Active |
| Language | Python | 3.x (venv-managed) |
| Frontend | HTML/CSS/JS templates | Active |
| Database | SQLite | Default active |
| Payment | PayHero | Integrated |
| Email | SMTP via Django EmailBackend | Integrated |
| Runtime | Localhost + optional ngrok callback setup | Active |

### 2.5 Design and Implementation Constraints
1. Current baseline uses a Django monolith architecture.
2. SQLite is default in local environment.
3. Payment callback success depends on externally reachable callback URL.
4. Role checks are implemented through decorators, request checks, and Django auth flags.

### 2.6 User Documentation
Current docs include:
1. User Manual.
2. SDD and testing docs.
3. This implementation-aligned SRS.

### 2.7 Assumptions and Dependencies
1. SMTP credentials are valid for verification/reset emails.
2. PayHero credentials and callback URL are valid.
3. Users provide valid phone number format for payment initiation.
4. Media upload storage remains writable.

---

## 3. SYSTEM FEATURES

## 3.1 User Registration, Authentication, and Verification

### Description
Users register with credentials, receive email verification, and access restricted pages only after verification.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F01-001] | System MUST allow registration with username, email, and password. | High |
| [KNOT-F01-002] | System MUST require password confirmation during signup. | High |
| [KNOT-F01-003] | System MUST enforce minimum 8-character password length at signup form/API level. | High |
| [KNOT-F01-004] | System MUST generate/store email verification token and send verification email. | High |
| [KNOT-F01-005] | System MUST prevent unverified users from accessing email-verified protected pages. | High |
| [KNOT-F01-006] | System MUST support login using username or email identifier. | High |
| [KNOT-F01-007] | System MUST provide password reset request and token-based reset flow. | High |
| [KNOT-F01-008] | System MUST allow profile update (names, bio, location, profile picture). | High |
| [KNOT-F01-009] | System MUST support account deletion workflow. | Medium |
| [KNOT-F01-010] | System MUST maintain verification-level fields (email/phone/id) in user model. | Medium |
| [KNOT-F01-011] | System MUST allow admin access request submission with reason and ID photo. | High |
| [KNOT-F01-012] | System MUST allow admins to approve/reject admin access requests. | High |
| [KNOT-F01-013] | System SHOULD preserve session continuity after password changes where applicable. | Medium |

### Verification Model in Current System
| Level | Stored Concept | Current Practical Use |
|---|---|---|
| 0 | Unverified | Restricted from verified pages |
| 1 | Email Verified | Core member access |
| 2 | Phone Verified | Field exists; not active end-user verification flow |
| 3 | ID Verified | Field exists; not active end-user self-service flow |

---

## 3.2 Role and Access Control

### Description
Role gating is implemented for member and admin areas.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F02-001] | System MUST require authentication for dashboard and protected member actions. | High |
| [KNOT-F02-002] | System MUST enforce email verification checks on protected member routes. | High |
| [KNOT-F02-003] | System MUST restrict admin routes to approved admin/staff/superuser users. | High |
| [KNOT-F02-004] | System MUST redirect unauthorized users from restricted pages with feedback messages. | High |
| [KNOT-F02-005] | System SHOULD centralize admin checks via reusable decorators/helpers. | Medium |

---

## 3.3 Item Listing and Discovery

### Description
Members discover inventory through listing, filtering, and item detail pages.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F03-001] | System MUST provide item listing endpoint with search support. | High |
| [KNOT-F03-002] | System MUST support category filtering in item listings. | High |
| [KNOT-F03-003] | System MUST support defined sorting options for items. | Medium |
| [KNOT-F03-004] | System MUST expose category list endpoint. | High |
| [KNOT-F03-005] | System MUST expose item detail by slug. | High |
| [KNOT-F03-006] | System MUST expose availability checks for optional date ranges. | High |
| [KNOT-F03-007] | Items MUST support statuses: available, borrowed, maintenance, retired. | High |
| [KNOT-F03-008] | Items MUST support multiple images and primary image behavior. | Medium |
| [KNOT-F03-009] | System SHOULD recover stale borrowed states where no blocking booking exists. | Medium |

---

## 3.4 Booking and Reservation Management

### Description
Booking flow includes member requests, steward moderation, and lifecycle transitions.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F04-001] | System MUST allow authenticated booking creation via API flow. | High |
| [KNOT-F04-002] | Booking request MUST include item, start date, end date, and borrower ID photo. | High |
| [KNOT-F04-003] | System MUST reject requests with missing required fields. | High |
| [KNOT-F04-004] | System MUST reject past dates and invalid date order. | High |
| [KNOT-F04-005] | System MUST enforce item max borrow days. | High |
| [KNOT-F04-006] | System MUST block overlapping bookings for blocking statuses. | High |
| [KNOT-F04-007] | System MUST block new booking creation when borrower has unreturned overdue bookings. | High |
| [KNOT-F04-008] | System MUST support steward approval with pickup details. | High |
| [KNOT-F04-009] | System MUST support steward decline with notes. | High |
| [KNOT-F04-010] | System MUST support cancellation under valid status/role conditions. | High |
| [KNOT-F04-011] | System MUST support checkout transition from paid to active. | High |
| [KNOT-F04-012] | System MUST support return/check-in transition from active to completed. | High |
| [KNOT-F04-013] | System MUST support overdue marking/synchronization and related notifications. | High |
| [KNOT-F04-014] | System MUST write booking history entries for key actions. | High |

### Booking Statuses (Implemented)
- pending
- approved
- paid
- declined
- active
- completed
- cancelled
- overdue

---

## 3.5 Booking Payment Integration

### Description
Approved bookings are paid via PayHero and reconciled through callback/manual verification.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F05-001] | System MUST allow borrower-initiated payment for approved bookings. | High |
| [KNOT-F05-002] | System MUST create pending transaction before payment gateway call. | High |
| [KNOT-F05-003] | System MUST send PayHero payment initiation request with reference and callback URL. | High |
| [KNOT-F05-004] | System MUST process callback payload and update transaction/booking states. | High |
| [KNOT-F05-005] | System MUST provide manual verify endpoint for pending payment states. | High |
| [KNOT-F05-006] | System MUST set booking payment status and date on successful confirmation. | High |
| [KNOT-F05-007] | System MUST preserve references/metadata required for reconciliation. | High |
| [KNOT-F05-008] | System SHOULD notify borrower after confirmed payment state changes. | Medium |

---

## 3.6 Item Suggestion and Voting

### Description
Members submit item suggestions. Admins moderate and can publish suggestions into active campaigns.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F06-001] | System MUST allow authenticated users to submit suggestions. | High |
| [KNOT-F06-002] | Suggestion MUST include name, estimated cost, and justification/description. | High |
| [KNOT-F06-003] | Suggestion MAY include optional image. | Medium |
| [KNOT-F06-004] | System MUST list suggestions with status filtering support. | High |
| [KNOT-F06-005] | System MUST allow vote toggle for authenticated users when suggestion is vote-eligible. | High |
| [KNOT-F06-006] | System MUST enforce one active vote per user per suggestion. | High |
| [KNOT-F06-007] | System MUST block voting while suggestion status is pending. | High |
| [KNOT-F06-008] | Admin MUST be able to approve suggestion and create/update corresponding campaign. | High |
| [KNOT-F06-009] | Admin MUST be able to delete invalid suggestions. | High |
| [KNOT-F06-010] | System SHOULD notify suggestion stakeholders when campaign is published. | Medium |

### Suggestion Statuses (Implemented)
- pending
- approved
- rejected
- campaign_created

---

## 3.7 Campaign and Contribution Management

### Description
Campaigns represent fundraising goals. Contributions are processed through PayHero.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F07-001] | System MUST provide campaign listing with status, search, and sorting options. | High |
| [KNOT-F07-002] | System MUST provide campaign statistics endpoint. | High |
| [KNOT-F07-003] | System MUST provide campaign contributors endpoint. | High |
| [KNOT-F07-004] | System MUST allow authenticated contribution initiation. | High |
| [KNOT-F07-005] | Contribution initiation MUST validate positive amount and phone format. | High |
| [KNOT-F07-006] | System MUST create pending transaction before payment request. | High |
| [KNOT-F07-007] | System MUST process callback outcomes: completed, failed, cancelled, timeout/pending. | High |
| [KNOT-F07-008] | System MUST create contribution record for successful transaction. | High |
| [KNOT-F07-009] | System MUST increment campaign funds and contributor count on successful payment. | High |
| [KNOT-F07-010] | System MUST provide verify/check-status endpoints for reconciliation. | High |
| [KNOT-F07-011] | System MUST provide user contributions feed including completed and pending/failed transaction rows. | High |
| [KNOT-F07-012] | Admin MUST be able to record campaign pullout for funded/completed campaigns. | High |
| [KNOT-F07-013] | System MUST auto-create item from funded suggestion when pullout is recorded and no item exists. | High |
| [KNOT-F07-014] | System SHOULD transition active campaign to funded when target is reached. | High |

### Campaign Statuses (Implemented)
- draft
- active
- funded
- completed
- expired
- cancelled

---

## 3.8 Review and Reputation System

### Description
Borrowers and stewards review each other after completed bookings.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F08-001] | System MUST allow reviews only for completed bookings. | High |
| [KNOT-F08-002] | System MUST enforce role-appropriate review types (borrower_to_steward / steward_to_borrower). | High |
| [KNOT-F08-003] | System MUST enforce rating scale 1 to 5. | High |
| [KNOT-F08-004] | System MUST prevent duplicate review per booking/reviewer/review_type. | High |
| [KNOT-F08-005] | System MUST allow reviewee response to review. | Medium |
| [KNOT-F08-006] | System MUST update reviewee aggregate rating metrics after review save. | High |
| [KNOT-F08-007] | System MUST provide user review statistics endpoint. | Medium |

---

## 3.9 Dashboard and Notifications

### Description
Dashboard aggregates user-specific operations and exposes notification state.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F09-001] | System MUST provide authenticated user dashboard. | High |
| [KNOT-F09-002] | Dashboard MUST show active/past booking summaries. | High |
| [KNOT-F09-003] | Dashboard MUST show user suggestions and contributions. | High |
| [KNOT-F09-004] | Dashboard MUST show pending review prompts and overdue blockers. | High |
| [KNOT-F09-005] | Dashboard MUST include recent activity feed. | Medium |
| [KNOT-F09-006] | System MUST provide in-app notifications model and listing API. | High |
| [KNOT-F09-007] | System MUST support mark-read actions and unread count endpoint. | High |
| [KNOT-F09-008] | System SHOULD include booking-chat unread count signals in dashboard context. | Medium |

---

## 3.10 Administrative Functions

### Description
Admin and steward users manage core operations from custom admin pages.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F10-001] | System MUST provide admin dashboard for authorized admin/staff/approved users. | High |
| [KNOT-F10-002] | Admin MUST be able to manage users (view/activate/deactivate/delete/export). | High |
| [KNOT-F10-003] | Admin MUST be able to manage items (create/edit/status/delete). | High |
| [KNOT-F10-004] | Admin MUST be able to manage booking decisions and lifecycle actions. | High |
| [KNOT-F10-005] | Admin MUST be able to moderate suggestions and campaign publication. | High |
| [KNOT-F10-006] | Admin MUST provide reports page with analytics and CSV exports. | High |
| [KNOT-F10-007] | Admin MUST provide settings page for site configuration fields. | Medium |
| [KNOT-F10-008] | System SHOULD log booking lifecycle actions with actor and timestamp. | High |

---

## 3.11 Messaging and Booking Chat

### Description
Messaging domain supports conversations/messages, plus booking chat endpoints used in admin flow.

### Functional Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-F11-001] | System MUST support conversation and message entities between participants. | Medium |
| [KNOT-F11-002] | System MUST scope conversation/message visibility to participating users. | High |
| [KNOT-F11-003] | System MUST support send and mark-read actions for messages. | Medium |
| [KNOT-F11-004] | System MUST support booking chat message retrieval and send actions in admin workflows. | Medium |
| [KNOT-F11-005] | Messaging API router SHOULD be exposed in root URL config for full API discoverability. | Low |

---

## 4. EXTERNAL INTERFACE REQUIREMENTS

## 4.1 User Interfaces
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-UI-001] | System MUST provide template-rendered interfaces for member and admin workflows. | High |
| [KNOT-UI-002] | System MUST provide consistent navigation between major pages (browse, goals, suggest, dashboard, admin pages). | High |
| [KNOT-UI-003] | System MUST provide user feedback messages on major actions and errors. | High |
| [KNOT-UI-004] | System SHOULD support responsive layout for common desktop and mobile viewports. | Medium |

### Key Implemented Screens
- Home page
- Login/Signup/Verification pages
- Browse and item detail pages
- Booking page
- Member dashboard
- Suggest and goals pages
- Admin dashboard and admin management pages (users/items/bookings/suggestions/reports/settings)
- Campaign detail page
- Profile pages

## 4.2 Hardware Interfaces
No custom hardware interfaces are required. Standard browser input devices are sufficient.

## 4.3 Software Interfaces
| Interface | Purpose | Current Implementation | Priority |
|---|---|---|---|
| SQLite Database | Data persistence | Active default DB | High |
| Django Email SMTP | Verification and reset emails | Active | High |
| PayHero API | Booking and campaign payments | Active | High |
| Django Media Storage | Uploaded images and ID photos | Active | High |
| DRF JSON Endpoints | Programmatic access to workflows | Active | High |

## 4.4 Communication Interfaces
- HTTP/HTTPS request-response flows for pages and APIs.
- JSON payload exchange for API endpoints.
- Session authentication in template workflows.
- Callback endpoint ingestion for payment confirmations.

---

## 5. NON-FUNCTIONAL REQUIREMENTS

## 5.1 Performance Requirements
| ID | Requirement | Target | Priority |
|---|---|---|---|
| [KNOT-NF01-001] | Common page/API requests SHOULD return in user-acceptable time for local/small deployment. | Sub-second to few seconds depending on route | Medium |
| [KNOT-NF01-002] | Booking overlap and status queries MUST be index-assisted where defined. | Query optimization by model indexes | High |
| [KNOT-NF01-003] | Dashboard and reports SHOULD use aggregated queries for summaries. | Efficient aggregate computation | Medium |

## 5.2 Safety and Reliability Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-NF02-001] | System MUST validate booking date and overlap constraints to protect data integrity. | High |
| [KNOT-NF02-002] | System MUST preserve transaction and booking state consistency during payment reconciliation. | High |
| [KNOT-NF02-003] | System SHOULD support idempotent callback behavior for repeated provider notifications. | Medium |
| [KNOT-NF02-004] | System MUST provide robust handling for missing/invalid callback references. | High |

## 5.3 Security Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-NF03-001] | System MUST hash passwords via Django authentication stack. | High |
| [KNOT-NF03-002] | System MUST enforce CSRF middleware protections on web form workflows. | High |
| [KNOT-NF03-003] | System MUST enforce role-based restrictions for admin functionality. | High |
| [KNOT-NF03-004] | System MUST avoid local storage of card/CVV details in payment models. | High |
| [KNOT-NF03-005] | Production deployment SHOULD use secure cookie and HTTPS settings. | High |
| [KNOT-NF03-006] | Credentials/secrets SHOULD be moved to environment variables for production. | High |

## 5.4 Software Quality Attributes

### Reliability
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-NF04-001] | System MUST maintain booking and payment state integrity under normal operation. | High |
| [KNOT-NF04-002] | System SHOULD tolerate transient provider status delays through manual verification endpoints. | Medium |

### Maintainability
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-NF04-003] | Code SHOULD remain organized by Django app domains. | High |
| [KNOT-NF04-004] | Validation logic SHOULD remain centralized in serializers/services where feasible. | Medium |
| [KNOT-NF04-005] | Requirement-to-feature traceability SHOULD be preserved via stable requirement IDs. | Medium |

### Usability
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-NF04-006] | System MUST provide clear user messages for booking and payment actions. | High |
| [KNOT-NF04-007] | System SHOULD expose actionable troubleshooting feedback for failed operations. | Medium |

### Portability
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-NF04-008] | System SHOULD run in standard Python/Django environments across major OS platforms. | Medium |
| [KNOT-NF04-009] | User-facing pages SHOULD operate on modern browsers. | High |

## 5.5 Business Rules (Current Enforcement)
| ID | Rule | Enforcement Status | Priority |
|---|---|---|---|
| [KNOT-NF05-001] | Borrower cannot create new booking while holding unreturned overdue booking. | Enforced | High |
| [KNOT-NF05-002] | Booking cannot exceed item max borrow duration. | Enforced | High |
| [KNOT-NF05-003] | Overlapping bookings on same item and blocking statuses are not allowed. | Enforced | High |
| [KNOT-NF05-004] | Email verification required before access to protected member pages. | Enforced | High |
| [KNOT-NF05-005] | Age >= 18 policy, max 3 concurrent bookings, and 3-strikes policy are global policy statements. | Not fully enforced in current code | Medium |

---

## 6. OTHER REQUIREMENTS

## 6.1 Legal and Policy Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-L01-001] | System MUST provide Terms of Service page route. | High |
| [KNOT-L01-002] | System MUST provide Privacy Policy page route. | High |
| [KNOT-L01-003] | System MUST provide Cookie Policy page route. | Medium |
| [KNOT-L01-004] | System SHOULD support account deletion request path for data lifecycle control. | Medium |

## 6.2 Ethical Requirements
| ID | Requirement | Priority |
|---|---|---|
| [KNOT-E01-001] | Platform workflows SHOULD treat users consistently regardless of background. | High |
| [KNOT-E01-002] | Moderation workflows SHOULD remain transparent via explicit status decisions. | Medium |
| [KNOT-E01-003] | System SHOULD continue emphasizing community benefit over pure commercial optimization. | Medium |

## 6.3 Accessibility Requirements
| ID | Requirement | Priority | Current Status |
|---|---|---|---|
| [KNOT-A01-001] | Forms SHOULD include clear labels and validation feedback. | High | Partially implemented |
| [KNOT-A01-002] | Keyboard accessibility SHOULD be supported across major interactions. | Medium | Not fully validated |
| [KNOT-A01-003] | Color contrast and semantic heading structure SHOULD be reviewed against WCAG guidance. | Medium | Pending formal audit |

---

## 7. CURRENT LIMITATIONS AND GAP NOTES

1. SMS/Twilio verification flow is not implemented despite phone verification fields in model.
2. Social login is not implemented.
3. Payment receipt emails for booking/campaign transactions are not currently implemented.
4. Messaging app API routes exist but are not mounted under root URL configuration.
5. Cross-module centralized admin audit logging is partial; booking actions are the most explicitly logged.
6. Some policy rules from earlier planning SRS are not globally enforced in code (age gate, strict concurrent-booking cap, strikes policy).
7. Current settings are development-oriented; production hardening is still required.

---

## APPENDIX A: GLOSSARY
| Term | Definition |
|---|---|
| Member | Registered platform user with verified email |
| Admin/Steward | User with elevated management privileges |
| Suggestion | Proposed item submitted by community member |
| Campaign | Fundraising goal for acquiring a suggested resource |
| Contribution | Successful monetary contribution linked to transaction |
| Booking | Reservation record for borrowing an item |
| Booking History | Audit-like timeline of booking state actions |
| Verification Token | Code/link used for email verification or password reset |

---

## APPENDIX B: PRIORITY DEFINITIONS
| Priority | Meaning |
|---|---|
| High | Essential for current baseline behavior and core operation |
| Medium | Important and largely supported, may be partial in some routes |
| Low | Useful enhancement or currently non-critical behavior |

---

## APPENDIX C: STATUS ENUMERATIONS

### Booking Status
- pending
- approved
- paid
- declined
- active
- completed
- cancelled
- overdue

### Item Status
- available
- borrowed
- maintenance
- retired

### Suggestion Status
- pending
- approved
- rejected
- campaign_created

### Campaign Status
- draft
- active
- funded
- completed
- expired
- cancelled

### Transaction Status
- pending
- processing
- completed
- failed
- refunded
- cancelled

---

End of Detailed Implementation-Aligned SRS
