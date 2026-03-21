'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { Card } from '@/components/ui/Card';
import ArticleList from './ArticleList';
import ArticleView from './ArticleView';
import ArticleEditor from './ArticleEditor';
import CategorySidebar from './CategorySidebar';
import {
  Search,
  Plus,
  BookOpen,
  ArrowLeft,
  Loader2
} from 'lucide-react';

export interface KBArticle {
  id: string;
  _id: string;
  title: string;
  slug: string;
  excerpt: string;
  content?: string;
  category: string;
  tags: string[];
  status: string;
  is_official: boolean;
  featured: boolean;
  author_name: string;
  author_email: string;
  view_count: number;
  helpful_count: number;
  not_helpful_count: number;
  card_image?: string;
  og_image?: string;
  estimated_read_minutes: number;
  created_at: string;
  updated_at: string;
  author_info?: {
    name: string;
    first_name?: string;
    last_name?: string;
    company_name?: string;
    profile_image_url?: string;
  };
}

export interface KBCategory {
  category: string;
  display_name: string;
  article_count: number;
}

interface KnowledgeBaseProps {
  isRootAdmin: boolean;
}

type ViewMode = 'list' | 'view' | 'create' | 'edit' | 'my-articles';

export default function KnowledgeBase({ isRootAdmin }: KnowledgeBaseProps) {
  const { apiRequest } = useAdmin();

  // State
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [articles, setArticles] = useState<KBArticle[]>([]);
  const [categories, setCategories] = useState<KBCategory[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<KBArticle | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [totalArticles, setTotalArticles] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Fetch articles
  const fetchArticles = useCallback(async (category?: string, search?: string, page: number = 1) => {
    try {
      setLoading(true);

      let endpoint = `/admin/kb/articles?page=${page}&limit=12`;
      if (category && category !== 'all') {
        endpoint += `&category=${category}`;
      }
      if (search && search.length >= 2) {
        endpoint = `/admin/kb/search?q=${encodeURIComponent(search)}&limit=20`;
      }

      const response = await apiRequest<{
        articles: KBArticle[];
        total: number;
        page: number;
        pages: number;
      }>(endpoint, 'GET');

      setArticles(response?.articles || []);
      setTotalArticles(response?.total || 0);
      setCurrentPage(response?.page || 1);
      setTotalPages(response?.pages || 1);
    } catch (error) {
      console.error('Error fetching articles:', error);
      setArticles([]);
    } finally {
      setLoading(false);
      setSearching(false);
    }
  }, [apiRequest]);

  // Fetch categories
  const fetchCategories = useCallback(async () => {
    try {
      const response = await apiRequest<{
        categories: KBCategory[];
        total_articles: number;
      }>('/admin/kb/categories', 'GET');

      setCategories(response?.categories || []);
    } catch (error) {
      console.error('Error fetching categories:', error);
      setCategories([]);
    }
  }, [apiRequest]);

  // Fetch my articles
  const fetchMyArticles = useCallback(async (page: number = 1) => {
    try {
      setLoading(true);
      const response = await apiRequest<{
        articles: KBArticle[];
        total: number;
        page: number;
        pages: number;
      }>(`/admin/kb/my-articles?page=${page}&limit=12`, 'GET');

      setArticles(response?.articles || []);
      setTotalArticles(response?.total || 0);
      setCurrentPage(response?.page || 1);
      setTotalPages(response?.pages || 1);
    } catch (error) {
      console.error('Error fetching my articles:', error);
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [apiRequest]);

  // Initial load
  useEffect(() => {
    fetchCategories();
    fetchArticles();
  }, [fetchCategories, fetchArticles]);

  // Handle category change
  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
    setSearchQuery('');
    setCurrentPage(1);
    if (viewMode === 'my-articles') {
      setViewMode('list');
    }
    fetchArticles(category, '', 1);
  };

  // Handle search
  const handleSearch = (query: string) => {
    setSearchQuery(query);
    if (query.length >= 2) {
      setSearching(true);
      fetchArticles(selectedCategory, query);
    } else if (query.length === 0) {
      fetchArticles(selectedCategory);
    }
  };

  // Handle article click
  const handleArticleClick = async (article: KBArticle) => {
    try {
      // Fetch full article with content
      const fullArticle = await apiRequest<KBArticle>(
        `/admin/kb/articles/slug/${article.slug}`,
        'GET'
      );
      setSelectedArticle(fullArticle || null);
      setViewMode('view');
    } catch (error) {
      console.error('Error fetching article:', error);
    }
  };

  // Handle back navigation
  const handleBack = () => {
    setSelectedArticle(null);
    setViewMode('list');
    // Refresh articles after potential edits
    if (viewMode === 'edit' || viewMode === 'create') {
      fetchArticles(selectedCategory, searchQuery);
      fetchCategories();
    }
  };

  // Handle article creation success
  const handleArticleCreated = () => {
    setViewMode('list');
    fetchArticles(selectedCategory, searchQuery);
    fetchCategories();
  };

  // Handle article update success
  const handleArticleUpdated = () => {
    setViewMode('list');
    setSelectedArticle(null);
    fetchArticles(selectedCategory, searchQuery);
    fetchCategories();
  };

  // Handle my articles click
  const handleMyArticlesClick = () => {
    setViewMode('my-articles');
    setSelectedCategory('all');
    setSearchQuery('');
    fetchMyArticles(1);
  };

  // Render based on view mode
  if (viewMode === 'create') {
    return (
      <div className="space-y-4">
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Articles
        </button>
        <ArticleEditor
          onSuccess={handleArticleCreated}
          onCancel={handleBack}
        />
      </div>
    );
  }

  if (viewMode === 'edit' && selectedArticle) {
    return (
      <div className="space-y-4">
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Articles
        </button>
        <ArticleEditor
          article={selectedArticle}
          onSuccess={handleArticleUpdated}
          onCancel={handleBack}
        />
      </div>
    );
  }

  if (viewMode === 'view' && selectedArticle) {
    return (
      <div className="space-y-4">
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Articles
        </button>
        <ArticleView
          article={selectedArticle}
          isRootAdmin={isRootAdmin}
          onEdit={() => setViewMode('edit')}
          onBack={handleBack}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Knowledge Base</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {viewMode === 'my-articles' ? 'Your contributed articles' : 'Documentation and guides for planners'}
          </p>
        </div>
        {isRootAdmin && (
          <div className="flex gap-2">
            <button
              onClick={handleMyArticlesClick}
              className={`px-4 py-2 border rounded-lg transition-colors text-sm font-medium ${
                viewMode === 'my-articles'
                  ? 'bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-900/30 dark:border-blue-700 dark:text-blue-300'
                  : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
              }`}
            >
              My Articles
            </button>
            <button
              onClick={() => setViewMode('create')}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              Write Article
            </button>
          </div>
        )}
      </div>

      {/* Search Bar */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search articles..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base"
          />
          {searching && (
            <Loader2 className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400 animate-spin" />
          )}
        </div>
      </Card>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Category Sidebar */}
        {viewMode !== 'my-articles' && (
          <div className="lg:col-span-1">
            <CategorySidebar
              categories={categories}
              selectedCategory={selectedCategory}
              onCategoryChange={handleCategoryChange}
              totalArticles={totalArticles}
            />
          </div>
        )}

        {/* Article List */}
        <div className={viewMode === 'my-articles' ? 'lg:col-span-4' : 'lg:col-span-3'}>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
                <p className="text-gray-500 dark:text-gray-400">Loading articles...</p>
              </div>
            </div>
          ) : articles.length > 0 ? (
            <ArticleList
              articles={articles}
              onArticleClick={handleArticleClick}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={(page) => {
                setCurrentPage(page);
                if (viewMode === 'my-articles') {
                  fetchMyArticles(page);
                } else {
                  fetchArticles(selectedCategory, searchQuery, page);
                }
              }}
            />
          ) : (
            <Card className="p-12 text-center">
              <BookOpen className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
                {searchQuery ? 'No articles found' : viewMode === 'my-articles' ? 'No articles yet' : 'No articles in this category'}
              </h3>
              <p className="text-gray-500 dark:text-gray-400 mb-6">
                {searchQuery
                  ? 'Try adjusting your search terms'
                  : viewMode === 'my-articles'
                  ? 'You haven\'t written any articles yet.'
                  : isRootAdmin
                  ? 'Be the first to write an article in this category!'
                  : 'No articles available in this category yet. Check back soon!'}
              </p>
              {isRootAdmin && (
                <button
                  onClick={() => setViewMode('create')}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Write Article
                </button>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
