# Payment Categorization Guide

## Current Product Logic

EduPulse now uses a hybrid collection model for school fees:

1. manual office entry still exists for cash and externally confirmed payments
2. ordinary bank webhook imports still work where a provider can reliably send back learner references
3. Paystack tracked transfer accounts are now the preferred automatic-tracking rail for tuition and other fee routes
4. tuition can be configured either as one live outstanding balance or as a saved installment schedule

Categorization still happens inside EduPulse. The provider route improves matching, but EduPulse still decides which learner and fee purpose the payment belongs to.

## Active Payment Paths

### 1. Manual recorded payment

Route: `POST /api/finance/receive-payment`

Use this when staff are recording:

- a confirmed cash payment
- an offline transfer that was verified outside the automated rails
- a structured reference that the staff member is entering manually

Stored fields can include:

- `student_id`
- `amount`
- `payment_type`
- `payment_category`
- `reference_code`
- external transaction metadata when available

### 2. Imported parent payment notice

Route: `POST /api/finance/import-parent-payment`

Use this when the school pastes an SMS-like payment notice or other externally received transfer details and EduPulse tries to extract a learner reference.

### 3. Ordinary bank webhook tracking

Route: `POST /api/finance/webhook/bank`

This path still works when the upstream bank or aggregator provides a signed callback with:

- a learner reference
- a transaction id
- a success status

It is not the most dependable automatic path unless the provider reliably returns the right reference values.

### 4. Paystack tracked transfer account

Primary route creation endpoint:

`POST /api/students/<student_id>/payment-codes/<reference_code>/virtual-account`

This is now the preferred automatic transfer-tracking path.

EduPulse creates or reuses a `PaymentCollectionIntent`, provisions a Paystack dedicated virtual account for that learner fee reference, and waits for `charge.success` on the Paystack webhook.

When the webhook lands:

- EduPulse matches the incoming transfer back to the stored route
- only the base school fee reduces the learner balance
- convenience-fee and split metadata remain preserved for settlement and audit

### 5. Reconciliation fallback for successful-but-untracked transfers

Fallback route:

`POST /api/finance/paystack/recover-reference`

Use this only when:

- the transfer already succeeded in Paystack
- the automatic route match did not produce the EduPulse payment record
- staff need to recover the payment from the Paystack reference after a temporary system issue

This is not the normal collection path. It is a support recovery tool.

## Fee Categorization Rules

### Tuition without installments

If a school is not using tuition installments, EduPulse still builds one tuition route from the learner's live outstanding tuition balance.

That means the tuition tracked-transfer amount is based on the learner's current outstanding debt, not just the school-wide tuition default.

### Tuition with installments

If a school enables the installment plan in Settings:

- each installment gets its own reference
- each installment gets its own tracked transfer route
- EduPulse allocates confirmed tuition payments across the schedule in order
- small overpayments carry forward into the next installment as credit
- each installment exposes status metadata in the payment-code payload

Current installment statuses:

- `upcoming`
- `open`
- `partial`
- `paid`
- `overdue`

### Feeding

Feeding can now be configured by plan instead of one generic amount.

Current structured feeding references:

- `STUDENT-FEED-DAY`
- `STUDENT-FEED-WEK`
- `STUDENT-FEED-MON`

### Legacy compact fee codes

Uniform, transport, classic tuition, and many older fee families may still appear as compact references from `backend/utils.py`.

Those codes remain valid in the current system.

## Convenience Fee And Settlement Logic

For tracked transfer accounts, EduPulse stores:

- `base_amount`
- `convenience_fee_amount`
- `estimated_provider_fee_amount`
- `platform_fee_amount`
- `total_amount`

New tuition routes use the versioned `gross_up_margin_v1` fee model. The default estimated Paystack rate is 1.95% of the complete parent transfer; EduPulse's selected margin is 1% of the school tuition amount. The total is rounded upward to the next pesewa so the school amount and target margin are covered.

For a GH₵25 installment:

- school tuition: GH₵25.00
- target EduPulse margin: GH₵0.25
- estimated provider fee on the gross transfer: GH₵0.50
- cent-rounding adjustment: GH₵0.01
- parent transfer total: GH₵25.76

The parent's total is calculated as `(school fee + target margin + provider flat fee) / (1 - provider percentage)`, rounded upward. The service fee is separate from tuition, and the displayed exact total applies only to the dedicated account for that learner and installment.

When the payment record is written, EduPulse separates the tracked-transfer payment into distinct accounting values:

- gross amount paid
- convenience portion collected for the route
- actual Paystack/provider fee when Paystack returns it
- applied school-fee amount

For the new model, an exact GH₵25.76 payment to an account-bearer flat split credits the full GH₵25.00 school tuition. The provider fee is paid from the platform's GH₵0.76 gross remainder, not deducted again from the learner's school credit. At an actual GH₵0.50 fee, platform net is GH₵0.26: the GH₵0.25 target margin plus GH₵0.01 rounding surplus. Missing provider fees are labeled as estimates rather than represented as known actual fees.

Underpayments, overpayments, invalid split settings, and provider fees that would consume the target margin are retained as Pending for settlement review. Gross funds remain recorded, applied school credit is zero, balances and confirmed ledgers are unchanged, and normal manual-payment approval cannot bypass the hold. Replayed callbacks do not duplicate the record.

Historical routes without this fee-model version retain their original calculations and recorded amounts. Do not reprice previously paid accounts or rewrite historical receipts.

Tracked transfer accounts use Paystack split settlement so that:

- the school's Paystack subaccount receives the fixed school-fee portion
- the remainder settles into EduPulse's main Paystack account

## School Setup Requirement

Tracked transfer accounts become available only after the school saves verified bank details and EduPulse successfully creates the school's Paystack subaccount.

Without that subaccount:

- the tracked transfer route is not ready
- printed instructions can still show the fee reference, but the dedicated account path will not be attachable

## Main Data Structures

### `Payment.payment_category`

Can include:

- `reference_code`
- `fee_type`
- `frequency`
- `installment_number`
- `installment_label`
- `installment_status`
- `installment_start_date`
- `installment_due_date`
- `collection_channel`
- `payment_collection_intent_id`
- `gross_amount_paid`
- `charged_total_amount`
- `applied_school_fee_amount`
- `convenience_fee_amount`
- `collected_convenience_fee_amount`
- `actual_provider_fee_amount`
- `platform_fee_amount`
- `estimated_provider_fee_amount`
- `settlement_mode`
- `split_code`

### `PaymentCollectionIntent`

Stores the provider route itself, including:

- dedicated account number
- Paystack customer code
- school subaccount code
- split code
- base amount
- convenience fee
- total amount
- expiry and payment status

## Operational Rule

If dependable automatic transfer tracking matters, use the EduPulse-generated tracked transfer account for that fee route. If parents send money directly into the ordinary school bank account, automatic identification is only as good as the narration or callback data the provider returns.

## Related References

- `docs/finance/PAYMENT_REFERENCE_FORMAT.md`
- `docs/finance/PAYMENT_REFERENCE_CODE_SYSTEM.md`
- `docs/finance/BANK_TRANSFER_INTEGRATION.md`
- `backend/payment_collection_service.py`
- `backend/payment_instruction_service.py`
