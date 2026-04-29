# 🏢 EduPulse SMT Business Process Model

## Executive Overview

EduPulse SMT operates a **Freemium SaaS** model with three pricing tiers designed to drive conversion and retention through feature throttling and capacity limits.

```
┌─────────────────────────────────────────────────────────────────┐
│                  EDUPULSE SMT BUSINESS MODEL                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ACQUISITION → ONBOARDING → ACTIVATION → MONETIZATION → RETENTION
│  (Marketing)   (Free Trial)  (Core Use)   (Upgrades)   (Renewals)
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

EduPulse remains a school-led B2B platform first, but the next product evolution is a **B2B2C operating layer** where parents interact directly with school-controlled admissions and payment workflows.

- The school remains the paying customer and policy owner.
- Parents become transacting users inside the school's branded workflows.
- AI Employees are meant to perform scoped operational labor, not replace school authority.

### Current vs Planned Scope

Current implementation:
- school onboarding and subscription billing
- school-managed admissions and bulk student onboarding
- parent payment instructions with stable payment identity, structured reference parsing, and optional Paystack fee-route DVAs
- Student Rescue Agent for intervention workflows

Planned near-term expansion:
- AI Registrar for admissions intake, document completeness checks, and routing
- parent-facing admissions application and status tracking
- online-test or school-visit decisioning based on connectivity and policy
- AI Bursar for reconciliation support, payment stress flagging, and collections recommendations

Future-only items:
- fully autonomous admission approval without staff review
- voice-first multilingual parent bots
- pure outcome-based pricing for AI labor
- predictive dropout automation and advanced autonomous escalation

---

## 1️⃣ CUSTOMER ACQUISITION FLOW

### Target Markets
```
PRIMARY: Schools with 50-200 students
├─ Small-to-mid primary & JHS
├─ Pain points: Manual attendance, paper grades, cash leakage
└─ Decision maker: School Proprietor/Principal

SECONDARY: Large schools (200+ students)
├─ Secondary schools, boarding schools
├─ Pain points: Complex workflows, dropouts, AI governance
└─ Decision maker: Headmaster/Finance Officer

TERTIARY: School Districts/Chains
├─ Multi-school operators
├─ Pain points: Centralized reporting, compliance
└─ Decision maker: District Coordinator
```

### Acquisition Channels

```
CHANNEL 1: Direct Sales (B2B)
├─ School proprietor networks
├─ Educational associations
├─ Business development calls
└─ ROI: GH₵200-500/month × 12-24 month contract

CHANNEL 2: Digital Marketing
├─ Facebook ads targeting school administrators
├─ Google Ads ("School Management Software Ghana")
├─ WhatsApp business groups
└─ ROI: GH₵20-50 CAC, 50% conversion to Basic/Premium

CHANNEL 3: Partnerships
├─ MTN Ghana (MoMo integration partnerships)
├─ GCB/Ecobank (payment infrastructure)
├─ NPOs in education sector
└─ ROI: Volume deals, long-term contracts

CHANNEL 4: Freemium Viral Loop
├─ Teachers share logins with other schools
├─ "Try free for 50 students" word-of-mouth
├─ Parent networks
└─ ROI: Low CAC, viral coefficient = 0.3-0.5

CHANNEL 5: Parent Self-Service Pull (Planned B2B2C)
├─ Schools share branded admissions links
├─ Parents apply remotely without first visiting campus
├─ AI Registrar reduces admissions friction and follow-up delays
└─ ROI: Higher application conversion and lower admissions admin cost
```

### Customer Acquisition Cost (CAC) & LTV

```
FREEMIUM MODEL METRICS:

Free Tier:
  CAC: GH₵10-30 (low-friction signup)
  LTV: GH₵0 (no revenue)
  Purpose: Maximize reach, drive upgrades

Basic Plan:
  CAC: GH₵50-150 (sales + trial period)
  Monthly Value: GH₵200
  LTV (24-month): GH₵4,800 (assume 80% retention)
  LTV/CAC Ratio: 32:1 ✓ (Excellent)

Premium Plan:
  CAC: GH₵200-400 (enterprise sales)
  Monthly Value: GH₵500
  LTV (24-month): GH₵12,000 (assume 90% retention)
  LTV/CAC Ratio: 30:1 ✓ (Excellent)

Blended Metrics (70% Basic, 30% Premium):
  Blended LTV/CAC: ~30:1
  Payback Period: ~3 months ✓ (Unit economics solid)
```

---

## 2️⃣ ONBOARDING & ACTIVATION FLOW

```
                    SCHOOL SIGNUP
                          ↓
        ┌─────────────────────────────────┐
        │  Create School Organization     │
        │  ├─ School Code (CCA-OFK)       │
        │  ├─ Name, Email, Logo           │
        │  └─ Primary Color (Branding)    │
        └─────────────────────────────────┘
                        ↓
        ┌─────────────────────────────────┐
        │  Plan Selection at Signup       │
        │  Free / Basic / Premium         │
        │  Student count for billing calc │
        └─────────────────────────────────┘
                        ↓
        ┌─────────────────────────────────┐
        │  Decision Gateway               │
        │  ├─ Free: Activate immediately  │
        │  └─ Paid: Redirect to Paystack  │
        └─────────────────────────────────┘
            ↓
        ┌─────────────────────────────────┐
        │  Create First Admin User        │
        │  ├─ Proprietor Role             │
        │  ├─ Staff ID (username)         │
        │  └─ School Credentials          │
        └─────────────────────────────────┘
                        ↓
        ┌─────────────────────────────────┐
        │  Onboarding Dashboard           │
        │  ├─ Add 2-3 Teachers            │
        │  ├─ Add 5-10 Sample Students    │
        │  ├─ Enter First Attendance      │
        │  └─ Record First Payment        │
        └─────────────────────────────────┘
                        ↓
        ┌─────────────────────────────────┐
        │  ACTIVATION SUCCESS             │
        │  Free: instant activation        │
        │  Paid: activation after payment  │
        └─────────────────────────────────┘

ACTIVATION METRICS TARGET:
├─ Signup to First Login: <24 hours
├─ First Data Entry: <48 hours
├─ 5+ Interactions: <1 week
└─ 30% of Free Users → Trial Conversion
```

---

## 3️⃣ FEATURE USAGE & ENGAGEMENT FLOW

### Day 1-7: Core Usage (All Tiers)

```
Teacher Dashboard
├─ Mark Attendance (30 sec)
├─ Enter Grades (2 min)
├─ View Lesson Notes (1 min)
└─ Submit Work

Proprietor Dashboard
├─ View Live Feed (real-time)
├─ Check Revenue (auto-updated)
├─ Monitor Student Attendance
└─ See Basic Analytics

ENGAGEMENT: 5-7 interactions/day
RETENTION SIGNAL: Returns on Day 2
```

### Week 1-4: Expansion (Free → Basic Consideration)

```
School hits 50-student limit
           ↓
┌──────────────────────────────────┐
│  UPGRADE PROMPT                  │
│  "You've reached 50-student cap" │
│  "Upgrade to Basic for 200"      │
│  [UPGRADE NOW] button            │
└──────────────────────────────────┘
           ↓
CONVERSION OPTIONS:
├─ 30% → Upgrade to Basic (GH₵200/mo)
├─ 40% → Continue with Free (manage 50)
├─ 30% → Churn (find alternative)
```

### Month 1-3: Premium Features (Basic → Premium)

```
Basic Plan User Sees:
├─ "🔒 AI Student Pulse (Premium Feature)"
├─ "🔒 Automated Payment Processing"
├─ "🔒 Exam Papers Module"
├─ "🔒 AI Exam Assistant"
└─ Dashboard banners: "Unlock AI for GH₵500/mo"

ENGAGEMENT METRICS:
├─ Clicks on locked features: 60% of users
├─ Feature demand signals detected
└─ Point-of-friction identification
```

---

## 4️⃣ MONETIZATION FLOW

### Pricing Tier Ladder

```
┌───────────────────────────┐
│    FREEMIUM FUNNEL        │
├───────────────────────────┤
│                           │
│  1,000 Free Signups       │
│  (GH₵ 0/mo)              │
│         ↓ 30%             │
│  300 → Basic Trial        │
│  (GH₵ 200/mo)            │
│         ↓ 25%             │
│  75 → Premium             │
│  (GH₵ 500/mo)            │
│                           │
└───────────────────────────┘

REVENUE FROM 1,000 SIGNUPS:

Free Tier: 625 schools × GH₵0 = GH₵0
Basic Plan: 300 schools × GH₵200 = GH₵60,000/month
Premium Plan: 75 schools × GH₵500 = GH₵37,500/month
─────────────────────────────────────
Total: GH₵97,500/month (from 1,000 signups)

Blended ARPU: GH₵97.50/month per signup
Lifetime Value (24-mo): GH₵2,340 per signup
```

### Payment Processing Pipeline

```
                        SCHOOL SELECTS PLAN
                              ↓
                    Select: Basic or Premium
                              ↓
        ┌─────────────────────────────────┐
        │  PAYMENT METHOD SELECTION       │
        ├─────────────────────────────────┤
        │  Option 1: MoMo (50% choose)    │
        │  ├─ Send to: +233501234567      │
        │  └─ Reference: SCHOOL-CODE      │
        │                                 │
        │  Option 2: Bank Transfer (30%)  │
        │  ├─ GCB, Ecobank, STD Chartered │
        │  └─ Reference: SCHOOL-CODE      │
        │                                 │
        │  Option 3: Debit Card (20%)     │
        │  ├─ Via Paystack/Flutterwave    │
        │  └─ Auto-debit on renewal date  │
        └─────────────────────────────────┘
                        ↓
        ┌─────────────────────────────────┐
        │  SUBSCRIPTION ACTIVATED         │
        │  ├─ Monthly recurring           │
        │  ├─ Renewal date set            │
        │  ├─ Features unlocked           │
        │  └─ Invoice emailed             │
        └─────────────────────────────────┘
                        ↓
        ┌─────────────────────────────────┐
        │  MONTHLY RENEWAL CYCLE          │
        │  ├─ 7 days before: Reminder     │
        │  ├─ Payment processed           │
        │  ├─ Invoice + Receipt           │
        │  └─ Features continue           │
        └─────────────────────────────────┘
```

---

## 5️⃣ REVENUE STREAMS & FINANCIAL MODEL

### Primary Revenue: Subscription

```
MONTHLY RECURRING REVENUE (MRR) MODEL:

Tier 1 - Free Customers:
  Number: 1,000 schools × 30% blended
  = 300 schools
  Revenue: GH₵0/month
  ┗─ Purpose: User acquisition funnel

Tier 2 - Basic Customers:
  Number: 1,000 schools × 42% blended
  = 420 schools
  Price: GH₵200/month each
  Monthly Revenue: GH₵84,000
  Annual Revenue: GH₵1,008,000
  ┗─ Retention: 80%/month → 9.6 months avg customer life

Tier 3 - Premium Customers:
  Number: 1,000 schools × 28% blended
  = 280 schools
  Price: GH₵500/month each
  Monthly Revenue: GH₵140,000
  Annual Revenue: GH₵1,680,000
  ┗─ Retention: 90%/month → 10.5 months avg customer life

TOTAL MRR: GH₵224,000/month
TOTAL ARR: GH₵2,688,000/year (1,000 schools)
```

### Secondary Revenue: Premium Add-ons (Future)

```
SMS Notifications:
├─ Cost: GH₵0.05 per SMS
├─ Usage: 2-5 SMS per student/month
├─ Revenue: GH₵0.25-1.25 per student/month
└─ Estimated: +15% to blended ARPU

Advanced Reporting:
├─ Cost: +GH₵50/month add-on
├─ Adoption: 10% of Basic, 30% of Premium
├─ Additional Revenue: ~GH₵8,000/month

API Access for Districts:
├─ Cost: GH₵1,000/month per district
├─ Usage: Multi-school reporting integration
├─ Estimated: 5-10 districts × GH₵1,000 = GH₵7,500/month
```

### Total Potential Revenue Model

```
BASE (Subscription): GH₵224,000/month

Add-ons:
├─ SMS Notifications: +GH₵18,000/month
├─ Advanced Reporting: +GH₵8,000/month
└─ District API: +GH₵7,500/month

TOTAL EXPANDED MRR: GH₵257,500/month
EXPANDED ARR (1,000 schools): GH₵3,090,000/year
MRR Growth per 100 new schools: ~GH₵22,400/month
```

---

## 6️⃣ CHURN & RETENTION FLOW

### Churn Points & Mitigation

```
CHURN RISK 1: Free → Basic Conversion Stalls
Risk: 70% of free users stay at 50 students
├─ Current: 30% convert to paid
├─ Target: 40% convert to paid
└─ Mitigation:
    ├─ Email sequences: "Your 51st student is waiting"
    ├─ Pricing page optimization
    ├─ Free trial extended to 14 days
    └─ Estimated lift: +5-10% conversion

CHURN RISK 2: Basic → Premium Upgrade Stalls
Risk: AI features not perceived as valuable
├─ Current: 18% of Basic → Premium
├─ Target: 25% of Basic → Premium
└─ Mitigation:
    ├─ Show AI wins: "Saved X dropouts last month"
    ├─ Free AI trial: 7-day access to AI Pulse
    ├─ Case studies: School A reduced dropouts 30%
    └─ Estimated lift: +3-5% upgrade rate

CHURN RISK 3: Mid-Contract Cancellation
Risk: ~10% month-to-month churn (80% of contracts)
├─ Current: Natural churn from school closures/holidays
├─ Target: <5% voluntary churn
└─ Mitigation:
    ├─ Dedicated support for Premium tier
    ├─ Executive check-ins at month 2, 6, 12
    ├─ Health score tracking (usage metrics)
    └─ Pro-active issue resolution

CHURN RISK 4: School Year Seasonality
Risk: Drop-off during school holidays (Dec/Jul)
├─ Current: Holiday churn = 15-20%
└─ Mitigation:
    ├─ Annual plans (20% discount) → shift churn curve
    ├─ Automatic pause feature: Reactivate next term
    └─ Holiday support for data entry tasks

OVERALL RETENTION TARGETS:
├─ Free Tier: 50% MoM (short lifecycle by design)
├─ Basic Plan: 80% MoM (9.6 month average customer life)
├─ Premium Plan: 90% MoM (10.5 month average customer life)
└─ Blended: 75% MoM (9 month average customer life)
```

---

## 7️⃣ GROWTH MECHANICS

### Viral Coefficient & Network Effects

```
VIRAL LOOP 1: Teacher Referral
├─ Teacher A uses EduPulse at School X
├─ Teacher B (friend) asks: "What's that app?"
├─ Teacher A shares login/recommendation
├─ Teacher B signs up at School Y
├─ Viral Coefficient: 0.15 (each customer brings 0.15 new customers)

VIRAL LOOP 2: Parent Network
├─ Parent A sees student grades in EduPulse app
├─ Parent A tells Parents B & C at church/market
├─ Parents B & C ask school: "Do you have this app?"
├─ School gets pressure to adopt
├─ Viral Coefficient: 0.08

VIRAL LOOP 3: Staff Mobility
├─ Subject Teacher changes school at end of term
├─ Previous school was using EduPulse
├─ Teacher recommends to new school
├─ New school evaluates and signs up
├─ Viral Coefficient: 0.20

BLENDED VIRAL COEFFICIENT: ~0.3 - 0.4
INTERPRETATION: Each paying customer brings 0.3-0.4 new customers
└─ Result: Compounding growth at scale
```

### Unit Economics & Scaling

```
CUSTOMER ACQUISITION COST (CAC)
├─ Free Tier: GH₵15 (low touch)
├─ Basic Plan: GH₵100 (with trial conversion)
└─ Premium Plan: GH₵300 (enterprise sales)

CUSTOMER LIFETIME VALUE (LTV)
├─ Free Tier: GH₵0 (no revenue)
├─ Basic Plan: GH₵1,920 (200/mo × 9.6 mo × 80% retention)
└─ Premium Plan: GH₵4,500 (500/mo × 10.5 mo × 90% retention)

LTV/CAC RATIO (Key Health Metric)
├─ Free → Basic: 19:1 ✓ (Healthy)
├─ Free → Premium: 15:1 ✓ (Healthy)
└─ Blended: 18:1 ✓ (Excellent - Target is 3:1)

PAYBACK PERIOD
├─ Basic Plan: 6 months (100/200 cap cost)
├─ Premium Plan: 7.2 months (300/500 cap cost)
└─ Blended: 6.2 months (Fast - targets <9 months)

SCALING IMPLICATIONS:
├─ Unit economics improve at scale (CAC decreases, LTV stays same)
├─ 10,000 schools TAM = GH₵25.8M ARR potential
├─ Path to profitability: 500-1,000 paying customers
```

---

## 8️⃣ KEY BUSINESS METRICS

### Monthly Dashboard Metrics

```
ACQUISITION
├─ New Free Signups: 150-200/month (Target: 200+)
├─ Free→Basic Conversions: 40-50/month (Target: 30%)
├─ Free→Premium Conversions: 8-12/month (Target: 25% of Basic)
└─ New MRR Added: GH₵12,000-18,000/month

ACTIVATION & ENGAGEMENT
├─ DAU (Daily Active Users): 60% of trial users
├─ WAU (Weekly Active): 75% of active schools
├─ Feature Usage %: Attendance 90%, Grades 80%, Finance 70%
└─ Time-to-First-Action: <2 hours target

RETENTION & CHURN
├─ Free Tier Retention (30-day): 40% (by design, conversion funnel)
├─ Basic Plan Retention (30-day): 80% (Target: 85%)
├─ Premium Retention (30-day): 90% (Target: 92%)
├─ Overall Churn Rate: 25% (Target: 18%)
└─ Net Revenue Retention: 105% (upsells > churn)

MONETIZATION
├─ MRR: GH₵224,000 (from 1,000 schools)
├─ ARR: GH₵2,688,000
├─ Blended ARPU: GH₵2,688
├─ Monthly Revenue Growth: 8-12% MoM (Target: 10%+)
└─ Expansion Revenue: +GH₵33,500/month (add-ons)

LTCV & Unit Economics
├─ Blended LTV: GH₵2,880
├─ Blended CAC: GH₵160
├─ LTV/CAC Ratio: 18:1
├─ Payback Period: 6.2 months
└─ CAC Efficiency: ✓ (Excellent)
```

---

## 9️⃣ FINANCIAL PROJECTIONS (Year 1)

### Scenario: Average School Growth

```
                    MONTH 1   MONTH 3   MONTH 6   MONTH 12
─────────────────────────────────────────────────────────────
Free Users            100        300       500        800
Basic Plans            10         35        60        120
Premium Plans           2          8        15         40

MRR                GH₵4,000   GH₵15,000  GH₵30,000  GH₵72,000
ARR                GH₵48,000  GH₵180,000 GH₵360,000 GH₵864,000

Churn Rate           35%        28%        22%        18%
Retention            65%        72%        78%        82%

CAC              GH₵200     GH₵150     GH₵120     GH₵100
LTV              GH₵1,920   GH₵2,400   GH₵2,880   GH₵3,600

LTV/CAC Ratio        9.6:1     16:1       24:1       36:1
Payback Period     6.1 mo     5.2 mo     4.8 mo     4.2 mo

─────────────────────────────────────────────────────────────
MRR Growth Rate:     —        37%/mo     100%/6mo   140%/12mo
```

---

## 🔟 COMPETITIVE MOAT & RETENTION

### Why Schools Don't Leave

```
SWITCHING COSTS (Low to Medium)
├─ Data Export: Easy (CSV export available)
├─ Migration Effort: 2-4 weeks to re-enter manually
├─ Vendor Lock-in: Free for 50 students (retry cost: GH₵0)
└─ Overall Lock-in Strength: MODERATE

NETWORK EFFECTS (Growing Over Time)
├─ Teacher switching: Familiarity with platform
├─ Parent adoption: Need to learn new app
├─ Integration investments: MoMo webhook setups
└─ Overall Network Strength: WEAK-TO-MODERATE

VALUE CREATION (Strong & Growing)
├─ AI insights: Can't replace easily (proprietary data)
├─ Payment automation: Process efficiency built in
├─ Daily use: Ingrained in teacher workflows
├─ Financial data: 1 year of payment history
└─ Overall Value Moat: STRONG

RETENTION DRIVERS:
├─ Free tier prevents churn (no switching risk)
├─ Basic plan users have 80% data inertia
├─ Premium plan users locked into AI workflows
├─ Seasonal renewal (school year calendar)
└─ Result: 75% blended retention (healthy SaaS baseline)
```

---

## 11️⃣ SCALING PLAYBOOK

### Year 1: Establish PMF (Product-Market Fit)
```
├─ Deploy in 5-10 pilot schools
├─ Validate:
│  ├─ Free → Basic conversion rate (Target: 30%+)
│  ├─ Churn rate (Target: <20%/month)
│  └─ NPS score from proprietors (Target: 40+)
├─ Iterate on pricing, features, UX
└─ Outcome: Proven unit economics (LTV/CAC > 3:1)
```

### Year 2: Product Expansion & Sales
```
├─ Add 5-10 schools/month → 50-100 total
├─ Expand sales channels:
│  ├─ Direct sales to 5 high-revenue schools
│  ├─ Pilot partnership with 1 school association
│  └─ Launch Facebook ads campaign
├─ Achieve 1,000 MRR benchmark
└─ Outcome: Predictable growth curve, 12% MoM
```

### Year 3: Market Expansion
```
├─ Scale to 500+ schools across Ghana
├─ Geographic expansion:
│  ├─ Open regional sales offices (Accra, Kumasi, Takoradi)
│  └─ Adapt for regional languages (Twi, Ga, Hausa)
├─ Product scaling:
│  ├─ Move to paid-only for new signups (reduce support burden)
│  ├─ Introduce Advanced Reporting add-on
│  └─ Launch SMS parent notification feature
└─ Outcome: GH₵500K+ MRR, Path to breakeven
```

---

## SUMMARY: 1-PAGE BUSINESS MODEL

```
┌────────────────────────────────────────────────────────────────┐
│                  EDUPULSE BUSINESS MODEL                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  CUSTOMER ACQUISITION: Freemium model (Free Tier entry)      │
│  └─ CAC: GH₵100-300 (blended) | LTV: GH₵2,880 (blended)     │
│                                                                │
│  MONETIZATION: 3-tier subscription ladder                     │
│  ├─ Free: 0/mo (high volume, conversion funnel)              │
│  ├─ Basic: 200/mo (50-75% of paying customers)              │
│  └─ Premium: 500/mo (25-50% of paying customers)            │
│                                                                │
│  REVENUE: Recurring subscription + add-on features            │
│  └─ Year 1 Target: GH₵864,000 (1,000 schools)               │
│  └─ Year 3 Target: GH₵6,000,000+                            │
│                                                                │
│  RETENTION: 75% blended MoM (healthy SaaS)                   │
│  ├─ Free: 40-50% (high churn by design)                     │
│  ├─ Basic: 80% (medium-term loyalty)                        │
│  └─ Premium: 90% (high AI feature lock-in)                  │
│                                                                │
│  UNIT ECONOMICS: 18:1 LTV/CAC ratio (excellent)             │
│  ├─ Payback: 6 months (fast)                                │
│  └─ Scaling: Improves with volume                           │
│                                                                │
│  MARKET: 20,000+ schools TAM in Ghana                        │
│  ├─ Year 1: 1% penetration = 200 schools                   │
│  ├─ Year 3: 2-3% penetration = 400-600 schools             │
│  └─ Year 5: 5% penetration = 1,000 schools                 │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## KEY TAKEAWAYS FOR PITCH

✅ **Strong Unit Economics**: 18:1 LTV/CAC ratio means every customer pays for acquisition 18x over

✅ **Freemium Funnel Works**: Free tier drives top-of-funnel, pricing ladder captures value

✅ **Viral Coefficient**: 0.3-0.4 coefficient means exponential growth potential at scale

✅ **Recurring Revenue**: 75% retention = predictable, compounding revenue stream

✅ **AI Moat**: Premium features not easily replicated by competitors

✅ **Path to Profitability**: 500-1,000 paying customers = positive unit economics at scale

✅ **TAM**: GH₵69.6M potential ARR across 20,000 Ghana schools

✅ **Defensibility**: Tech + Network + Data = hard to replicate competitive advantage
