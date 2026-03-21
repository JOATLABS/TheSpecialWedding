'use client';

import { useState, useRef } from 'react';
import { BlogArticle } from './BlogManager';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import {
  Save,
  Loader2,
  Eye,
  Edit3,
  Upload,
  X,
  Image as ImageIcon,
} from 'lucide-react';

interface BlogArticleEditorProps {
  article: BlogArticle | null;
  onSave: (data: Record<string, unknown>, id?: string) => Promise<void>;
  onCancel: () => void;
}

const CATEGORIES = [
  { value: 'platform-updates', label: 'Platform Updates' },
  { value: 'pricing-strategy', label: 'Pricing Strategy' },
  { value: 'guest-management', label: 'Guest Management' },
  { value: 'industry-comparison', label: 'Industry Comparison' },
  { value: 'contracts-legal', label: 'Contracts & Legal' },
  { value: 'ai-technology', label: 'AI & Technology' },
  { value: 'event-logistics', label: 'Event Logistics' },
  { value: 'tips-guides', label: 'Tips & Guides' },
  { value: 'general', label: 'General' },
];

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5 MB

export default function BlogArticleEditor({ article, onSave, onCancel }: BlogArticleEditorProps) {
  const { token } = useAdmin();

  const [title, setTitle] = useState(article?.title || '');
  const [content, setContent] = useState(article?.content || '');
  const [excerpt, setExcerpt] = useState(article?.excerpt || '');
  const [category, setCategory] = useState(article?.category || 'general');
  const [tags, setTags] = useState(article?.tags?.join(', ') || '');
  const [status, setStatus] = useState(article?.status || 'draft');
  const [featured, setFeatured] = useState(article?.featured || false);
  const [authorName, setAuthorName] = useState(article?.author_name || 'The Special Wedding');
  const [metaTitle, setMetaTitle] = useState(article?.meta_title || '');
  const [metaDescription, setMetaDescription] = useState(article?.meta_description || '');
  const [cardImage, setCardImage] = useState(article?.card_image || '');
  const [ogImage, setOgImage] = useState(article?.og_image || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [uploadingCard, setUploadingCard] = useState(false);
  const [uploadingOg, setUploadingOg] = useState(false);

  const cardFileRef = useRef<HTMLInputElement>(null);
  const ogFileRef = useRef<HTMLInputElement>(null);

  // ── Image Upload ──
  const uploadImage = async (file: File, folder: string): Promise<string> => {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      throw new Error('Only JPEG, PNG, and WebP images are allowed.');
    }
    if (file.size > MAX_IMAGE_SIZE) {
      throw new Error('Image must be under 5 MB.');
    }

    const baseUrl = getApiBaseUrl();

    // Step 1: Get presigned URL
    const params = new URLSearchParams({
      filename: file.name,
      content_type: file.type,
      folder,
    });
    const res = await fetch(`${baseUrl}/admin/blog/upload-url?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || 'Failed to get upload URL');
    }
    const { upload_url, cdn_url } = await res.json();

    // Step 2: Upload directly to R2
    const uploadRes = await fetch(upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type },
      body: file,
    });
    if (!uploadRes.ok) {
      throw new Error(`Upload failed: ${uploadRes.status}`);
    }

    return cdn_url;
  };

  const handleCardImageUpload = async (file: File) => {
    setUploadingCard(true);
    setError('');
    try {
      const url = await uploadImage(file, 'blog/cards');
      setCardImage(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Card image upload failed');
    } finally {
      setUploadingCard(false);
    }
  };

  const handleOgImageUpload = async (file: File) => {
    setUploadingOg(true);
    setError('');
    try {
      const url = await uploadImage(file, 'blog/og');
      setOgImage(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'OG image upload failed');
    } finally {
      setUploadingOg(false);
    }
  };

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim() || !excerpt.trim()) {
      setError('Title, content, and excerpt are required.');
      return;
    }

    setSaving(true);
    setError('');

    try {
      const data: Record<string, unknown> = {
        title: title.trim(),
        content: content.trim(),
        excerpt: excerpt.trim(),
        category,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        status,
        featured,
        author_name: authorName.trim(),
      };

      if (metaTitle.trim()) data.meta_title = metaTitle.trim();
      if (metaDescription.trim()) data.meta_description = metaDescription.trim();
      if (cardImage) data.card_image = cardImage;
      if (ogImage) data.og_image = ogImage;

      await onSave(data, article?.id);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save article';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">
          {article ? 'Edit Article' : 'New Blog Article'}
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 text-sm text-slate-300 hover:text-white transition"
          >
            {showPreview ? <Edit3 className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            {showPreview ? 'Editor' : 'Preview'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
        </div>
      )}

      {showPreview ? (
        <div className="rounded-xl border border-white/10 bg-white/[0.02] p-6">
          {cardImage && (
            <div className="mb-6 rounded-lg overflow-hidden">
              <img src={cardImage} alt="Card preview" className="w-full h-48 object-cover" />
            </div>
          )}
          <h2 className="text-2xl font-bold text-white mb-4">{title || 'Untitled'}</h2>
          <div
            className="prose prose-invert prose-sm max-w-none text-slate-300"
            dangerouslySetInnerHTML={{ __html: content }}
          />
        </div>
      ) : (
        <div className="space-y-5">
          {/* Title */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Article title..."
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50"
            />
          </div>

          {/* Excerpt */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">Excerpt</label>
            <textarea
              value={excerpt}
              onChange={(e) => setExcerpt(e.target.value)}
              placeholder="Short summary for card listings..."
              rows={2}
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50 resize-none"
            />
          </div>

          {/* ── Images ── */}
          <div className="border border-white/10 rounded-xl p-5 space-y-4">
            <h4 className="text-sm font-medium text-white flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-wedding-rose" />
              Images
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Card Image */}
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Card Image</label>
                {cardImage ? (
                  <div className="relative rounded-lg overflow-hidden border border-white/10">
                    <img src={cardImage} alt="Card" className="w-full h-32 object-cover" />
                    <button
                      onClick={() => setCardImage('')}
                      className="absolute top-2 right-2 p-1 rounded-full bg-black/60 text-white hover:bg-black/80 transition"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => cardFileRef.current?.click()}
                    disabled={uploadingCard}
                    className="w-full h-32 rounded-lg border-2 border-dashed border-white/10 hover:border-wedding-rose/30 flex flex-col items-center justify-center gap-2 text-slate-500 hover:text-slate-300 transition"
                  >
                    {uploadingCard ? (
                      <Loader2 className="w-5 h-5 animate-spin text-wedding-rose" />
                    ) : (
                      <>
                        <Upload className="w-5 h-5" />
                        <span className="text-xs">Upload card image</span>
                      </>
                    )}
                  </button>
                )}
                <input
                  ref={cardFileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleCardImageUpload(file);
                    e.target.value = '';
                  }}
                />
                {/* Manual URL input */}
                <input
                  type="text"
                  value={cardImage}
                  onChange={(e) => setCardImage(e.target.value)}
                  placeholder="or paste CDN URL..."
                  className="mt-2 w-full px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-wedding-rose/50"
                />
              </div>

              {/* OG Image */}
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">OG / Social Image</label>
                {ogImage ? (
                  <div className="relative rounded-lg overflow-hidden border border-white/10">
                    <img src={ogImage} alt="OG" className="w-full h-32 object-cover" />
                    <button
                      onClick={() => setOgImage('')}
                      className="absolute top-2 right-2 p-1 rounded-full bg-black/60 text-white hover:bg-black/80 transition"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => ogFileRef.current?.click()}
                    disabled={uploadingOg}
                    className="w-full h-32 rounded-lg border-2 border-dashed border-white/10 hover:border-wedding-rose/30 flex flex-col items-center justify-center gap-2 text-slate-500 hover:text-slate-300 transition"
                  >
                    {uploadingOg ? (
                      <Loader2 className="w-5 h-5 animate-spin text-wedding-rose" />
                    ) : (
                      <>
                        <Upload className="w-5 h-5" />
                        <span className="text-xs">Upload OG image</span>
                      </>
                    )}
                  </button>
                )}
                <input
                  ref={ogFileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleOgImageUpload(file);
                    e.target.value = '';
                  }}
                />
                <input
                  type="text"
                  value={ogImage}
                  onChange={(e) => setOgImage(e.target.value)}
                  placeholder="or paste CDN URL..."
                  className="mt-2 w-full px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-wedding-rose/50"
                />
              </div>
            </div>
          </div>

          {/* Content (HTML) */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">
              Content (HTML)
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="<p>Your blog post content...</p>"
              rows={20}
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50 font-mono resize-y"
            />
          </div>

          {/* Category + Status + Featured */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:border-wedding-rose/50"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value} className="bg-slate-900">{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:border-wedding-rose/50"
              >
                <option value="draft" className="bg-slate-900">Draft</option>
                <option value="published" className="bg-slate-900">Published</option>
                <option value="archived" className="bg-slate-900">Archived</option>
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={featured}
                  onChange={(e) => setFeatured(e.target.checked)}
                  className="rounded border-white/20 bg-white/5 text-wedding-rose focus:ring-wedding-rose/50"
                />
                <span className="text-sm text-slate-300">Featured article</span>
              </label>
            </div>
          </div>

          {/* Tags + Author */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Tags (comma-separated)</label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="wedding planner, AI, contracts..."
                className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Author Name</label>
              <input
                type="text"
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50"
              />
            </div>
          </div>

          {/* SEO Fields */}
          <div className="border-t border-white/5 pt-5">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">SEO (optional)</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Meta Title</label>
                <input
                  type="text"
                  value={metaTitle}
                  onChange={(e) => setMetaTitle(e.target.value)}
                  placeholder="SEO title override (max 70 chars)"
                  maxLength={70}
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Meta Description</label>
                <input
                  type="text"
                  value={metaDescription}
                  onChange={(e) => setMetaDescription(e.target.value)}
                  placeholder="SEO description (max 160 chars)"
                  maxLength={160}
                  className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-wedding-rose/50"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg bg-white/5 text-sm text-slate-300 hover:text-white transition"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={saving}
          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-wedding-rose text-white text-sm font-medium hover:bg-wedding-blush disabled:opacity-50 transition"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          {article ? 'Update Article' : 'Create Article'}
        </button>
      </div>
    </div>
  );
}
