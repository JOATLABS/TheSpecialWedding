'use client';

import { BlogArticle } from './BlogManager';
import {
  Clock,
  Eye,
  Star,
  Edit,
  Trash2,
  Image as ImageIcon,
} from 'lucide-react';

interface BlogArticleCardProps {
  article: BlogArticle;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}

// Category colors matching the dark theme
const categoryColors: Record<string, string> = {
  'platform-updates': 'bg-blue-500/15 text-blue-400',
  'pricing-strategy': 'bg-amber-500/15 text-amber-400',
  'guest-management': 'bg-cyan-500/15 text-cyan-400',
  'industry-comparison': 'bg-purple-500/15 text-purple-400',
  'contracts-legal': 'bg-orange-500/15 text-orange-400',
  'ai-technology': 'bg-violet-500/15 text-violet-400',
  'event-logistics': 'bg-teal-500/15 text-teal-400',
  'tips-guides': 'bg-emerald-500/15 text-emerald-400',
  'general': 'bg-slate-500/15 text-slate-400',
};

const categoryDisplayNames: Record<string, string> = {
  'platform-updates': 'Platform Updates',
  'pricing-strategy': 'Pricing Strategy',
  'guest-management': 'Guest Management',
  'industry-comparison': 'Industry Comparison',
  'contracts-legal': 'Contracts & Legal',
  'ai-technology': 'AI & Technology',
  'event-logistics': 'Event Logistics',
  'tips-guides': 'Tips & Guides',
  'general': 'General',
};

const statusColors: Record<string, string> = {
  published: 'bg-emerald-500/15 text-emerald-400',
  draft: 'bg-yellow-500/15 text-yellow-400',
  archived: 'bg-slate-500/15 text-slate-400',
};

export default function BlogArticleCard({ article, onEdit, onDelete }: BlogArticleCardProps) {
  const categoryColor = categoryColors[article.category] || categoryColors['general'];
  const categoryName = categoryDisplayNames[article.category] || article.category;
  const statusColor = statusColors[article.status] || statusColors.draft;

  return (
    <div className="group bg-slate-800/50 rounded-xl border border-slate-700/50 hover:border-wedding-rose/30 hover:shadow-lg hover:shadow-wedding-rose/5 transition-all cursor-pointer overflow-hidden">
      {/* Card Image */}
      {article.card_image ? (
        <div className="relative h-36 overflow-hidden">
          <img
            src={article.card_image}
            alt={article.title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/60 to-transparent" />
        </div>
      ) : (
        <div className="relative h-24 bg-gradient-to-br from-slate-700/50 to-slate-800/50 flex items-center justify-center">
          <ImageIcon className="w-8 h-8 text-slate-600" />
        </div>
      )}

      <div className="p-5">
        {/* Header badges */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${categoryColor}`}>
              {categoryName}
            </span>
            <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${statusColor}`}>
              {article.status}
            </span>
            {article.featured && (
              <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400" />
            )}
          </div>
        </div>

        {/* Title */}
        <h3 className="text-sm font-semibold text-white mb-2 group-hover:text-wedding-rose transition-colors line-clamp-2">
          {article.title}
        </h3>

        {/* Excerpt */}
        <p className="text-xs text-slate-400 mb-3 line-clamp-2">
          {article.excerpt}
        </p>

        {/* Tags */}
        {article.tags && article.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {article.tags.slice(0, 3).map((tag, index) => (
              <span
                key={index}
                className="px-1.5 py-0.5 text-[10px] bg-slate-700/50 text-slate-400 rounded"
              >
                {tag}
              </span>
            ))}
            {article.tags.length > 3 && (
              <span className="px-1.5 py-0.5 text-[10px] text-slate-500">
                +{article.tags.length - 3} more
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-700/50">
          <div className="flex items-center gap-3 text-[10px] text-slate-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {article.estimated_read_minutes} min
            </span>
            <span className="flex items-center gap-1">
              <Eye className="w-3 h-3" />
              {article.view_count}
            </span>
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
            <button
              onClick={(e) => { e.stopPropagation(); onEdit(article.id); }}
              className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition"
              title="Edit"
            >
              <Edit className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(article.id); }}
              className="p-1.5 rounded-lg hover:bg-red-500/10 text-slate-400 hover:text-red-400 transition"
              title="Delete"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Author */}
        <div className="mt-2 pt-2 border-t border-slate-700/50">
          <p className="text-[10px] text-slate-500">
            By <span className="font-medium text-slate-400">{article.author_name}</span>
          </p>
        </div>
      </div>
    </div>
  );
}
