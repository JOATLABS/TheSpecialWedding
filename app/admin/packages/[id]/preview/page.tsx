'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getApiBaseUrl } from '@/utils/env';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import { Button } from '../../../../components/ui/Button';
import { Card } from '../../../../components/ui/Card';
import PackagePreview from '../../../../components/packages/PackagePreview';
import { ArrowLeft, Loader2, Edit, Send, Share2, Copy } from 'lucide-react';

interface PackageData {
  id: string;
  name: string;
  description?: string;
  total_amount: number;
  currency: string;
  status: string;
  services: Array<{ name: string; description?: string; included: boolean }>;
  payment_schedule: Array<{
    name: string;
    trigger: string;
    percentage?: number;
    amount?: number;
    days_after?: number;
    days_before?: number;
  }>;
  cancellation_policy?: string;
  late_payment_policy?: string;
  custom_terms?: string;
}

export default function PackagePreviewPage() {
  const params = useParams();
  const packageId = params.id as string;
  const { token, userProfile } = useAdmin();

  const [loading, setLoading] = useState(true);
  const [packageData, setPackageData] = useState<PackageData | null>(null);
  const [showShareModal, setShowShareModal] = useState(false);

  const fetchPackage = useCallback(async () => {
    if (!token || !packageId) return;

    setLoading(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/admin/packages/${packageId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch package');
      }

      const data = await response.json();
      setPackageData(data.package);
    } catch (err) {
      toast.error('Failed to load package');
    } finally {
      setLoading(false);
    }
  }, [token, packageId]);

  useEffect(() => {
    fetchPackage();
  }, [fetchPackage]);

  const getPreviewUrl = () => {
    if (typeof window === 'undefined') return '';
    return `${window.location.origin}/admin/packages/${packageId}/preview`;
  };

  const copyPreviewLink = () => {
    navigator.clipboard.writeText(getPreviewUrl());
    toast.success('Preview link copied!');
    setShowShareModal(false);
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
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Preview Package
          </h1>
        </div>
        <Card className="p-12 text-center">
          <p className="text-red-600 dark:text-red-400">Package not found</p>
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
            href={`/admin/packages/${packageId}/edit`}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              Preview
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-1">
              {packageData.name}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setShowShareModal(true)}
            className="flex items-center gap-2"
          >
            <Share2 size={16} />
            Share Preview
          </Button>
          <Link href={`/admin/packages/${packageId}/edit`}>
            <Button variant="outline" className="flex items-center gap-2">
              <Edit size={16} />
              Edit
            </Button>
          </Link>
          {packageData.status === 'active' && (
            <Link href={`/admin/packages/${packageId}/send`}>
              <Button className="flex items-center gap-2">
                <Send size={16} />
                Send to Couple
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Preview */}
      <PackagePreview
        name={packageData.name}
        description={packageData.description}
        total_amount={packageData.total_amount}
        currency={packageData.currency}
        services={packageData.services || []}
        payment_schedule={packageData.payment_schedule || []}
        cancellation_policy={packageData.cancellation_policy}
        late_payment_policy={packageData.late_payment_policy}
        custom_terms={packageData.custom_terms}
        plannerName={userProfile?.business_name || userProfile?.email}
      />

      {/* Share Modal */}
      {showShareModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Share Preview Link
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
              Share this link to let others preview how the package will appear to couples.
            </p>
            <div className="flex items-center gap-2 p-3 bg-slate-100 dark:bg-slate-800 rounded-lg mb-4">
              <input
                type="text"
                value={getPreviewUrl()}
                readOnly
                className="flex-1 bg-transparent text-sm text-slate-900 dark:text-white outline-none"
              />
              <Button size="sm" onClick={copyPreviewLink} className="flex items-center gap-1">
                <Copy size={14} />
                Copy
              </Button>
            </div>
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setShowShareModal(false)}>
                Close
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
