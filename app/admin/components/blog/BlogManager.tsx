'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import BlogArticleList from './BlogArticleList';
import BlogArticleEditor from './BlogArticleEditor';
import BlogCategorySidebar from './BlogCategorySidebar';
import SyncBabyLoveGrowthButton from './SyncBabyLoveGrowthButton';
import {
  Search,
  Plus,
  BookOpen,
  ArrowLeft,
  Loader2,
  RefreshCw,
} from 'lucide-react';

export interface BlogArticle {
  id: string;
  _id: string;
  title: string;
  slug: string;
  excerpt: string;
  content?: string;
  category: string;
  tags: string[];
  status: string;
  featured: boolean;
  author_name: string;
  author_email: string;
  meta_title?: string;
  meta_description?: string;
  og_image?: string;
  card_image?: string;
  view_count: number;
  estimated_read_minutes: number;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

type ViewMode = 'list' | 'create' | 'edit';

export default function BlogManager() {
  const { apiRequest } = useAdmin();

  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<BlogArticle | null>(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [totalArticles, setTotalArticles] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});

  const fetchArticles = useCallback(async (page: number = 1) => {
    try {
      setLoading(true);
      let endpoint = `/admin/blog/articles?page=${page}&limit=12`;

      // Handle category vs status filtering
      if (selectedCategory.startsWith('status:')) {
        const status = selectedCategory.replace('status:', '');
        endpoint += `&status=${status}`;
      } else if (selectedCategory && selectedCategory !== 'all') {
        endpoint += `&category=${selectedCategory}`;
      }

      if (searchQuery && searchQuery.length >= 2) {
        endpoint += `&search=${encodeURIComponent(searchQuery)}`;
      }

      const data = await apiRequest(endpoint);
      setArticles(data.articles || []);
      setTotalArticles(data.total || 0);
      setCurrentPage(data.page || 1);
      setTotalPages(data.pages || 1);
    } catch (error) {
      console.error('Failed to fetch blog articles:', error);
    } finally {
      setLoading(false);
    }
  }, [apiRequest, selectedCategory, searchQuery]);

  // Fetch category counts on mount
  const fetchCategoryCounts = useCallback(async () => {
    try {
      const data = await apiRequest('/admin/blog/articles?limit=100');
      const counts: Record<string, number> = {};
      for (const article of (data.articles || [])) {
        counts[article.category] = (counts[article.category] || 0) + 1;
      }
      setCategoryCounts(counts);
    } catch {
      // Silently fail — counts are optional
    }
  }, [apiRequest]);

  useEffect(() => {
    fetchArticles(1);
  }, [fetchArticles]);

  useEffect(() => {
    fetchCategoryCounts();
  }, [fetchCategoryCounts]);

  const handleEdit = async (articleId: string) => {
    try {
      const article = await apiRequest(`/admin/blog/articles/${articleId}`);
      setSelectedArticle(article);
      setViewMode('edit');
    } catch (error) {
      console.error('Failed to fetch article:', error);
    }
  };

  const handleDelete = async (articleId: string) => {
    if (!confirm('Are you sure you want to delete this blog article?')) return;
    try {
      await apiRequest(`/admin/blog/articles/${articleId}`, 'DELETE');
      fetchArticles(currentPage);
      fetchCategoryCounts();
    } catch (error) {
      console.error('Failed to delete article:', error);
    }
  };

  const handleSave = async (articleData: Record<string, unknown>, articleId?: string) => {
    try {
      if (articleId) {
        await apiRequest(`/admin/blog/articles/${articleId}`, 'PUT', articleData);
      } else {
        await apiRequest(`/admin/blog/articles`, 'POST', articleData);
      }
      setViewMode('list');
      setSelectedArticle(null);
      fetchArticles(1);
      fetchCategoryCounts();
    } catch (error) {
      console.error('Failed to save article:', error);
      throw error;
    }
  };

  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
    setCurrentPage(1);
  };

  // Editor view
  if (viewMode === 'create' || viewMode === 'edit') {
    return (
      <div>
        <button
          onClick={() => { setViewMode('list'); setSelectedArticle(null); }}
          className="mb-4 flex items-center gap-2 text-sm text-slate-600 transition hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to articles
        </button>
        <BlogArticleEditor
          article={viewMode === 'edit' ? selectedArticle : null}
          onSave={handleSave}
          onCancel={() => { setViewMode('list'); setSelectedArticle(null); }}
        />
      </div>
    );
  }

  // List view — grid layout with sidebar (matching KB)
  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-wedding-rose" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Blog Articles</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400">{totalArticles} articles on /resources</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SyncBabyLoveGrowthButton
            onSyncComplete={() => { fetchArticles(currentPage); fetchCategoryCounts(); }}
          />
          <button
            onClick={() => { fetchArticles(currentPage); fetchCategoryCounts(); }}
            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:shadow-none dark:hover:text-white dark:hover:bg-white/10"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => setViewMode('create')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-wedding-rose text-white text-sm font-medium hover:bg-wedding-blush transition"
          >
            <Plus className="w-4 h-4" />
            New Article
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Search articles..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:outline-none focus:border-wedding-rose/50 focus:ring-2 focus:ring-wedding-rose/15 dark:border-white/10 dark:bg-white/5 dark:text-white dark:placeholder-slate-500 dark:shadow-none"
        />
      </div>

      {/* Grid layout: Sidebar + Cards (matching KB layout) */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Category Sidebar */}
        <div className="lg:col-span-1">
          <BlogCategorySidebar
            selectedCategory={selectedCategory}
            onCategoryChange={handleCategoryChange}
            categoryCounts={categoryCounts}
            totalArticles={totalArticles}
          />
        </div>

        {/* Article Grid */}
        <div className="lg:col-span-3">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-6 h-6 text-wedding-rose animate-spin" />
            </div>
          ) : articles.length === 0 ? (
            <Card className="p-12 text-center">
              <BookOpen className="mx-auto mb-3 h-10 w-10 text-slate-400 dark:text-slate-600" />
              <p className="mb-2 text-slate-600 dark:text-slate-400">No blog articles found.</p>
              <p className="mb-4 text-xs text-slate-500 dark:text-slate-500">
                {searchQuery ? 'Try a different search term.' : 'Create your first article to get started.'}
              </p>
              <button
                onClick={() => setViewMode('create')}
                className="text-sm text-wedding-rose hover:text-wedding-blush transition"
              >
                Create your first article →
              </button>
            </Card>
          ) : (
            <BlogArticleList
              articles={articles}
              onEdit={handleEdit}
              onDelete={handleDelete}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={(page) => fetchArticles(page)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
