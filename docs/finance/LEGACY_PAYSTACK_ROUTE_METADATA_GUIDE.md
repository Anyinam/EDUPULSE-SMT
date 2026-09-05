# Legacy Paystack Route Metadata Guide

## Status

This guide is retained for historical reference only.

As of the current EduPulse SMT payment model:

- the old proprietor-managed fee-route setup is retired;
- historical route-management payloads can still exist in older audit trails; and
- the active tracked-transfer setup is now the intent-based Paystack dedicated virtual account flow created from the student payment tracker.

## What Is Still True

- Older ledger records, webhook payloads, and audit logs may still contain legacy route metadata such as archived route identifiers, virtual account numbers, bank names, or provider markers.
- Historical route metadata may still matter when interpreting older payments or migration-era records.
- Settlement to the school's approved bank destination remains part of the payment trail.

## What Is No Longer Current

- school users do not manually manage old fee-route records
- documentation that says dedicated virtual accounts are retired is outdated
- generic reference-only transfers to an ordinary school account should not be described as guaranteed auto-tracked unless the provider actually returns a usable webhook

## Current Recommended Payment Model

Use the following active pattern instead:

1. Configure the school's approved bank details and fee settings.
2. Let EduPulse create the school's Paystack subaccount from those verified bank details.
3. Issue structured references per learner and fee purpose.
4. For reliable auto-tracked transfers, generate a tracked transfer account per learner fee reference.
5. Let parents pay the displayed total into that tracked account.
6. Preserve cash-at-school-office and manual confirmation as fallback paths.

## Migration Note

If you are reviewing older documentation, screenshots, or payload examples that mention retired proprietor route-management endpoints, treat those as legacy behavior. The current DVA path is still active, but it is created on demand from the student payment tracker and stored as a `PaymentCollectionIntent`.

## Related Current References

- `docs/finance/PAYMENT_REFERENCE_FORMAT.md`
- `docs/finance/PAYMENT_CATEGORIZATION.md`
- `docs/finance/BANK_TRANSFER_INTEGRATION.md`
- `backend/routes.py`

---

**Last Updated:** September 5, 2026  
**Version:** 2.3 (Legacy Reference Clarified)