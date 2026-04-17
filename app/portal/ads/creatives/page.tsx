'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useVendorAuth } from '../components/VendorAuthContext';
import { toast } from 'sonner';
import {
  listVendorCampaigns,
  listCreatives,
  createCreative,
  updateCreative,
  setPrimaryCreative,
  getCreativeStatusLabel,
  getCreativeStatusColor,
  type AdCampaign,
  type AdCreative,
  type CreateCreativeRequest,
} from '@/services/campaignAdvertisingApi';
import { VendorMediaUploader } from '../components/VendorMediaUploader';
import {
  Image as ImageIcon,
  Plus,
  Star,
  RefreshCw,
  Edit2,
  CheckCircle2,
} from 'lucide-react';

function createEmptyCreativeForm(): CreateCreativeRequest {
  return {
    headline: '',
    description: '',
    offer: '',
    call_to_action: 'View Portfolio',
    is_primary: false,
    image_url: null,
    image_alt_text: null,
  };
}

export default function VendorCreativesPage() {
  const { token } = useVendorAuth();
  const [campaigns, setCampaigns] = useState<AdCampaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('');
  const [creatives, setCreatives] = useState<AdCreative[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<CreateCreativeRequest>(createEmptyCreativeForm);
  const [saving, setSaving] = useState(false);
  const [mediaUploading, setMediaUploading] = useState(false);

  // Load campaigns
  useEffect(() => {
    if (!token) return;
    listVendorCampaigns(token, { limit: 100 })
      .then((data) => {
        setCampaigns(data);
        if (data.length > 0) setSelectedCampaignId(data[0]._id);
      })
      .catch((err) => toast.error(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  // Load creatives when campaign changes
  const loadCreatives = useCallback(async () => {
    if (!token || !selectedCampaignId) return;
    try {
      const data = await listCreatives(token, selectedCampaignId);
      setCreatives(data);
    } catch (err: any) {
      toast.error(err.message);
    }
  }, [token, selectedCampaignId]);

  useEffect(() => { loadCreatives(); }, [loadCreatives]);

  const handleSave = async () => {
    if (!token || !selectedCampaignId) return;
    if (!formData.headline.trim() || !formData.description.trim()) {
      toast.error('Headline and description are required');
      return;
    }
    if (mediaUploading) {
      toast.error('Wait for the creative image to finish uploading before saving.');
      return;
    }

    try {
      setSaving(true);
      const payload: CreateCreativeRequest = {
        ...formData,
        creative_type: formData.image_url ? 'image' : 'text',
        image_alt_text: formData.image_url ? formData.headline.trim() || 'Vendor creative image' : null,
      };
      if (editingId) {
        await updateCreative(token, editingId, payload);
        toast.success('Creative updated');
      } else {
        await createCreative(token, selectedCampaignId, payload);
        toast.success('Creative created');
      }
      setShowForm(false);
      setEditingId(null);
      setFormData(createEmptyCreativeForm());
      loadCreatives();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSetPrimary = async (creativeId: string) => {
    if (!token || !selectedCampaignId) return;
    try {
      await setPrimaryCreative(token, selectedCampaignId, creativeId);
      toast.success('Primary creative updated');
      loadCreatives();
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const startEdit = (creative: AdCreative) => {
    setFormData({
      creative_type: creative.creative_type,
      image_url: creative.image_url ?? null,
      image_alt_text: creative.image_alt_text ?? null,
      headline: creative.headline,
      description: creative.description,
      offer: creative.offer,
      call_to_action: creative.call_to_action,
      is_primary: creative.is_primary,
    });
    setEditingId(creative._id);
    setShowForm(true);
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Creatives</h1>
          <p className="text-sm text-slate-500 mt-1">Manage ad creatives for your campaigns</p>
        </div>
        <button
          onClick={() => { setShowForm(true); setEditingId(null); setFormData(createEmptyCreativeForm()); }}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={16} /> New Creative
        </button>
      </div>

      {/* Campaign Selector */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-slate-700 dark:text-slate-200">Campaign:</label>
        <select
          value={selectedCampaignId}
          onChange={(e) => setSelectedCampaignId(e.target.value)}
          className="w-full sm:w-auto text-sm border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 bg-white dark:bg-slate-800"
        >
          {campaigns.map((c) => (
            <option key={c._id} value={c._id}>{c.campaign_name}</option>
          ))}
        </select>
      </div>

      {/* Creative Form */}
      {showForm && (
        <div className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 p-5 space-y-4">
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            {editingId ? 'Edit Creative' : 'New Creative'}
          </h3>
          <VendorMediaUploader
            inputId="vendor-creative-image-upload"
            assetKind="creative"
            label="Creative Image"
            value={formData.image_url ?? null}
            onChange={(url) => setFormData((current) => ({ ...current, image_url: url }))}
            onUploadStateChange={setMediaUploading}
            previewAlt={formData.image_alt_text || formData.headline || 'Vendor creative image'}
            emptyTitle="Upload an image for this creative"
            emptyDescription="Use a polished image that planners should see alongside your headline and call to action."
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Headline *</label>
            <input
              type="text"
              value={formData.headline}
              onChange={(e) => setFormData({ ...formData, headline: e.target.value })}
              maxLength={100}
              className="w-full px-3 py-2 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
            />
            <p className="text-xs text-slate-400 mt-1">{formData.headline.length}/100</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Description *</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              maxLength={300}
              rows={3}
              className="w-full px-3 py-2 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700 resize-none"
            />
            <p className="text-xs text-slate-400 mt-1">{formData.description.length}/300</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Special Offer</label>
            <input
              type="text"
              value={formData.offer || ''}
              onChange={(e) => setFormData({ ...formData, offer: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">Button Text</label>
            <select
              value={formData.call_to_action}
              onChange={(e) => setFormData({ ...formData, call_to_action: e.target.value })}
              className="w-full px-3 py-2 border border-slate-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-700"
            >
              <option>View Portfolio</option>
              <option>Get a Quote</option>
              <option>Book Now</option>
              <option>Learn More</option>
              <option>Contact Us</option>
            </select>
          </div>
          <div className="flex gap-3">
            <button onClick={handleSave} disabled={saving || mediaUploading} className="px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:opacity-50">
              {mediaUploading ? 'Uploading image…' : saving ? 'Saving...' : editingId ? 'Update' : 'Create'}
            </button>
            <button onClick={() => { setShowForm(false); setEditingId(null); }} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Creative Grid */}
      {creatives.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700">
          <ImageIcon size={40} className="mx-auto text-slate-300 mb-3" aria-hidden="true" />
          <h3 className="text-sm font-medium text-slate-900 dark:text-white">No ad creatives yet</h3>
          <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">Creatives are the headline, description, and call-to-action that planners see in your ads. Create one to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {creatives.map((creative) => (
            <div key={creative._id} className="bg-white dark:bg-slate-800/95 rounded-2xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
              {creative.image_url && (
                <div className="aspect-video bg-slate-100 dark:bg-slate-700">
                  <img src={creative.image_url} alt={creative.image_alt_text || creative.headline} className="w-full h-full object-cover" />
                </div>
              )}
              <div className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white truncate">{creative.headline}</h4>
                    {creative.is_primary && (
                      <Star size={14} className="text-amber-500 fill-amber-500 flex-shrink-0" />
                    )}
                  </div>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getCreativeStatusColor(creative.review_status)}`}>
                    {getCreativeStatusLabel(creative.review_status)}
                  </span>
                </div>
                <p className="text-xs text-slate-500 line-clamp-2 mb-3">{creative.description}</p>
                {creative.offer && <p className="text-xs text-amber-600 font-medium mb-3">{creative.offer}</p>}
                <div className="flex gap-2">
                  <button onClick={() => startEdit(creative)} className="flex items-center gap-1 px-2 py-1 text-xs text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 rounded">
                    <Edit2 size={12} /> Edit
                  </button>
                  {!creative.is_primary && (
                    <button onClick={() => handleSetPrimary(creative._id)} title="The primary creative is shown by default in your ad placements" className="flex items-center gap-1 px-2 py-1 text-xs text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/20 rounded">
                      <Star size={12} /> Set Primary
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
