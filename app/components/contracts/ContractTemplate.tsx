'use client';

import { CheckCircle, Calendar, DollarSign, FileText, Shield, MapPin, Heart } from 'lucide-react';

interface ServiceItem {
  name: string;
  description?: string;
  included: boolean;
}

interface ScheduleItem {
  name: string;
  trigger: string;
  percentage?: number;
  amount?: number;
  days_after?: number;
  days_before?: number;
}

interface PackageSnapshot {
  name: string;
  description?: string;
  total_amount: number;
  currency: string;
  services: ServiceItem[];
  payment_schedule: ScheduleItem[];
  cancellation_policy?: string;
  late_payment_policy?: string;
  custom_terms?: string;
}

interface CoupleInfo {
  name: string;
  email: string;
  partner_name?: string;
  partner_email?: string;
  phone?: string;
}

interface ContractTemplateProps {
  packageSnapshot: PackageSnapshot;
  couple: CoupleInfo;
  weddingDate?: string;
  venue?: string;
  plannerName?: string;
  plannerEmail?: string;
  plannerPhone?: string;
  plannerLogo?: string;
  status: string;
  signedAt?: string;
  signatureName?: string;
}

export default function ContractTemplate({
  packageSnapshot,
  couple,
  weddingDate,
  venue,
  plannerName = 'Your Wedding Planner',
  plannerEmail,
  plannerPhone,
  plannerLogo,
  status,
  signedAt,
  signatureName
}: ContractTemplateProps) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: (packageSnapshot.currency || 'usd').toUpperCase(),
    }).format(amount);
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'TBD';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  const getTriggerLabel = (item: ScheduleItem) => {
    switch (item.trigger) {
      case 'on_signing':
        return 'Due on signing';
      case 'days_after_signing':
        return `${item.days_after} days after signing`;
      case 'days_before_wedding':
        return `${item.days_before} days before wedding`;
      case 'fixed_date':
        return 'Fixed date';
      default:
        return '';
    }
  };

  const includedServices = packageSnapshot.services?.filter(s => s.included) || [];
  const isSigned = status === 'signed' || status === 'active' || status === 'completed';

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl overflow-hidden print:shadow-none">
      {/* Header - Planner Branding */}
      <div className="bg-gradient-to-r from-primary-500 via-primary-600 to-primary-700 px-8 py-10 text-white text-center relative overflow-hidden">
        {/* Decorative elements */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 left-0 w-40 h-40 bg-white rounded-full -translate-x-1/2 -translate-y-1/2" />
          <div className="absolute bottom-0 right-0 w-60 h-60 bg-white rounded-full translate-x-1/4 translate-y-1/4" />
        </div>

        <div className="relative z-10">
          {plannerLogo ? (
            <img
              src={plannerLogo}
              alt={plannerName}
              className="h-16 mx-auto mb-4 object-contain"
            />
          ) : (
            <Heart className="w-12 h-12 mx-auto mb-4 opacity-80" />
          )}
          <p className="text-primary-100 text-sm mb-2 uppercase tracking-wider">
            Wedding Planning Agreement
          </p>
          <h1 className="text-3xl font-bold mb-2">
            {packageSnapshot.name || 'Wedding Package'}
          </h1>
          <p className="text-primary-100">
            Prepared by {plannerName}
          </p>
        </div>
      </div>

      <div className="p-8 space-y-8">
        {/* Couple & Wedding Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Couple Info */}
          <div className="p-6 bg-slate-50 dark:bg-slate-800 rounded-xl">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white mb-4">
              <Heart size={20} className="text-pink-500" />
              The Happy Couple
            </h2>
            <div className="space-y-2 text-slate-600 dark:text-slate-400">
              <p className="font-medium text-slate-900 dark:text-white">
                {couple.name}
                {couple.partner_name && ` & ${couple.partner_name}`}
              </p>
              <p className="text-sm">{couple.email}</p>
              {couple.partner_email && (
                <p className="text-sm">{couple.partner_email}</p>
              )}
              {couple.phone && (
                <p className="text-sm">{couple.phone}</p>
              )}
            </div>
          </div>

          {/* Wedding Details */}
          <div className="p-6 bg-slate-50 dark:bg-slate-800 rounded-xl">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white mb-4">
              <Calendar size={20} className="text-primary-500" />
              Wedding Details
            </h2>
            <div className="space-y-3 text-slate-600 dark:text-slate-400">
              <div className="flex items-start gap-2">
                <Calendar size={16} className="mt-1 flex-shrink-0" />
                <div>
                  <p className="text-xs text-slate-500 dark:text-slate-500">Date</p>
                  <p className="font-medium text-slate-900 dark:text-white">
                    {formatDate(weddingDate)}
                  </p>
                </div>
              </div>
              {venue && (
                <div className="flex items-start gap-2">
                  <MapPin size={16} className="mt-1 flex-shrink-0" />
                  <div>
                    <p className="text-xs text-slate-500 dark:text-slate-500">Venue</p>
                    <p className="font-medium text-slate-900 dark:text-white">{venue}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Package Description */}
        {packageSnapshot.description && (
          <div className="prose dark:prose-invert max-w-none">
            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
              {packageSnapshot.description}
            </p>
          </div>
        )}

        {/* Investment */}
        <div className="text-center py-8 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700">
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
            Total Investment
          </p>
          <p className="text-4xl font-bold text-slate-900 dark:text-white">
            {formatCurrency(packageSnapshot.total_amount || 0)}
          </p>
        </div>

        {/* Services */}
        {includedServices.length > 0 && (
          <div>
            <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900 dark:text-white mb-6">
              <FileText size={24} className="text-primary-500" />
              Services Included
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {includedServices.map((service, index) => (
                <div
                  key={index}
                  className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-100 dark:border-slate-700"
                >
                  <CheckCircle size={20} className="text-green-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {service.name}
                    </p>
                    {service.description && (
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        {service.description}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Payment Schedule */}
        {packageSnapshot.payment_schedule?.length > 0 && (
          <div>
            <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900 dark:text-white mb-6">
              <DollarSign size={24} className="text-primary-500" />
              Payment Schedule
            </h2>
            <div className="space-y-3">
              {packageSnapshot.payment_schedule.map((payment, index) => {
                const amount = payment.percentage
                  ? (packageSnapshot.total_amount * payment.percentage) / 100
                  : (payment.amount || 0);

                return (
                  <div
                    key={index}
                    className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-100 dark:border-slate-700"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-600 dark:text-primary-400 font-semibold text-sm">
                        {index + 1}
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {payment.name || `Payment ${index + 1}`}
                        </p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                          {getTriggerLabel(payment)}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-slate-900 dark:text-white">
                        {formatCurrency(amount)}
                      </p>
                      {payment.percentage && (
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {payment.percentage}%
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Terms & Conditions */}
        {(packageSnapshot.cancellation_policy || packageSnapshot.late_payment_policy || packageSnapshot.custom_terms) && (
          <div className="border-t border-slate-200 dark:border-slate-700 pt-8">
            <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900 dark:text-white mb-6">
              <Shield size={24} className="text-primary-500" />
              Terms & Conditions
            </h2>
            <div className="space-y-6 text-sm text-slate-600 dark:text-slate-400">
              {packageSnapshot.cancellation_policy && (
                <div>
                  <h3 className="font-semibold text-slate-700 dark:text-slate-300 mb-2">
                    Cancellation Policy
                  </h3>
                  <p className="leading-relaxed">{packageSnapshot.cancellation_policy}</p>
                </div>
              )}
              {packageSnapshot.late_payment_policy && (
                <div>
                  <h3 className="font-semibold text-slate-700 dark:text-slate-300 mb-2">
                    Late Payment Policy
                  </h3>
                  <p className="leading-relaxed">{packageSnapshot.late_payment_policy}</p>
                </div>
              )}
              {packageSnapshot.custom_terms && (
                <div>
                  <h3 className="font-semibold text-slate-700 dark:text-slate-300 mb-2">
                    Additional Terms
                  </h3>
                  <p className="leading-relaxed whitespace-pre-wrap">{packageSnapshot.custom_terms}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Signature Section (for signed contracts) */}
        {isSigned && signatureName && (
          <div className="border-t border-slate-200 dark:border-slate-700 pt-8">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-6">
              Signature
            </h2>
            <div className="flex items-center justify-between p-6 bg-green-50 dark:bg-green-900/20 rounded-xl border border-green-200 dark:border-green-800">
              <div>
                <p className="text-sm text-green-600 dark:text-green-400 mb-1">
                  Digitally Signed
                </p>
                <p className="text-2xl font-script text-slate-900 dark:text-white" style={{ fontFamily: 'cursive' }}>
                  {signatureName}
                </p>
              </div>
              <div className="text-right text-sm text-slate-600 dark:text-slate-400">
                <p>Signed on</p>
                <p className="font-medium text-slate-900 dark:text-white">
                  {formatDate(signedAt)}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Planner Contact */}
        <div className="border-t border-slate-200 dark:border-slate-700 pt-8">
          <div className="text-center text-sm text-slate-500 dark:text-slate-400">
            <p className="font-medium text-slate-700 dark:text-slate-300 mb-2">
              {plannerName}
            </p>
            {plannerEmail && <p>{plannerEmail}</p>}
            {plannerPhone && <p>{plannerPhone}</p>}
          </div>
        </div>
      </div>

      {/* Print Styles */}
      <style jsx global>{`
        @media print {
          body {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          .no-print {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
