'use client';

import { useState, useEffect, useRef } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { getApiBaseUrl } from '@/utils/env';
import { KBArticle } from './KnowledgeBase';
import { Card } from '@/components/ui/Card';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Save,
  Eye,
  Edit3,
  X,
  Loader2,
  FileText,
  Upload,
  Image as ImageIcon,
} from 'lucide-react';

interface ArticleEditorProps {
  article?: KBArticle;
  onSuccess: () => void;
  onCancel: () => void;
}

const KB_CATEGORIES = [
  { value: 'getting-started', label: 'Getting Started' },
  { value: 'guest-management', label: 'Guest Management' },
  { value: 'rsvp-invitations', label: 'RSVP & Invitations' },
  { value: 'budget-payments', label: 'Budget & Payments' },
  { value: 'vendors', label: 'Vendors' },
  { value: 'forms-questionnaires', label: 'Forms & Questionnaires' },
  { value: 'wedding-configuration', label: 'Wedding Configuration' },
  { value: 'notifications', label: 'Notifications' },
  { value: 'calendar-tasks', label: 'Calendar & Tasks' },
  { value: 'billing-subscription', label: 'Billing & Subscription' },
  { value: 'troubleshooting', label: 'Troubleshooting' },
  { value: 'tips-tricks', label: 'Tips & Tricks' },
  { value: 'integrations', label: 'Integrations' },
  { value: 'general', label: 'General' }
];

const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_SIZE = 5 * 1024 * 1024; // 5 MB

export default function ArticleEditor({ article, onSuccess, onCancel }: ArticleEditorProps) {
  const { apiRequest, token } = useAdmin();
  const isEditing = !!article;

  const [title, setTitle] = useState(article?.title || '');
  const [content, setContent] = useState(article?.content || '');
  const [excerpt, setExcerpt] = useState(article?.excerpt || '');
  const [category, setCategory] = useState(article?.category || 'general');
  const [tags, setTags] = useState(article?.tags?.join(', ') || '');
  const [status, setStatus] = useState<'draft' | 'published' | 'archived'>(
    (article?.status as 'draft' | 'published' | 'archived') || 'published'
  );
  const [cardImage, setCardImage] = useState(article?.card_image || '');
  const [ogImage, setOgImage] = useState(article?.og_image || '');

  const [previewMode, setPreviewMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [uploadingCard, setUploadingCard] = useState(false);
  const [uploadingOg, setUploadingOg] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const cardFileRef = useRef<HTMLInputElement>(null);
  const ogFileRef = useRef<HTMLInputElement>(null);

  // Auto-generate excerpt from content if not provided
  useEffect(() => {
    if (!excerpt && content) {
      const plainText = content
        .replace(/[#*_`\[\]()]/g, '')
        .replace(/\n+/g, ' ')
        .trim();
      if (plainText.length > 0) {
        setExcerpt(plainText.substring(0, 150) + (plainText.length > 150 ? '...' : ''));
      }
    }
  }, [content, excerpt]);

  // ── Image Upload (reuses blog R2 bucket) ──
  const uploadImage = async (file: File, folder: string): Promise<string> => {
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      throw new Error('Only JPEG, PNG, and WebP images are allowed.');
    }
    if (file.size > MAX_IMAGE_SIZE) {
      throw new Error('Image must be under 5 MB.');
    }

    const baseUrl = getApiBaseUrl();
    const params = new URLSearchParams({
      filename: file.name,
      content_type: file.type,
      folder,
    });

    // Uses the shared blog upload endpoint (same R2 bucket)
    const res = await fetch(`${baseUrl}/admin/blog/upload-url?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || 'Failed to get upload URL');
    }
    const { upload_url, cdn_url } = await res.json();

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
    setUploadError('');
    try {
      const url = await uploadImage(file, 'kb/cards');
      setCardImage(url);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Card image upload failed');
    } finally {
      setUploadingCard(false);
    }
  };

  const handleOgImageUpload = async (file: File) => {
    setUploadingOg(true);
    setUploadError('');
    try {
      const url = await uploadImage(file, 'kb/og');
      setOgImage(url);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'OG image upload failed');
    } finally {
      setUploadingOg(false);
    }
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!title.trim() || title.length < 5) {
      newErrors.title = 'Title must be at least 5 characters';
    }
    if (title.length > 200) {
      newErrors.title = 'Title must be less than 200 characters';
    }

    if (!content.trim() || content.length < 50) {
      newErrors.content = 'Content must be at least 50 characters';
    }

    if (!excerpt.trim() || excerpt.length < 20) {
      newErrors.excerpt = 'Excerpt must be at least 20 characters';
    }
    if (excerpt.length > 500) {
      newErrors.excerpt = 'Excerpt must be less than 500 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) {
      return;
    }

    try {
      setSaving(true);

      const tagsArray = tags
        .split(',')
        .map(tag => tag.trim().toLowerCase())
        .filter(tag => tag.length > 0);

      const articleData: Record<string, unknown> = {
        title,
        content,
        excerpt,
        category,
        tags: tagsArray,
        status,
      };

      // Include images if set
      if (cardImage) articleData.card_image = cardImage;
      if (ogImage) articleData.og_image = ogImage;

      if (isEditing) {
        await apiRequest(`/admin/kb/articles/${article.id}`, 'PUT', articleData);
        alert('Article updated successfully!');
      } else {
        await apiRequest('/admin/kb/articles', 'POST', articleData);
        alert('Article created successfully!');
      }

      onSuccess();
    } catch (error: any) {
      console.error('Error saving article:', error);
      alert(error?.message || 'Failed to save article. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <Card className="overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-slate-700">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              {isEditing ? 'Edit Article' : 'Write New Article'}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              Share your knowledge with other wedding planners
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPreviewMode(!previewMode)}
              className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                previewMode
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                  : 'text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-slate-700 hover:bg-gray-200 dark:hover:bg-slate-600'
              }`}
            >
              {previewMode ? <Edit3 className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              {previewMode ? 'Edit' : 'Preview'}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {previewMode ? (
            /* Preview Mode */
            <div className="space-y-6">
              {cardImage && (
                <div className="relative h-48 rounded-lg overflow-hidden">
                  <img src={cardImage} alt="Card preview" className="w-full h-full object-cover" />
                </div>
              )}
              <div className="px-3 py-1 inline-block text-sm font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                {KB_CATEGORIES.find(c => c.value === category)?.label || category}
              </div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
                {title || 'Article Title'}
              </h1>
              <p className="text-gray-600 dark:text-gray-400 italic">
                {excerpt || 'Article excerpt will appear here...'}
              </p>
              <div className="prose prose-slate dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content || '*Start writing your article content...*'}
                </ReactMarkdown>
              </div>
              {tags && (
                <div className="flex flex-wrap gap-2 pt-4 border-t border-gray-200 dark:border-slate-700">
                  {tags.split(',').map((tag, index) => (
                    <span
                      key={index}
                      className="px-3 py-1 text-sm bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-400 rounded-full"
                    >
                      #{tag.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Edit Mode */
            <div className="space-y-6">
              {/* Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter a descriptive title"
                  className={`w-full px-4 py-3 border rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    errors.title ? 'border-red-500' : 'border-gray-300 dark:border-slate-600'
                  }`}
                />
                {errors.title && (
                  <p className="mt-1 text-sm text-red-500">{errors.title}</p>
                )}
              </div>

              {/* Category and Status */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {KB_CATEGORIES.map((cat) => (
                      <option key={cat.value} value={cat.value}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Status
                  </label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value as 'draft' | 'published' | 'archived')}
                    className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    <option value="published">Published</option>
                    <option value="draft">Draft</option>
                    <option value="archived">Archived</option>
                  </select>
                </div>
              </div>

              {/* ── Image Upload Section ── */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 space-y-4">
                <div className="flex items-center gap-2 mb-1">
                  <ImageIcon className="w-4 h-4 text-blue-500" />
                  <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Article Images</h3>
                </div>

                {uploadError && (
                  <p className="text-sm text-red-500 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded-lg">{uploadError}</p>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Card Image */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                      Card / Thumbnail Image
                    </label>
                    {cardImage ? (
                      <div className="relative group rounded-lg overflow-hidden border border-slate-200 dark:border-slate-600">
                        <img src={cardImage} alt="Card" className="w-full h-32 object-cover" />
                        <button
                          onClick={() => setCardImage('')}
                          className="absolute top-2 right-2 p-1 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => cardFileRef.current?.click()}
                        disabled={uploadingCard}
                        className="w-full h-32 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-blue-400 dark:hover:border-blue-500 transition text-slate-400 hover:text-blue-500"
                      >
                        {uploadingCard ? (
                          <Loader2 className="w-6 h-6 animate-spin" />
                        ) : (
                          <>
                            <Upload className="w-5 h-5 mb-1" />
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
                        const f = e.target.files?.[0];
                        if (f) handleCardImageUpload(f);
                        e.target.value = '';
                      }}
                    />
                    {/* Manual URL input */}
                    <input
                      type="text"
                      value={cardImage}
                      onChange={(e) => setCardImage(e.target.value)}
                      placeholder="Or paste CDN URL"
                      className="mt-2 w-full px-3 py-1.5 text-xs border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-300"
                    />
                  </div>

                  {/* OG / Social Image */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                      OG / Social Share Image
                    </label>
                    {ogImage ? (
                      <div className="relative group rounded-lg overflow-hidden border border-slate-200 dark:border-slate-600">
                        <img src={ogImage} alt="OG" className="w-full h-32 object-cover" />
                        <button
                          onClick={() => setOgImage('')}
                          className="absolute top-2 right-2 p-1 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => ogFileRef.current?.click()}
                        disabled={uploadingOg}
                        className="w-full h-32 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-blue-400 dark:hover:border-blue-500 transition text-slate-400 hover:text-blue-500"
                      >
                        {uploadingOg ? (
                          <Loader2 className="w-6 h-6 animate-spin" />
                        ) : (
                          <>
                            <Upload className="w-5 h-5 mb-1" />
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
                        const f = e.target.files?.[0];
                        if (f) handleOgImageUpload(f);
                        e.target.value = '';
                      }}
                    />
                    <input
                      type="text"
                      value={ogImage}
                      onChange={(e) => setOgImage(e.target.value)}
                      placeholder="Or paste CDN URL"
                      className="mt-2 w-full px-3 py-1.5 text-xs border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-700 dark:text-gray-300"
                    />
                  </div>
                </div>
              </div>

              {/* Excerpt */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Excerpt <span className="text-red-500">*</span>
                  <span className="font-normal text-gray-500 dark:text-gray-400 ml-2">
                    (Short summary shown in article listings)
                  </span>
                </label>
                <textarea
                  value={excerpt}
                  onChange={(e) => setExcerpt(e.target.value)}
                  placeholder="A brief summary of your article (20-500 characters)"
                  rows={2}
                  className={`w-full px-4 py-3 border rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none ${
                    errors.excerpt ? 'border-red-500' : 'border-gray-300 dark:border-slate-600'
                  }`}
                />
                <div className="flex justify-between mt-1">
                  {errors.excerpt ? (
                    <p className="text-sm text-red-500">{errors.excerpt}</p>
                  ) : (
                    <span />
                  )}
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {excerpt.length}/500
                  </span>
                </div>
              </div>

              {/* Content */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Content <span className="text-red-500">*</span>
                  <span className="font-normal text-gray-500 dark:text-gray-400 ml-2">
                    (Supports Markdown formatting)
                  </span>
                </label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Write your article content here using Markdown...

# Heading 1
## Heading 2

**Bold text** and *italic text*

- Bullet point 1
- Bullet point 2

1. Numbered item
2. Another item

`code snippet`

```
code block
```

[Link text](https://example.com)"
                  rows={20}
                  className={`w-full px-4 py-3 border rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm resize-y ${
                    errors.content ? 'border-red-500' : 'border-gray-300 dark:border-slate-600'
                  }`}
                />
                {errors.content && (
                  <p className="mt-1 text-sm text-red-500">{errors.content}</p>
                )}
              </div>

              {/* Tags */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Tags
                  <span className="font-normal text-gray-500 dark:text-gray-400 ml-2">
                    (Comma-separated, helps with search)
                  </span>
                </label>
                <input
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="guest-list, rsvp, tips, beginner"
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center p-6 border-t border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700/50">
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <FileText className="w-4 h-4" />
            {content.split(/\s+/).filter(Boolean).length} words
          </div>
          <div className="flex gap-3">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-600 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  {isEditing ? 'Update Article' : 'Publish Article'}
                </>
              )}
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}
