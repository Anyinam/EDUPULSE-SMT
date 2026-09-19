# Bank Transfer Integration Guide

## Current Recommendation

EduPulse supports two transfer-style payment models:

1. ordinary bank webhook integration
2. Paystack tracked transfer accounts built on dedicated virtual accounts

The Paystack tracked transfer path is now the preferred automatic-tracking rail for school-fee collection.

## 1. Ordinary Bank Webhook Integration

Route: `POST /api/finance/webhook/bank`

Use this only when a bank or aggregator can reliably send EduPulse a signed callback containing:

- a learner reference
- a transaction id
- a success status
- a provider signature validated with `BANK_WEBHOOK_SECRET`

This path can still auto-record payments, but it depends on the upstream provider returning enough data for matching.

## 2. Paystack Tracked Transfer Accounts

Route to create or reuse the account:

`POST /api/students/<student_id>/payment-codes/<reference_code>/virtual-account`

This creates or reuses a Paystack dedicated virtual account for one learner fee reference.

Operational workflow:

- schools do not need to pre-create every virtual account
- EduPulse can create or reuse the tracked transfer account while preparing the learner's payment instructions
- batch-printing can prepare instruction sheets for filtered learners and attach tracked transfer accounts where the school is configured for them
- the visible reference remains a support hint even when route matching should happen automatically

## Why This Is The Preferred Rail

- Paystack creates a customer-linked transfer event when the money lands
- EduPulse receives `charge.success` from `POST /api/paystack/webhook`
- EduPulse matches the transfer back to the stored `PaymentCollectionIntent`
- nested or alternate receiver-account payload shapes are normalized before matching
- the school fee and convenience fee stay separated correctly

## Settlement Behavior

Each tracked transfer account uses split settlement on the Paystack dedicated virtual account:

- the school's Paystack subaccount receives the fixed school-fee amount
- the remainder settles into EduPulse's main Paystack account
- Paystack processing fees are currently borne by the main account in this setup

For learner-balance accounting, EduPulse now records the school-fee credit as the net school portion actually attributable to the payment route:

- start from the gross amount paid
- subtract the convenience-fee slice carried by that route
- subtract the actual Paystack/provider fee when Paystack returns it
- apply the remaining net school amount to tuition, capped by the route base amount

This requires the school to have verified bank details saved in Settings so EduPulse can create the school subaccount first.

## Tuition Installment Support

Tracked transfer accounts now support installment-based tuition collection.

When a school enables installments:

- each installment gets its own exact reference
- each installment gets its own exact payable amount
- each installment can have its own start date and deadline
- late installments remain collectible
- tiny overpayments can carry forward as credit into the next installment

## Example

If a tuition installment route has:

- base fee: `GH₵500`
- convenience fee: `GH₵9.75`

Then:

- parent transfers `GH₵509.75`
- school settlement target is `GH₵500`
- EduPulse settlement remainder is `GH₵9.75`
- if Paystack reports no additional provider fee, the learner balance is reduced by `GH₵500`
- if Paystack reports an actual provider fee, the learner balance is reduced by the remaining net school portion after that fee is deducted

Example with provider fee:

- parent transfers `GH₵509.75`
- convenience fee remains `GH₵9.75`
- Paystack fee returned on the transaction is `GH₵0.41`
- learner tuition credit becomes `GH₵499.59`

## Reconciliation Fallback

Fallback route:

`POST /api/finance/paystack/recover-reference`

Use this when a Paystack transfer succeeded but the automatic EduPulse record did not appear. This recovery path is meant for temporary glitches, not as the normal workflow.

## Security

Ordinary bank webhook path:

- requires `X-Bank-Signature` with HMAC SHA256 using `BANK_WEBHOOK_SECRET`

Paystack tracked transfer path:

- requires Paystack HMAC SHA512 verification using `PAYSTACK_SECRET_KEY`
- relies on `charge.success` webhook events

## Operational Limits

- Paystack dedicated virtual accounts are currently available only in supported Paystack countries such as Ghana and Nigeria
- Paystack defaults to a limited number of dedicated accounts per business until your account is reviewed upward
- EduPulse avoids waste by creating tracked transfer accounts only when instructions are printed or a staff user explicitly requests one

## Practical Rule

If you want dependable automatic tracking for parent transfer payments, use the EduPulse-generated tracked transfer account shown on the learner's instruction sheet. If parents pay directly into the ordinary school account, automatic tracking is only as good as the webhook or notice data the provider returns.

## Related References

- `docs/finance/PAYMENT_CATEGORIZATION.md`
- `docs/finance/PAYMENT_REFERENCE_FORMAT.md`
- `docs/finance/PAYMENT_REFERENCE_CODE_SYSTEM.md`
- `backend/payment_collection_service.py`
