# EduPulse SMT Subscription Billing Guide

**Date:** August 2026  
**Version:** Model A (Hybrid Base + Overage, Trial + Proration Update)

---

## Table of Contents
1. [Overview](#overview)
2. [Pricing Model Explained](#pricing-model-explained)
3. [Plan Comparison](#plan-comparison)
4. [How Billing Works](#how-billing-works)
5. [Pro-Ration System](#pro-ration-system)
6. [Examples & Calculations](#examples--calculations)
7. [FAQ](#faq)

---

## Overview

EduPulse SMT uses a **hybrid subscription model** designed to align with the academic calendar in Ghana:

- **Billing Cycle:** Per term (3 terms per academic year)
- **Payment Trigger:** At the start of each term when activated
- **Mid-Term Admissions:** Pro-rated charges for students added during active term
- **Currency:** Ghana Cedis (₵ or GH₵)

**Why per-term billing?**
Schools have distinct cash flow periods tied to term beginnings. Billing by term (rather than monthly) aligns with when schools collect fees from parents.

---

## Pricing Model Explained

### Model A: Base Fee + Included Students + Overage

Each paid plan has **three components**:

1. **Base Platform Fee** - Fixed cost per term for access to the platform
2. **Included Students** - Number of students covered by the base fee
3. **Per-Student Overage Rate** - Cost for each additional student above the included threshold

**Formula:**
```
Total Cost = Base Fee + (Students Over Threshold × Overage Rate)

Where:
  Students Over Threshold = max(0, Total Students - Included Students)
```

---

## Plan Comparison

| Feature | Free Tier | Basic | Premium |
|---------|-----------|-------|---------|
| **Base Fee (per term)** | ₵0 | ₵360 | ₵750 |
| **Included Students** | 0 | 30 | 30 |
| **Overage Rate (per student/term)** | N/A | ₵12 | ₵22 |
| **Annual Cost (3 terms)** | ₵0 | ₵1,080 base + overage | ₵2,250 base + overage |
| | | | |
| **Max Students** | 50 | 200 | Unlimited (∞) |
| **Max Classes** | 1 | 5 | Unlimited (∞) |
| **Max Staff** | 3 | 15 | Unlimited (∞) |
| | | | |
| **Grade Entry & Editing** | ❌ | ✅ | ✅ |
| **Payment Tracking** | ❌ | ✅ | ✅ |
| **Lesson Notes** | ❌ | ✅ | ✅ |
| **Bulk Operations** | ❌ | ✅ | ✅ |
| **AI Analysis** | ❌ | Basic | Full |
| **Advanced Analytics** | ❌ | ❌ | ✅ |
| **Custom Templates** | ❌ | ❌ | ✅ |
| **Priority Support** | ❌ | ❌ | ✅ |

---

## How Billing Works

### Premium Trial Window

- Premium trial access is a 30-day window from activation.
- Trial access does not apply a separate promotional discount. When a school converts, the paid plan uses the normal term price model.
- When a trial school converts to a paid term plan before the current term ends, EduPulse prorates the first paid charge by the remaining days in that term.
- EduPulse uses the school's active academic term when it covers the current date.
- Schools can manage their own term start/end dates in Academic Term Management and can import the published GES calendar for a selected academic year.
- If the school's term calendar is missing, EduPulse falls back to the centrally maintained national basic-school term calendar.

### Checkout And Entitlement Guardrails

- Paid upgrades must complete through Paystack before EduPulse grants the higher plan entitlement.
- Direct subscription update routes are reserved for non-paid transitions such as scheduled downgrades or administrative cleanup.
- Billing views now treat `base_plan` and `effective_plan` separately so active trials do not hide the school's underlying paid or free subscription state.

### 1. Initial Subscription (Start of Term)

When a school subscribes at the **beginning of a term**:

1. School selects a plan (Free/Basic/Premium)
2. System counts current enrolled students
3. Calculates cost based on formula above
4. School pays via Paystack (mobile money, card, or bank transfer)
5. Subscription activated for the term

**Invoice Breakdown Example (Basic, 50 students):**
```
Base Platform Fee:           ₵360.00
Included Students:           30 (covered by base)
Billable Students:           20 (50 - 30)
Rate per Extra Student:      ₵12.00
Student Overage Cost:        ₵240.00 (20 × ₵12)
────────────────────────────────────
Total Term Cost:             ₵600.00
```

### 2. Mid-Term Admissions (Pro-Rated)

When students are admitted **during an active term**:

1. System calculates remaining days in the term
2. Applies pro-ration factor: `remaining_days ÷ total_term_days`
3. Only charges for students **over the included threshold**
4. Sends invoice email to proprietor
5. Logs charge in ledger

**Example:** School on Basic plan (30 included) admits 3 students with 40 days remaining in a 101-day term:

```
Pro-ration Factor: 40 ÷ 101 = 39.6%
Students Over Threshold: 3
Full Term Rate: ₵12/student
Pro-rated Charge: 3 × ₵12 × 0.396 = ₵14.26
```

### 3. Term Renewal

At the start of each new term:

1. System detects term activation
2. Counts current enrolled students
3. Calculates full-term cost
4. Sends billing email to proprietor
5. School pays via Paystack link in email
6. Subscription continues

**If payment is not made:**
- Grace period depends on plan
- After grace period, account may be suspended
- No student data is lost - reactivation restores access
- The system should not silently grant a higher paid plan before successful checkout verification

### 3a. Term Close And Access Policy

Operationally, term close should be treated as an archive event, not a data cutoff.

- Closing one term does **not** delete or hide that term's records.
- Activating the next term is the renewal trigger for paid plans.
- If billing becomes overdue, schools move through grace and overdue handling before suspension.
- If an account reaches suspension, EduPulse should still preserve limited read-only access to historical records needed for recovery.

**Suspended-school read-only access currently preserved for:**
- Academic term history
- Archived student report history and terminal report reads
- Billing timeline and subscription statement access
- Finance transaction history
- Finance audit ledger, audit summary, and audit event export

**Suspended-school actions still blocked:**
- New operational writes
- New term activation workflows outside billing recovery
- Protected create, update, and delete actions across the tenant app

Recommended operating rule:

1. Keep completed terms visible as historical records.
2. Use term activation as the moment to initiate renewal billing.
3. Let suspended schools review past terms and billing evidence so they can reconcile and pay.
4. Restore full access immediately after successful payment or reactivation.

---

## Pro-Ration System

### When Pro-Ration Applies

✅ **Pro-rated:**
- Mid-term student admissions (single or bulk CSV upload)
- Only charges for students **over included threshold**

❌ **NOT pro-rated:**
- Initial subscription at term start (full term charge)
- Term renewals (full term charge)
- Base platform fee (always charged in full)

### Pro-Ration Formula

```python
# Calculate remaining term percentage
days_remaining = (term_end_date - today) + 1
days_total = (term_end_date - term_start_date) + 1
pro_ration_factor = days_remaining / days_total

# Calculate overage students
overage_students = max(0, new_total_students - included_students)

# Calculate pro-rated charge
pro_rated_charge = overage_students × per_student_rate × pro_ration_factor
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| **No active term** | No charge (admission allowed) |
| **Free Tier school** | No charge (always free) |
| **Students within included limit** | No charge (covered by base) |
| **Last week of term** | Small charge based on the actual term length (e.g., 7/101 = ~7%) |
| **Term just started** | Near-full charge based on the actual term length |

---

## Examples & Calculations

### Example 1: Small School (20 Students) - Basic Plan

**Scenario:** School has 20 students, subscribes to Basic plan at term start

```
Base Fee:                    ₵360.00
Included:                    30 students
Current Students:            20
Students Over Threshold:     0 (20 < 30)
Overage Charge:              ₵0.00
────────────────────────────────────
Total per Term:              ₵360.00
Total per Year (3 terms):    ₵1,080.00
```

**Key Point:** Small schools pay only the base fee if under the included limit.

---

### Example 2: Medium School (80 Students) - Basic Plan

**Scenario:** School has 80 students, subscribes to Basic plan at term start

```
Base Fee:                    ₵360.00
Included:                    30 students
Current Students:            80
Students Over Threshold:     50 (80 - 30)
Overage Rate:                ₵12/student
Overage Charge:              ₵600.00 (50 × ₵12)
────────────────────────────────────
Total per Term:              ₵960.00
Total per Year (3 terms):    ₵2,880.00
```

**Average per student:** ₵960 ÷ 80 = ₵12/student/term

---

### Example 3: Large School (150 Students) - Premium Plan

**Scenario:** School has 150 students, subscribes to Premium plan at term start

```
Base Fee:                    ₵750.00
Included:                    30 students
Current Students:            150
Students Over Threshold:     120 (150 - 30)
Overage Rate:                ₵22/student
Overage Charge:              ₵2,640.00 (120 × ₵22)
────────────────────────────────────
Total per Term:              ₵3,390.00
Total per Year (3 terms):    ₵10,170.00
```

**Average per student:** ₵3,390 ÷ 150 = ₵22.60/student/term

---

### Example 4: Mid-Term Admission - Basic Plan

**Scenario:** School on Basic plan (currently 30 students) admits 10 more students mid-term

**Current State:**
- Plan: Basic (₵360 base, 30 included, ₵12/extra)
- Already paid for term: ₵360 + (0 × ₵12) = ₵360
- Days remaining: 35 out of 120

**New Admission:**
```
New Students:                10
New Total:                   40 students
New Overage:                 10 (40 - 30)
Previously Charged For:      0 students
Additional Overage:          10 students

Full-Term Rate:              ₵12/student
Days Remaining:              35 of 120 = 29.2%
Pro-rated Rate:              ₵12 × 0.292 = ₵3.50/student

Pro-rated Charge:            10 × ₵3.50 = ₵35.00
────────────────────────────────────
Additional Mid-Term Charge:  ₵35.00
```

**Next term (full):** System will charge for all 40 students at full rate = ₵360 + (10 × ₵12) = ₵480

---

### Example 5: Scaling Comparison (100 Students)

Let's compare the cost for a school with **100 students** across plans:

| Plan | Base Fee | Included | Overage | Overage Charge | **Total/Term** | **Total/Year** |
|------|----------|----------|---------|----------------|----------------|----------------|
| Free Tier | ₵0 | 0 | N/A | N/A | **₵0** | **₵0** |
| Basic | ₵360 | 30 | 70 × ₵12 | ₵840 | **₵1,200** | **₵3,600** |
| Premium | ₵750 | 30 | 70 × ₵22 | ₵1,540 | **₵2,290** | **₵6,870** |

**Free Tier limitation:** Max 50 students, 1 class, read-only features

---

## FAQ

### Q1: What happens if we have zero students when subscribing?

**A:** You pay only the base platform fee:
- Basic: ₵360/term
- Premium: ₵750/term

When you later admit students, mid-term pro-ration applies.

---

### Q2: Can we switch plans mid-term?

**A:** Yes! Upgrades are pro-rated based on remaining days. Downgrades take effect at the next term.

Example: Upgrade from Basic to Premium with 60 days left:
```
Premium Term Cost: ₵750 base + overage
Pro-ration: 60/120 = 50.0%
You pay: 50.0% of (Premium Cost - Already Paid)
```

---

### Q3: What if a student leaves/graduates mid-term?

**A:** No refunds for mid-term departures, but future terms will reflect the reduced count automatically.

---

### Q4: How do bulk CSV uploads affect billing?

**A:** Bulk uploads are treated as a single mid-term admission event:
- All students in CSV counted together
- Single pro-rated charge calculated
- One invoice email sent

Example: Upload 50 students via CSV with 45 days remaining = pro-rated charge for all 50 at once.

---

### Q5: Do class/staff limits count toward billing?

**A:** No. Only student count affects billing. Class and staff limits are **feature restrictions** based on your plan, not billing factors.

---

### Q6: Can we pay annually upfront for a discount?

**A:** Currently, the system bills per term. Annual payment option (3 terms upfront) may be added in future with a discount. Contact support for custom arrangements.

---

### Q7: What payment methods are accepted?

**A:** Via **Paystack** integration:
- Mobile Money (MTN, Vodafone, AirtelTigo)
- Bank cards (Visa, Mastercard, Verve)
- Bank transfer/direct debit
- USSD codes

All payments processed securely through Paystack Ghana.

---

### Q8: When exactly is billing triggered?

**Billing Events:**

1. **Term Activation:** When proprietor/headmaster activates a new term
2. **Plan Upgrade:** Immediately upon confirmation
3. **Mid-Term Admission:** When student(s) admitted/uploaded during active term

---

### Q9: Why base fee + overage instead of simple per-student pricing?

**Benefits:**

1. **Fairness:** Small schools pay less total (not penalized for fewer students)
2. **Predictability:** Base cost is fixed; overage is transparent
3. **Scalability:** Large schools get better per-student rate due to base fee amortization
4. **Flexibility:** Can start with 0 students and grow at low incremental cost

**Old Model (simple):** 100 students × ₵12 = ₵1,200/term  
**New Model A (hybrid):** ₵360 base + (70 × ₵12) = ₵1,200/term

---

### Q10: Where can I see my billing history?

**In the Dashboard:**
- Go to **Subscription** menu
- View current plan, enrollment, next billing date
- See term-by-term cost breakdown

**In the Database:**
- `LedgerEntry` table logs all subscription charges
- `PaymentTransaction` table records all Paystack payments

---

## Quick Reference

### Billing Formulas

```python
# Full Term Cost
term_cost = base_fee + (max(0, students - included) × overage_rate)

# Annual Cost
annual_cost = term_cost × 3

# Mid-Term Pro-ration
days_remaining = term_end - today
pro_ration_factor = days_remaining / term_total_days
pro_rated_charge = overage_students × overage_rate × pro_ration_factor
```

### Current Pricing (Model A)

| Plan | Base/Term | Included | Overage Rate | Annual Base |
|------|-----------|----------|--------------|-------------|
| **Free Tier** | ₵0 | 0 | N/A | ₵0 |
| **Basic** | ₵360 | 30 | ₵12/student | ₵1,080 |
| **Premium** | ₵750 | 30 | ₵22/student | ₵2,250 |

### Key Files in Codebase

- **Backend Logic:** `backend/subscription_features.py`
- **API Routes:** `backend/routes.py` (search: `calculate_prorated_admission_charge`)
- **Email Templates:** `backend/email_templates/term_billing_notification.txt`
- **Frontend UI:** `frontend/react/src/features/SubscriptionManager.jsx`
- **Plan Selection:** `frontend/react/src/features/SubscriptionPlans.jsx`

---

## Support

For billing questions or issues:
- **Email:** danielasareanyinam2020@gmail.com
- **Phone:** [Your support number]
- **Dashboard:** Use the chat widget or submit a ticket

---

**Document Version:** 1.0  
**Last Updated:** March 5, 2026  
**Author:** Daniel Asare Anyinam
