'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import RootAdminGuard from '@/components/RootAdminGuard';
import { toast } from 'sonner';
import {
  getFeatureFlag,
  toggleFeatureFlag,
  updateFeatureFlagConfig,
  triggerRollup,
  backfillRollups,
  type FeatureFlagConfig,
} from '@/services/advertisingApi';
import {
  Loader2,
  Database,
  RefreshCw,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------
export default function ConfigPage() {
  return (
    <RootAdminGuard>
      <ConfigContent />
    </RootAdminGuard>
  );
}

function ConfigContent() {
  const { token } = useAdmin();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* Page header */}
      <div className="sticky top-0 z-50 flex items-center px-6 border-b bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700" style={{ height: 56 }}>
        <h1 className="text-slate-900 dark:text-white font-bold text-lg">
          Ad System Configuration
        </h1>
      </div>

      <div className="p-6">
        <SystemConfigTab token={token} />
      </div>
    </div>
  );
}

// ===========================================================================
// SYSTEM CONFIG TAB CONTENT
// ===========================================================================

function SystemConfigTab({ token }: { token: string | null }) {
  const [featureFlag, setFeatureFlag] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const flag = await getFeatureFlag(token);
      setFeatureFlag(flag);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load config');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleToggleFeature = async () => {
    if (!token || !featureFlag) return;
    setSaving(true);
    try {
      const updated = await toggleFeatureFlag(token, !featureFlag.is_enabled);
      setFeatureFlag(updated);
      toast.success(
        updated.is_enabled
          ? 'Advertising feature enabled'
          : 'Advertising feature disabled'
      );
    } catch (err: any) {
      toast.error(err.message || 'Failed to toggle feature');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateConfig = async (key: string, value: any) => {
    if (!token) return;
    setSaving(true);
    try {
      const updated = await updateFeatureFlagConfig(token, { [key]: value });
      setFeatureFlag(updated);
      toast.success('Configuration updated');
    } catch (err: any) {
      toast.error(err.message || 'Failed to update config');
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerRollup = async () => {
    if (!token) return;
    setSaving(true);
    try {
      const result = await triggerRollup(token);
      toast.success(
        `Rollup completed: ${result.documents_upserted} documents processed`
      );
    } catch (err: any) {
      toast.error(err.message || 'Failed to trigger rollup');
    } finally {
      setSaving(false);
    }
  };

  const handleBackfill = async () => {
    if (!token) return;
    setSaving(true);
    try {
      const result = await backfillRollups(token, 90);
      toast.success(
        `Backfill completed: ${result.total_documents} documents over ${result.days_backfilled} days`
      );
    } catch (err: any) {
      toast.error(err.message || 'Failed to backfill');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="animate-spin mr-2 text-wedding-sage" size={20} />
        <span className="text-sm text-slate-500 dark:text-slate-400">
          Loading configuration...
        </span>
      </div>
    );
  }

  const config = featureFlag?.config || {};

  return (
    <div className="space-y-4">
      {/* Feature Flags */}
      <ConfigSection title="Feature Flags" desc="Core advertising feature controls">
        <ConfigToggleRow
          label="Ads Enabled"
          hint="Master switch for all advertising features"
          enabled={featureFlag?.is_enabled || false}
          onChange={handleToggleFeature}
          saving={saving}
        />
        <ConfigToggleRow
          label="Show Sponsored Badge"
          hint="Display 'Sponsored' label on ad cards"
          enabled={config.show_sponsored_badge ?? true}
          onChange={() =>
            handleUpdateConfig(
              'show_sponsored_badge',
              !(config.show_sponsored_badge ?? true)
            )
          }
          saving={saving}
        />
        <ConfigToggleRow
          label="Enable Tracking"
          hint="Track impressions, clicks, and events"
          enabled={config.enable_tracking ?? true}
          onChange={() =>
            handleUpdateConfig(
              'enable_tracking',
              !(config.enable_tracking ?? true)
            )
          }
          saving={saving}
        />
      </ConfigSection>

      {/* Serving Limits */}
      <ConfigSection title="Serving Limits" desc="Control ad delivery volume">
        <ConfigValueRow
          label="Max Ads Per Page"
          value={config.max_sponsored_per_page ?? 3}
          onSave={(v) => handleUpdateConfig('max_sponsored_per_page', Number(v))}
          saving={saving}
        />
        <ConfigValueRow
          label="Impressions Per Session"
          value={config.impressions_per_session_limit ?? 5}
          onSave={(v) =>
            handleUpdateConfig('impressions_per_session_limit', Number(v))
          }
          saving={saving}
        />
        <ConfigValueRow
          label="Min Priority Threshold"
          value={config.min_priority_threshold ?? 1}
          onSave={(v) => handleUpdateConfig('min_priority_threshold', Number(v))}
          saving={saving}
        />
      </ConfigSection>

      {/* Review Workflow */}
      <ConfigSection title="Review Workflow" desc="Campaign approval settings">
        <ConfigToggleRow
          label="Require Review"
          hint="All new campaigns require admin review before going live"
          enabled={config.require_review ?? true}
          onChange={() =>
            handleUpdateConfig('require_review', !(config.require_review ?? true))
          }
          saving={saving}
        />
        <ConfigToggleRow
          label="Auto-Approve Returning Vendors"
          hint="Skip review for vendors with previously approved campaigns"
          enabled={config.auto_approve_returning_vendors ?? false}
          onChange={() =>
            handleUpdateConfig(
              'auto_approve_returning_vendors',
              !(config.auto_approve_returning_vendors ?? false)
            )
          }
          saving={saving}
        />
        <ConfigValueRow
          label="Review SLA (hours)"
          value={config.review_sla_hours ?? 48}
          onSave={(v) => handleUpdateConfig('review_sla_hours', Number(v))}
          saving={saving}
        />
      </ConfigSection>

      {/* Data Pipeline Controls */}
      <ConfigSection title="Data Pipeline Controls" desc="Manage rollup computation and backfill">
        <div className="flex items-center justify-between py-3">
          <div>
            <p className="text-[13px] font-medium text-wedding-navy dark:text-white">
              Manual Rollup
            </p>
            <p className="text-[10px] text-slate-400 dark:text-slate-500">
              Compute daily stats rollup for yesterday
            </p>
          </div>
          <button
            onClick={handleTriggerRollup}
            disabled={saving}
            className="px-3.5 py-1.5 rounded-md text-[11px] font-semibold text-white bg-wedding-sage hover:bg-wedding-navy"
            style={{ minHeight: 44 }}
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <span className="flex items-center gap-1.5">
                <Database size={12} /> Run Rollup
              </span>
            )}
          </button>
        </div>
        <div className="flex items-center justify-between py-3 border-t border-slate-100 dark:border-slate-700">
          <div>
            <p className="text-[13px] font-medium text-wedding-navy dark:text-white">
              Backfill (90 days)
            </p>
            <p className="text-[10px] text-slate-400 dark:text-slate-500">
              Recompute rollup data for the last 90 days
            </p>
          </div>
          <button
            onClick={handleBackfill}
            disabled={saving}
            className="px-3.5 py-1.5 rounded-md text-[11px] font-semibold border bg-slate-100 dark:bg-slate-700/50 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-600"
            style={{ minHeight: 44 }}
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <span className="flex items-center gap-1.5">
                <RefreshCw size={12} /> Backfill
              </span>
            )}
          </button>
        </div>
      </ConfigSection>
    </div>
  );
}

// ===========================================================================
// SUB-COMPONENTS
// ===========================================================================

function ConfigSection({
  title,
  desc,
  children,
}: {
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 p-5">
      <h4 className="text-sm font-bold text-wedding-navy dark:text-white">
        {title}
      </h4>
      <p className="text-xs mb-3 text-slate-500 dark:text-slate-400">
        {desc}
      </p>
      {children}
    </div>
  );
}

function ConfigToggleRow({
  label,
  hint,
  enabled,
  onChange,
  saving,
}: {
  label: string;
  hint?: string;
  enabled: boolean;
  onChange: () => void;
  saving: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-100 dark:border-slate-700">
      <div>
        <p className="text-[13px] font-medium text-wedding-navy dark:text-white">
          {label}
        </p>
        {hint && (
          <p className="text-[10px] text-slate-400 dark:text-slate-500">
            {hint}
          </p>
        )}
      </div>
      <button
        onClick={onChange}
        disabled={saving}
        className="relative rounded-full transition-colors"
        style={{
          width: 40,
          height: 22,
          background: enabled ? 'var(--color-wedding-sage, #457B9D)' : '#cbd5e1',
          minHeight: 22,
          flexShrink: 0,
        }}
      >
        <span
          className="absolute top-0.5 rounded-full bg-white shadow transition-transform"
          style={{
            width: 18,
            height: 18,
            left: 2,
            transform: enabled ? 'translateX(18px)' : 'translateX(0)',
          }}
        />
      </button>
    </div>
  );
}

function ConfigValueRow({
  label,
  value,
  onSave,
  saving,
}: {
  label: string;
  value: number;
  onSave: (val: string) => void;
  saving: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [editVal, setEditVal] = useState(String(value));

  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-100 dark:border-slate-700">
      <p className="text-[13px] font-medium text-wedding-navy dark:text-white">
        {label}
      </p>
      {editing ? (
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={editVal}
            onChange={(e) => setEditVal(e.target.value)}
            className="w-16 px-2 py-1 border border-slate-200 dark:border-slate-600 rounded text-xs text-right bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
            style={{ minHeight: 32 }}
          />
          <button
            onClick={() => {
              onSave(editVal);
              setEditing(false);
            }}
            disabled={saving}
            className="px-2 py-1 rounded text-[10px] font-semibold text-white bg-wedding-sage hover:bg-wedding-navy"
            style={{ minHeight: 32 }}
          >
            Save
          </button>
          <button
            onClick={() => {
              setEditVal(String(value));
              setEditing(false);
            }}
            className="px-2 py-1 rounded text-[10px] font-semibold border border-slate-200 dark:border-slate-600 bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
            style={{ minHeight: 32 }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setEditing(true)}
          className="text-[13px] font-semibold cursor-pointer hover:underline text-wedding-sage"
        >
          {value}
        </button>
      )}
    </div>
  );
}
