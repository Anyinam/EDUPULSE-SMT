import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Info, Loader } from 'lucide-react';
import axios from 'axios';

const SubscriptionPlans = () => {
  const [billingPeriod, setBillingPeriod] = useState('term'); // 'term' or 'annual'
  const [studentCount, setStudentCount] = useState(100);
  const [plansData, setPlansData] = useState([]);
  const [currentSubscription, setCurrentSubscription] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch all plans
        const plansResponse = await axios.get('/api/subscription/plans');
        
        // Fetch current subscription (if logged in)
        let currentPlan = null;
        try {
          const schoolId = localStorage.getItem('school_id');
          const subResponse = await axios.get('/api/school/subscription', {
            headers: {
              Authorization: `Bearer ${localStorage.getItem('token')}`,
              'X-School-ID': schoolId
            }
          });
          currentPlan = subResponse.data;
          setStudentCount(currentPlan.current_enrollment || 100);
        } catch (err) {
          // User not logged in or no access - that's okay for public plans view
          console.log('No subscription data available');
        }
        
        setPlansData(plansResponse.data.plans || []);
        setCurrentSubscription(currentPlan);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching subscription data:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);
  
  const plans = [
    {
      name: 'Free',
      price: 0,
      priceLabel: 'Forever Free',
      description: 'Perfect for small schools getting started',
      maxStudents: 50,
      maxClasses: 1,
      maxStaff: 3,
      color: 'gray',
      features: [
        { name: 'Up to 50 students', included: true },
        { name: '1 class only', included: true },
        { name: 'View attendance & feeding', included: true, note: 'Read-only' },
        { name: 'Basic report generation', included: true },
        { name: 'Grade viewing', included: true },
        { name: 'Grade entry & editing', included: false },
        { name: 'Lesson notes', included: false },
        { name: 'Payment tracking', included: false },
        { name: 'Bulk operations', included: false },
        { name: 'AI analysis', included: false },
        { name: 'Advanced analytics', included: false },
      ],
    },
    {
      name: 'Basic',
      price: 12,
      baseFee: 200,
      includedStudents: 25,
      priceLabel: '200 GHS base + 12/student above 25',
      description: 'Full school operations for growing institutions',
      maxStudents: 200,
      maxClasses: 5,
      maxStaff: 15,
      color: 'blue',
      popular: true,
      features: [
        { name: 'Up to 200 students', included: true },
        { name: '5 classes', included: true },
        { name: 'Full attendance & feeding management', included: true },
        { name: 'Grade entry & editing', included: true },
        { name: 'Lesson notes creation', included: true },
        { name: 'Payment tracking & reconciliation', included: true },
        { name: 'Bulk operations (attendance/feeding)', included: true },
        { name: '5 report templates', included: true },
        { name: 'Basic AI feedback on lesson notes', included: true },
        { name: 'AI grade narratives', included: false },
        { name: 'Custom HTML templates', included: false },
        { name: 'Advanced analytics dashboard', included: false },
      ],
    },
    {
      name: 'Premium',
      price: 27,
      baseFee: 450,
      includedStudents: 30,
      priceLabel: '450 GHS base + 27/student above 30',
      description: 'Unlimited access with AI-powered insights',
      maxStudents: '∞',
      maxClasses: '∞',
      maxStaff: '∞',
      color: 'purple',
      features: [
        { name: 'Unlimited students', included: true },
        { name: 'Unlimited classes', included: true },
        { name: 'Everything in Basic, plus:', included: true, bold: true },
        { name: 'AI-generated grade narratives', included: true },
        { name: 'Full AI analysis & scoring', included: true },
        { name: 'Advanced analytics dashboard', included: true },
        { name: 'Custom HTML report templates', included: true },
        { name: 'Priority support', included: true },
        { name: 'API access', included: true },
        { name: 'White-label options', included: true },
      ],
    },
  ];

  const calculateCost = (plan) => {
    if (plan.name === 'Free') return 0;
    
    const students = Math.min(studentCount, 
      plan.maxStudents === '∞' ? studentCount : plan.maxStudents
    );
    
    const baseFee = plan.baseFee || 0;
    const included = plan.includedStudents || 0;
    const billableStudents = Math.max(0, students - included);
    const termCost = baseFee + (plan.price * billableStudents);
    const annualCost = termCost * 3; // 3 terms per year
    
    return billingPeriod === 'term' ? termCost : annualCost;
  };

  const colorClasses = {
    gray: {
      border: 'border-gray-300',
      badge: 'bg-gray-100 text-gray-800',
      button: 'bg-gray-600 hover:bg-gray-700 text-white',
      accent: 'text-gray-600',
    },
    blue: {
      border: 'border-blue-500 ring-2 ring-blue-200',
      badge: 'bg-blue-100 text-blue-800',
      button: 'bg-blue-600 hover:bg-blue-700 text-white',
      accent: 'text-blue-600',
    },
    purple: {
      border: 'border-purple-500',
      badge: 'bg-purple-100 text-purple-800',
      button: 'bg-purple-600 hover:bg-purple-700 text-white',
      accent: 'text-purple-600',
    },
  };

  const handleSubscribe = async (planName) => {
    try {
      const token = localStorage.getItem('token');
      const schoolId = localStorage.getItem('school_id');
      const normalizedPlan = planName === 'Free' ? 'Free Tier' : planName;
      const response = await axios.post(
        '/api/school/subscription/upgrade',
        { plan: normalizedPlan },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-School-ID': schoolId
          }
        }
      );
      alert(`Successfully upgraded to ${normalizedPlan}!`);
      window.location.reload();
    } catch (error) {
      console.error('Subscription error:', error);
      alert('Failed to process subscription. Please try again or contact support.');
    }
  };

  const isCurrentPlan = (planName) => {
    if (!currentSubscription) return false;
    const currentPlan = currentSubscription.plan || 'Free Tier';
    return currentPlan.includes(planName) || planName.includes(currentPlan.replace(' Tier', ''));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-linear-to-br from-gray-50 to-blue-50 flex items-center justify-center">
        <Loader className="w-12 h-12 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-linear-to-br from-gray-50 to-blue-50 py-12 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Choose Your Plan
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Flexible pricing that grows with your school
          </p>

          {/* Billing Toggle */}
          <div className="flex items-center justify-center gap-4 mb-8">
            <button
              onClick={() => setBillingPeriod('term')}
              className={`px-6 py-2 rounded-lg font-medium transition ${
                billingPeriod === 'term'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-100'
              }`}
            >
              Per Term
            </button>
            <button
              onClick={() => setBillingPeriod('annual')}
              className={`px-6 py-2 rounded-lg font-medium transition ${
                billingPeriod === 'annual'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-100'
              }`}
            >
              Annual (3 Terms)
            </button>
          </div>

          {/* Student Count Calculator */}
          <div className="bg-white rounded-lg shadow-sm p-6 max-w-md mx-auto">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Number of Students
            </label>
            <input
              type="number"
              value={studentCount}
              onChange={(e) => setStudentCount(Math.max(1, parseInt(e.target.value) || 0))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              min="1"
              max="1000"
            />
            <p className="text-xs text-gray-500 mt-2">
              Adjust to calculate cost for your school
            </p>
          </div>
        </div>

        {/* Plans Grid */}
        <div className="grid md:grid-cols-3 gap-8 mb-12">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative bg-white rounded-2xl shadow-lg overflow-hidden border-2 ${
                colorClasses[plan.color].border
              } ${plan.popular ? 'transform scale-105' : ''}`}
            >
              {isCurrentPlan(plan.name) && (
                <div className="absolute top-0 left-0 bg-green-600 text-white px-4 py-1 text-xs font-bold rounded-br-lg">
                  CURRENT PLAN
                </div>
              )}
              {plan.popular && !isCurrentPlan(plan.name) && (
                <div className="absolute top-0 right-0 bg-blue-600 text-white px-4 py-1 text-xs font-bold rounded-bl-lg">
                  MOST POPULAR
                </div>
              )}

              <div className="p-8">
                {/* Plan Header */}
                <h3 className="text-2xl font-bold text-gray-900 mb-2">
                  {plan.name}
                </h3>
                <p className="text-gray-600 text-sm mb-6 min-h-10">
                  {plan.description}
                </p>

                {/* Pricing */}
                <div className="mb-6">
                  {plan.name === 'Free' ? (
                    <div>
                      <div className="text-4xl font-bold text-gray-900">
                        GH₵ 0
                      </div>
                      <div className="text-sm text-gray-500">Forever</div>
                    </div>
                  ) : (
                    <div>
                      <div className="text-4xl font-bold text-gray-900">
                        GH₵ {calculateCost(plan).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-600 space-y-0.5">
                        <div>per {billingPeriod === 'annual' ? 'year (3 terms)' : 'term'} ({studentCount} students)</div>
                        {billingPeriod === 'term' && plan.baseFee !== undefined && (
                          <div className="text-xs text-gray-500 mt-1">
                            <div>Base: ₵{plan.baseFee} + {plan.includedStudents} included</div>
                            {studentCount > plan.includedStudents && (
                              <div>Overage: {studentCount - plan.includedStudents} × ₵{plan.price} = ₵{((studentCount - plan.includedStudents) * plan.price).toLocaleString()}</div>
                            )}
                          </div>
                        )}
                        {billingPeriod === 'annual' && plan.baseFee !== undefined && (
                          <div className="text-xs text-gray-500">
                            ₵{(calculateCost(plan) / 3).toLocaleString()}/term
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Limits Badge */}
                <div className={`inline-flex px-3 py-1 rounded-full text-xs font-medium mb-6 ${colorClasses[plan.color].badge}`}>
                  {plan.maxStudents} students • {plan.maxClasses} classes
                </div>

                {/* CTA Button */}
                <button
                  onClick={() => !isCurrentPlan(plan.name) && handleSubscribe(plan.name)}
                  disabled={isCurrentPlan(plan.name)}
                  className={`w-full py-3 px-6 rounded-lg font-semibold transition ${
                    isCurrentPlan(plan.name)
                      ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                      : colorClasses[plan.color].button
                  }`}
                >
                  {isCurrentPlan(plan.name)
                    ? 'Current Plan'
                    : plan.name === 'Free'
                    ? 'Get Started'
                    : 'Upgrade Now'}
                </button>

                {/* Features List */}
                <div className="mt-8 space-y-3">
                  {plan.features.map((feature, idx) => (
                    <div key={idx} className="flex items-start gap-3">
                      {feature.included ? (
                        <CheckCircle className="w-5 h-5 text-green-500 shrink-0 mt-0.5" />
                      ) : (
                        <XCircle className="w-5 h-5 text-gray-300 shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1">
                        <span className={`text-sm ${feature.bold ? 'font-semibold text-gray-900' : 'text-gray-600'}`}>
                          {feature.name}
                        </span>
                        {feature.note && (
                          <span className="text-xs text-gray-400 ml-2">
                            ({feature.note})
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* FAQ / Info Section */}
        <div className="bg-white rounded-xl shadow-sm p-8 max-w-4xl mx-auto">
          <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Info className="w-6 h-6 text-blue-600" />
            Billing Information
          </h3>
          <div className="space-y-4 text-gray-600">
            <div>
              <strong className="text-gray-900">Per-term billing:</strong> You pay a base platform fee per term plus overage only for active students above your included threshold.
            </div>
            <div>
              <strong className="text-gray-900">Student count:</strong> Based on students with <code className="bg-gray-100 px-2 py-0.5 rounded">status='Active'</code> in your system.
            </div>
            <div>
              <strong className="text-gray-900">Mid-term changes:</strong> Student uploads during a term do not auto-charge instantly; billing is applied at subscription billing events.
            </div>
            <div>
              <strong className="text-gray-900">Overage:</strong> If you exceed your plan's student limit, you'll be prompted to upgrade before the next term.
            </div>
            <div>
              <strong className="text-gray-900">Payment:</strong> Pay via Paystack (card, bank, USSD). Automatic subscription billing at term start.
            </div>
            <div>
              <strong className="text-gray-900">Subscription convenience fee:</strong> Not applied (0 GHS).
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SubscriptionPlans;
