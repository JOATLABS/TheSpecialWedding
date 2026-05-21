'use client';

import { useState, type ChangeEvent } from 'react';
import { BlogArticle } from './BlogManager';
import MarkdownArticle from '@/components/blog/MarkdownArticle';
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

  const handleImageInputChange = (
    event: ChangeEvent<HTMLInputElement>,
    upload: (file: File) => Promise<void>,
  ) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';

    if (file) {
      void upload(file);
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
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
          {article ? 'Edit Article' : 'New Blog Article'}
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:shadow-none dark:hover:text-white dark:hover:bg-white/10"
          >
            {showPreview ? <Edit3 className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            {showPreview ? 'Editor' : 'Preview'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-400">
          {error}
        </div>
      )}

      {showPreview ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-white/10 dark:bg-white/[0.02] dark:shadow-none">
          {cardImage && (
            <div className="mb-6 rounded-lg overflow-hidden">
              <img src={cardImage} alt="Card preview" className="w-full h-48 object-cover" />
            </div>
          )}
          <h2 className="mb-4 text-2xl font-bold text-slate-900 dark:text-white">{title || 'Untitled'}</h2>
          <MarkdownArticle content={content} className="prose-sm" />
        </div>
      ) : (
        <div className="space-y-5">
          {/* Title */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Article title..."
              className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 focus:ring-2 focus:ring-wedding-rose/15 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
            />
          </div>

          {/* Excerpt */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Excerpt</label>
            <textarea
              value={excerpt}
              onChange={(e) => setExcerpt(e.target.value)}
              placeholder="Short summary for card listings..."
              rows={2}
              className="w-full resize-none rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 focus:ring-2 focus:ring-wedding-rose/15 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
            />
          </div>

          {/* ── Images ── */}
          <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-white/[0.02] dark:shadow-none">
            <h4 className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-white">
              <ImageIcon className="w-4 h-4 text-wedding-rose" />
              Images
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Card Image */}
              <div>
                <label
                  htmlFor="blog-card-image-url"
                  className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400"
                >
                  Card Image
                </label>
                {cardImage ? (
                  <div className="relative overflow-hidden rounded-lg border border-slate-200 dark:border-white/10">
                    <img src={cardImage} alt="Card" className="w-full h-32 object-cover" />
                    <button
                      type="button"
                      onClick={() => setCardImage('')}
                      className="absolute top-2 right-2 p-1 rounded-full bg-black/60 text-white hover:bg-black/80 transition"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <label
                    htmlFor="blog-card-image-upload"
                    aria-disabled={uploadingCard}
                    className={`flex h-32 w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 text-slate-500 transition dark:border-white/10 dark:text-slate-500 ${
                      uploadingCard
                        ? 'cursor-wait opacity-70'
                        : 'cursor-pointer hover:border-wedding-rose/40 hover:text-slate-700 dark:hover:border-wedding-rose/30 dark:hover:text-slate-300'
                    }`}
                  >
                    {uploadingCard ? (
                      <Loader2 className="w-5 h-5 animate-spin text-wedding-rose" />
                    ) : (
                      <>
                        <Upload className="w-5 h-5" />
                        <span className="text-xs">Upload card image</span>
                      </>
                    )}
                  </label>
                )}
                <input
                  id="blog-card-image-upload"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={uploadingCard}
                  className="sr-only"
                  aria-label="Blog card image file"
                  onChange={(event) => handleImageInputChange(event, handleCardImageUpload)}
                />
                {/* Manual URL input */}
                <input
                  id="blog-card-image-url"
                  type="text"
                  value={cardImage}
                  onChange={(e) => setCardImage(e.target.value)}
                  placeholder="or paste CDN URL..."
                  aria-label="Blog card image CDN URL"
                  className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-600 dark:shadow-none"
                />
              </div>

              {/* OG Image */}
              <div>
                <label
                  htmlFor="blog-og-image-url"
                  className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400"
                >
                  OG / Social Image
                </label>
                {ogImage ? (
                  <div className="relative overflow-hidden rounded-lg border border-slate-200 dark:border-white/10">
                    <img src={ogImage} alt="OG" className="w-full h-32 object-cover" />
                    <button
                      type="button"
                      onClick={() => setOgImage('')}
                      className="absolute top-2 right-2 p-1 rounded-full bg-black/60 text-white hover:bg-black/80 transition"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <label
                    htmlFor="blog-og-image-upload"
                    aria-disabled={uploadingOg}
                    className={`flex h-32 w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 text-slate-500 transition dark:border-white/10 dark:text-slate-500 ${
                      uploadingOg
                        ? 'cursor-wait opacity-70'
                        : 'cursor-pointer hover:border-wedding-rose/40 hover:text-slate-700 dark:hover:border-wedding-rose/30 dark:hover:text-slate-300'
                    }`}
                  >
                    {uploadingOg ? (
                      <Loader2 className="w-5 h-5 animate-spin text-wedding-rose" />
                    ) : (
                      <>
                        <Upload className="w-5 h-5" />
                        <span className="text-xs">Upload OG image</span>
                      </>
                    )}
                  </label>
                )}
                <input
                  id="blog-og-image-upload"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={uploadingOg}
                  className="sr-only"
                  aria-label="Blog OG image file"
                  onChange={(event) => handleImageInputChange(event, handleOgImageUpload)}
                />
                <input
                  id="blog-og-image-url"
                  type="text"
                  value={ogImage}
                  onChange={(e) => setOgImage(e.target.value)}
                  placeholder="or paste CDN URL..."
                  aria-label="Blog OG image CDN URL"
                  className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-600 dark:shadow-none"
                />
              </div>
            </div>
          </div>

          {/* Content */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">
              Content (Markdown or basic HTML)
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="# Your blog post content...\n\nOr paste sanitized editorial HTML."
              rows={20}
              className="w-full resize-y rounded-lg border border-slate-200 bg-white px-4 py-2.5 font-mono text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 focus:ring-2 focus:ring-wedding-rose/15 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
            />
          </div>

          {/* Category + Status + Featured */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:shadow-none"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value} className="bg-white text-slate-900 dark:bg-slate-900 dark:text-white">{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:shadow-none"
              >
                <option value="draft" className="bg-white text-slate-900 dark:bg-slate-900 dark:text-white">Draft</option>
                <option value="published" className="bg-white text-slate-900 dark:bg-slate-900 dark:text-white">Published</option>
                <option value="archived" className="bg-white text-slate-900 dark:bg-slate-900 dark:text-white">Archived</option>
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={featured}
                  onChange={(e) => setFeatured(e.target.checked)}
                  className="rounded border-slate-300 bg-white text-wedding-rose focus:ring-wedding-rose/50 dark:border-white/20 dark:bg-white/5"
                />
                <span className="text-sm text-slate-700 dark:text-slate-300">Featured article</span>
              </label>
            </div>
          </div>

          {/* Tags + Author */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Tags (comma-separated)</label>
              <input
                type="text"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="wedding planner, AI, contracts..."
                className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Author Name</label>
              <input
                type="text"
                value={authorName}
                onChange={(e) => setAuthorName(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
              />
            </div>
          </div>

          {/* SEO Fields */}
          <div className="border-t border-slate-200 pt-5 dark:border-white/5">
            <p className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">SEO (optional)</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Meta Title</label>
                <input
                  type="text"
                  value={metaTitle}
                  onChange={(e) => setMetaTitle(e.target.value)}
                  placeholder="SEO title override (max 70 chars)"
                  maxLength={70}
                  className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-400">Meta Description</label>
                <input
                  type="text"
                  value={metaDescription}
                  onChange={(e) => setMetaDescription(e.target.value)}
                  placeholder="SEO description (max 160 chars)"
                  maxLength={160}
                  className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
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
          className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:shadow-none dark:hover:text-white dark:hover:bg-white/10"
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
