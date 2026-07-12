'use client';

import React, { useState, useEffect } from 'react';
import { Sparkles, Save, Loader2, Globe, Paintbrush, Eye, ExternalLink, X } from 'lucide-react';
import { useAdmin } from '../../contexts/AdminContext';
import { CustomDomainManager } from '../components/storefront/CustomDomainManager';

const ToggleSwitch = ({ checked, onChange, label, description }: { checked: boolean, onChange: (v: boolean) => void, label: string, description: string }) => (
  <div className="flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
    <div>
      <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">{label}</p>
      <p className="text-[10px] text-slate-500 dark:text-slate-400">{description}</p>
    </div>
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
        checked ? 'bg-primary-500' : 'bg-slate-300 dark:bg-slate-600'
      }`}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? 'translate-x-4' : 'translate-x-0'
        }`}
      />
    </button>
  </div>
);

const ImageUploadZone = ({ label, hint, imageUrl, uploading, onUpload, onClear, compact = false }: { label: string, hint: string, imageUrl: string, uploading: boolean, onUpload: (f: File) => void, onClear: () => void, compact?: boolean }) => {
  const [dragOver, setDragOver] = useState(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.[0]) onUpload(e.dataTransfer.files[0]);
  };
  return (
    <div>
      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">{label}</label>
      <p className="text-[10px] text-slate-500 dark:text-slate-400 mb-2">{hint}</p>
      
      {imageUrl ? (
        <div className={`relative group rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700 shadow-sm ${compact ? 'h-24' : 'h-32'}`}>
          <img src={imageUrl} alt={label} className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-sm">
            <button onClick={onClear} className="text-xs font-medium text-white hover:text-red-300 transition-colors bg-black/40 px-3 py-1.5 rounded-lg backdrop-blur-md">
              Remove Image
            </button>
          </div>
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all cursor-pointer bg-slate-50/50 dark:bg-slate-800/30
            ${dragOver ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'}
            ${compact ? 'py-4' : 'py-6'}`}
        >
          {uploading ? (
            <Loader2 className="h-6 w-6 animate-spin text-primary-500 mb-2" />
          ) : (
            <svg className="mx-auto h-6 w-6 text-slate-400 mb-2" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
              <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
          <p className="text-[11px] text-slate-600 dark:text-slate-400">Drop an image or <span className="text-primary-500 font-medium hover:text-primary-600">browse</span></p>
          <p className="text-[9px] text-slate-400 mt-1">JPEG, PNG, WebP — max 5 MB</p>
        </div>
      )}
    </div>
  );
};

export default function StorefrontSettingsModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  const { apiRequest } = useAdmin();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<any>({
    slug: '',
    slug_persisted: false,
    title: '',
    description: '',
    contact_email: '',
    contact_phone: '',
    hero_asset_id: null,
    about_asset_id: null,
    hero_image_url: '',
    about_image_url: '',
    theme_color: '#0f172a',
    packages_enabled: true,
    reviews_enabled: true,
    is_published: false,
    custom_domain: '',
    cloudflare_hostname_status: 'none',
    ownership_verification: null
  });

  const [uploadingHero, setUploadingHero] = useState(false);
  const [uploadingAbout, setUploadingAbout] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const load = async () => {
        setLoading(true);
        try {
          const res = await apiRequest('/admin/storefront/settings', 'GET');
          if (res.settings) {
            setSettings({
              slug: res.settings.slug || '',
              slug_persisted: res.settings.slug_persisted ?? true,
              title: res.settings.title || '',
              description: res.settings.description || '',
              contact_email: res.settings.contact_email || '',
              contact_phone: res.settings.contact_phone || '',
              hero_asset_id: res.settings.hero_asset_id || null,
              about_asset_id: res.settings.about_asset_id || null,
              hero_image_url: '',
              about_image_url: '',
              theme_color: res.settings.theme_color || '#0f172a',
              packages_enabled: res.settings.packages_enabled ?? true,
              reviews_enabled: res.settings.reviews_enabled ?? true,
              is_published: res.settings.is_published ?? false,
              custom_domain: res.settings.custom_domain || '',
              cloudflare_hostname_status: res.settings.cloudflare_hostname_status || 'none',
              ownership_verification: res.settings.ownership_verification || null
            });
          }
        } catch (err) {
          console.error(err);
        } finally {
          setLoading(false);
        }
      };
      load();
    }
  }, [isOpen, apiRequest]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const savePayload = {
        slug: settings.slug || undefined,
        title: settings.title || null,
        description: settings.description || null,
        contact_email: settings.contact_email || null,
        contact_phone: settings.contact_phone || null,
        hero_asset_id: settings.hero_asset_id || null,
        about_asset_id: settings.about_asset_id || null,
        theme_color: settings.theme_color,
        packages_enabled: settings.packages_enabled,
        reviews_enabled: settings.reviews_enabled,
        is_published: settings.is_published,
      };
      await apiRequest('/admin/storefront/settings', 'POST', savePayload);
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const uploadFileToR2 = async (file: File) => {
    const filename = `${Date.now()}_${file.name}`;
    const contentType = file.type || 'application/octet-stream';
    const presignedRes = await apiRequest(`/admin/storefront/upload-url?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`);
    const uploadRes = await fetch(presignedRes.url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': contentType },
    });
    if (!uploadRes.ok) throw new Error('Upload failed');
    return presignedRes.public_url;
  };

  const handleHeroUpload = async (file: File) => {
    setUploadingHero(true);
    try {
      const url = await uploadFileToR2(file);
      setSettings((prev: any) => ({ ...prev, hero_image_url: url }));
    } catch (err) {
      console.error(err);
    } finally {
      setUploadingHero(false);
    }
  };

  const handleAboutUpload = async (file: File) => {
    setUploadingAbout(true);
    try {
      const url = await uploadFileToR2(file);
      setSettings((prev: any) => ({ ...prev, about_image_url: url }));
    } catch (err) {
      console.error(err);
    } finally {
      setUploadingAbout(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setSettings((prev: any) => ({ ...prev, [name]: value }));
  };

  if (!isOpen) return null;

  // A derived legacy slug is not routable until the planner explicitly saves it.
  const storefrontUrl = settings.slug && settings.slug_persisted
    ? `/storefront/${settings.slug}?preview=1`
    : '#';

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-start sm:justify-center p-4 bg-slate-900/60 backdrop-blur-sm sm:p-6 lg:p-8 overflow-y-auto">
      <div className="w-full max-w-5xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden relative">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 shadow-sm">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">Storefront Profile</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Configure your premium public page and custom domain.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={storefrontUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 shadow-sm transition hover:bg-slate-50 dark:hover:bg-slate-700/60"
            >
              <ExternalLink className="h-4 w-4" /> Preview
            </a>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50 dark:bg-slate-900/30">
          {loading ? (
            <div className="flex h-64 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-slate-400" /></div>
          ) : (
            <div className="grid lg:grid-cols-2 gap-6">
              {/* Left Column: Identity & Domains */}
              <div className="flex flex-col gap-6">
                
                {/* Domain Manager Component */}
                <div className="rounded-xl bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 shadow-sm p-5">
                  <CustomDomainManager 
                    initialDomain={settings.custom_domain} 
                    initialStatus={settings.cloudflare_hostname_status}
                    verification={settings.ownership_verification}
                    onDomainUpdate={(d) => setSettings((prev: any) => ({ ...prev, custom_domain: d || '' }))}
                  />
                </div>

                <div className="rounded-xl bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 shadow-sm p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Globe className="h-5 w-5 text-slate-400" />
                    <h3 className="text-sm font-semibold text-slate-800 dark:text-white">Storefront Identity</h3>
                  </div>
                  
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="sf-title" className="block text-xs font-medium text-slate-700 dark:text-slate-300">Storefront Title</label>
                      <input type="text" id="sf-title" name="title" value={settings.title} onChange={handleChange} className="mt-1 w-full rounded-lg border border-slate-200/70 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-900/40 px-3 py-2 text-sm text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-primary-400/40" placeholder="Jane's Luxury Weddings" />
                    </div>

                    <div>
                      <label htmlFor="sf-description" className="block text-xs font-medium text-slate-700 dark:text-slate-300">Bio / Description</label>
                      <textarea id="sf-description" name="description" value={settings.description} onChange={handleChange} rows={4} className="mt-1 w-full rounded-lg border border-slate-200/70 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-900/40 px-3 py-2 text-sm text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-primary-400/40 resize-none" placeholder="We specialize in crafting unforgettable celebrations…" />
                    </div>
                  </div>
                </div>

                <div className="rounded-xl bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 shadow-sm p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Eye className="h-5 w-5 text-slate-400" />
                    <h3 className="text-sm font-semibold text-slate-800 dark:text-white">Content Modules</h3>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <ToggleSwitch checked={settings.packages_enabled} onChange={(v) => setSettings((prev: any) => ({ ...prev, packages_enabled: v }))} label="Display Packages" description="Show public packages." />
                    <ToggleSwitch checked={settings.reviews_enabled} onChange={(v) => setSettings((prev: any) => ({ ...prev, reviews_enabled: v }))} label="Display Reviews" description="Show integrated reviews." />
                  </div>
                </div>
              </div>

              {/* Right Column: Media & Appearance */}
              <div className="rounded-xl bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 shadow-sm p-5 flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <Paintbrush className="h-5 w-5 text-slate-400" />
                  <h3 className="text-sm font-semibold text-slate-800 dark:text-white">Media & Appearance</h3>
                </div>

                <div className="space-y-6 flex-1">
                  <div>
                    <label htmlFor="sf-theme-color" className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-2">Theme Color</label>
                    <div className="flex items-center gap-3">
                      <input type="color" id="sf-theme-color" name="theme_color" value={settings.theme_color} onChange={handleChange} className="h-10 w-10 rounded-lg border border-slate-200/70 dark:border-slate-700/50 cursor-pointer p-0.5 bg-slate-50 dark:bg-slate-900/40" />
                      <input type="text" name="theme_color" value={settings.theme_color} onChange={handleChange} className="w-28 rounded-lg border border-slate-200/70 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-900/40 px-3 py-2 text-sm text-slate-700 dark:text-slate-200 uppercase outline-none focus:ring-2 focus:ring-primary-400/40" />
                    </div>
                  </div>

                  <ImageUploadZone
                    label="Hero Background Image"
                    hint="Banner image visitors see first. Landscape recommended (1600×900px+)."
                    imageUrl={settings.hero_image_url}
                    uploading={uploadingHero}
                    onUpload={handleHeroUpload}
                    onClear={() => setSettings((prev: any) => ({ ...prev, hero_image_url: '' }))}
                  />

                  <ImageUploadZone
                    label="About / Portrait Image"
                    hint="A professional headshot. Square or portrait works best."
                    imageUrl={settings.about_image_url}
                    uploading={uploadingAbout}
                    onUpload={handleAboutUpload}
                    onClear={() => setSettings((prev: any) => ({ ...prev, about_image_url: '' }))}
                    compact
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}
