# EduPulse: AI-Driven School Governance, Revenue Integrity & Subscription Intelligence

EduPulse is a multi-tenant SaaS platform for Ghanaian schools that combines academic operations, payment governance, and usage-based subscription controls in one system.

## 🚀 Current Implementation Snapshot

### Core Platform
- Multi-tenant authentication and school-level data isolation (`JWT + X-School-ID + tenant guard`)
- Role-based access control across `proprietor`, `headmaster`, `teacher`, `finance`, and `admin`
- Dynamic school branding and configurable school settings
- Audit-oriented workflows for sensitive operations

### Academic Operations
- Attendance tracking and summaries
- Grade entry and report-card generation workflows
- Report builder with staged approvals (teacher → headmaster → proprietor)
- Lesson notes and academic analytics tooling
- Exam papers workflow (teacher authoring + headmaster/proprietor review) for Premium tenants
- AI Exam Assistant for guided question generation (Premium only)

### Finance & Payments
- Manual and digital payment recording
- Reconciliation workflows and transaction history
- Payment tracking dashboards and oversight views
- Immutable/auditable ledger-style operational records

### Subscription, Metering & Monetization (Metronome-Aligned)
- Active-student metering with manual sync endpoint
- Billing visibility endpoint with cost breakdown and threshold alerts (`80% warning`, `100% critical`)
- Premium trial entitlement lifecycle (status, activate, end, expiry checks)
- Pricing grandfathering/version lock endpoint
- Price-cap management endpoint for predictable billing control
- Usage-report email trigger endpoint and backend email service utilities

### Frontend Billing Experience
- Billing visibility widget (meter + alerts + cost transparency)
- Trial management widget (activate/end, countdown, state-aware messaging)
- Billing control panel (price cap toggle, cap amount, budget feedback)
- Email usage report trigger button from billing UI

## 🧠 AI & Governance Features
- AI-assisted academic insight surfaces
- Risk-aware governance loops for intervention workflows
- Remote oversight feed for proprietor monitoring
- Operational analytics to support school decision-making

## 💳 Registration & Billing Flow (Current)
- Tenant registration supports plan selection at onboarding.
- If `Free` is selected: registration completes and user proceeds to login.
- If `Basic` or `Premium` is selected: payment is initialized immediately at registration and user is redirected to Paystack.
- After successful payment verification, user is redirected to login and receives one welcome email.
- Duplicate registration welcome emails are prevented by audit-logged single-send checks.

## 🧩 API Highlights (Recent)
- `GET /api/school/subscription/billing-visibility`
- `POST /api/school/subscription/meter/sync`
- `GET /api/school/subscription/trial/status`
- `POST /api/school/subscription/trial/activate`
- `POST /api/school/subscription/trial/end`
- `POST /api/school/subscription/lock-pricing`
- `GET /api/school/subscription/price-cap`
- `POST /api/school/subscription/price-cap`
- `GET /api/school/subscription/usage-stats`
- `POST /api/school/subscription/usage-report/send`
- `GET /api/platform/registration-email-trace`

## 🔄 End-to-End Workflow (BPMN-Style with Gateways)

```mermaid
flowchart TD
    S([Start]) --> A[School Onboarding]
    A --> B{School registered?}
    B -- No --> A
    B -- Yes --> C[Create Proprietor Account]
    C --> D[User Login]
    D --> E{Auth valid + tenant context valid?}
    E -- No --> D
    E -- Yes --> F{Role Gateway}

    %% Teacher lane
    F -- Teacher --> T1[Mark Attendance]
    T1 --> T2[Enter Grades / Lesson Notes]
    T2 --> T3[Submit Report Data]

    %% Homeroom / Headmaster lane
    F -- Headmaster --> H1[Review Class Performance]
    H1 --> H2{Report complete?}
    H2 -- No --> T2
    H2 -- Yes --> H3[Approve / Return Report]

    %% Finance lane
    F -- Finance --> FN1[Record Payment / Confirm Transfer]
    FN1 --> FN2[Reconcile Transactions]
    FN2 --> FN3[Update Ledger + Payment Status]

    %% Proprietor lane
    F -- Proprietor --> P1[Open Proprietor Dashboard]
    P1 --> P2[Review AI Insights + Risk Feed]
    P2 --> P3{Intervention needed?}
    P3 -- Yes --> P4[Initiate Parent/Staff Intervention]
    P3 -- No --> P5[Continue Monitoring]

    %% Subscription monetization lane
    P1 --> M1[Open Subscription & Billing]
    M1 --> M2[Fetch Billing Visibility]
    M2 --> M3{Usage threshold reached?}
    M3 -- Under 80% --> M4[Status OK]
    M3 -- 80-99% --> M5[Warning Alert]
    M3 -- 100%+ --> M6[Critical Alert + Overage Impact]

    M4 --> M7{Need control actions?}
    M5 --> M7
    M6 --> M7

    M7 -- Sync meter --> M8[Manual Meter Sync]
    M7 -- Activate premium trial --> M9[Trial Activate]
    M7 -- End trial --> M10[Trial End]
    M7 -- Lock pricing --> M11[Grandfather Pricing Version]
    M7 -- Set price cap --> M12[Update Price Cap]
    M7 -- Email usage report --> M13[Send Usage Report Email]

    %% Payment/plan path
    M13 --> G1{Upgrade decision?}
    M11 --> G1
    M12 --> G1
    M9 --> G1
    G1 -- Yes --> U1[Initialize Payment]
    U1 --> U2{Payment successful?}
    U2 -- No --> U3[Retry / Alternate Method]
    U2 -- Yes --> U4[Apply Plan + Entitlements]

    %% Continuous governance loop
    U4 --> Z[Audit Log + Notifications]
    FN3 --> Z
    H3 --> Z
    P4 --> Z
    P5 --> Z
    M8 --> Z
    M10 --> Z

    Z --> R{Cycle complete for current term?}
    R -- No --> F
    R -- Yes --> END([Term Close + Next-Term Rollforward])
```

## 🧱 Tech Stack
- **Backend**: Flask, SQLAlchemy, Alembic, JWT
- **Frontend**: React (Vite), Tailwind, Axios
- **Database**: SQLite/PostgreSQL-compatible data model patterns
- **Security**: Password hashing, role/tenant middleware, protected endpoints

## 🧪 Validation Status
- Migration and subscription-metering updates applied
- Frontend billing widgets integrated and built successfully
- Test suite status: `86 passed, 0 failed`

## 📦 Run Locally

```bash
docker compose up --build
```

## 📁 Helpful Docs
- `BUSINESS_PROCESS_MODEL.md`
- `BPM_QUICK_REFERENCE.txt`
- `PAYMENT_INTEGRATION.md`
- `SUBSCRIPTION_FEATURES.md`
- `REPORT_BUILDER_GUIDE.md`
