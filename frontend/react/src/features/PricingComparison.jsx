import React, { useEffect, useState } from 'react';
import { Check, X, Info, Loader } from 'lucide-react';
import axios from 'axios';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';

export default function PricingComparison() {
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);
  const [plansData, setPlansData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const res = await axios.get('/api/subscription/plans');
        setPlansData(res.data?.plans || []);
      } catch (error) {
        console.error('Failed to load pricing plans:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPlans();
  }, []);

  const plans = (plansData || []).map((plan) => ({
    rawName: plan.name,
    name: plan.display_name || plan.name,
    color: plan.ui_color || 'gray',
    baseFee: Number(plan.base_fee_per_term || 0),
    baseFeeLabel: `₵${Number(plan.base_fee_per_term || 0).toLocaleString()}/term`,
    includedStudents: Number(plan.included_students || 0),
    overageRate: Number(plan.price_per_student_per_term || 0),
    overageLabel: Number(plan.price_per_student_per_term || 0) > 0 ? `₵${plan.price_per_student_per_term}/extra student` : 'N/A',
    description: plan.description,
    features: plan.marketing_features || [],
    addonOptions: plan.addon_options || [],
    packagingSummary: plan.packaging_summary || '',
    cta: plan.name === 'Free Tier' ? 'Get Started Free' : 'Start 30-Day Premium Trial',
    highlighted: Boolean(plan.popular),
    badge: plan.popular ? 'MOST POPULAR' : undefined,
  }));

  const colorStyles = {
    gray: {
      badge: 'bg-gray-100 text-gray-800 border-gray-300',
      border: 'border-gray-300',
      button: 'bg-gray-600 hover:bg-gray-700 text-white',
      header: 'bg-gray-50',
      accent: 'text-gray-700',
    },
    blue: {
      badge: 'bg-blue-100 text-blue-800 border-blue-300 ring-2 ring-blue-200',
      border: 'border-blue-500 ring-2 ring-blue-200',
      button: 'bg-blue-600 hover:bg-blue-700 text-white',
      header: 'bg-blue-50',
      accent: 'text-blue-700',
      shadow: 'shadow-xl',
    },
    amber: {
      badge: 'bg-amber-100 text-amber-800 border-amber-300',
      border: 'border-amber-500',
      button: 'bg-amber-600 hover:bg-amber-700 text-white',
      header: 'bg-amber-50',
      accent: 'text-amber-700',
    },
  };

  const calculateExample = (students, baseFee, included, rate) => {
    if (baseFee === 0) return '₵0';
    const billable = Math.max(0, students - included);
    const total = baseFee + (billable * rate);
    return `₵${total.toLocaleString()}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-linear-to-br from-slate-50 to-blue-50 flex items-center justify-center">
        <Loader className="h-10 w-10 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 to-blue-50 py-16 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-black text-slate-900 mb-4">
            Simple, Transparent Pricing
          </h1>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto">
            Choose the plan that fits your school. Pay only for what you use. No surprises.
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl overflow-hidden transition-all duration-300 hover:shadow-lg ${
                plan.highlighted
                  ? `${colorStyles[plan.color].border} ${colorStyles[plan.color].shadow}`
                  : `border ${colorStyles[plan.color].border}`
              }`}
            >
              {/* Badge */}
              {plan.badge && (
                <div className={`absolute -right-12 top-6 transform rotate-45 ${colorStyles[plan.color].badge} py-1 px-12 text-sm font-bold`}>
                  {plan.badge}
                </div>
              )}

              {/* Header */}
              <div className={`${colorStyles[plan.color].header} p-8 border-b`}>
                <h3 className={`text-3xl font-black ${colorStyles[plan.color].accent} mb-2`}>
                  {plan.name}
                </h3>
                <p className="text-slate-600 text-sm mb-6">{plan.description}</p>
              </div>

              {/* Pricing */}
              <div className="p-8">
                <div className="mb-8">
                  <div className="text-5xl font-black text-slate-900 mb-2">
                    {plan.baseFeeLabel}
                  </div>
                  <p className="text-slate-600 text-sm">
                    Base platform fee per term
                  </p>
                </div>

                {/* Included & Overage */}
                <div className="space-y-4 mb-8 p-4 bg-slate-50 rounded-lg">
                  <div className="text-sm">
                    <span className="font-semibold text-slate-900">
                      {plan.rawName === 'Free Tier' ? 'Up to' : 'First'} {plan.rawName === 'Free Tier' ? 50 : (plan.includedStudents || 0)} students
                    </span>
                    <span className="text-slate-600 ml-2">included</span>
                  </div>
                  {plan.overageRate > 0 && (
                    <div className="text-sm">
                      <span className="font-semibold text-slate-900">
                        {plan.overageLabel}
                      </span>
                      <span className="text-slate-600 ml-2">above {plan.includedStudents}</span>
                    </div>
                  )}
                </div>

                {/* Example Cost */}
                <div className="mb-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <p className="text-xs text-slate-600 mb-2">Example: 100 students</p>
                  <p className="text-2xl font-black text-blue-700">
                    {calculateExample(100, plan.baseFee, plan.includedStudents, plan.overageRate)}
                    <span className="text-sm font-normal text-slate-600 ml-2">/term</span>
                  </p>
                </div>

                {/* CTA Button */}
                <button
                  className={`w-full py-3 rounded-lg font-bold text-lg transition-all duration-300 ${colorStyles[plan.color].button}`}
                >
                  {plan.cta}
                </button>

                {plan.packagingSummary && (
                  <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    {plan.packagingSummary}
                  </p>
                )}

                <p className="text-center text-xs text-slate-500 mt-3 leading-relaxed">
                  By creating a school account, you accept our{' '}
                  <button type="button" onClick={() => setShowTerms(true)} className="text-blue-600 font-semibold hover:underline">Terms of Service</button>,{' '}
                  <button type="button" onClick={() => setShowPrivacy(true)} className="text-blue-600 font-semibold hover:underline">Privacy Policy</button>, and{' '}
                  <button type="button" onClick={() => setShowRetention(true)} className="text-blue-600 font-semibold hover:underline">Data Retention Policy</button>.
                </p>

                <p className="text-center text-xs text-slate-500 mt-4">
                  {plan.rawName === 'Free Tier' ? 'Start free immediately' : 'Start the trial without a card. Pay only when you activate a paid plan.'}
                </p>
              </div>

              {/* Features */}
              <div className="px-8 pb-8">
                <h4 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <span>What's Included</span>
                </h4>
                <ul className="space-y-3">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-3">
                      {feature.included ? (
                        <Check className="w-5 h-5 text-green-500 shrink-0 mt-0.5" />
                      ) : (
                        <X className="w-5 h-5 text-gray-300 shrink-0 mt-0.5" />
                      )}
                      <span
                        className={`text-sm ${
                          feature.bold
                            ? 'font-semibold text-slate-900'
                            : feature.included
                            ? 'text-slate-700'
                            : 'text-slate-400'
                        }`}
                      >
                        {feature.name}
                      </span>
                    </li>
                  ))}
                </ul>

                {plan.addonOptions.length > 0 && (
                  <div className="mt-6 border-t border-slate-100 pt-4">
                    <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Future Add-Ons</p>
                    <p className="mb-2 text-xs text-slate-500">These are future optional products and are not bundled into the listed plan price.</p>
                    <div className="flex flex-wrap gap-2">
                      {plan.addonOptions.map((addon) => (
                        <span key={addon} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
                          {addon}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Info Section */}
        <div className="bg-white rounded-xl shadow-sm p-8 max-w-4xl mx-auto">
          <div className="flex gap-4 mb-6">
            <Info className="w-6 h-6 text-blue-600 shrink-0 mt-1" />
            <div>
              <h3 className="text-2xl font-bold text-slate-900 mb-4">
                How Billing Works
              </h3>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-8 text-slate-700">
            <div>
              <h4 className="font-bold text-slate-900 mb-3">📅 Term Billing</h4>
              <p className="text-sm mb-3">
                You're charged at the start of each academic term (3 terms per year). The amount depends on how many active students you have.
              </p>
              <p className="text-sm">
                <strong>Example:</strong> Basic plan with 150 students:
                <br />₵360 (base) + (120 × ₵12) = <strong>₵1,800/term</strong>
              </p>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 mb-3">✅ Active Students Count</h4>
              <p className="text-sm mb-3">
                Only students with status = "Active" are counted for billing.
              </p>
              <p className="text-sm">
                New paid activations after trial are prorated to the remaining days in the current term. Regular billing continues on the normal term cycle.
              </p>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 mb-3">🧾 Transparent Billing</h4>
              <p className="text-sm mb-3">
                Subscription charges stay aligned with the invoice amount, with no extra charge layered on top at checkout.
              </p>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 mb-3">🔄 Flexible Upgrades</h4>
              <p className="text-sm mb-3">
                You can change plans anytime. Mid-term paid activations are charged only for the remaining days in the current term.
              </p>
            </div>
          </div>
        </div>

        {/* FAQ Snippet */}
        <div className="mt-16 text-center">
          <p className="text-slate-600 mb-4">
            Questions about pricing? <a href="mailto:support@edupulse.com" className="text-blue-600 font-bold hover:underline">
              Contact our team
            </a>
          </p>

          <div className="max-w-2xl mx-auto bg-white border border-slate-200 rounded-xl p-4">
            <p className="text-xs font-bold text-slate-500 uppercase mb-2">Legal Policies</p>
            <p className="text-sm text-slate-600">By creating a school account, you accept our Terms of Service, Privacy Policy, and Data Retention Policy.</p>
            <div className="mt-2 text-sm flex flex-wrap justify-center gap-3">
              <button type="button" onClick={() => setShowTerms(true)} className="text-blue-600 font-semibold hover:underline">Terms of Service</button>
              <button type="button" onClick={() => setShowPrivacy(true)} className="text-blue-600 font-semibold hover:underline">Privacy Policy</button>
              <button type="button" onClick={() => setShowRetention(true)} className="text-blue-600 font-semibold hover:underline">Data Retention Policy</button>
            </div>
          </div>
        </div>
      </div>

      <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
      <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
      <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
    </div>
  );
}
