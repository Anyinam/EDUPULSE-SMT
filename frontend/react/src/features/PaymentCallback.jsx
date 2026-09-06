import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { CheckCircle, XCircle, Loader } from 'lucide-react';

export default function PaymentCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('verifying'); // verifying, success, failed
  const [message, setMessage] = useState('Verifying your payment...');
  const [details, setDetails] = useState(null);

  useEffect(() => {
    const verifyPayment = async () => {
      const reference = searchParams.get('reference');
      const trxref = searchParams.get('trxref'); // Alternative param name
      const paymentRef = reference || trxref;

      if (!paymentRef) {
        setStatus('failed');
        setMessage('No payment reference found. Please contact support.');
        return;
      }

      try {
        const headers = {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id')
        };

        const res = await axios.get(`/api/paystack/verify/${paymentRef}`, { headers });

        if (res.data.status === 'success') {
          const isCardSetup = Boolean(res.data?.data?.card && !res.data?.data?.plan_name);
          const isAddonPurchase = res.data?.data?.transaction_type === 'addon_purchase';
          setStatus('success');
          setMessage(
            isCardSetup
              ? 'Card saved successfully for recurring pay-as-you-go billing.'
              : isAddonPurchase
              ? `Payment successful! ${res.data?.data?.addon_name || 'Your add-on'} is now active.`
              : 'Payment successful! Your subscription has been updated.'
          );
          setDetails(res.data.data);
          const isRegistrationFlow = Boolean(res.data.registration_flow || searchParams.get('onboarding') === 'registration');
          
          // CRITICAL: Refresh subscription data in localStorage
          try {
            const schoolRes = await axios.get('/api/school/subscription', { headers });
            if (schoolRes.data) {
              // Update localStorage with new subscription plan
              const newPlan = schoolRes.data.subscription_plan || schoolRes.data.plan || 'Free Tier';
              localStorage.setItem('subscription_plan', newPlan);
              
              // Update enabled modules from backend
              if (schoolRes.data.enabled_modules) {
                localStorage.setItem('enabled_modules', JSON.stringify(schoolRes.data.enabled_modules));
              }
              
              console.log('✅ Subscription refreshed:', newPlan, schoolRes.data.enabled_modules);
            }
          } catch (refreshErr) {
            console.error('Failed to refresh subscription data:', refreshErr);
            // Continue anyway - user can manually refresh
          }
          
          // Registration payment should finish at login page.
          setTimeout(() => {
            if (isRegistrationFlow) {
              localStorage.removeItem('token');
              localStorage.removeItem('role');
              localStorage.removeItem('roles');
              localStorage.removeItem('assigned_class');
              window.location.href = '/login';
              return;
            }
            window.location.href = '/proprietor?tab=subscription';
          }, 2000);
        } else {
          setStatus('failed');
          setMessage(res.data.message || 'Payment verification failed. Please contact support.');
        }
      } catch (err) {
        console.error('Payment verification error:', err);
        setStatus('failed');
        setMessage(err.response?.data?.message || 'Failed to verify payment. Please contact support.');
      }
    };

    verifyPayment();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full text-center">
        {status === 'verifying' && (
          <>
            <div className="mb-6">
              <Loader className="animate-spin text-blue-600 mx-auto" size={64} />
            </div>
            <h1 className="text-2xl font-bold text-slate-800 mb-2">Verifying Payment</h1>
            <p className="text-slate-600">{message}</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="mb-6">
              <CheckCircle className="text-green-600 mx-auto" size={64} />
            </div>
            <h1 className="text-2xl font-bold text-green-900 mb-2">Payment Successful!</h1>
            <p className="text-slate-600 mb-4">{message}</p>
            
            {details && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-left mb-4">
                {details.plan_name && (
                  <p className="text-sm text-green-800">
                    <strong>Plan:</strong> {details.plan_name}
                  </p>
                )}
                {details.addon_name && (
                  <p className="text-sm text-green-800">
                    <strong>Add-On:</strong> {details.addon_name}
                  </p>
                )}
                {typeof details.amount === 'number' && (
                  <p className="text-sm text-green-800">
                    <strong>Amount:</strong> GH₵ {Number(details.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                )}
                {details.card && (
                  <p className="text-sm text-green-800">
                    <strong>Saved Card:</strong> {details.card.brand || 'Card'} •••• {details.card.last4 || '----'}
                  </p>
                )}
                <p className="text-sm text-green-800">
                  <strong>Reference:</strong> {details.reference}
                </p>
              </div>
            )}

            <p className="text-xs text-slate-500">Redirecting to subscription page...</p>
          </>
        )}

        {status === 'failed' && (
          <>
            <div className="mb-6">
              <XCircle className="text-red-600 mx-auto" size={64} />
            </div>
            <h1 className="text-2xl font-bold text-red-900 mb-2">Payment Failed</h1>
            <p className="text-slate-600 mb-6">{message}</p>
            
            <div className="flex gap-3">
              <button
                onClick={() => navigate('/proprietor?tab=subscription')}
                className="flex-1 py-3 bg-slate-200 text-slate-700 rounded-xl font-bold hover:bg-slate-300 transition-all"
              >
                Back to Subscription
              </button>
              <button
                onClick={() => window.location.reload()}
                className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-bold hover:bg-blue-700 transition-all"
              >
                Try Again
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
