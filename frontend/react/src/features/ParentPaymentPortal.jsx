import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { ArrowLeft, Building2, ShieldCheck } from 'lucide-react';
import PaymentInstructions from '../components/PaymentInstructions';
import usePublicSchoolProfile from '../hooks/usePublicSchoolProfile';

export default function ParentPaymentPortal() {
  const { schoolId, studentCode } = useParams();
  const { schoolProfile } = usePublicSchoolProfile(schoolId);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    const fetchPayload = async () => {
      try {
        const response = await axios.get(`/api/public/schools/${schoolId}/payments/${studentCode}`);
        if (mounted) {
          setPayload(response.data);
          setLoading(false);
        }
      } catch (requestError) {
        if (mounted) {
          setError(requestError.response?.data?.message || 'Unable to load payment instructions.');
          setLoading(false);
        }
      }
    };

    fetchPayload();
    return () => {
      mounted = false;
    };
  }, [schoolId, studentCode]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.15),_transparent_24%),linear-gradient(180deg,_#f8fffc_0%,_#ffffff_50%,_#f8fbff_100%)] px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-6xl space-y-8">
        <section className="rounded-[2rem] border border-slate-200 bg-white px-6 py-8 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.35)] sm:px-8">
          <div className="grid gap-6 lg:grid-cols-[1.1fr,0.9fr] lg:items-end">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.24em] text-emerald-700">Parent Payment Portal</p>
              <h1 className="mt-3 text-4xl font-black text-slate-950">Clear payment instructions for every school-approved channel.</h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
                This page keeps the learner payment identity, reference codes, fee-route accounts, and school-office fallback instructions in one place.
              </p>
              {schoolProfile ? (
                <div className="mt-5 flex items-center gap-4">
                  {schoolProfile.logo_url ? (
                    <img src={schoolProfile.logo_url} alt={`${schoolProfile.school_name} logo`} className="h-14 w-14 rounded-2xl object-cover ring-1 ring-slate-200" />
                  ) : null}
                  <div>
                    <p className="text-lg font-black text-slate-950">{schoolProfile.school_name}</p>
                    {schoolProfile.motto ? <p className="text-sm text-slate-500">{schoolProfile.motto}</p> : null}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-3 text-slate-900">
                  <Building2 size={18} />
                  <p className="text-sm font-black uppercase tracking-[0.14em]">School ID</p>
                </div>
                <p className="mt-3 text-lg font-bold text-slate-900">{schoolId}</p>
              </div>
              <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-3 text-slate-900">
                  <ShieldCheck size={18} />
                  <p className="text-sm font-black uppercase tracking-[0.14em]">Learner Code</p>
                </div>
                <p className="mt-3 text-lg font-bold text-slate-900">{studentCode}</p>
              </div>
            </div>
          </div>

          <div className="mt-6">
            <Link to={`/apply/${schoolId}`} className="inline-flex items-center gap-2 text-sm font-bold text-slate-700 transition hover:text-slate-950">
              <ArrowLeft size={16} />
              Back to admissions page
            </Link>
          </div>
        </section>

        <PaymentInstructions payload={payload} loading={loading} error={error} />
      </div>
    </div>
  );
}