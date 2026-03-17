'use client';

import React from 'react';
import {
  DollarSign,
  CreditCard,
  Clock,
  FileText,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';

const NAVY = '#1D3557';
const SAGE = '#457B9D';
const GOLD = '#E9C46A';

export default function BillingPage() {
  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-bold" style={{ color: NAVY }}>
          Billing & Payments
        </h2>
        <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>
          Manage your advertising spend and payment methods
        </p>
      </div>

      {/* Notice banner */}
      <div
        className="rounded-xl p-4 mb-6 flex gap-3 items-start"
        style={{
          background: 'rgba(233,196,106,0.08)',
          border: '1px solid rgba(233,196,106,0.25)',
        }}
      >
        <AlertTriangle size={18} style={{ color: GOLD, flexShrink: 0, marginTop: 1 }} />
        <div className="text-xs leading-relaxed" style={{ color: '#78716c' }}>
          <strong style={{ color: NAVY }}>Billing is not yet active.</strong> During the
          current free tier period, all advertising features are available at no cost.
          When billing is introduced, you will be notified in advance. No charges will
          be applied retroactively.
        </div>
      </div>

      {/* Billing summary — all zeroed, no fake data */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div
          className="rounded-xl border p-4"
          style={{ background: '#fff', borderColor: '#cbd5e1', borderStyle: 'dashed' }}
        >
          <div className="flex items-center gap-2 mb-1">
            <DollarSign size={16} style={{ color: '#94a3b8' }} />
            <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: '#94a3b8' }}>
              Current Balance
            </span>
          </div>
          <div className="text-2xl font-extrabold" style={{ color: '#94a3b8' }}>$0.00</div>
          <p className="text-[11px] mt-1 italic" style={{ color: SAGE }}>Free tier</p>
        </div>
        <div
          className="rounded-xl border p-4"
          style={{ background: '#fff', borderColor: '#cbd5e1', borderStyle: 'dashed' }}
        >
          <div className="flex items-center gap-2 mb-1">
            <FileText size={16} style={{ color: '#94a3b8' }} />
            <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: '#94a3b8' }}>
              Total Spent
            </span>
          </div>
          <div className="text-2xl font-extrabold" style={{ color: '#94a3b8' }}>$0.00</div>
          <p className="text-[11px] mt-1 italic" style={{ color: SAGE }}>No charges</p>
        </div>
        <div
          className="rounded-xl border p-4"
          style={{ background: '#fff', borderColor: '#cbd5e1', borderStyle: 'dashed' }}
        >
          <div className="flex items-center gap-2 mb-1">
            <CreditCard size={16} style={{ color: '#94a3b8' }} />
            <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: '#94a3b8' }}>
              Payment Method
            </span>
          </div>
          <div className="text-lg font-extrabold" style={{ color: '#94a3b8' }}>None</div>
          <p className="text-[11px] mt-1 italic" style={{ color: SAGE }}>Not required yet</p>
        </div>
      </div>

      {/* What is tracked */}
      <div
        className="rounded-xl border p-5 mb-4"
        style={{ background: '#fff', borderColor: '#e2e8f0' }}
      >
        <h4 className="text-sm font-bold mb-3" style={{ color: NAVY }}>
          Usage Data Being Tracked
        </h4>
        <p className="text-xs mb-3" style={{ color: '#64748b' }}>
          The following metrics are already being captured and will feed into billing
          when it becomes active. This data is real and comes from your live campaigns.
        </p>
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs" style={{ color: '#475569' }}>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Impression counts per campaign</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Click counts per campaign</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Lead generation events</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>CPC and CPL bid values</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Daily and lifetime budget settings</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: '#16a34a' }} />
            <span>Daily rollup aggregations</span>
          </div>
        </div>
      </div>

      {/* What needs to be built */}
      <div
        className="rounded-xl border p-5"
        style={{ background: '#fff', borderColor: '#e2e8f0' }}
      >
        <h4 className="text-sm font-bold mb-3" style={{ color: NAVY }}>
          Coming Soon
        </h4>
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs" style={{ color: '#475569' }}>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Stripe payment method setup</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Automated invoice generation</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Budget enforcement and auto-pause</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock size={14} style={{ color: '#8b5cf6' }} />
            <span>Payment history and receipts</span>
          </div>
        </div>
      </div>
    </div>
  );
}
