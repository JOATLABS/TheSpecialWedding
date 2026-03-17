'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import {
  getSponsoredVendors,
  getAdPlacementLabel,
  type SponsoredVendor,
} from '@/services/advertisingApi';
import {
  Plus,
  Loader2,
  Eye,
  EyeOff,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Megaphone,
} from 'lucide-react';

const NAVY = '#1D3557';
const SAGE = '#457B9D';

export default function CampaignsPage() {
  const { token, userProfile } = useAdmin();
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<SponsoredVendor[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchCampaigns = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await getSponsoredVendors(token, { limit: 100 });
      setCampaigns(data);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  const getStatusInfo = (campaign: SponsoredVendor) => {
    const reviewStatus = (campaign as any).review_status;
    if (reviewStatus === 'pending_review') {
      return { label: 'Pending Review', color: '#8b5cf6', icon: <Clock size={12} /> };
    }
    if (reviewStatus === 'rejected') {
      return { label: 'Rejected', color: '#dc2626', icon: <XCircle size={12} /> };
    }
    if (reviewStatus === 'changes_requested') {
      return { label: 'Changes Requested', color: '#f59e0b', icon: <AlertTriangle size={12} /> };
    }
    if (campaign.is_active) {
      return { label: 'Active', color: '#16a34a', icon: <CheckCircle2 size={12} /> };
    }
    return { label: 'Inactive', color: '#94a3b8', icon: <EyeOff size={12} /> };
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold" style={{ color: NAVY }}>
            My Campaigns
          </h2>
          <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>
            View and manage your advertising campaigns
          </p>
        </div>
        <button
          onClick={() => router.push('/admin/vendor/ads/campaigns/new')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white"
          style={{ background: SAGE, minHeight: 44 }}
        >
          <Plus size={16} />
          New Campaign
        </button>
      </div>

      {/* Campaign list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="animate-spin mr-2" size={20} style={{ color: SAGE }} />
          <span className="text-sm" style={{ color: '#64748b' }}>Loading campaigns...</span>
        </div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-16 rounded-xl border" style={{ background: '#fff', borderColor: '#e2e8f0' }}>
          <Megaphone size={36} className="mx-auto mb-3" style={{ color: '#cbd5e1' }} />
          <p className="text-sm font-bold" style={{ color: NAVY }}>
            No campaigns yet
          </p>
          <p className="text-xs mt-1 mb-4" style={{ color: '#64748b' }}>
            Create your first advertising campaign to start reaching wedding planners.
          </p>
          <button
            onClick={() => router.push('/admin/vendor/ads/campaigns/new')}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
            style={{ background: SAGE, minHeight: 44 }}
          >
            Create Campaign
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((campaign) => {
            const id = String(campaign._id);
            const status = getStatusInfo(campaign);
            return (
              <div
                key={id}
                className="flex items-center gap-4 p-4 rounded-xl border"
                style={{ background: '#fff', borderColor: '#e2e8f0' }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold truncate" style={{ color: NAVY }}>
                      {campaign.headline || 'Untitled Campaign'}
                    </p>
                    <span
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold"
                      style={{ background: `${status.color}15`, color: status.color }}
                    >
                      {status.icon}
                      {status.label}
                    </span>
                  </div>
                  <p className="text-[11px] mt-0.5" style={{ color: '#64748b' }}>
                    {getAdPlacementLabel(campaign.placement as any)}
                    {' | '}
                    Priority: {campaign.priority}
                    {campaign.start_date && (
                      <> | Start: {new Date(campaign.start_date).toLocaleDateString()}</>
                    )}
                  </p>
                </div>
                <div className="text-right text-xs" style={{ color: '#64748b' }}>
                  <p>{(campaign.impression_count || 0).toLocaleString()} impressions</p>
                  <p>{(campaign.click_count || 0).toLocaleString()} clicks</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
