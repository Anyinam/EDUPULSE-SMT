# Paystack Fee-Route DVA Guide

## Overview
EduPulse currently supports Paystack dedicated virtual accounts as an optional convenience layer for payment-type tracking.

- School registers one real bank account with Paystack.
- Current implementation can create one virtual route per fee type (Tuition, Feeding, Uniform, Transport, Other) if the school chooses to use them.
- Parents can still pay using the structured reference without depending on those routes.
- Paystack route metadata can help identify the payment type automatically when such routes are enabled.
- Funds settle to the school’s single real bank account.

Important product note:
- This is the current implementation, not the mandatory long-term architecture for every school.
- The recommended medium-term direction is a stable student or family payment identity with structured references across web, bank app, USSD, and manual fallback rails.
- Shortcode and low-data payment paths should remain supported because they fit the Ghanaian market.

## Architecture

### How It Works Today
1. School saves one settlement bank account in EduPulse.
2. EduPulse issues structured references against a stable learner or family payment identity.
3. Proprietor may optionally create fee-route DVAs by payment type.
4. Parent pays using the structured reference, with or without the optional route.
5. Webhook confirms payment and updates student balance.
6. Settlement goes to the school’s single real account.

### Payment Flow
```
Parent pays Tuition GH₵500
    ↓
Uses reference S001-TUITION-T1
    ↓
May optionally also use a Tuition virtual route/shortcode
    ↓
EduPulse webhook confirms and updates records
    ↓
Paystack settles to school's one real bank account
```

### Virtual vs Real Accounts

**Real Settlement Account (One):**
- Fidelity Bank: `1234567890`
- Registered once
- Receives all settlements

**Virtual Payment Routes (Current Optional Pattern):**
- Tuition route
- Feeding route
- Uniform route
- Transport route

## Recommended Direction

Near-term recommended model:
- one stable student or family payment identity
- structured references for fee categorization
- one reconciliation engine across bank app, shortcode / USSD, and manual fallback
- optional continued use of fee-route DVAs only where the school has a clear operational reason

Why:
- fewer payment rails for parents to memorize
- less account sprawl per school
- better fit for mixed online and offline parent behavior
- still compatible with current reference parsing already used elsewhere in EduPulse

## What Should Stay Future-Only

Do not treat these as immediate implementation requirements:
- one DVA per student plus one DVA per fee type on top of that
- autonomous collections bots contacting parents without school approval
- removing shortcode or manual fallback payment paths
- pricing purely on recovered fees before baseline data exists

## Setup Instructions

### 1) Configure School Bank Account
Go to Settings and save:
- Bank name
- Account number
- Account name

This is the only account that receives settlement.

### 2) Fetch Bank Codes
Endpoint: `GET /api/proprietor/paystack/banks`

### 3) Optionally Create Fee-Route DVA per Payment Type
Endpoint: `POST /api/proprietor/paystack/subaccounts/create`

Request:
```json
{
  "payment_type": "Tuition",
  "bank_code": "GH190101",
  "percentage_charge": 2.5
}
```

Notes:
- `account_number` is not sent here.
- The endpoint uses the school bank account already saved in settings.

Sample response:
```json
{
  "message": "Dedicated virtual account created for Tuition. Parents can pay to this virtual account.",
  "subaccount": {
    "payment_type": "Tuition",
    "subaccount_code": "ACCT_xyz123abc",
    "virtual_bank_account": "9876000001",
    "virtual_bank_name": "Wema Bank (Paystack)",
    "momo_shortcode": "*920*4567#"
  },
  "settlement_info": {
    "settles_to": "1234567890",
    "bank_name": "Fidelity Bank Ghana",
    "account_name": "ABC SCHOOL LIMITED"
  }
}
```

### 4) List Configured Subaccounts
Endpoint: `GET /api/proprietor/paystack/subaccounts`

### 5) Share Parent Instructions
The recommended instruction set is:
- stable learner payment identity
- structured reference per fee purpose
- amount due
- school-office fallback guidance

Only add the virtual bank account or shortcode when the school has explicitly enabled that optional route.

Parents should be able to pay successfully even without memorizing multiple route accounts.

### 6) Optional Payment Link Flow
Endpoint: `POST /api/finance/paystack/initialize-payment`

## Webhook

Configure Paystack webhook URL:
`https://yourdomain.com/api/finance/webhook/paystack`

Implemented behavior:
- Signature verification
- Idempotency
- Student mapping
- Payment-type handling
- Ledger entry
- Subaccount metadata tracking

## Settlement Notes

- Virtual routes are an optional convenience layer for payment identification.
- Settlement destination is still the one real school bank account.
- Timing depends on Paystack settlement schedule.

## Architecture Decision Summary

Use the current fee-route DVA pattern when:
- the school wants clear fee-type separation now
- the operations team can manage multiple payment routes
- Paystack economics and bank support are acceptable

Prefer a unified payment identity model over time when:
- parent usability matters more than fee-type route separation
- schools need simpler instructions for mixed-literacy households
- USSD, bank app, and manual flows must all converge cleanly

## Troubleshooting

### "School bank account not configured"
Save bank details in school settings first.

### Payment type not detected
Ensure parent used the correct virtual route for that fee type.

### Virtual route missing
Confirm subaccount is active and generated by Paystack.

### Webhook not updating records
Check webhook URL, secret key, and backend logs.

---

**Last Updated:** April 21, 2026  
**Version:** 1.2 (Current Fee-Route DVA + Future Direction)
