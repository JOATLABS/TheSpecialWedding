'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useVendorAuth } from '../components/VendorAuthContext';
import { toast } from 'sonner';
import { getVendorLeads, formatNumber } from '@/services/campaignAdvertisingApi';
import {
  Users,
  Mail,
  MessageSquare,
  FolderPlus,
  RefreshCw,
  Filter,
  Clock,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

interface Lead {
  _id: string;
  campaign_id: string;
  planner_email: string;
  planner_name?: string;
  lead_type: string;
  status: string;
  message?: string;
  wedding_id?: string;
  wedding_context?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export default function VendorLeadsPage() {
  const { token } = useVendorAuth();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const data = await getVendorLeads(token, {
        status: statusFilter || undefined,
        lead_type: typeFilter || undefined,
        limit: 100,
      });
      setLeads(data);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, typeFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const getTypeLabel = (type: string): string => {
    switch (type) {
      case 'quote_request': return 'Quote Request';
      case 'add_to_directory': return 'Added to Directory';
      case 'message': return 'Direct Message';
      default: return type.replace(/_/g, ' ');
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'quote_request': return <MessageSquare size={14} className="text-blue-500" />;
      case 'add_to_directory': return <FolderPlus size={14} className="text-emerald-500" />;
      case 'message': return <Mail size={14} className="text-purple-500" />;
      default: return <Users size={14} className="text-slate-400" />;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <Clock size={14} className="text-amber-500" />;
      case 'contacted': return <Mail size={14} className="text-blue-500" />;
      case 'responded': return <CheckCircle2 size={14} className="text-emerald-500" />;
      case 'converted': return <CheckCircle2 size={14} className="text-emerald-600" />;
      case 'closed': return <XCircle size={14} className="text-slate-400" />;
      default: return <Clock size={14} className="text-slate-400" />;
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <RefreshCw size={24} className="animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Leads</h1>
        <p className="text-sm text-slate-500 mt-1">Wedding planners who interacted with your ads</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="contacted">Contacted</option>
          <option value="responded">Responded</option>
          <option value="converted">Converted</option>
          <option value="closed">Closed</option>
        </select>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800"
        >
          <option value="">All Types</option>
          <option value="quote_request">Quote Requests</option>
          <option value="add_to_directory">Directory Adds</option>
          <option value="message">Messages</option>
        </select>
        <button onClick={loadData} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg">
          <RefreshCw size={16} className="text-slate-400" />
        </button>
        <span className="text-sm text-slate-500">{leads.length} lead{leads.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Leads List */}
      {leads.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700">
          <Users size={40} className="mx-auto text-slate-300 mb-3" />
          <h3 className="text-sm font-medium text-slate-900 dark:text-white">No leads yet</h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">Leads appear when wedding planners click your ads, request quotes, or send messages. Make sure you have an active campaign running!</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700">
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Planner</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Type</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Message</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-slate-500 uppercase">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {leads.map((lead) => (
                  <tr key={lead._id} className="hover:bg-slate-50 dark:hover:bg-slate-700/50">
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-900 dark:text-white">{lead.planner_name || lead.planner_email}</p>
                      {lead.planner_name && (
                        <a href={`mailto:${lead.planner_email}`} className="text-xs text-primary-500 hover:underline">{lead.planner_email}</a>
                      )}
                      {!lead.planner_name && (
                        <a href={`mailto:${lead.planner_email}`} className="sr-only">Email {lead.planner_email}</a>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5">
                        {getTypeIcon(lead.lead_type)}
                        <span className="text-slate-600 dark:text-slate-300">{getTypeLabel(lead.lead_type)}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5">
                        {getStatusIcon(lead.status)}
                        <span className="capitalize text-slate-600 dark:text-slate-300">{lead.status}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 max-w-[250px]">
                      <p className="text-slate-500 truncate">{lead.message || '—'}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      {new Date(lead.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
