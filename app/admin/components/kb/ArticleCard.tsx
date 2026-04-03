'use client';

import { KBArticle } from './KnowledgeBase';
import { formatDate } from '@/utils/dateFormat';
import {
  Clock,
  Eye,
  ThumbsUp,
  Star,
  CheckCircle,
  Image as ImageIcon,
} from 'lucide-react';

interface ArticleCardProps {
  article: KBArticle;
  onClick: () => void;
}

// Category colors
const categoryColors: Record<string, string> = {
  'getting-started': 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  'guest-management': 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  'rsvp-invitations': 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  'budget-payments': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  'vendors': 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  'forms-questionnaires': 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300',
  'wedding-configuration': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300',
  'notifications': 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300',
  'calendar-tasks': 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300',
  'billing-subscription': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  'troubleshooting': 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  'tips-tricks': 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300',
  'integrations': 'bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300',
  'general': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
};

// Category display names
const categoryDisplayNames: Record<string, string> = {
  'getting-started': 'Getting Started',
  'guest-management': 'Guest Management',
  'rsvp-invitations': 'RSVP & Invitations',
  'budget-payments': 'Budget & Payments',
  'vendors': 'Vendors',
  'forms-questionnaires': 'Forms',
  'wedding-configuration': 'Configuration',
  'notifications': 'Notifications',
  'calendar-tasks': 'Calendar',
  'billing-subscription': 'Billing',
  'troubleshooting': 'Troubleshooting',
  'tips-tricks': 'Tips & Tricks',
  'integrations': 'Integrations',
  'general': 'General'
};

export default function ArticleCard({ article, onClick }: ArticleCardProps) {
  const categoryColor = categoryColors[article.category] || categoryColors['general'];
  const categoryName = categoryDisplayNames[article.category] || article.category;

  return (
    <div
      onClick={onClick}
      className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 hover:shadow-lg hover:border-blue-300 dark:hover:border-blue-600 transition-all cursor-pointer group overflow-hidden"
    >
      {/* Card Image */}
      {article.card_image ? (
        <div className="relative h-36 overflow-hidden">
          <img
            src={article.card_image}
            alt={article.title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/40 to-transparent" />
        </div>
      ) : (
        <div className="relative h-24 bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-700/50 dark:to-slate-800/50 flex items-center justify-center">
          <ImageIcon className="w-8 h-8 text-slate-300 dark:text-slate-600" />
        </div>
      )}

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`px-2 py-1 text-xs font-medium rounded-full ${categoryColor}`}>
              {categoryName}
            </span>
            {article.is_official && (
              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                <CheckCircle className="w-3 h-3" />
                Official
              </span>
            )}
            {article.featured && (
              <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
            )}
          </div>
        </div>

        {/* Title */}
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors line-clamp-2">
          {article.title}
        </h3>

        {/* Excerpt */}
        <p className="text-gray-600 dark:text-gray-400 text-sm mb-4 line-clamp-2">
          {article.excerpt}
        </p>

        {/* Tags */}
        {article.tags && article.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {article.tags.slice(0, 3).map((tag, index) => (
              <span
                key={index}
                className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-400 rounded"
              >
                {tag}
              </span>
            ))}
            {article.tags.length > 3 && (
              <span className="px-2 py-0.5 text-xs text-gray-500 dark:text-gray-400">
                +{article.tags.length - 3} more
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-slate-700">
          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {article.estimated_read_minutes} min read
            </span>
            <span className="flex items-center gap-1">
              <Eye className="w-3.5 h-3.5" />
              {article.view_count}
            </span>
            <span className="flex items-center gap-1">
              <ThumbsUp className="w-3.5 h-3.5" />
              {article.helpful_count}
            </span>
          </div>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {formatDate(article.created_at)}
          </span>
        </div>

        {/* Author */}
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-slate-700">
          <p className="text-xs text-gray-500 dark:text-gray-400">
            By <span className="font-medium text-gray-700 dark:text-gray-300">{article.author_name}</span>
          </p>
        </div>
      </div>
    </div>
  );
}
