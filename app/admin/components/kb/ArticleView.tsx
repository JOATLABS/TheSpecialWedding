'use client';

import { useState } from 'react';
import { useAdmin } from '@/contexts/AdminContext';
import { KBArticle } from './KnowledgeBase';
import { Card } from '@/components/ui/Card';
import { formatDate } from '@/utils/dateFormat';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Clock,
  Eye,
  ThumbsUp,
  ThumbsDown,
  Star,
  CheckCircle,
  Edit,
  Trash2,
  Share2,
  Loader2
} from 'lucide-react';

interface ArticleViewProps {
  article: KBArticle;
  isRootAdmin: boolean;
  onEdit: () => void;
  onBack: () => void;
}

// Category display names
const categoryDisplayNames: Record<string, string> = {
  'getting-started': 'Getting Started',
  'guest-management': 'Guest Management',
  'rsvp-invitations': 'RSVP & Invitations',
  'budget-payments': 'Budget & Payments',
  'vendors': 'Vendors',
  'forms-questionnaires': 'Forms & Questionnaires',
  'wedding-configuration': 'Wedding Configuration',
  'notifications': 'Notifications',
  'calendar-tasks': 'Calendar & Tasks',
  'billing-subscription': 'Billing & Subscription',
  'troubleshooting': 'Troubleshooting',
  'tips-tricks': 'Tips & Tricks',
  'integrations': 'Integrations',
  'general': 'General'
};

export default function ArticleView({ article, isRootAdmin, onEdit, onBack }: ArticleViewProps) {
  const { apiRequest, userProfile } = useAdmin();
  const [feedback, setFeedback] = useState<'helpful' | 'not_helpful' | null>(null);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const canEdit = isRootAdmin || article.author_email === userProfile?.email;
  const categoryName = categoryDisplayNames[article.category] || article.category;

  const handleFeedback = async (helpful: boolean) => {
    try {
      setSubmittingFeedback(true);
      await apiRequest(`/admin/kb/articles/${article.id}/feedback`, 'POST', {
        helpful,
        comment: null
      });
      setFeedback(helpful ? 'helpful' : 'not_helpful');
    } catch (error) {
      console.error('Error submitting feedback:', error);
      alert('Failed to submit feedback');
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this article? This action cannot be undone.')) {
      return;
    }

    try {
      setDeleting(true);
      await apiRequest(`/admin/kb/articles/${article.id}`, 'DELETE');
      alert('Article deleted successfully');
      onBack();
    } catch (error) {
      console.error('Error deleting article:', error);
      alert('Failed to delete article');
    } finally {
      setDeleting(false);
    }
  };

  const handleShare = () => {
    const url = `${window.location.origin}/admin/support?article=${article.slug}`;
    navigator.clipboard.writeText(url);
    alert('Article link copied to clipboard!');
  };

  return (
    <div className="max-w-4xl mx-auto">
      <Card className="overflow-hidden">
        {/* Article Header */}
        <div className="p-6 sm:p-8 border-b border-gray-200 dark:border-slate-700">
          {/* Badges */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="px-3 py-1 text-sm font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
              {categoryName}
            </span>
            {article.is_official && (
              <span className="inline-flex items-center gap-1 px-3 py-1 text-sm font-medium rounded-full bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                <CheckCircle className="w-3.5 h-3.5" />
                Official
              </span>
            )}
            {article.featured && (
              <span className="inline-flex items-center gap-1 px-3 py-1 text-sm font-medium rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
                <Star className="w-3.5 h-3.5" />
                Featured
              </span>
            )}
          </div>

          {/* Title */}
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-gray-100 mb-4">
            {article.title}
          </h1>

          {/* Meta */}
          <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {article.estimated_read_minutes} min read
            </span>
            <span className="flex items-center gap-1">
              <Eye className="w-4 h-4" />
              {article.view_count} views
            </span>
            <span className="flex items-center gap-1">
              <ThumbsUp className="w-4 h-4" />
              {article.helpful_count} found helpful
            </span>
            <span>Updated {formatDate(article.updated_at)}</span>
          </div>

          {/* Author */}
          <div className="mt-4 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-medium">
              {article.author_name?.charAt(0).toUpperCase() || 'A'}
            </div>
            <div>
              <p className="font-medium text-gray-900 dark:text-gray-100">{article.author_name}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">Author</p>
            </div>
          </div>

          {/* Action Buttons */}
          {canEdit && (
            <div className="mt-6 flex flex-wrap gap-2">
              <button
                onClick={onEdit}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-600 transition-colors"
              >
                <Edit className="w-4 h-4" />
                Edit
              </button>
              <button
                onClick={handleShare}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-600 transition-colors"
              >
                <Share2 className="w-4 h-4" />
                Share
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-white dark:bg-slate-700 border border-red-300 dark:border-red-600 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
              >
                {deleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                Delete
              </button>
            </div>
          )}
        </div>

        {/* Article Content */}
        <div className="p-6 sm:p-8">
          <div className="prose prose-slate dark:prose-invert max-w-none prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-code:bg-gray-100 dark:prose-code:bg-slate-700 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-pre:bg-gray-100 dark:prose-pre:bg-slate-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {article.content || ''}
            </ReactMarkdown>
          </div>
        </div>

        {/* Tags */}
        {article.tags && article.tags.length > 0 && (
          <div className="px-6 sm:px-8 pb-6">
            <div className="flex flex-wrap gap-2">
              {article.tags.map((tag, index) => (
                <span
                  key={index}
                  className="px-3 py-1 text-sm bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-400 rounded-full"
                >
                  #{tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Feedback Section */}
        <div className="px-6 sm:px-8 py-6 bg-gray-50 dark:bg-slate-700/50 border-t border-gray-200 dark:border-slate-700">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-gray-700 dark:text-gray-300 font-medium">
              Was this article helpful?
            </p>
            <div className="flex items-center gap-3">
              {feedback ? (
                <p className="text-green-600 dark:text-green-400 font-medium">
                  Thanks for your feedback!
                </p>
              ) : (
                <>
                  <button
                    onClick={() => handleFeedback(true)}
                    disabled={submittingFeedback}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-green-700 dark:text-green-300 bg-green-100 dark:bg-green-900/30 rounded-lg hover:bg-green-200 dark:hover:bg-green-900/50 transition-colors disabled:opacity-50"
                  >
                    {submittingFeedback ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ThumbsUp className="w-4 h-4" />
                    )}
                    Yes, helpful
                  </button>
                  <button
                    onClick={() => handleFeedback(false)}
                    disabled={submittingFeedback}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-slate-600 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-500 transition-colors disabled:opacity-50"
                  >
                    {submittingFeedback ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ThumbsDown className="w-4 h-4" />
                    )}
                    Not helpful
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
