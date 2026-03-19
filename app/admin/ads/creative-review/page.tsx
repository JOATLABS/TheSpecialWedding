'use client';

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { useAdmin } from '@/contexts/AdminContext';
import { motion, AnimatePresence } from 'framer-motion';
import PageHeader from '../../components/PageHeader';
import RootAdminGuard from '@/components/RootAdminGuard';
import {
  getReviewQueue,
  getReviewQueueCounts,
  reviewCampaign,
  getAdPlacementLabel,
  type ReviewQueueItem,
  type ReviewQueueCounts,
  type ReviewStatus,
} from '@/services/advertisingApi';
import {
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Eye,
  ShieldCheck,
} from 'lucide-react';

export default function CreativeReviewPage() {
  return (
    <RootAdminGuard>
      <CreativeReviewContent />
    </RootAdminGuard>
  );
}

function CreativeReviewContent() {
  const { token } = useAdmin();
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [placementFilter, setPlacementFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | ''>('pending_review');
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [notesModalId, setNotesModalId] = useState<string | null>(null);
  const [queueCounts, setQueueCounts] = useState<ReviewQueueCounts>({
    pending_review: 0,
    approved: 0,
    rejected: 0,
    changes_requested: 0,
  });

  const fetchCounts = useCallback(async () => {
    if (!token) return;
    try {
      const counts = await getReviewQueueCounts(token);
      setQueueCounts(counts);
    } catch {
      // Silently fail for counts
    }
  }, [token]);

  const fetchQueue = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const items = await getReviewQueue(token, {
        status: (statusFilter || 'pending_review') as ReviewStatus,
        placement: placementFilter || undefined,
        limit: 50,
      });
      setQueue(items);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, [token, statusFilter, placementFilter]);

  useEffect(() => {
    fetchCounts();
  }, [fetchCounts]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleReview = async (id: string, status: ReviewStatus, notes?: string) => {
    if (!token) return;
    setReviewingId(id);
    try {
      await reviewCampaign(token, id, {
        review_status: status,
        review_notes: notes || undefined,
      });
      toast.success(
        status === 'approved'
          ? 'Campaign approved and activated'
          : status === 'rejected'
          ? 'Campaign rejected'
          : 'Changes requested from vendor'
      );
      await fetchQueue();
      await fetchCounts();
    } catch (err: any) {
      toast.error(err.message || 'Review action failed');
    } finally {
      setReviewingId(null);
      setNotesModalId(null);
      setReviewNotes('');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Creative Review"
        description="Review and approve vendor ad campaigns"
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-violet-500/20 to-purple-500/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center shadow-lg shadow-violet-500/30">
              <Clock className="w-7 h-7 text-white" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Pending Review</p>
              <p className="text-4xl font-bold text-violet-400">{queueCounts.pending_review}</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-emerald-500/20 to-green-500/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <CheckCircle2 className="w-7 h-7 text-white" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Approved</p>
              <p className="text-4xl font-bold text-emerald-400">{queueCounts.approved}</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-red-500/20 to-rose-500/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500 to-rose-500 flex items-center justify-center shadow-lg shadow-red-500/30">
              <XCircle className="w-7 h-7 text-white" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Rejected</p>
              <p className="text-4xl font-bold text-red-400">{queueCounts.rejected}</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="group relative overflow-hidden rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-amber-500/20 to-yellow-500/20 rounded-full blur-2xl group-hover:scale-150 transition-transform" />
          <div className="relative flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-amber-500 to-yellow-500 flex items-center justify-center shadow-lg shadow-amber-500/30">
              <AlertTriangle className="w-7 h-7 text-white" />
            </div>
            <div>
              <p className="text-sm text-slate-400 font-medium">Changes Requested</p>
              <p className="text-4xl font-bold text-amber-400">{queueCounts.changes_requested}</p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Filter Row */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">
          {statusFilter === 'pending_review'
            ? 'Pending Creative Reviews'
            : statusFilter === 'approved'
            ? 'Approved Campaigns'
            : statusFilter === 'rejected'
            ? 'Rejected Campaigns'
            : 'Changes Requested'}
        </h2>
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ReviewStatus | '')}
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 text-sm hover:bg-white/10 transition-all"
            style={{ minHeight: 44 }}
          >
            <option value="pending_review">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="changes_requested">Changes Requested</option>
          </select>
          <select
            value={placementFilter}
            onChange={(e) => setPlacementFilter(e.target.value)}
            className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 text-sm hover:bg-white/10 transition-all"
            style={{ minHeight: 44 }}
          >
            <option value="">All Placements</option>
            <option value="vendor_rail">Vendor Rail</option>
            <option value="vendor_detail">Vendor Detail</option>
            <option value="milestone_module">Milestone Module</option>
            <option value="directory_boost">Directory Boost</option>
            <option value="dashboard_rail">Dashboard Rail</option>
          </select>
        </div>
      </div>

      {/* Review Queue */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-5 h-5 text-slate-400 animate-spin mr-3" />
          <span className="text-slate-400">Loading review queue...</span>
        </div>
      ) : queue.length === 0 ? (
        <div className="rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-12 text-center">
          <ShieldCheck className="w-12 h-12 text-slate-400 mx-auto mb-4" />
          <p className="text-lg font-semibold text-white mb-1">No campaigns to review</p>
          <p className="text-slate-400">All caught up. New submissions will appear here.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {queue.map((item) => {
            const id = String(item._id);
            const vendorName = item.vendor_profile?.business_name || 'Unknown Vendor';
            const category = item.vendor_profile?.service_category || 'uncategorized';
            const logoUrl = item.vendor_profile?.logo_url;
            const isReviewing = reviewingId === id;

            return (
              <motion.div
                key={id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl bg-white/5 dark:bg-slate-800/50 backdrop-blur-sm border border-white/10 p-6 hover:bg-white/10 transition-all"
              >
                <div className="flex gap-6">
                  {/* Vendor Preview Image */}
                  <div
                    className="flex-shrink-0 rounded-xl overflow-hidden flex items-center justify-center"
                    style={{
                      width: 140,
                      height: 100,
                      background: logoUrl
                        ? `url(${logoUrl}) center/cover`
                        : 'linear-gradient(135deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))',
                    }}
                  >
                    {!logoUrl && (
                      <Eye className="w-7 h-7 text-slate-400" />
                    )}
                  </div>

                  {/* Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div>
                        <p className="text-lg font-semibold text-white truncate">{vendorName}</p>
                        <p className="text-sm text-slate-400 mt-1">
                          Goal: {item.metadata?.goal || 'N/A'}
                          <span className="ml-3 inline-flex px-2.5 py-1 rounded-lg bg-slate-500/20 text-slate-300 text-xs font-medium">
                            {getAdPlacementLabel(item.placement as any)}
                          </span>
                        </p>
                      </div>
                      <ReviewStatusBadge status={item.review_status as ReviewStatus} />
                    </div>

                    {/* Creative Preview */}
                    <div className="rounded-xl bg-slate-500/10 border border-white/5 p-4 mb-3">
                      <p className="text-sm font-semibold text-white">{item.headline || 'No headline'}</p>
                      <p className="text-sm text-slate-400 mt-2">{item.description || 'No description provided'}</p>
                      {item.metadata?.offer_text && (
                        <p className="text-sm font-medium text-emerald-400 mt-2">{item.metadata.offer_text}</p>
                      )}
                      {item.metadata?.cta_text && (
                        <span className="inline-flex mt-3 px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs font-semibold">
                          {item.metadata.cta_text}
                        </span>
                      )}
                    </div>

                    {/* Meta Info */}
                    <p className="text-xs text-slate-500 mb-3">
                      Category: {category} • Submitted: {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'N/A'}
                      {item.reviewed_by && ` • Reviewed by: ${item.reviewed_by}`}
                    </p>

                    {/* Review Notes Modal */}
                    <AnimatePresence>
                      {notesModalId === id && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="rounded-xl bg-slate-500/10 border border-white/5 p-4 mb-3 overflow-hidden"
                        >
                          <label className="block text-sm font-semibold text-white mb-2">
                            Review Notes
                          </label>
                          <textarea
                            value={reviewNotes}
                            onChange={(e) => setReviewNotes(e.target.value)}
                            placeholder="Reason for rejection or requested changes..."
                            className="w-full bg-slate-900/50 border border-white/10 rounded-lg px-4 py-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-white/20 resize-none"
                            style={{ minHeight: 80 }}
                          />
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Show review notes if present */}
                    {item.review_notes && item.review_status !== 'pending_review' && (
                      <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 mb-3 text-xs text-amber-200">
                        <strong>Review notes:</strong> {item.review_notes}
                      </div>
                    )}

                    {/* Action Buttons */}
                    {item.review_status === 'pending_review' && notesModalId !== id && (
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleReview(id, 'approved')}
                          disabled={isReviewing}
                          className="px-4 py-2 rounded-lg bg-emerald-500/20 text-emerald-400 font-medium text-sm hover:bg-emerald-500/30 transition-all disabled:opacity-50"
                          style={{ minHeight: 44 }}
                        >
                          {isReviewing ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Approve'}
                        </button>
                        <button
                          onClick={() => setNotesModalId(id)}
                          disabled={isReviewing}
                          className="px-4 py-2 rounded-lg bg-red-500/20 text-red-400 font-medium text-sm hover:bg-red-500/30 transition-all disabled:opacity-50"
                          style={{ minHeight: 44 }}
                        >
                          Reject
                        </button>
                        <button
                          onClick={() => setNotesModalId(id)}
                          disabled={isReviewing}
                          className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 font-medium text-sm hover:bg-white/10 transition-all disabled:opacity-50"
                          style={{ minHeight: 44 }}
                        >
                          Request Changes
                        </button>
                      </div>
                    )}

                    {/* Confirm buttons in notes modal */}
                    {notesModalId === id && (
                      <div className="flex gap-3">
                        <button
                          onClick={() =>
                            handleReview(
                              id,
                              notesModalId === id ? 'rejected' : 'changes_requested',
                              reviewNotes
                            )
                          }
                          disabled={isReviewing}
                          className="px-4 py-2 rounded-lg bg-red-500/20 text-red-400 font-medium text-sm hover:bg-red-500/30 transition-all disabled:opacity-50"
                          style={{ minHeight: 44 }}
                        >
                          {isReviewing ? 'Submitting...' : 'Confirm'}
                        </button>
                        <button
                          onClick={() => {
                            setNotesModalId(null);
                            setReviewNotes('');
                          }}
                          className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 font-medium text-sm hover:bg-white/10 transition-all"
                          style={{ minHeight: 44 }}
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ReviewStatusBadge({ status }: { status: ReviewStatus | string | undefined }) {
  if (!status) return null;

  const styles: Record<string, { bg: string; text: string; label: string }> = {
    pending_review: {
      bg: 'bg-violet-500/20',
      text: 'text-violet-400',
      label: 'PENDING',
    },
    approved: {
      bg: 'bg-emerald-500/20',
      text: 'text-emerald-400',
      label: 'APPROVED',
    },
    rejected: {
      bg: 'bg-red-500/20',
      text: 'text-red-400',
      label: 'REJECTED',
    },
    changes_requested: {
      bg: 'bg-amber-500/20',
      text: 'text-amber-400',
      label: 'CHANGES REQUESTED',
    },
  };

  const s = styles[status] || styles.pending_review;

  return (
    <span className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}
