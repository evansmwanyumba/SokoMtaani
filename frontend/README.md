# SokoMtaani frontend

Responsive, API-driven marketplace interface using HTML, CSS, vanilla JavaScript, Bootstrap 5 and Bootstrap Icons. There is no build step, frontend framework, mock-data mode, or bundled sample marketplace content.

## Run locally

From the repository root, start the backend in one terminal:

```bash
cd backend
source .venv/bin/activate
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

In another terminal, serve the frontend:

```bash
python3 -m http.server 5500 --directory frontend
```

Open [http://127.0.0.1:5500](http://127.0.0.1:5500). Configure the API host only in `assets/js/config.js`. The default is `http://127.0.0.1:8000/api/v1`. API errors are displayed; the UI never falls back to fixtures. Empty product and category databases therefore show real empty states until actual records are created.

The app uses hash routing (`/#/search`, `/#/verify-email?...`) for static hosting. Authentication uses Django's HttpOnly session cookie and CSRF protection; no password or authentication token is stored in browser storage. Configure the frontend origin in Django's `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`.
Local asset URLs carry a cache version in `index.html`; increment its `v` value when publishing changed frontend assets so browsers don't reuse an older API configuration or JavaScript bundle. A `304 Not Modified` for a static asset is a normal browser-cache response, not an account-creation result.

New registrations are approved automatically and establish a session immediately; email verification and OTP are not required. Account mode (buy, sell, or both) is selected at registration, while seller activation still requires phone verification. The superuser dashboard supports account creation, deactivation/deletion, team-owned live listings, categories, announcements, support conversations, report review, and editing public contact/about/team information. A direct account report suspends that account and pauses its active listings while notifying superusers; administrators investigate and can reactivate the account. These development authentication settings are not suitable for production; restore stronger verification and secure deployment settings before launch.

For a complete local reset, follow the destructive `flush`, superuser creation and demo seed steps in the backend README. Superuser login uses the email address entered by `createsuperuser`; after login it opens the super-admin dashboard. Seeded sample accounts and listings can be edited or deleted there.

## Frontend checks

From the repository root:

```bash
for file in frontend/assets/js/*.js; do node --check "$file"; done
```

With both servers running, verify the home and search pages, category and price filters, sorting, pagination, product details, login/registration, seller tools, messaging, favourites, notifications, account preferences, admin pages and legal routes. Creating accounts and listings requires a migrated backend and an approved account; seller activation requires phone verification through a configured SMS provider.

## API endpoints

Base URL: `http://127.0.0.1:8000/api/v1/`. Implemented endpoints are served by Django and enforce authorization server-side:

| Method | Path | Purpose |
|---|---|---|
| GET | `auth/csrf/` | Start a CSRF-protected session |
| POST | `auth/register/`, `auth/login/`, `auth/logout/` | Session-based authentication; registration accepts `account_mode` (`buyer`, `seller`, `general`) and signs the new account in immediately |
| POST | `auth/mfa/verify/` | Legacy MFA endpoint; not used by current development login |
| GET | `auth/me/` | Current account |
| POST | `auth/email-verification/`, `auth/email-verification/resend/` | Verify/resend email |
| POST | `auth/password-reset/`, `auth/password-reset/confirm/`, `auth/password-change/` | Password management |
| GET | `categories/` | Active categories |
| GET, POST | `products/` | Search, filter, paginate and create listings with multipart images |
| GET, PATCH, DELETE | `products/{uuid}/` | Read or manage an owned listing |
| POST | `products/{uuid}/availability/` | Change owned listing availability |
| GET, POST | `products/{uuid}/comments/` | Public questions and comments |
| POST | `products/{uuid}/comments/{commentId}/helpful/` | Vote a comment helpful |
| GET | `sellers/`, `sellers/{userId}/` | Public seller directory/profile |
| POST | `sellers/phone-verification/`, `sellers/phone-verification/confirm/`, `sellers/activate/` | Verify phone and activate seller features |
| GET, PATCH | `users/me/`, `sellers/me/` | Update own profile and seller contact preferences |
| GET | `sellers/me/products/`, `analytics/seller/overview/` | Seller listings and analytics |
| GET, POST | `conversations/` | List/start conversations |
| GET | `conversations/{uuid}/` | Read a participant conversation |
| GET, POST | `conversations/{uuid}/messages/` | Read/send messages and image attachments |
| GET, POST, DELETE | `favourites/`, `favourites/{productUuid}/` | Manage favourites |
| POST | `reports/` | Report a supported content or member target |
| GET, POST | `users/blocked/`, `users/{userUuid}/block/` | Manage blocked members |
| GET | `notifications/`, `notifications/preferences/` | Notifications and preferences |
| POST, DELETE | `notifications/{id}/read/`, `notifications/{id}/` | Mark read or delete an own notification |
| GET | `site-info/` | Public contact/about/team information |
| GET | `admin/{resource}/` | Role-protected data, including pending approvals, users, reports, analytics, conversations and settings |
| POST | `admin/users/`, `admin/products/`, `admin/conversations/`, `admin/categories/`, `admin/announcements/` | Superuser creates an account, team-owned live listing, conversation, category or announcement |
| PATCH | `admin/users/{id}/`, `admin/products/{id}/`, `admin/announcements/{id}/` | Superuser edits a member account, listing or announcement |
| GET | `announcements/` | Published community announcements |
| GET, POST, DELETE | `cart/`, `cart/{productUuid}/` | Manage the signed-in member's cart |
| GET, POST | `category-suggestions/` | Members request categories; moderators review and approve or dismiss them |
| GET, POST | `support/conversations/` | Member-owned support threads; authorized support staff see the support inbox |
| GET, POST | `support/conversations/{id}/messages/` | Read or reply to an authorized support thread |
| PATCH | `admin/settings/` | Superuser edits public contact/about/team information |
| POST | `admin/{resource}/{id}/actions/` | Review reports, reactivate accounts, and approve or dismiss category requests |
| GET | `admin/message-reports/{reportUuid}/evidence/` | Access assigned reported-message evidence; access is audited |

Report submissions create in-dashboard notifications for active superusers. Direct account reports automatically suspend the reported account and pause its active listings pending investigation; moderators can reactivate the account after review.

Product discovery accepts `search`, `category`, `subcategory`, `county`, `town`, `condition`, `min_price`, `max_price`, `rating`, `sort` (`newest`, `price_asc`, `price_desc`, `popular`) and `page`.

## External services and deployment

The SMS sender is a provider-agnostic adapter configured with `SMS_PROVIDER_URL`, `SMS_PROVIDER_API_KEY` and `SMS_SENDER_ID`; no verification code is returned to the browser. Configure real email, SMS, PostgreSQL, Redis and media storage before production. Run security/deployment checks and obtain independent legal review of the terms and privacy disclosures before launch.
