'use client';

import { KBCategory } from './KnowledgeBase';
import { Card } from '@/components/ui/Card';
import {
  BookOpen,
  Users,
  Mail,
  DollarSign,
  Store,
  FileText,
  Settings,
  Bell,
  Calendar,
  CreditCard,
  AlertCircle,
  Lightbulb,
  Puzzle,
  MessageSquare,
  Layers
} from 'lucide-react';

interface CategorySidebarProps {
  categories: KBCategory[];
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
  totalArticles: number;
}

// Category icons
const categoryIcons: Record<string, React.ReactNode> = {
  'getting-started': <BookOpen className="w-4 h-4" />,
  'guest-management': <Users className="w-4 h-4" />,
  'rsvp-invitations': <Mail className="w-4 h-4" />,
  'budget-payments': <DollarSign className="w-4 h-4" />,
  'vendors': <Store className="w-4 h-4" />,
  'forms-questionnaires': <FileText className="w-4 h-4" />,
  'wedding-configuration': <Settings className="w-4 h-4" />,
  'notifications': <Bell className="w-4 h-4" />,
  'calendar-tasks': <Calendar className="w-4 h-4" />,
  'billing-subscription': <CreditCard className="w-4 h-4" />,
  'troubleshooting': <AlertCircle className="w-4 h-4" />,
  'tips-tricks': <Lightbulb className="w-4 h-4" />,
  'integrations': <Puzzle className="w-4 h-4" />,
  'general': <MessageSquare className="w-4 h-4" />
};

export default function CategorySidebar({
  categories,
  selectedCategory,
  onCategoryChange,
  totalArticles
}: CategorySidebarProps) {
  return (
    <Card className="p-4 sticky top-4">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
        <Layers className="w-4 h-4" />
        Categories
      </h3>

      <nav className="space-y-1">
        {/* All Articles */}
        <button
          onClick={() => onCategoryChange('all')}
          className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg transition-colors ${
            selectedCategory === 'all'
              ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 font-medium'
              : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700'
          }`}
        >
          <span className="flex items-center gap-2">
            <BookOpen className="w-4 h-4" />
            All Articles
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            selectedCategory === 'all'
              ? 'bg-blue-200 dark:bg-blue-800'
              : 'bg-gray-100 dark:bg-slate-600'
          }`}>
            {totalArticles}
          </span>
        </button>

        {/* Category List */}
        {categories.map((category) => (
          <button
            key={category.category}
            onClick={() => onCategoryChange(category.category)}
            className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg transition-colors ${
              selectedCategory === category.category
                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300 font-medium'
                : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-slate-700'
            }`}
          >
            <span className="flex items-center gap-2">
              {categoryIcons[category.category] || <MessageSquare className="w-4 h-4" />}
              <span className="truncate">{category.display_name}</span>
            </span>
            {category.article_count > 0 && (
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                selectedCategory === category.category
                  ? 'bg-blue-200 dark:bg-blue-800'
                  : 'bg-gray-100 dark:bg-slate-600'
              }`}>
                {category.article_count}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* Quick Tips */}
      <div className="mt-6 pt-4 border-t border-gray-200 dark:border-slate-700">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          <Lightbulb className="w-3 h-3 inline mr-1" />
          Share your knowledge! Write an article to help other planners.
        </p>
      </div>
    </Card>
  );
}
