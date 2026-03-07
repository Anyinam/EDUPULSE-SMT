import React from 'react';
import { Check, X, Info } from 'lucide-react';

export default function PricingComparison() {
  const plans = [
    {
      name: 'Free Tier',
      color: 'gray',
      baseFee: 0,
      baseFeeLabel: '₵0/term',
      includedStudents: 100,
      overageRate: 0,
      overageLabel: 'N/A',
      description: 'Perfect for small schools getting started',
      features: [
        { name: 'Up to 50 students', included: true },
        { name: '1 class only', included: true },
        { name: 'View attendance & feeding', included: true },
        { name: 'View grades', included: true },
        { name: 'Basic reports (1 template)', included: true },
        { name: 'Grade entry & editing', included: false },
        { name: 'Lesson notes', included: false },
        { name: 'Payment tracking', included: false },
        { name: 'AI features', included: false },
        { name: 'Bulk operations', included: false },
        { name: 'Advanced analytics', included: false },
      ],
      cta: 'Get Started Free',
      highlighted: false,
    },
    {
      name: 'Basic',
      color: 'blue',
      baseFee: 200,
      baseFeeLabel: '₵200/term',
      includedStudents: 25,
      overageRate: 12,
      overageLabel: '₵12/extra student',
      description: 'Full school operations for growing institutions',
      features: [
        { name: 'Up to 200 students', included: true },
        { name: '5 classes', included: true },
        { name: 'Full attendance & feeding', included: true },
        { name: 'Grade entry & editing', included: true },
        { name: 'Lesson notes creation', included: true },
        { name: 'Payment tracking', included: true },
        { name: 'Basic AI feedback', included: true },
        { name: '5 report templates', included: true },
        { name: 'Bulk operations', included: true },
        { name: 'AI grade narratives', included: false },
        { name: 'Custom HTML templates', included: false },
      ],
      cta: 'Start 14-Day Trial',
      highlighted: true,
      badge: 'MOST POPULAR',
    },
    {
      name: 'Premium',
      color: 'purple',
      baseFee: 450,
      baseFeeLabel: '₵450/term',
      includedStudents: 30,
      overageRate: 27,
      overageLabel: '₵27/extra student',
      description: 'Unlimited access with AI-powered insights',
      features: [
        { name: 'Unlimited students', included: true },
        { name: 'Unlimited classes', included: true },
        { name: 'Everything in Basic, plus:', included: true, bold: true },
        { name: 'AI-generated grade narratives', included: true },
        { name: 'Full AI analysis & scoring', included: true },
        { name: 'Advanced analytics dashboard', included: true },
        { name: 'Custom HTML templates', included: true },
        { name: 'Unlimited staff', included: true },
        { name: 'Priority support', included: true },
        { name: 'API access', included: true },
        { name: 'White-label options', included: true },
      ],
      cta: 'Start 14-Day Trial',
      highlighted: false,
    },
  ];

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
    purple: {
      badge: 'bg-purple-100 text-purple-800 border-purple-300',
      border: 'border-purple-500',
      button: 'bg-purple-600 hover:bg-purple-700 text-white',
      header: 'bg-purple-50',
      accent: 'text-purple-700',
    },
  };

  const calculateExample = (students, baseFee, included, rate) => {
    if (baseFee === 0) return '₵0';
    const billable = Math.max(0, students - included);
    const total = baseFee + (billable * rate);
    return `₵${total.toLocaleString()}`;
  };

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
                      {plan.includedStudents === 100 ? 'Up to' : 'First'} {plan.includedStudents} students
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

                <p className="text-center text-xs text-slate-500 mt-4">
                  No credit card required
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
                <br />₵200 (base) + (125 × ₵12) = <strong>₵1,700/term</strong>
              </p>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 mb-3">✅ Active Students Count</h4>
              <p className="text-sm mb-3">
                Only students with status = "Active" are counted for billing. If students leave mid-term, you get a credit.
              </p>
              <p className="text-sm">
                Student uploads don't auto-charge instantly. Billing happens at term activation.
              </p>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 mb-3">🎁 No Convenience Fee</h4>
              <p className="text-sm mb-3">
                Subscription charges have zero convenience fee. You pay exactly what's on your invoice—no hidden costs.
              </p>
            </div>

            <div>
              <h4 className="font-bold text-slate-900 mb-3">🔄 Flexible Upgrades</h4>
              <p className="text-sm mb-3">
                Upgrade or downgrade plans between terms. Changes take effect in the next billing cycle.
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
        </div>
      </div>
    </div>
  );
}
