'use client';

import { useAdmin } from '@/contexts/AdminContext';
import { motion } from 'framer-motion';
import PageHeader from '../../components/PageHeader';
import RootAdminGuard from '@/components/RootAdminGuard';
import {
  DollarSign,
  Activity,
  MousePointerClick,
  Target,
  CheckCircle2,
  Clock,
  AlertTriangle,
} from 'lucide-react';

export default function RevenuePage() {
  return (
    <RootAdminGuard>
      <RevenueContent />
    </RootAdminGuard>
  );
}

function RevenueContent() {
  const { token } = useAdmin();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Revenue & Billing"
        description="Track billing and revenue data"
      />

      {/* Warning Banner */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl bg-amber-500/10 border border-amber-500/20 backdrop-blur-sm p-6 flex gap-4"
      >
        <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-white mb-1">Billing is not active</p>
          <p className="text-sm text-slate-400">
            Revenue tracking will be enabled once Stripe billing integration is built. All monetary values shown below are $0 — this section is a placeholder for the eventual billing infrastructure. No fake data is displayed.
          </p>
        </div>
      </motion.div>

      {/* Revenue Metrics - All Zeroed with Dashed Borders */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border-2 border-dashed border-white/20 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-500/10 to-cyan-500/10 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
              <DollarSign className="w-7 h-7 text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Total Revenue</p>
              <p className="text-4xl font-bold text-slate-500">$0</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border-2 border-dashed border-white/20 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-emerald-500/10 to-green-500/10 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <Activity className="w-7 h-7 text-emerald-400" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Active Invoices</p>
              <p className="text-4xl font-bold text-slate-500">0</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border-2 border-dashed border-white/20 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-violet-500/10 to-purple-500/10 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
              <MousePointerClick className="w-7 h-7 text-violet-400" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Avg CPC</p>
              <p className="text-4xl font-bold text-slate-500">$0.00</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border-2 border-dashed border-white/20 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-amber-500/10 to-yellow-500/10 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
              <Target className="w-7 h-7 text-amber-400" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Avg CPL</p>
              <p className="text-4xl font-bold text-slate-500">$0.00</p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Data Already Being Captured */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <h3 className="text-lg font-semibold text-white">Data Already Being Captured</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-slate-400">pricing_model (cpc, cpl, flat_monthly)</span>
          </div>
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-slate-400">cpc_bid and cpl_bid per campaign</span>
          </div>
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-slate-400">daily_budget and lifetime_budget</span>
          </div>
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-slate-400">Click and lead event tracking</span>
          </div>
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-slate-400">Rollup aggregation pipeline</span>
          </div>
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
            <span className="text-slate-400">Vendor leaderboard with impressions/clicks/leads</span>
          </div>
        </div>
      </motion.div>

      {/* Needs to Be Built */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <Clock className="w-5 h-5 text-violet-400" />
          <h3 className="text-lg font-semibold text-white">Needs to Be Built</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex items-center gap-3">
            <Clock className="w-4 h-4 text-violet-400 flex-shrink-0" />
            <span className="text-slate-400">Stripe billing integration</span>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="w-4 h-4 text-violet-400 flex-shrink-0" />
            <span className="text-slate-400">Usage metering (click/lead consumption records)</span>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="w-4 h-4 text-violet-400 flex-shrink-0" />
            <span className="text-slate-400">Budget enforcement (pause when exhausted)</span>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="w-4 h-4 text-violet-400 flex-shrink-0" />
            <span className="text-slate-400">Invoice generation and history</span>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="w-4 h-4 text-violet-400 flex-shrink-0" />
            <span className="text-slate-400">Webhook handlers for payment events</span>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="w-4 h-4 text-violet-400 flex-shrink-0" />
            <span className="text-slate-400">Revenue dashboard with real calculations</span>
          </div>
        </div>
      </motion.div>

      {/* Implementation Note */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7 }}
        className="rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6"
      >
        <p className="text-sm text-slate-400 leading-relaxed">
          <strong className="text-white">Implementation note:</strong> This section will become functional once the Stripe integration is connected. The pricing data (CPC bids, CPL bids, daily budgets) is already stored per campaign in metadata. The billing system will read these values, multiply by real event counts from the rollup pipeline, and produce invoices. No synthetic data will be generated.
        </p>
      </motion.div>
    </div>
  );
}
