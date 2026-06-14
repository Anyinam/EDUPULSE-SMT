# Reliability Scenarios

This playbook lists real-life SaaS failure scenarios for EduPulse billing, admissions, reporting, and operations, along with the mitigation or recovery path currently implemented.

## Payment And Billing

1. Reconciliation nightmare
   Scenario: Paystack marks a transaction successful, but the app fails before the database commit.
   Protection: Manual failpoints exist for subscription confirmation and finance payment recording. A daily Paystack reconciliation sweep now cross-checks recent successful Paystack transactions against local records and recovers missing ones.
   Manual recovery: POST `/api/school/subscription/ledger/reconciliation/recover`

2. Duplicate webhook delivery
   Scenario: Paystack retries the same webhook several times.
   Protection: Duplicate transaction references are ignored safely for both subscription and finance flows.

3. Out-of-order callback and webhook
   Scenario: The webhook arrives first, then the frontend verify callback runs later.
   Protection: Subscription verification is idempotent and returns an already-processed success response.

4. Delayed webhook after network outage
   Scenario: Paystack succeeds, but the webhook arrives minutes or hours later.
   Protection: Verification and reconciliation both process the same reference idempotently.

5. Saved-card setup succeeds without reusable authorization
   Scenario: Paystack returns success but no reusable token.
   Protection: The system records a warning timeline event instead of silently assuming recurring billing is ready.

6. Overdue overage auto-charge fails
   Scenario: The grace period ends, but the saved card charge fails.
   Protection: A failed ledger entry is recorded, the billing timeline captures the failure, and the proprietor is notified.

7. Payment submitted with the wrong structured reference
   Scenario: A parent intends to pay Tuition but uses a reference that maps to another fee category.
   Protection: Structured-reference parsing and payment-category review preserve the mismatch for investigation instead of silently reclassifying it.

8. Manual transfer details hidden from unauthorized viewers
   Scenario: A staff member tries to view school bank details after they were saved.
   Protection: Bank details stay masked unless the user re-enters the account password.

9. Pending downgrade during paid period
   Scenario: A Premium school switches to Free Tier before the current paid period ends.
   Protection: The downgrade is scheduled through `pending_plan`; paid access remains active until the billing date.

10. Ledger tampering suspicion
    Scenario: Finance disputes an amount and needs proof that records were not altered.
    Protection: Subscription ledger entries are chained with HMAC hashes and can be verified via reconciliation endpoints.

## Admissions And Capacity

1. Over-admitted student race condition
   Scenario: Two staff users try to admit students at the same time near the plan limit.
   Protection: Admissions now lock the school capacity check inside the transaction before creating a student. This prevents stale-count freebies.

2. Meter drift below reality
   Scenario: `current_student_count` is stale and lower than the actual active student total.
   Protection: Admissions recompute active enrollment before capacity enforcement instead of trusting the cached meter alone.

3. Mid-term overage invoice drift
   Scenario: A school crosses included-student thresholds mid-term.
   Protection: Pro-rated overage invoices are calculated from actual term length and recorded in the ledger and billing timeline.

4. Bulk upload hits capacity mid-file
   Scenario: CSV admission keeps uploading after the plan limit is reached.
   Protection: Bulk upload stops at the cap and returns per-row errors.

5. Duplicate student names
   Scenario: Two students legitimately share the same name.
   Protection: Admission allows duplicates but returns a warning with existing student references to prevent silent confusion.

## Analytics And Reporting

1. Duplicate analytics preset names
   Scenario: The same preset is saved as `Board View` and `board view`.
   Protection: Preset save, delete, and default selection are now case-insensitive.

2. Default preset deleted
   Scenario: The saved default analytics preset is removed.
   Protection: The next available preset becomes the default automatically; otherwise the default is cleared.

3. Nested JSON persistence drift
   Scenario: Preset changes appear in memory but are not persisted reliably.
   Protection: Nested JSON config is deep-cloned before mutation and assignment.

4. Report comparisons across years
   Scenario: A school needs same-term, previous-year, and cohort migration insight.
   Protection: Multi-year class and subject trends, same-term year-over-year comparisons, and cohort migration comparisons are supported.

## Security And Access

1. Proprietor password recovery without account enumeration
   Scenario: A malicious actor probes forgot-password responses.
   Protection: The reset endpoint returns the same response whether the account exists or not.

2. 2FA token replay
   Scenario: An email OTP is reused after completion.
   Protection: Tokens are marked consumed and rejected after expiry or repeated bad attempts.

3. Overdue-school write attempts
   Scenario: A school whose billing is overdue tries to mutate protected resources.
   Protection: Overdue schools remain read-only for protected write routes.

## Operational Failure Modes

1. Email notification failure after business event success
   Scenario: The business event commits, but SMTP fails.
   Protection: The core transaction still completes, and the email failure is logged without rolling back the business state.

2. Scheduler misses one run
   Scenario: A background sweep is skipped during deployment or restart.
   Protection: Daily reconciliation and interval sweeps are idempotent and can be re-run manually.

3. External API temporary outage
   Scenario: Paystack or SMTP is unavailable for a short window.
   Protection: Critical flows surface errors immediately, and reconciliation plus retryable scheduled jobs restore eventual consistency.

## Recommended Validation Drills

1. Trigger `finance_payment_before_commit` in a test or staging payment and verify reconciliation restores the missing payment.
2. Trigger `subscription_payment_before_commit` and verify the daily or manual reconciliation recreates the missing subscription ledger entry.
3. Run concurrent admission attempts near the plan boundary and verify only the allowed capacity is admitted.
4. Replay the same webhook payload multiple times and verify only one local record is created.
5. Delete the active analytics preset and confirm fallback default behavior.
6. Run the full backend and frontend suites before each release.