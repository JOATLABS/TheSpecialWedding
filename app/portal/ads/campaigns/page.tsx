'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useVendorAuth } from '../layout';
import { toast } from 'sonner';
import {
  listVendorCampaigns,
  deleteCampaign,
  submitCampaignForReview,
  pauseVendorCampaign,
  getCampaignStatusLabel,
  getCampaignStatusColor,
  getCampaignGoalLabel,
  formatNumber,
  formatPercent,
  type AdCampaign,
} from '@/services/campaignAdvertisingApi';
import {
  Plus,
  Trash2,
  Send,
  Pause,
  Play,
  RefreshCw,
  Search,
  Filter,
  MoreHorizontal,
  Megaphone,
  Eye,
  MousePointerClick,
  Users,
  ChevronDown,
} from 'lucide-react';

export default function VendorCampaignsPage() {
  const { token } = useVendorAuth();
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const data = await listVendorCampaigns(token, {
        status: statusFilter || undefined,
        limit: 100,
      });
      setCampaigns(data);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSubmit = async (id: string) => {
    if (!token) return;
    try {
      setActionLoading(id);
      await submitCampaignForReview(token, id);
      toast.success('Campaign submitted for review');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); setOpenMenu(null); }
  };

  const handlePause = async (id: string) => {
    if (!token) return;
    try {
      setActionLoading(id);
      await pauseVendorCampaign(token, id);
      toast.success('Campaign paused');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); setOpenMenu(null); }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    if (!window.confirm('Delete this campaign? This action cannot be undone.')) return;
    try {
      setActionLoading(id);
      await deleteCampaign(token, id);
      toast.success('Campaign deleted');
      loadData();
    } catch (err: any) { toast.error(err.message); }
    finally { setActionLoading(null); setOpenMenu(null); }
  };

  const handlePauseConfirm = async (id: string) => {
    if (!window.confirm('Pause this campaign? It will stop receiving impressions until you resume it.')) return;
    handlePause(id);
  };

  const filtered = campaigns.filter((c) =>
    !searchQuery || c.campaign_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Campaigns</h1>
          <p className="text-sm text-slate-500 mt-1">Manage your advertising campaigns</p>
        </div>
        <Link
          href="/portal/ads/campaigns/new"
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={16} /> New Campaign
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search campaigns..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="pending_review">Pending Review</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="completed">Completed</option>
          <option value="rejected">Rejected</option>
        </select>
        <button onClick={loadData} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg">
          <RefreshCw size={16} className="text-slate-400" />
        </button>
      </div>

      {/* Campaign List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <RefreshCw size={24} className="animate-spin text-slate-400" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700">
          <Megaphone size={40} className="mx-auto text-slate-300 mb-3" />
          <h3 className="text-sm font-medium text-slate-900 dark:text-white">No campaigns found</h3>
          <p className="text-sm text-slate-500 mt-1">
            {statusFilter ? `No ${statusFilter.replace('_', ' ')} campaigns found. Try selecting a different status or clear your filter.` : 'Create your first campaign to get started.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((campaign) => {
            const ctr = campaign.impression_count > 0 ? campaign.click_count / campaign.impression_count : 0;
            return (
              <div key={campaign._id} className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-4 hover:border-primary-300 dark:hover:border-primary-700 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-base font-semibold text-slate-900 dark:text-white truncate">{campaign.campaign_name}</h3>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getCampaignStatusColor(campaign.status)}`}>
                        {getCampaignStatusLabel(campaign.status)}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 mb-2">{getCampaignGoalLabel(campaign.goal)}</p>
                    <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600 dark:text-slate-400">
                      <span className="flex items-center gap-1"><Eye size={14} /> {formatNumber(campaign.impression_count)}</span>
                      <span className="flex items-center gap-1"><MousePointerClick size={14} /> {formatNumber(campaign.click_count)}</span>
                      <span className="flex items-center gap-1"><Users size={14} /> {formatNumber(campaign.lead_count)} leads</span>
                      <span className="text-xs">{formatPercent(ctr)} CTR</span>
                    </div>
                    {campaign.review_notes && campaign.status === 'rejected' && (
                      <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-xs text-red-600 dark:text-red-400">
                        <strong>Review notes:</strong> {campaign.review_notes}
                      </div>
                    )}
                  </div>

                  {/* Actions Menu */}
                  <div className="relative ml-3">
                    <button
                      onClick={() => setOpenMenu(openMenu === campaign._id ? null : campaign._id)}
                      className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
                    >
                      <MoreHorizontal size={16} className="text-slate-400" />
                    </button>
                    {openMenu === campaign._id && (
                      <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-10">
                        {campaign.status === 'draft' && (
                          <>
                            <button
                              onClick={() => handleSubmit(campaign._id)}
                              disabled={actionLoading === campaign._id}
                              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
                            >
                              <Send size={14} /> Submit for Review
                            </button>
                            <button
                              onClick={() => handleDelete(campaign._id)}
                              disabled={actionLoading === campaign._id}
                              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
                            >
                              <Trash2 size={14} /> Delete
                            </button>
                          </>
                        )}
                        {campaign.status === 'active' && (
                          <button
                            onClick={() => handlePauseConfirm(campaign._id)}
                            disabled={actionLoading === campaign._id}
                            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
                          >
                            <Pause size={14} /> Pause Campaign
                          </button>
                        )}
                        {campaign.status === 'rejected' && (
                          <button
                            onClick={() => handleSubmit(campaign._id)}
                            disabled={actionLoading === campaign._id}
                            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50"
                          >
                            <Send size={14} /> Edit &amp; Re-submit
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
