'use client';

import { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import {
  Monitor,
  Smartphone,
  CheckCircle,
  Calendar,
  DollarSign,
  FileText,
  Shield,
  CreditCard
} from 'lucide-react';

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

interface PackagePreviewProps {
  name: string;
  description?: string;
  total_amount: number;
  currency: string;
  services: ServiceItem[];
  payment_schedule: ScheduleItem[];
  cancellation_policy?: string;
  late_payment_policy?: string;
  custom_terms?: string;
  plannerName?: string;
}

export default function PackagePreview({
  name,
  description,
  total_amount,
  currency,
  services,
  payment_schedule,
  cancellation_policy,
  late_payment_policy,
  custom_terms,
  plannerName = 'Your Wedding Planner'
}: PackagePreviewProps) {
  const [viewMode, setViewMode] = useState<'desktop' | 'mobile'>('desktop');

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount);
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

  const includedServices = services.filter(s => s.included);

  return (
    <div className="space-y-4">
      {/* View Mode Toggle */}
      <div className="flex items-center justify-center gap-2 p-2 bg-slate-100 dark:bg-slate-800 rounded-lg">
        <button
          onClick={() => setViewMode('desktop')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            viewMode === 'desktop'
              ? 'bg-white dark:bg-slate-700 shadow-sm text-primary-600'
              : 'text-slate-600 dark:text-slate-400 hover:bg-white/50'
          }`}
        >
          <Monitor size={18} />
          Desktop
        </button>
        <button
          onClick={() => setViewMode('mobile')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            viewMode === 'mobile'
              ? 'bg-white dark:bg-slate-700 shadow-sm text-primary-600'
              : 'text-slate-600 dark:text-slate-400 hover:bg-white/50'
          }`}
        >
          <Smartphone size={18} />
          Mobile
        </button>
      </div>

      {/* Preview Container */}
      <div className={`mx-auto bg-white dark:bg-slate-900 rounded-xl shadow-xl overflow-hidden transition-all ${
        viewMode === 'mobile' ? 'max-w-sm' : 'max-w-3xl'
      }`}>
        {/* Header */}
        <div className="bg-gradient-to-r from-primary-500 to-primary-600 px-6 py-8 text-white text-center">
          <p className="text-primary-100 text-sm mb-2">
            Service Agreement from {plannerName}
          </p>
          <h1 className={`font-bold ${viewMode === 'mobile' ? 'text-xl' : 'text-2xl'}`}>
            {name || 'Package Name'}
          </h1>
        </div>

        <div className="p-6 space-y-6">
          {/* Description */}
          {description && (
            <div>
              <p className="text-slate-600 dark:text-slate-400">
                {description}
              </p>
            </div>
          )}

          {/* Price */}
          <div className="text-center py-4 bg-slate-50 dark:bg-slate-800 rounded-xl">
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-1">
              Total Investment
            </p>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">
              {formatCurrency(total_amount || 0)}
            </p>
          </div>

          {/* Services */}
          {includedServices.length > 0 && (
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white mb-4">
                <FileText size={20} className="text-primary-500" />
                What&apos;s Included
              </h2>
              <div className="space-y-3">
                {includedServices.map((service, index) => (
                  <div
                    key={index}
                    className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                  >
                    <CheckCircle size={20} className="text-green-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">
                        {service.name || `Service ${index + 1}`}
                      </p>
                      {service.description && (
                        <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
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
          {payment_schedule.length > 0 && (
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white mb-4">
                <DollarSign size={20} className="text-primary-500" />
                Payment Schedule
              </h2>
              <div className="space-y-3">
                {payment_schedule.map((payment, index) => {
                  const amount = payment.percentage
                    ? (total_amount * payment.percentage) / 100
                    : (payment.amount || 0);

                  return (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg"
                    >
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {payment.name || `Payment ${index + 1}`}
                        </p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                          {getTriggerLabel(payment)}
                        </p>
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

          {/* Terms */}
          {(cancellation_policy || late_payment_policy || custom_terms) && (
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white mb-4">
                <Shield size={20} className="text-primary-500" />
                Terms & Conditions
              </h2>
              <div className="space-y-4 text-sm text-slate-600 dark:text-slate-400">
                {cancellation_policy && (
                  <div>
                    <p className="font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Cancellation Policy
                    </p>
                    <p>{cancellation_policy}</p>
                  </div>
                )}
                {late_payment_policy && (
                  <div>
                    <p className="font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Late Payment Policy
                    </p>
                    <p>{late_payment_policy}</p>
                  </div>
                )}
                {custom_terms && (
                  <div>
                    <p className="font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Additional Terms
                    </p>
                    <p className="whitespace-pre-wrap">{custom_terms}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Sign Button (Preview) */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg mb-4">
              <CreditCard className="text-blue-500" size={24} />
              <div className="text-sm">
                <p className="font-medium text-blue-900 dark:text-blue-100">
                  Secure Payment
                </p>
                <p className="text-blue-700 dark:text-blue-300">
                  Your payment method will be saved for scheduled payments
                </p>
              </div>
            </div>
            <Button className="w-full" disabled>
              Review & Sign Contract
            </Button>
            <p className="text-xs text-center text-slate-500 dark:text-slate-400 mt-2">
              This is a preview. Couples will see this when they receive the contract.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
