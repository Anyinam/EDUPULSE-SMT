# Legacy Paystack Route Metadata Guide

## Status

This guide is retained for historical reference only.

As of the current EduPulse SMT payment model:

- new Paystack fee-route or dedicated-virtual-account setup is retired;
- the relevant proprietor route-management endpoints have been removed from the active API;
- the supported parent-payment flow is now a stable learner or family payment identity plus structured references; and
- parents should use the school's approved payment channel with the matching structured reference.

## What Is Still True

- Older ledger records, webhook payloads, and audit logs may still contain legacy route metadata such as archived route identifiers, virtual account numbers, bank names, or provider markers.
- Historical route metadata may still matter when interpreting older payments or migration-era records.
- Settlement to the school's approved bank destination remains part of the payment trail.

## Current Recommended Payment Model

Use the following active pattern instead:

1. Configure the school's approved bank details and fee settings.
2. Issue structured references per learner and fee purpose.
3. Let parents pay through approved bank, card, USSD, or other supported phone-payment channels using that reference.
4. Preserve the same amount and reference across supported payment channels.
5. Preserve cash-at-school-office as an available fallback where the school uses it.

## Migration Note

If you are reviewing older documentation, screenshots, or payload examples that mention retired proprietor route-management endpoints, fee-route DVAs, or dedicated virtual accounts by payment type, treat those as legacy behavior, not the current supported setup path.

## Related Current References

- `docs/finance/PAYMENT_REFERENCE_FORMAT.md`
- `docs/finance/PAYMENT_CATEGORIZATION.md`
- `docs/finance/BANK_TRANSFER_INTEGRATION.md`
- `backend/routes.py`

---

**Last Updated:** June 14, 2026  
**Version:** 2.2 (Legacy Reference Only)