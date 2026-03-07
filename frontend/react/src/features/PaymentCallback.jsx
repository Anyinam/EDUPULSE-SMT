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
          setStatus('success');
          setMessage('Payment successful! Your subscription has been upgraded.');
          setDetails(res.data.data);
          
          // Redirect to subscription page after 3 seconds
          setTimeout(() => {
            navigate('/proprietor?tab=subscription');
          }, 3000);
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
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
                <p className="text-sm text-green-800">
                  <strong>Plan:</strong> {details.plan_name}
                </p>
                <p className="text-sm text-green-800">
                  <strong>Amount:</strong> GH₵ {(details.amount / 100).toLocaleString()}
                </p>
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
