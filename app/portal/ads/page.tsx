'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useVendorAuth } from './components/VendorAuthContext';
import { toast } from 'sonner';
import PageHeader from '@/components/ui/PageHeader';
import {
  listVendorCampaigns,
  getVendorLeads,
  getCampaignStatusLabel,
  getCampaignStatusColor,
  formatNumber,
  formatPercent,
  type AdCampaign,
} from '@/services/campaignAdvertisingApi';
import {
  Megaphone,
  Eye,
  MousePointerClick,
  Users,
  Plus,
  ArrowRight,
  RefreshCw,
  BarChart3,
  type LucideIcon,
} from 'lucide-react';

export default function VendorOverviewPage() {
  const { token, user } = useVendorAuth();
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [leadCount, setLeadCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const [campaignData, leadsData] = await Promise.all([
        listVendorCampaigns(token, { limit: 50 }),
        getVendorLeads(token, { limit: 100 }),
      ]);
      setCampaigns(campaignData);
      setLeadCount(leadsData.length);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadData(); }, [loadData]);

  // Aggregate stats
  const activeCampaigns = campaigns.filter((c) => c.status === 'active');
  const totalImpressions = campaigns.reduce((sum, c) => sum + c.impression_count, 0);
  const totalClicks = campaigns.reduce((sum, c) => sum + c.click_count, 0);
  const totalLeads = campaigns.reduce((sum, c) => sum + c.lead_count, 0);
  const avgCtr = totalImpressions > 0 ? totalClicks / totalImpressions : 0;

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <RefreshCw size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description={
          user?.name
            ? `Manage ${user.name}'s campaigns, creative assets, and incoming leads from one workspace.`
            : 'Manage campaigns, creative assets, and incoming leads from one workspace.'
        }
      >
        <Link
          href="/portal/ads/campaigns/new"
          className="inline-flex items-center gap-2 rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-600"
        >
          <Plus size={16} />
          Create Campaign
        </Link>
      </PageHeader>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/95">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">
              Campaign performance at a glance
            </p>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Keep campaign spend, creative performance, and incoming leads in one focused workspace.
            </p>
          </div>
          <Link
            href="/portal/ads/settings"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary-500 transition-colors hover:text-primary-600"
          >
            Review business profile
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <KPICard label="Active Campaigns" value={activeCampaigns.length} icon={Megaphone} color="text-primary-500" />
        <KPICard label="Impressions" value={formatNumber(totalImpressions)} icon={Eye} color="text-blue-500" />
        <KPICard label="Clicks" value={formatNumber(totalClicks)} icon={MousePointerClick} color="text-purple-500" />
        <KPICard label="Leads" value={formatNumber(totalLeads)} icon={Users} color="text-amber-500" />
        <KPICard label="Avg CTR" value={formatPercent(avgCtr)} icon={BarChart3} color="text-emerald-500" />
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/95">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Your Campaigns</h2>
          <Link
            href="/portal/ads/campaigns"
            className="text-sm text-primary-500 hover:text-primary-600 flex items-center gap-1"
          >
            View All <ArrowRight size={14} />
          </Link>
        </div>

        {campaigns.length === 0 ? (
          <div className="text-center py-8">
            <Megaphone size={40} className="mx-auto text-slate-300 mb-3" />
            <h3 className="text-sm font-medium text-slate-900 dark:text-white">No campaigns yet</h3>
            <p className="text-sm text-slate-500 mt-1">Create your first campaign to start reaching wedding planners.</p>
            <Link
              href="/portal/ads/campaigns/new"
              className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-600"
            >
              <Plus size={14} /> Create Campaign
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {campaigns.slice(0, 5).map((campaign) => {
              const ctr = campaign.impression_count > 0
                ? (campaign.click_count / campaign.impression_count)
                : 0;
              return (
                <Link
                  key={campaign._id}
                  href={`/portal/ads/campaigns`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900 dark:text-white truncate">
                        {campaign.campaign_name}
                      </span>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getCampaignStatusColor(campaign.status)}`}>
                        {getCampaignStatusLabel(campaign.status)}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-xs text-slate-500">
                      <span>{formatNumber(campaign.impression_count)} impressions</span>
                      <span>{formatNumber(campaign.click_count)} clicks</span>
                      <span>{formatPercent(ctr)} CTR</span>
                    </div>
                  </div>
                  <ArrowRight size={16} className="text-slate-400" />
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Quick Stats: Lead Funnel */}
      {totalLeads > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800/95">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Lead Funnel</h2>
          <div className="flex items-center gap-2">
            <FunnelStep label="Impressions" value={totalImpressions} color="bg-blue-500" />
            <span className="text-slate-300">&rarr;</span>
            <FunnelStep label="Clicks" value={totalClicks} color="bg-purple-500" />
            <span className="text-slate-300">&rarr;</span>
            <FunnelStep label="Leads" value={totalLeads} color="bg-amber-500" />
            <span className="text-slate-300">&rarr;</span>
            <FunnelStep label="Conversions" value={campaigns.reduce((s, c) => s + c.conversion_count, 0)} color="bg-emerald-500" />
          </div>
        </div>
      )}
    </div>
  );
}

function KPICard({ label, value, icon: Icon, color }: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800/95">
      <div className={`p-2 rounded-lg bg-slate-50 dark:bg-slate-700 w-fit ${color}`}>
        <Icon size={18} />
      </div>
      <p className="text-xl font-bold text-slate-900 dark:text-white mt-2">{value}</p>
      <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
    </div>
  );
}

function FunnelStep({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex-1 text-center">
      <div className={`h-2 rounded-full ${color} mb-2`} />
      <p className="text-lg font-bold text-slate-900 dark:text-white">{formatNumber(value)}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}
