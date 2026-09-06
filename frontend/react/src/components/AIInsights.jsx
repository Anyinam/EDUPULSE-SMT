import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function AIInsights({ showPremiumOnly = false }) {
  const [insights, setInsights] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchInsights = async () => {
      try {
        const res = await axios.get('/api/proprietor/ai-insights', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-School-ID': localStorage.getItem('school_id')
          }
        });
        setInsights(res.data.insights || []);
        setAlerts(res.data.alerts || []);
        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch AI insights', err);
        setLoading(false);
      }
    };

    fetchInsights();
    const interval = setInterval(fetchInsights, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const getAlertStyle = (type) => {
    switch (type) {
      case 'success': return 'bg-green-50 border-green-200 text-green-800';
      case 'warning': return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'danger': return 'bg-red-50 border-red-200 text-red-800';
      case 'info': return 'bg-blue-50 border-blue-200 text-blue-800';
      default: return 'bg-gray-50 border-gray-200 text-gray-800';
    }
  };

  // Free tier: Show only critical alerts (first 2)
  // Premium: Show everything
  const displayAlerts = showPremiumOnly ? alerts.slice(0, 2) : alerts;
  const displayInsights = showPremiumOnly ? insights.slice(0, 1) : insights;

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 relative">
      {showPremiumOnly && (
        <div className="absolute top-2 right-2">
          <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded-full font-bold">
            🔒 Limited to Free Tier
          </span>
        </div>
      )}
      
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-gray-800 flex items-center gap-2">
          🤖 AI Governance Insights
          {loading && <span className="text-xs text-gray-400 font-normal">(Analyzing...)</span>}
        </h3>
        <span className="text-xs text-gray-400">Auto-refresh every 60s</span>
      </div>

      {loading ? (
        <div className="space-y-3">
          <div className="h-16 bg-gray-100 rounded-lg animate-pulse"></div>
          <div className="h-16 bg-gray-100 rounded-lg animate-pulse"></div>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Critical Alerts First */}
          {displayAlerts.length > 0 && (
            <>
              {displayAlerts.map((alert, index) => (
                <div key={`alert-${index}`} className={`p-4 rounded-lg border-l-4 ${getAlertStyle(alert.type)}`}>
                  <div className="flex items-start gap-2">
                    <span className="text-xl">{alert.icon}</span>
                    <div className="flex-1">
                      <p className="font-bold text-sm mb-1">{alert.title}</p>
                      <p className="text-xs">{alert.message}</p>
                    </div>
                  </div>
                </div>
              ))}
              {displayInsights.length > 0 && <div className="border-t my-3"></div>}
            </>
          )}

          {/* Regular Insights */}
          {displayInsights.map((insight, index) => (
            <div key={`insight-${index}`} className={`p-4 rounded-lg border ${getAlertStyle(insight.type)}`}>
              <div className="flex items-start gap-2">
                <span className="text-xl">{insight.icon}</span>
                <div className="flex-1">
                  <p className="font-bold text-sm mb-1">{insight.title}</p>
                  <p className="text-xs">{insight.message}</p>
                </div>
              </div>
            </div>
          ))}

          {displayInsights.length === 0 && displayAlerts.length === 0 && (
            <div className="text-center py-8 text-gray-400">
              <p className="text-sm">✅ All systems operating normally</p>
              <p className="text-xs mt-1">No critical issues detected</p>
            </div>
          )}

          {/* Premium Upsell */}
          {showPremiumOnly && (alerts.length > 2 || insights.length > 1) && (
            <div className="mt-4 p-4 bg-purple-50 rounded-lg border-2 border-dashed border-purple-200 text-center">
              <p className="text-sm text-purple-800 font-bold mb-1">
                📊 {alerts.length + insights.length - displayAlerts.length - displayInsights.length} more insights available
              </p>
              <p className="text-xs text-purple-600 mb-2">
                Add the AI Pack for complete AI-powered oversight
              </p>
              <button 
                onClick={() => window.location.href = '?tab=subscription'}
                className="text-xs bg-purple-600 text-white px-4 py-2 rounded-full font-bold hover:bg-purple-700"
              >
                Upgrade Now
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}