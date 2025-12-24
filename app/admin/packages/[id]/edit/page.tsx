'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Card } from '../../../../components/ui/Card';
import PackageForm, { type PackageFormData } from '../../../../components/packages/PackageForm';
import { ArrowLeft, Loader2, Eye } from 'lucide-react';
import { Button } from '../../../../components/ui/Button';

export default function EditPackagePage() {
  const router = useRouter();
  const params = useParams();
  const packageId = params.id as string;
  const { token } = useAdmin();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [packageData, setPackageData] = useState<PackageFormData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchPackage = useCallback(async () => {
    if (!token || !packageId) return;

    setLoading(true);
    setError('');

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/${packageId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch package');
      }

      const data = await response.json();
      const pkg = data.package;

      setPackageData({
        name: pkg.name || '',
        description: pkg.description || '',
        services: pkg.services || [],
        total_amount: pkg.total_amount || 0,
        currency: pkg.currency || 'usd',
        payment_schedule: pkg.payment_schedule || [],
        cancellation_policy: pkg.cancellation_policy || '',
        late_payment_policy: pkg.late_payment_policy || '',
        custom_terms: pkg.custom_terms || '',
        is_template: pkg.is_template || false
      });
    } catch (err) {
      setError('Failed to load package');
      toast.error('Failed to load package');
    } finally {
      setLoading(false);
    }
  }, [token, packageId]);

  useEffect(() => {
    fetchPackage();
  }, [fetchPackage]);

  const handleSubmit = async (data: PackageFormData, status: 'draft' | 'active') => {
    if (!token || !packageId) {
      toast.error('Not authenticated');
      return;
    }

    setIsSubmitting(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/${packageId}`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...data,
          status
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update package');
      }

      toast.success(`Package ${status === 'active' ? 'saved and activated' : 'saved'}`);
      fetchPackage(); // Refresh data
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update package';
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    );
  }

  if (error || !packageData) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            href="/admin/packages"
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Edit Package
          </h1>
        </div>

        <Card className="p-12 text-center">
          <p className="text-red-600 dark:text-red-400">{error || 'Package not found'}</p>
          <Link href="/admin/packages" className="text-primary-600 hover:underline mt-4 inline-block">
            Back to Packages
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/admin/packages"
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              Edit Package
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-1">
              {packageData.name}
            </p>
          </div>
        </div>
        <Link href={`/admin/packages/${packageId}/preview`}>
          <Button variant="outline" className="flex items-center gap-2">
            <Eye size={16} />
            Preview
          </Button>
        </Link>
      </div>

      {/* Form */}
      <PackageForm
        initialData={packageData}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        mode="edit"
        token={token || undefined}
      />
    </div>
  );
}
