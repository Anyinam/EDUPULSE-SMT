import React from 'react';
import { ShieldCheck } from 'lucide-react';

export default function SchoolVerifiedBadge({ verified, className = '', compact = false }) {
  if (!verified) {
    return null;
  }

  return (
    <span
      className={[
        'inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-800',
        compact ? 'px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.18em]' : 'px-3 py-1.5 text-xs font-black uppercase tracking-[0.18em]',
        className,
      ].filter(Boolean).join(' ')}
    >
      <ShieldCheck size={compact ? 12 : 14} />
      <span>Verified School</span>
    </span>
  );
}