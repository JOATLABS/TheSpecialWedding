'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { formatAdminDate } from '@/utils/dateFormat';
import { Button } from '../../../../components/ui/Button';
import { Card } from '../../../../components/ui/Card';
import {
  ArrowLeft,
  Loader2,
  Send,
  User,
  Mail,
  Phone,
  Calendar,
  FileText,
  DollarSign,
  CheckCircle
} from 'lucide-react';

interface PackageData {
  id: string;
  name: string;
  description?: string;
  total_amount: number;
  currency: string;
  status: string;
  services: Array<{ name: string; description?: string; included: boolean }>;
  payment_schedule: Array<{ name: string; percentage: number; trigger: string }>;
}

interface Wedding {
  id?: string;
  _id?: string;
  couple_names: string;
  date: string;
}

function splitCoupleNames(coupleNames: string): [string, string] {
  const normalized = coupleNames.trim();
  if (!normalized) {
    return ['', ''];
  }

  const parts = normalized.split(/\s+(?:&|and)\s+/i).map((part) => part.trim()).filter(Boolean);
  if (parts.length <= 1) {
    return [normalized, ''];
  }

  return [parts[0], parts.slice(1).join(' & ')];
}

function formatWeddingOptionDate(value?: string): string {
  if (!value) {
    return 'No date';
  }

  const datePrefix = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (datePrefix) {
    const [, year, month, day] = datePrefix;
    return new Date(Number(year), Number(month) - 1, Number(day)).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  return formatAdminDate(value);
}

export default function SendPackagePage() {
  const router = useRouter();
  const params = useParams();
  const packageId = params.id as string;
  const { token } = useAdmin();

  const [loading, setLoading] = useState(true);
  const [packageData, setPackageData] = useState<PackageData | null>(null);
  const [weddings, setWeddings] = useState<Wedding[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [contractUrl, setContractUrl] = useState<string>('');

  // Form state
  const [formData, setFormData] = useState({
    partner1_name: '',
    partner2_name: '',
    email: '',
    phone: '',
    wedding_date: '',
    wedding_id: ''
  });

  const fetchData = useCallback(async () => {
    if (!token || !packageId) return;

    setLoading(true);

    try {
      const baseUrl = getApiBaseUrl();

      // Fetch package and weddings in parallel
      const [packageRes, weddingsRes] = await Promise.all([
        fetch(`${baseUrl}/admin/packages/${packageId}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`${baseUrl}/admin/planner/weddings`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      ]);

      if (!packageRes.ok) {
        throw new Error('Failed to fetch package');
      }

      const packageResult = await packageRes.json();
      setPackageData(packageResult.package);

      if (weddingsRes.ok) {
        const weddingsData = await weddingsRes.json();
        setWeddings(Array.isArray(weddingsData) ? weddingsData : []);
      }
    } catch (err) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [token, packageId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // When a wedding is selected, auto-fill the form
  const handleWeddingSelect = (weddingId: string) => {
    const wedding = weddings.find(w => (w.id || w._id) === weddingId);
    if (wedding) {
      const [partner1Name, partner2Name] = splitCoupleNames(wedding.couple_names);
      setFormData(prev => ({
        ...prev,
        wedding_id: weddingId,
        partner1_name: partner1Name,
        partner2_name: partner2Name,
        wedding_date: wedding.date ? wedding.date.split('T')[0] : ''
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        wedding_id: ''
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!token || !packageId) return;

    if (!formData.partner1_name.trim()) {
      toast.error('Please enter the partner name');
      return;
    }

    if (!formData.email.trim()) {
      toast.error('Please enter an email address');
      return;
    }

    setIsSubmitting(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/${packageId}/send`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          couple: {
            partner1_name: formData.partner1_name,
            partner2_name: formData.partner2_name || undefined,
            email: formData.email,
            phone: formData.phone || undefined
          },
          wedding_date: formData.wedding_date || undefined,
          wedding_id: formData.wedding_id || undefined
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = errorData?.detail;
        // The Connect-readiness gate returns a structured detail —
        // {code: "CONNECT_NOT_READY", message, setup_url} — instead of a
        // plain string. Surface it with a CTA back to the billing page so
        // the planner can complete payout setup before retrying.
        if (
          detail &&
          typeof detail === 'object' &&
          detail.code === 'CONNECT_NOT_READY'
        ) {
          toast.error(detail.message || 'Set up payouts before sending packages.', {
            action: {
              label: 'Set up payouts',
              onClick: () => {
                router.push(detail.setup_url || '/admin/planner/billing');
              },
            },
            duration: 10_000,
          });
          return;
        }
        const message = typeof detail === 'string' ? detail : 'Failed to send package';
        throw new Error(message);
      }

      const result = await response.json();
      setSuccess(true);

      // Build contract URL
      if (result.contract?.token) {
        const contractBase = typeof window !== 'undefined' ? window.location.origin : '';
        setContractUrl(`${contractBase}/contracts/${result.contract.token}`);
      }

      toast.success('Package sent successfully!');
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send package';
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatCurrency = (amount: number, currency: string = 'usd') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    );
  }

  if (!packageData) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            href="/admin/packages"
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-2xl sm:text-3xl font-semibold leading-tight text-slate-900 dark:text-white">
            Send Package
          </h1>
        </div>
        <Card className="p-12 text-center">
          <p className="text-red-600 dark:text-red-400">Package not found</p>
        </Card>
      </div>
    );
  }

  if (packageData.status !== 'active') {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            href="/admin/packages"
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-2xl sm:text-3xl font-semibold leading-tight text-slate-900 dark:text-white">
            Send Package
          </h1>
        </div>
        <Card className="p-12 text-center">
          <p className="text-amber-600 dark:text-amber-400 mb-4">
            This package must be activated before sending to couples.
          </p>
          <Link href={`/admin/packages/${packageId}/edit`}>
            <Button>Edit & Activate Package</Button>
          </Link>
        </Card>
      </div>
    );
  }

  if (success) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            href="/admin/packages"
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-2xl sm:text-3xl font-semibold leading-tight text-slate-900 dark:text-white">
            Package Sent!
          </h1>
        </div>

        <Card className="p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
          </div>

          <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
            Contract Created Successfully
          </h2>

          <p className="text-slate-600 dark:text-slate-400 mb-6">
            A contract has been created for {formData.partner1_name}
            {formData.partner2_name ? ` & ${formData.partner2_name}` : ''}.
          </p>

          {contractUrl && (
            <div className="mb-6">
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
                Share this link with your couple:
              </p>
              <div className="flex items-center gap-2 p-3 bg-slate-100 dark:bg-slate-800 rounded-lg">
                <input
                  type="text"
                  value={contractUrl}
                  readOnly
                  className="flex-1 bg-transparent text-sm text-slate-900 dark:text-white outline-none"
                />
                <Button
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(contractUrl);
                    toast.success('Link copied to clipboard!');
                  }}
                >
                  Copy
                </Button>
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button variant="outline" onClick={() => setSuccess(false)}>
              Send to Another Couple
            </Button>
            <Link href="/admin/packages">
              <Button>Back to Packages</Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/admin/packages"
          className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
        >
          <ArrowLeft size={20} />
        </Link>
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold leading-tight text-slate-900 dark:text-white">
            Send Package
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            {packageData.name}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Form */}
        <div className="lg:col-span-2">
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Couple Information
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Link to Wedding */}
              {weddings.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Link to Wedding (optional)
                  </label>
                  <select
                    value={formData.wedding_id}
                    onChange={(e) => handleWeddingSelect(e.target.value)}
                    className="w-full px-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="">Select a wedding...</option>
                    {weddings.map((wedding) => (
                      <option key={wedding.id || wedding._id} value={wedding.id || wedding._id}>
                        {wedding.couple_names} ({formatWeddingOptionDate(wedding.date)})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Partner 1 Name *
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      value={formData.partner1_name}
                      onChange={(e) => setFormData(prev => ({ ...prev, partner1_name: e.target.value }))}
                      placeholder="First partner's name"
                      className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Partner 2 Name
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      value={formData.partner2_name}
                      onChange={(e) => setFormData(prev => ({ ...prev, partner2_name: e.target.value }))}
                      placeholder="Second partner's name"
                      className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Email Address *
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                    placeholder="couple@email.com"
                    className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Phone Number
                  </label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                      placeholder="+1 (555) 000-0000"
                      className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Wedding Date
                  </label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="date"
                      value={formData.wedding_date}
                      onChange={(e) => setFormData(prev => ({ ...prev, wedding_date: e.target.value }))}
                      className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4">
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send size={18} />
                      Create Contract & Send
                    </>
                  )}
                </Button>
              </div>
            </form>
          </Card>
        </div>

        {/* Package Summary */}
        <div>
          <Card className="p-6 sticky top-6">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Package Summary
            </h2>

            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-slate-900 dark:text-white">
                  {packageData.name}
                </h3>
                {packageData.description && (
                  <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                    {packageData.description}
                  </p>
                )}
              </div>

              <div className="text-2xl font-bold text-primary-600 dark:text-primary-400">
                {formatCurrency(packageData.total_amount, packageData.currency)}
              </div>

              {/* Services */}
              {packageData.services?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-2">
                    <FileText size={14} />
                    Services Included
                  </h4>
                  <ul className="space-y-1">
                    {packageData.services.filter(s => s.included).map((service, index) => (
                      <li key={index} className="text-sm text-slate-600 dark:text-slate-400 flex items-start gap-2">
                        <CheckCircle size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                        {service.name}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Payment Schedule */}
              {packageData.payment_schedule?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2 flex items-center gap-2">
                    <DollarSign size={14} />
                    Payment Schedule
                  </h4>
                  <ul className="space-y-1">
                    {packageData.payment_schedule.map((payment, index) => (
                      <li key={index} className="text-sm text-slate-600 dark:text-slate-400">
                        {payment.name}: {payment.percentage}%
                        ({formatCurrency(packageData.total_amount * payment.percentage / 100, packageData.currency)})
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
