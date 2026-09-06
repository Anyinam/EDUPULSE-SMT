# Bank Transfer Integration Guide

## Current Recommendation

EduPulse SMT supports 2 different transfer-style payment models:

1. Ordinary bank webhook integration
2. Paystack tracked transfer accounts built on dedicated virtual accounts

The second option is now the preferred automatic-tracking path for parent fee transfers.

## 1. Ordinary Bank Webhook Integration

Route: `POST /api/finance/webhook/bank`

Use this only when a bank or aggregator can reliably send EduPulse a signed callback that contains the learner reference and external transaction id.

This path can still auto-record payments, but it depends on the upstream provider returning enough information for matching.

Expected inputs:
- transfer amount
- structured learner reference
- transaction id
- success status

## 2. Paystack Tracked Transfer Account

Route to create the account:
`POST /api/students/<student_id>/payment-codes/<reference_code>/virtual-account`

This creates or reuses a Paystack dedicated virtual account for one learner fee reference.

Operational workflow:
- schools do not need to create every tracked transfer account one by one before sharing fees
- EduPulse can create or reuse the tracked transfer account while preparing the student's printed payment instructions
- batch printing can prepare instruction sheets for a filtered set of students and attach tracked transfer accounts where the school is configured for them
- the separate online checkout link remains optional and is not the default school workflow for routine fee collection

Why this is the preferred rail:
- Paystack automatically creates a customer-linked transaction when the transfer lands
- EduPulse receives `charge.success` from Paystack
- EduPulse matches the payment to the stored `PaymentCollectionIntent`
- the school fee and convenience fee stay separated correctly

## Settlement Behavior For Tracked Transfer Accounts

Each tracked transfer account now uses split settlement on the Paystack dedicated virtual account:

- the school’s Paystack subaccount receives the fixed school fee amount
- the remainder settles into EduPulse’s main Paystack account
- Paystack processing fees are currently borne by the main account in this setup

This requires the school to have verified bank details saved in Settings so EduPulse can create the school subaccount first.

## Example

If a fee reference has:
- base fee: `GH₵100`
- estimated Paystack fee: `GH₵3`
- EduPulse platform fee: `GH₵3`

Then:
- parent transfers `GH₵106`
- school settlement target is `GH₵100`
- EduPulse settlement remainder is `GH₵6`
- student balance is reduced by `GH₵100` only

## Security

Ordinary bank webhook path:
- requires `X-Bank-Signature` with HMAC SHA256 using `BANK_WEBHOOK_SECRET`

Paystack tracked transfer path:
- requires Paystack HMAC SHA512 verification using `PAYSTACK_SECRET_KEY`
- relies on `charge.success` webhook events

## Operational Limits

- Paystack dedicated virtual accounts are currently available for Ghana and Nigeria go-live businesses
- Paystack defaults to about 1,000 dedicated accounts per business until reviewed upward
- EduPulse avoids waste by creating tracked transfer accounts only when instructions are printed or a staff user explicitly requests one, instead of preallocating them for every fee code

## Practical Rule

If you want dependable automatic tracking for parent transfer payments, use the EduPulse-generated tracked transfer account that appears on the printed instruction sheet. If parents pay directly into the ordinary school account, automatic tracking is only as good as the webhook or notice data the provider returns.

## Related References

- `docs/finance/PAYMENT_CATEGORIZATION.md`
- `docs/finance/PAYMENT_REFERENCE_FORMAT.md`
- `backend/routes.py`
