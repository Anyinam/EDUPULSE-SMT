import React, { useState, useEffect } from 'react';
import { AlertCircle, Undo2, Loader, Check, Eye } from 'lucide-react';
import axios from 'axios';

const PromotionHistoryModal = ({ studentId, studentName, onClose }) => {
  const [promotions, setPromotions] = useState([]);
  const [reversingId, setReversingId] = useState(null);
  const [reversalReason, setReversalReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchPromotions();
  }, [studentId]);

  const fetchPromotions = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(
        `/api/students/${studentId}/promotions`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setPromotions(response.data.promotions || []);
    } catch (err) {
      console.error('Failed to fetch promotions', err);
    }
  };

  const handleReversePromotion = async (promotionId) => {
    if (!reversalReason.trim()) {
      alert('Please provide a reason for reversing this promotion');
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      
      const response = await axios.post(
        `/api/admissions/promotion/${promotionId}/reverse`,
        { reason: reversalReason },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setResult({
        success: true,
        message: response.data.message
      });

      // Refresh promotions
      setTimeout(() => {
        fetchPromotions();
        setReversalReason('');
        setReversingId(null);
      }, 1500);

    } catch (error) {
      setResult({
        success: false,
        message: error.response?.data?.message || 'Failed to reverse promotion'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xl font-bold text-slate-800">📋 Promotion History - {studentName}</h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-2xl"
          >
            ✕
          </button>
        </div>

        {result && (
          <div className={`p-4 rounded-lg mb-4 flex items-start gap-3 border ${
            result.success 
              ? 'bg-green-50 border-green-200' 
              : 'bg-red-50 border-red-200'
          }`}>
            {result.success ? (
              <Check className="text-green-600 shrink-0 mt-0.5" size={20} />
            ) : (
              <AlertCircle className="text-red-600 shrink-0 mt-0.5" size={20} />
            )}
            <p className={`text-sm font-medium ${
              result.success ? 'text-green-800' : 'text-red-800'
            }`}>
              {result.message}
            </p>
          </div>
        )}

        {promotions.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <p>No promotion history for this student</p>
          </div>
        ) : (
          <div className="space-y-4">
            {promotions.map((promo, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-xl border-2 ${
                  promo.is_reversed
                    ? 'bg-slate-50 border-slate-300'
                    : 'bg-blue-50 border-blue-200'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`font-bold text-sm px-3 py-1 rounded-full ${
                        promo.is_reversed
                          ? 'bg-slate-200 text-slate-700'
                          : 'bg-blue-200 text-blue-800'
                      }`}>
                        {promo.is_reversed ? '⏮️ REVERSED' : '✅ ACTIVE'}
                      </span>
                      <p className="text-xs text-slate-500">
                        {new Date(promo.date).toLocaleDateString()}
                      </p>
                    </div>

                    <p className="font-bold text-slate-800 mb-1">
                      {promo.from_class} → {promo.to_class}
                    </p>

                    {promo.remarks && (
                      <p className="text-sm text-slate-600 mb-2">
                        Reason: {promo.remarks}
                      </p>
                    )}

                    <p className="text-xs text-slate-500">
                      By: {promo.promoted_by}
                    </p>

                    {promo.is_reversed && (
                      <div className="mt-2 pt-2 border-t border-slate-300">
                        <p className="text-xs text-red-600 font-semibold">
                          ⚠️ This promotion was reversed
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Reverse button for non-reversed promotions */}
                  {!promo.is_reversed && reversingId !== idx && (
                    <button
                      onClick={() => setReversingId(idx)}
                      className="px-3 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 font-bold text-sm whitespace-nowrap flex items-center gap-2"
                    >
                      <Undo2 size={16} />
                      Override
                    </button>
                  )}
                </div>

                {/* Reversal form */}
                {reversingId === idx && !promo.is_reversed && (
                  <div className="mt-4 pt-4 border-t-2 border-orange-200 bg-orange-50 p-4 rounded-lg">
                    <p className="text-sm font-bold text-orange-900 mb-3">
                      ⚠️ Reverse this promotion?
                    </p>
                    <textarea
                      placeholder="Reason for reversing this promotion (required)"
                      value={reversalReason}
                      onChange={(e) => setReversalReason(e.target.value)}
                      className="w-full p-2 border rounded-lg text-sm mb-3 bg-white"
                      rows="2"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleReversePromotion(promo.id)}
                        disabled={loading || !reversalReason.trim()}
                        className="flex-1 px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-bold text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        {loading ? (
                          <>
                            <Loader size={16} className="animate-spin" />
                            Reversing...
                          </>
                        ) : (
                          <>
                            <Undo2 size={16} />
                            Confirm Reversal
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => {
                          setReversingId(null);
                          setReversalReason('');
                        }}
                        className="px-3 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 font-bold text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PromotionHistoryModal;
