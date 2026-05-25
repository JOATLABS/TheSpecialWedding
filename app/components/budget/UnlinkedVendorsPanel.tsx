'use client';

/**
 * UnlinkedVendorsPanel
 * ----------------------------------------------------------------
 * Surfaces vendor assignments that exist on a wedding but are not
 * linked to any budget category — i.e. `budget_category_id` is
 * null/missing. These typically come from the Vendor Directory tab,
 * where a planner adds a vendor to a wedding before deciding which
 * budget category it belongs to. Without this panel they would be
 * invisible on the Budget page yet still hold the (wedding, vendor)
 * uniqueness slot, blocking re-assignment from the Edit Category
 * modal.
 *
 * The component is intentionally presentational: it owns the local
 * "which row is being linked / removed" state but delegates all
 * mutations to the parent via callback props, so the parent can
 * reconcile its `vendorAssignments` state in one place.
 */

import { useState } from 'react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Link2, Trash2, Loader2, AlertCircle, X } from 'lucide-react';
import type { VendorAssignment } from '../../services/vendorManagementApi';
import type { BudgetCategory } from '../../types/budget';

export interface UnlinkedVendorsPanelProps {
  /** Assignments where `budget_category_id` is null/missing. */
  unlinkedAssignments: VendorAssignment[];
  /** All categories on the current wedding (drives the picker). */
  categories: BudgetCategory[];
  /**
   * Link an existing assignment to a budget category. Parent is
   * expected to call updateVendorAssignment and refresh state. Must
   * resolve on success and reject on failure so this panel can
   * render the spinner and clear the inline picker correctly.
   */
  onLinkToCategory: (assignmentId: string, categoryId: string) => Promise<void>;
  /**
   * Soft-delete an assignment. Parent calls deleteVendorAssignment
   * and refreshes state.
   */
  onRemoveAssignment: (assignmentId: string) => Promise<void>;
}

export default function UnlinkedVendorsPanel({
  unlinkedAssignments,
  categories,
  onLinkToCategory,
  onRemoveAssignment,
}: UnlinkedVendorsPanelProps) {
  // Which row currently shows the inline "Link to category…" picker.
  // Only one at a time — keeps the panel compact and avoids state
  // sprawl across rows.
  const [linkingId, setLinkingId] = useState<string | null>(null);
  // Per-row spinner state, keyed by assignment _id. Tracks both link
  // and remove operations because they're mutually exclusive on a
  // single row.
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string>('');

  if (unlinkedAssignments.length === 0) {
    return null;
  }

  const handleLink = async (assignmentId: string, categoryId: string) => {
    setError('');
    setBusyId(assignmentId);
    try {
      await onLinkToCategory(assignmentId, categoryId);
      setLinkingId(null);
    } catch (err: any) {
      setError(err?.message || 'Failed to link vendor to category');
    } finally {
      setBusyId(null);
    }
  };

  const handleRemove = async (assignmentId: string, vendorName: string) => {
    // confirm() is intentional — matches the existing pattern on the
    // budget page (handleDeleteCategory) so the destructive-action
    // affordance is consistent. Swap for a custom dialog if/when the
    // page adopts one.
    if (!confirm(
      `Remove ${vendorName} from this wedding? The vendor stays in your directory; only the wedding link is archived.`
    )) {
      return;
    }
    setError('');
    setBusyId(assignmentId);
    try {
      await onRemoveAssignment(assignmentId);
    } catch (err: any) {
      setError(err?.message || 'Failed to remove vendor');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card className="p-5 bg-amber-50/60 dark:bg-amber-900/15 border-amber-200 dark:border-amber-800">
      <div className="flex items-start justify-between mb-3 gap-3">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <h2 className="text-base font-semibold text-amber-900 dark:text-amber-100">
              Vendors on this wedding without a budget category
            </h2>
            <p className="text-xs text-amber-800 dark:text-amber-200 mt-0.5">
              {unlinkedAssignments.length === 1
                ? '1 vendor is attached to this wedding but isn’t linked to a category yet.'
                : `${unlinkedAssignments.length} vendors are attached to this wedding but aren’t linked to a category yet.`}
              {' '}Link them so they appear on the matching budget card.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-3 p-2 text-sm text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-md">
          {error}
        </div>
      )}

      <ul className="space-y-2">
        {unlinkedAssignments.map((assignment) => {
          const isBusy = busyId === assignment._id;
          const isLinking = linkingId === assignment._id;
          return (
            <li
              key={assignment._id}
              className="flex flex-col sm:flex-row sm:items-center gap-3 p-3 bg-white/70 dark:bg-slate-800/60 border border-amber-200/60 dark:border-amber-700/40 rounded-lg"
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                  {assignment.vendor_name}
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 truncate">
                  {assignment.service_category}
                  {assignment.vendor_email && ` · ${assignment.vendor_email}`}
                  {assignment.status && (
                    <span className="ml-1 inline-block px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200">
                      {assignment.status}
                    </span>
                  )}
                </div>
              </div>

              {isLinking ? (
                <div className="flex items-center gap-2 flex-shrink-0">
                  {/* Inline category picker. Disabled when busy so the
                      user can't double-submit. */}
                  <select
                    aria-label={`Pick a budget category for ${assignment.vendor_name}`}
                    disabled={isBusy || categories.length === 0}
                    className="text-sm rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 px-2 py-1.5 focus:ring-2 focus:ring-wedding-rose focus:border-transparent"
                    onChange={(e) => {
                      const id = e.target.value;
                      if (id) handleLink(assignment._id, id);
                    }}
                    defaultValue=""
                  >
                    <option value="" disabled>
                      {categories.length === 0
                        ? 'No categories yet'
                        : 'Choose a category…'}
                    </option>
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => setLinkingId(null)}
                    disabled={isBusy}
                    className="p-1.5 rounded-md text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                    aria-label="Cancel"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    type="button"
                    onClick={() => setLinkingId(assignment._id)}
                    disabled={isBusy}
                    className="text-xs px-3 py-1.5"
                  >
                    {isBusy ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <>
                        <Link2 className="w-3.5 h-3.5 mr-1.5" />
                        Link to category
                      </>
                    )}
                  </Button>
                  <button
                    type="button"
                    onClick={() => handleRemove(assignment._id, assignment.vendor_name)}
                    disabled={isBusy}
                    className="p-1.5 rounded-md text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    aria-label={`Remove ${assignment.vendor_name} from this wedding`}
                    title="Remove from wedding"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
