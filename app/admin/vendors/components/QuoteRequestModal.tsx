'use client';

import React, { useState } from 'react';
import { X, Send, Calendar, MapPin, Users, DollarSign, Building2, Sparkles } from 'lucide-react';
import {
  requestQuote,
  draftQuote,
  type SponsoredCard,
  type WeddingContext,
} from '@/services/campaignAdvertisingApi';
import { useAdmin } from '@/contexts/AdminContext';
import { toast } from 'sonner';

interface QuoteRequestModalProps {
  card: SponsoredCard;
  weddings?: Array<{ id: string; name: string }>;
  selectedWeddingId?: string;
  onClose: () => void;
}

export function QuoteRequestModal({
  card,
  weddings,
  selectedWeddingId,
  onClose,
}: QuoteRequestModalProps) {
  const { token, apiRequest } = useAdmin();
  const [message, setMessage] = useState(
    `Hi ${card.vendor_name},\n\nI found your profile on The Special Wedding and I'm interested in your services. Could you provide a quote?\n\nThank you!`
  );
  const [weddingId, setWeddingId] = useState(selectedWeddingId || '');
  const [weddingContext, setWeddingContext] = useState<WeddingContext>({});
  const [autoAdd, setAutoAdd] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [aiDrafted, setAiDrafted] = useState(false);

  const handleSubmit = async () => {
    if (!token || !message.trim()) {
      toast.error('Please enter a message');
      return;
    }

    try {
      setSubmitting(true);
      const result = await requestQuote(apiRequest, {
        campaign_id: card.campaign_id,
        message: message.trim(),
        wedding_id: weddingId || undefined,
        wedding_context: Object.values(weddingContext).some(Boolean) ? weddingContext : undefined,
        auto_add_to_directory: autoAdd,
      });
      if (!result) return;
      setSubmitted(true);
      toast.success(`Quote request sent to ${card.vendor_name}`);
      setTimeout(onClose, 1500);
    } catch (err: any) {
      toast.error(err.message || 'Failed to send quote request');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAiDraft = async () => {
    if (!token) return;
    try {
      setDrafting(true);
      const result = await draftQuote(apiRequest, {
        campaign_id: card.campaign_id,
        wedding_context: Object.values(weddingContext).some(Boolean) ? weddingContext : undefined,
      });
      if (!result) return;
      if (result.draft?.body) {
        setMessage(result.draft.body);
        setAiDrafted(true);
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to generate AI draft');
    } finally {
      setDrafting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" />

      {/* Modal */}
      <div
        className="relative bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Request quote from ${card.vendor_name}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-700">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Request Quote</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
              <span className="font-medium text-wedding-sage">{card.vendor_name}</span>
              {card.vendor_category && ` · ${card.vendor_category.replace(/_/g, ' ')}`}
              {card.vendor_service_area && ` · ${card.vendor_service_area}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            aria-label="Close"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {submitted ? (
          <div className="p-8 text-center">
            <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Send size={24} className="text-emerald-600" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Quote Request Sent!</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
              {card.vendor_name} will receive your request and respond via the platform.
            </p>
          </div>
        ) : (
          <div className="p-5 space-y-4">
            {/* Wedding Selector */}
            {weddings && weddings.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1.5">
                  Link to a wedding? <span className="font-normal text-slate-400">(optional)</span>
                </label>
                <select
                  value={weddingId}
                  onChange={(e) => setWeddingId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200"
                >
                  <option value="">General inquiry (no specific wedding)</option>
                  {weddings.map((w) => (
                    <option key={w.id} value={w.id}>{w.name}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Wedding Context (collapsible) */}
            <details className="group">
              <summary className="text-sm font-medium text-wedding-sage cursor-pointer hover:underline">
                Add wedding details (helps get better quotes)
              </summary>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                    <Calendar size={12} /> Date
                  </label>
                  <input
                    type="date"
                    value={weddingContext.date || ''}
                    onChange={(e) => setWeddingContext((prev) => ({ ...prev, date: e.target.value }))}
                    className="w-full px-2 py-1.5 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700"
                  />
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                    <MapPin size={12} /> Location
                  </label>
                  <input
                    type="text"
                    placeholder="City, State"
                    value={weddingContext.location || ''}
                    onChange={(e) => setWeddingContext((prev) => ({ ...prev, location: e.target.value }))}
                    className="w-full px-2 py-1.5 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700"
                  />
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                    <Users size={12} /> Guest Count
                  </label>
                  <input
                    type="number"
                    placeholder="e.g. 150"
                    value={weddingContext.guest_count || ''}
                    onChange={(e) => setWeddingContext((prev) => ({ ...prev, guest_count: parseInt(e.target.value) || undefined }))}
                    className="w-full px-2 py-1.5 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700"
                  />
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                    <DollarSign size={12} /> Budget Range
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. $5K-$10K"
                    value={weddingContext.budget_range || ''}
                    onChange={(e) => setWeddingContext((prev) => ({ ...prev, budget_range: e.target.value }))}
                    className="w-full px-2 py-1.5 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700"
                  />
                </div>
              </div>
            </details>

            {/* Message */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  Message
                </label>
                <button
                  onClick={handleAiDraft}
                  disabled={drafting}
                  className="flex items-center gap-1 text-xs text-purple-600 dark:text-purple-400 hover:text-purple-700 transition-colors disabled:opacity-50"
                >
                  <Sparkles size={12} />
                  {drafting ? 'Drafting...' : 'Suggest with AI'}
                </button>
              </div>
              {aiDrafted && (
                <div className="flex items-center gap-1.5 mb-1.5 px-2 py-1 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-md">
                  <Sparkles size={10} className="text-purple-500" />
                  <span className="text-[10px] text-purple-600 dark:text-purple-400">AI-suggested draft — feel free to edit before sending</span>
                </div>
              )}
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={5}
                className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 resize-none"
                placeholder="Write your message to the vendor..."
                maxLength={2000}
              />
              <p className="text-xs text-slate-400 mt-1 text-right">{message.length}/2000</p>
            </div>

            {/* Auto-add checkbox */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoAdd}
                onChange={(e) => setAutoAdd(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-wedding-sage focus:ring-wedding-sage"
              />
              <span className="text-sm text-slate-600 dark:text-slate-300">
                Also add this vendor to my directory
              </span>
            </label>

            {/* Submit */}
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !message.trim()}
                className="flex items-center gap-2 px-5 py-2 bg-wedding-sage hover:bg-wedding-navy text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                <Send size={14} />
                {submitting ? 'Sending...' : 'Send Quote Request'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
