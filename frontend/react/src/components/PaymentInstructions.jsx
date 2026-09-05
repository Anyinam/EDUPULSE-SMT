import { AlertTriangle, ArrowRight, Banknote, Building2, CircleDollarSign, Landmark, Smartphone } from 'lucide-react';

const currency = new Intl.NumberFormat('en-GH', {
  style: 'currency',
  currency: 'GHS',
  minimumFractionDigits: 2,
});

function formatMoney(value) {
  return currency.format(Number(value || 0));
}

function PaymentInstructions({ payload, loading, error, errorDetails }) {
  if (loading) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white/90 p-6 text-slate-600 shadow-sm">
        Loading payment instructions...
      </div>
    );
  }

  if (error) {
    if (errorDetails?.error === 'payment_collection_blocked') {
      return (
        <section className="rounded-4xl border border-amber-300 bg-amber-50 p-6 text-amber-950 shadow-sm sm:p-8">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-amber-100 p-3 text-amber-700">
              <AlertTriangle size={22} />
            </div>
            <div className="space-y-4">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.24em] text-amber-700">Collection Paused</p>
                <h2 className="mt-2 text-2xl font-black text-slate-950">Parent payments are temporarily paused for this school.</h2>
              </div>
              <p className="max-w-3xl text-sm leading-7 text-slate-700">{errorDetails.message || error}</p>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <div className="rounded-2xl border border-amber-200 bg-white px-4 py-3">
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-700">Current Plan</p>
                  <p className="mt-2 text-lg font-black text-slate-950">{errorDetails.effective_plan || 'Free Tier'}</p>
                </div>
                <div className="rounded-2xl border border-amber-200 bg-white px-4 py-3">
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-700">Active Students</p>
                  <p className="mt-2 text-lg font-black text-slate-950">{errorDetails.active_students ?? 'Unknown'}</p>
                </div>
                <div className="rounded-2xl border border-amber-200 bg-white px-4 py-3">
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-700">Plan Limit</p>
                  <p className="mt-2 text-lg font-black text-slate-950">{errorDetails.plan_limit ?? 50}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                Do not send funds until the school confirms that collection has reopened. Contact the school office or proprietor for an updated payment instruction.
              </div>
            </div>
          </div>
        </section>
      );
    }

    return (
      <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700 shadow-sm">
        {error}
      </div>
    );
  }

  if (!payload) {
    return null;
  }

  const identity = payload.payment_identity || {};
  const paymentCodes = payload.payment_codes || [];
  const admissionFee = payload.admission_fee || {};
  const schoolPaymentAccount = payload.school_payment_account || {};
  const hasBankDetails = Boolean(
    schoolPaymentAccount.bank_name
    || schoolPaymentAccount.bank_account
    || schoolPaymentAccount.bank_account_name
    || schoolPaymentAccount.bank_branch
  );
  const totalDigitalAmount = paymentCodes.reduce((sum, item) => sum + Number(item.total_amount || 0), 0);
  const totalCashAmount = paymentCodes.reduce((sum, item) => sum + Number(item.cash_amount || 0), 0);
  const rails = {
    bank_app: { label: 'Bank app', icon: Landmark },
    ussd_or_shortcode: { label: 'USSD / shortcode', icon: Smartphone },
    school_office_manual: { label: 'School office', icon: Building2 },
  };

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-4xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60">
        <div className="bg-[linear-gradient(120deg,#065f46_0%,#0f766e_45%,#155e75_100%)] px-6 py-8 text-white sm:px-8">
          <p className="text-sm uppercase tracking-[0.3em] text-emerald-100">Parent Payment Portal</p>
          <h1 className="mt-3 text-3xl font-black sm:text-4xl">{payload.student_name}</h1>
          <p className="mt-3 max-w-3xl text-sm text-emerald-50 sm:text-base">
            Use the stable learner payment identity for every digital payment. Structured references keep
            reconciliation accurate even when you pay through different channels.
          </p>
        </div>

        <div className="grid gap-6 px-6 py-8 sm:px-8 lg:grid-cols-[1.2fr,0.8fr]">
          <div className="space-y-4">
            <div className="rounded-[1.75rem] border border-emerald-100 bg-emerald-50 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Stable Payment Identity</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{identity.stable_payment_identity || payload.student_code}</p>
              <p className="mt-2 text-sm text-slate-600">
                Class: {payload.class || 'Not assigned yet'}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                <div className="flex items-center gap-3 text-slate-900">
                  <CircleDollarSign size={18} />
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">All Digital Payments</p>
                </div>
                <p className="mt-3 text-2xl font-black text-slate-950">{formatMoney(totalDigitalAmount)}</p>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                <div className="flex items-center gap-3 text-slate-900">
                  <Banknote size={18} />
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">School Office Cash</p>
                </div>
                <p className="mt-3 text-2xl font-black text-slate-950">{formatMoney(totalCashAmount)}</p>
              </div>
            </div>

            {admissionFee.enabled ? (
              <div className="rounded-3xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
                This school has enabled an admission fee of {admissionFee.currency || 'GH₵'} {Number(admissionFee.amount || 0).toFixed(2)}. It appears below as a school-configured fee where applicable.
              </div>
            ) : null}

            <div className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">How To Pay</p>
              <ol className="mt-3 space-y-2 text-sm text-slate-700">
                <li>1. Choose the fee below and copy the exact reference shown.</li>
                <li>2. Pay with bank transfer, bank app, USSD, or the school office fallback channel.</li>
                <li>3. Keep the learner code {identity.stable_payment_identity || payload.student_code} in the payment narration.</li>
              </ol>
            </div>

            {hasBankDetails ? (
              <div className="rounded-[1.75rem] border border-cyan-100 bg-cyan-50 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700">School Bank Account</p>
                <div className="mt-3 space-y-2 text-sm text-slate-700">
                  {schoolPaymentAccount.bank_name ? <p><strong>Bank:</strong> {schoolPaymentAccount.bank_name}</p> : null}
                  {schoolPaymentAccount.bank_account ? <p><strong>Account Number:</strong> {schoolPaymentAccount.bank_account}</p> : null}
                  {schoolPaymentAccount.bank_account_name ? <p><strong>Account Name:</strong> {schoolPaymentAccount.bank_account_name}</p> : null}
                  {schoolPaymentAccount.bank_branch ? <p><strong>Branch:</strong> {schoolPaymentAccount.bank_branch}</p> : null}
                  <p className="pt-1 text-xs text-cyan-800">Use the payment reference below in the bank transfer narration.</p>
                </div>
              </div>
            ) : null}
          </div>

          <div className="rounded-[1.75rem] border border-slate-200 bg-slate-950 p-5 text-slate-100">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">Supported Rails</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(identity.supported_rails || []).map((rail) => (
                <span
                  key={rail}
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-2 text-xs font-medium uppercase tracking-wide"
                >
                  {rails[rail] ? React.createElement(rails[rail].icon, { size: 13 }) : null}
                  {rails[rail]?.label || rail.replaceAll('_', ' ')}
                </span>
              ))}
            </div>

            <div className="mt-6 space-y-3 text-sm text-slate-300">
              <p>Recommended references:</p>
              {(identity.recommended_examples || []).map((reference) => (
                <div key={reference} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 font-medium text-white">
                  {reference}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4">
        {paymentCodes.map((item) => (
          <article
            key={item.reference_code}
            className="rounded-4xl border border-slate-200 bg-white p-6 shadow-lg shadow-slate-200/50"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{item.fee_type}</p>
                <h2 className="mt-2 text-2xl font-black text-slate-900">Reference: {item.reference_code}</h2>
                <p className="mt-2 max-w-3xl text-sm text-slate-600">{item.instructions}</p>
              </div>

              <div className="grid min-w-60 gap-2 rounded-3xl bg-slate-50 p-4 text-sm text-slate-700">
                <div className="flex items-center justify-between gap-4">
                  <span>Amount to pay</span>
                  <strong>{formatMoney(item.cash_amount ?? item.base_amount ?? item.total_amount)}</strong>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span>School office amount</span>
                  <strong>{formatMoney(item.cash_amount ?? item.base_amount ?? item.total_amount)}</strong>
                </div>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-3xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Plan</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{item.payment_category?.frequency || item.fee_type}</p>
              </div>

              <div className="rounded-3xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Learner Code</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{item.payment_identity_base}</p>
              </div>

              <div className="rounded-3xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Payment Reference</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{item.reference_code}</p>
                <p className="mt-1 text-sm text-slate-500">Use this exact reference in the payment narration.</p>
              </div>

              <div className="rounded-3xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Digital Channel</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">Phone Payment</p>
                <p className="mt-1 text-sm text-slate-500">Bank transfer, bank app, USSD, or the school's approved phone channel.</p>
              </div>

              <div className="rounded-3xl border border-slate-200 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Collection Model</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{item.preferred_payment_model || 'reference_first'}</p>
                <p className="mt-1 text-sm text-slate-500">
                  Use the same structured reference across the school's approved payment channels.
                </p>
              </div>
            </div>

            <div className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-emerald-700">
              Continue with this reference
              <ArrowRight size={15} />
            </div>
          </article>
        ))}
      </section>

      {payload.note ? (
        <section className="rounded-3xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
          {payload.note}
        </section>
      ) : null}
    </div>
  );
}

export default PaymentInstructions;