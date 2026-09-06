import React from 'react';

function resolveUpgradeTarget() {
  const rawRole = localStorage.getItem('role') || '';
  let roles = [];

  try {
    roles = JSON.parse(localStorage.getItem('roles') || '[]');
  } catch {
    roles = [];
  }

  const hasProprietorRole = rawRole === 'proprietor' || roles.includes('proprietor');
  if (hasProprietorRole) {
    return {
      href: '/proprietor?tab=subscription',
      label: 'Open Subscription Options',
      helper: 'Update this school\'s subscription or add-ons to unlock this feature set.',
    };
  }

  return {
    href: '',
    label: '',
    helper: 'Ask the school proprietor to update the school subscription or add-ons to unlock this feature.',
  };
}

export default function PremiumFeatureNotice({
  title = 'Subscription Access Required',
  description = 'This workspace is not available on the current subscription.',
}) {
  const upgradeTarget = resolveUpgradeTarget();

  return (
    <div className="rounded-3xl border border-amber-300 bg-linear-to-r from-amber-50 to-orange-50 p-6 shadow-sm">
      <p className="text-xs font-black uppercase tracking-[0.24em] text-amber-700">Restricted Access</p>
      <h3 className="mt-2 text-2xl font-black text-slate-900">{title}</h3>
      <p className="mt-2 text-sm text-slate-700">{description}</p>
      <p className="mt-3 text-sm font-medium text-amber-900">{upgradeTarget.helper}</p>
      {upgradeTarget.href && (
        <div className="mt-5">
          <button
            type="button"
            onClick={() => { window.location.href = upgradeTarget.href; }}
            className="rounded-xl bg-amber-600 px-4 py-3 text-sm font-bold text-white hover:bg-amber-700"
          >
            {upgradeTarget.label}
          </button>
        </div>
      )}
    </div>
  );
}