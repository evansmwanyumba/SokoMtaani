# SokoMtaani backend — Development status

The backend now includes session-based authentication, buyer and seller profiles, categories and product/image APIs, search and filtering, internal messaging, community favourites/reviews/reports, notifications and preferences, seller analytics, and role-protected moderation/admin APIs. It defaults to SQLite for local development and can use PostgreSQL, Redis and external email/SMS services through environment configuration. Production security, external-service credentials, deployment and independent legal review are still required before launch.

## Structure

```text
backend/
├── apps/accounts/       # Custom account model and authentication API
├── apps/categories/     # Public category taxonomy
├── apps/profiles/       # Member and seller profiles, phone verification and analytics
├── apps/products/       # Product listings, images, comments, views and discovery filters
├── apps/community/      # Favourites, reviews, reports, suspensions, audit and admin APIs
├── apps/messaging/      # Participant-protected conversations and messages
├── apps/notifications/  # Member notifications and preferences
├── config/              # Django settings, URL routing, ASGI/WSGI
├── tests/               # Authentication tests
├── .env.example
├── manage.py
└── requirements.txt
```

`role` is not an authorization grant. Public registration accepts a buyer/seller/general account mode but cannot assign administrative authority; new accounts are approved and signed in immediately without email verification or OTP. Seller activation still requires verified phone. Administrative role creation is reserved for the superuser. Admin-owned listings display as SokoMtaani Team, and private marketplace messages remain separate from the dedicated support inbox. Reporting a member account immediately suspends that account and pauses its active listings while notifying superusers; the action is recorded for investigation, and administrators can reactivate accounts. Access to reported message evidence is restricted to the assigned moderator and audited. Frontend role checks are navigation only.

## Install and configure

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Put the generated value in `.env` as `DJANGO_SECRET_KEY`. The example file selects SQLite by default for local setup. To use PostgreSQL, create a database and role (the commands prompt for a password):

```bash
sudo -u postgres createuser --pwprompt sokomtaani
sudo -u postgres createdb --owner=sokomtaani sokomtaani
```

Set `DATABASE_URL` in `.env`, URL-encoding any special characters in the password:

```text
DATABASE_URL=postgresql://sokomtaani:your-password@127.0.0.1:5432/sokomtaani
```

The local email backend prints verification and password-reset links to the development server console. Configure a real email provider using `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and TLS settings before deployment. Development uses an in-process cache for throttling; production requires `REDIS_URL` so login and other anonymous request throttles are shared across web workers. Never commit `.env`.

## Migrate and run

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

The administrator command creates a Django superuser. Do not assign administrator roles from public registration. The development server is not suitable for production.

### Fresh local database and demo marketplace

To deliberately erase all records from the configured **development** database and start over:

```bash
python manage.py flush --noinput
python manage.py createsuperuser
python manage.py seed_demo_data
```

`createsuperuser` asks for the login **email address** and password. A Django superuser has the `super_admin` role and is routed to the full Admin dashboard after sign-in. `flush` deletes all users and marketplace records; never run it against a database containing data you need or against production. The seed command is disabled when `DEBUG=False`. It creates reserved `.test` demo accounts (without usable passwords), sample categories, three sample live listings, and a sample conversation. A superuser can edit or remove those sample users and listings from the dashboard. Demo users can be deleted together with their sample conversations.

## Authentication contract

Base URL: `http://127.0.0.1:8000/api/v1/`

Authentication uses Django's server-side session cookie, not bearer tokens. In this development configuration, login does not require email verification or OTP/TOTP, including for superusers. New registrations are approved automatically and establish a login session immediately. The legacy MFA and email-verification endpoints remain available but are not required in the current flow. This password-only administrator access is a development convenience, not production security: restore stronger verification and secure deployment settings before launch.

From a browser frontend:

1. Call `GET /auth/csrf/` with credentials included. It returns `{"csrfToken":"..."}` and sets a CSRF cookie.
2. Send credentials on requests (`credentials: "include"` for `fetch`, or `withCredentials: true` for Axios). For unsafe methods, send the returned value in `X-CSRFToken`.
3. Use only a frontend origin listed in both `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`. The frontend URL used in verification and reset emails is `FRONTEND_BASE_URL`.
4. Successful approved-account login sets an HttpOnly session cookie. Use `GET /auth/me/` to retrieve the current account and `POST /auth/logout/` to invalidate the session.

If frontend and API are on separate sites in production, use HTTPS and set `SESSION_COOKIE_SAMESITE=None`, `SESSION_COOKIE_SECURE=True`, and `CSRF_COOKIE_SECURE=True`. Do not use wildcard CORS with credentials.

### Endpoints

| Method | Path | Access | Contract |
|---|---|---|---|
| GET | `/auth/csrf/` | Public | Returns a CSRF token and sets the CSRF cookie. |
| POST | `/auth/register/` | Public, throttled | `{email, password, first_name?, last_name?, account_mode?}`. Creates an approved account, signs it in immediately, and does not send verification email. `account_mode` is `buyer`, `seller`, or `general`; seller activation still requires phone verification. |
| POST | `/auth/login/` | Public, CSRF-protected, throttled | `{email, password}`. Active accounts receive `200` and a session; email verification and OTP are not required in this development configuration. |
| POST | `/auth/mfa/verify/` | Legacy endpoint, not used by current login | MFA implementation retained for a future secured configuration. |
| POST | `/auth/logout/` | Authenticated, CSRF-protected | Clears the current session; returns `204`. |
| GET | `/auth/me/` | Authenticated | Returns the public account object. |
| POST | `/auth/email-verification/` | Public, throttled | `{token}` from the verification email. |
| POST | `/auth/email-verification/resend/` | Public, throttled | `{email}`. Response does not disclose whether an account exists. |
| POST | `/auth/password-reset/` | Public, throttled | `{email}`. Response does not disclose whether an account exists. |
| POST | `/auth/password-reset/confirm/` | Public, throttled | `{uid, token, new_password}` from the reset email. Existing sessions are invalidated. |
| POST | `/auth/password-change/` | Authenticated, CSRF-protected | `{old_password, new_password}`. Keeps the current session and invalidates other sessions. |
| GET | `/site-info/` | Public | Configurable community contact, about, and team details. |
| GET | `/announcements/` | Public | Published community announcements. |
| POST | `/category-suggestions/` | Authenticated member | Request a category not in the active taxonomy; moderators approve or dismiss the request. |
| GET, POST, DELETE | `/cart/`, `/cart/{productUuid}/` | Authenticated member | Manage the signed-in member's cart; product availability and ownership are checked server-side. |
| GET, POST | `/support/conversations/` | Authenticated member; support staff may list all | Create a support conversation or list only conversations available to the current account. |
| GET, POST | `/support/conversations/{id}/messages/` | Conversation owner or support staff | Read or reply to a support thread; private marketplace conversations are not exposed here. |
| DELETE | `/notifications/{id}/` | Authenticated member | Delete only an own notification. |
| GET | `/admin/{resource}/` | Role-protected | Admin data, including `pending-approvals`, reports, users, listings, conversations, analytics and settings. |
| POST | `/admin/users/` | Superuser | Create an immediately approved account; only superuser may set administrative roles. |
| POST | `/admin/products/` | Superuser | Create a live team-owned listing, optionally on behalf of an active seller. |
| POST | `/admin/conversations/` | Superuser | Open a conversation and notify both members; does not send a message on their behalf. |
| POST | `/admin/categories/`, `/admin/announcements/` | Superuser | Create a category or community announcement. |
| PATCH | `/admin/announcements/{id}/` | Superuser | Edit or unpublish an announcement. |
| PATCH | `/admin/settings/` | Superuser | Update public contact, about, and team information. |
| POST | `/admin/{resource}/{id}/actions/` | Role-protected; action-specific superuser checks | Approve legacy pending accounts, deactivate/delete accounts, review reports, reactivate accounts, and approve/dismiss category suggestions. Direct account reports automatically suspend the target and notify superusers. |
| PATCH | `/admin/users/{id}/`, `/admin/products/{id}/` | Superuser | Edit a member's email/name or a listing's details. |

Account responses contain `id`, `email`, `first_name`, `last_name`, `role`, `admin_role`, `is_email_verified`, `is_admin_approved`, and `date_joined`. Validation errors use DRF's field-keyed JSON format; authentication errors include a `detail` field. Request throttles return HTTP `429`.

OpenAPI schema: `/api/schema/`; interactive docs: `/api/docs/`.

## Marketplace endpoints

Base URL: `http://127.0.0.1:8000/api/v1/`

| Method | Path | Access | Contract |
|---|---|---|---|
| GET | `/categories/` | Public | Paginated active top-level categories with active subcategories and active-listing counts. |
| GET | `/categories/{slug}/` | Public | Retrieve an active top-level category. |
| GET | `/products/` | Public | Paginated active listings. Supports `search`, `category`, `subcategory`, `county`, `town`, `condition`, `min_price`, `max_price`, seller `rating`, and `sort` (`newest`, `price_asc`, `price_desc`, `popular`). |
| POST | `/products/` | Active seller | Create an active listing; seller is always the authenticated member. Accepts JSON or multipart form data. Multipart accepts repeated `images` files, up to 6 images, JPEG/PNG/WebP, 5 MB each. |
| GET | `/products/{uuid}/` | Public for active listings; owners can access their own inactive listings | Retrieve a listing and its image URLs. |
| PATCH, PUT, DELETE | `/products/{uuid}/` | Listing owner or superuser | Update or remove an owned listing. New images supplied in multipart are appended, not substituted. |
| POST | `/products/{uuid}/availability/` | Listing owner | Set availability to `active`, `paused`, or `sold`. |
| GET | `/products/{uuid}/comments/` | Public | List visible community comments. |
| POST | `/products/{uuid}/comments/` | Authenticated, approved account | Add `{ "content": "..." }`; author is assigned from the session. |

Product condition input accepts either the API values (`new`, `like_new`, `gently_used`) or the display labels (`New`, `Like new`, `Gently used`). Product image uploads are validated by content as images as well as by extension and size. Configure durable, private-aware media storage before production; Django's development server serves local uploads only while `DEBUG=True`.

Seller, messaging, community, notification and admin endpoints are documented in the frontend API contract at `../frontend/README.md`. The local SMS adapter requires a configured provider endpoint/key to deliver phone codes; it does not provide a development bypass.

## Authentication smoke test

Start the server, then in another terminal:

```bash
curl -i http://127.0.0.1:8000/api/v1/auth/csrf/
```

For browser-based login, first obtain the CSRF token, retain the cookie, then submit it in `X-CSRFToken`; direct `curl` login without both is intentionally rejected. A new public account must first be approved by a superuser from the Admin dashboard. Approved accounts, including superusers, can then sign in with email and password. Call `/auth/logout/` with the same cookie and CSRF header to invalidate the session.

## Tests

```bash
python manage.py test tests apps.accounts apps.profiles apps.categories apps.products apps.community apps.messaging apps.notifications
```

The tests cover authentication, immediate registration, password reset/change, throttling, marketplace filtering/uploads and seller permissions, phone verification, participant-only messaging, cart and support access isolation, category requests, notifications, moderation, admin workflows and audited message-evidence access. Django's test runner uses an isolated SQLite database unless configured otherwise.

## Production notes

Set `DJANGO_DEBUG=False`, a unique secret key, explicit allowed hosts, PostgreSQL `DATABASE_URL`, Redis `REDIS_URL`, HTTPS-only secure cookies, a real email backend, and narrowly scoped CORS/CSRF origins. Terminate TLS at a trusted reverse proxy and ensure it sanitizes forwarded client-IP headers before Django applies IP-based throttles. Use a production WSGI server such as Gunicorn. Keep database, Redis, and email credentials in a secret manager/environment, restrict database privileges, and establish encrypted backups and retention policies before storing real user data. Legal compliance and retention settings require independent review.
