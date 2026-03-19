'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';
import {
  getAdLeads,
  updateAdLeadStatus,
  type AdLead,
  type LeadStatus,
} from '@/services/advertisingApi';
import {
  Loader2,
  MessageSquare,
  Clock,
  CheckCircle2,
  Phone,
  ArrowRight,
  Users,
} from 'lucide-react';

const NAVY = '#1D3557';
const SAGE = '#457B9D';

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending: { label: 'Pending', color: '#8b5cf6' },
  contacted: { label: 'Contacted', color: '#3b82f6' },
  responded: { label: 'Responded', color: '#f59e0b' },
  converted: { label: 'Converted', color: '#16a34a' },
  closed: { label: 'Closed', color: '#94a3b8' },
};

const LEAD_TYPE_LABELS: Record<string, string> = {
  quote_request: 'Quote Request',
  message: 'Message',
  add_to_wedding: 'Added to Wedding',
  vendor_invite: 'Vendor Invite',
};

export default function LeadsPage() {
  const { token } = useAdmin();
  const [leads, setLeads] = useState<AdLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<LeadStatus | ''>('');

  const fetchLeads = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await getAdLeads(token, {
        status: statusFilter || undefined,
        limit: 50,
      });
      setLeads(data);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load leads');
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold" style={{ color: NAVY }}>
            Ad Leads
          </h2>
          <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>
            Planner inquiries and interactions from your sponsored ads
          </p>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as LeadStatus | '')}
          className="px-3 py-2 border rounded-lg text-xs"
          style={{ borderColor: '#e2e8f0', color: '#64748b', minHeight: 44 }}
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="contacted">Contacted</option>
          <option value="responded">Responded</option>
          <option value="converted">Converted</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {/* Lead list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="animate-spin mr-2" size={20} style={{ color: SAGE }} />
          <span className="text-sm" style={{ color: '#64748b' }}>Loading leads...</span>
        </div>
      ) : leads.length === 0 ? (
        <div className="text-center py-16 rounded-xl border" style={{ background: '#fff', borderColor: '#e2e8f0' }}>
          <Users size={36} className="mx-auto mb-3" style={{ color: '#cbd5e1' }} />
          <p className="text-sm font-bold" style={{ color: NAVY }}>
            No leads yet
          </p>
          <p className="text-xs mt-1" style={{ color: '#64748b' }}>
            Leads will appear here when planners interact with your sponsored ads.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {leads.map((lead) => {
            const id = String(lead._id);
            const statusInfo = STATUS_CONFIG[lead.status] || STATUS_CONFIG.pending;
            return (
              <div
                key={id}
                className="p-4 rounded-xl border"
                style={{ background: '#fff', borderColor: '#e2e8f0' }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold"
                        style={{
                          background: `${statusInfo.color}15`,
                          color: statusInfo.color,
                        }}
                      >
                        {statusInfo.label}
                      </span>
                      <span
                        className="text-[10px] font-semibold px-2 py-0.5 rounded"
                        style={{ background: '#f1f5f9', color: '#64748b' }}
                      >
                        {LEAD_TYPE_LABELS[lead.lead_type] || lead.lead_type}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: NAVY }}>
                      <strong>From:</strong> {lead.planner_id}
                    </p>
                    {lead.message && (
                      <p className="text-[11px] mt-1 line-clamp-2" style={{ color: '#475569' }}>
                        {lead.message}
                      </p>
                    )}
                    {lead.quote_amount != null && lead.quote_amount > 0 && (
                      <p className="text-[11px] mt-1 font-semibold" style={{ color: SAGE }}>
                        Quote: ${lead.quote_amount.toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="text-right text-[10px] flex-shrink-0" style={{ color: '#94a3b8' }}>
                    {lead.created_at && (
                      <p>{new Date(lead.created_at).toLocaleDateString()}</p>
                    )}
                    {lead.responded_at && (
                      <p className="mt-0.5" style={{ color: '#16a34a' }}>
                        Responded {new Date(lead.responded_at).toLocaleDateString()}
                      </p>
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
