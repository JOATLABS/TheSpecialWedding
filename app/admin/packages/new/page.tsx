'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Card } from '../../../components/ui/Card';
import PackageForm, { type PackageFormData } from '../../../components/packages/PackageForm';
import { ArrowLeft } from 'lucide-react';

export default function NewPackagePage() {
  const router = useRouter();
  const { token } = useAdmin();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (data: PackageFormData, status: 'draft' | 'active') => {
    if (!token) {
      toast.error('Not authenticated');
      return;
    }

    setIsSubmitting(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages`, {
        method: 'POST',
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
        throw new Error(errorData.detail || 'Failed to create package');
      }

      const result = await response.json();
      toast.success(`Package ${status === 'active' ? 'created and activated' : 'saved as draft'}`);
      router.push(`/admin/packages/${result.package.id}/edit`);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create package';
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

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
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Create Package
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Define your wedding service package
          </p>
        </div>
      </div>

      {/* Form */}
      <PackageForm
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        token={token || undefined}
        mode="create"
      />
    </div>
  );
}
