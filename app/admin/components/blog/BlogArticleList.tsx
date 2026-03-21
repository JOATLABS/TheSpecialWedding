'use client';

import { BlogArticle } from './BlogManager';
import BlogArticleCard from './BlogArticleCard';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface BlogArticleListProps {
  articles: BlogArticle[];
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export default function BlogArticleList({
  articles,
  onEdit,
  onDelete,
  currentPage,
  totalPages,
  onPageChange,
}: BlogArticleListProps) {
  return (
    <div className="space-y-6">
      {/* Article Grid — matches KB layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {articles.map((article) => (
          <BlogArticleCard
            key={article.id || article._id}
            article={article}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-6">
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-slate-300 bg-slate-800 border border-slate-600 rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </button>

          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter(page => {
                return page === 1 ||
                       page === totalPages ||
                       Math.abs(page - currentPage) <= 1;
              })
              .map((page, index, filtered) => {
                const prevPage = filtered[index - 1];
                const showEllipsis = prevPage && page - prevPage > 1;

                return (
                  <div key={page} className="flex items-center gap-1">
                    {showEllipsis && (
                      <span className="px-2 py-1 text-slate-500">...</span>
                    )}
                    <button
                      onClick={() => onPageChange(page)}
                      className={`w-10 h-10 text-sm font-medium rounded-lg transition-colors ${
                        page === currentPage
                          ? 'bg-wedding-rose text-white'
                          : 'text-slate-300 bg-slate-800 border border-slate-600 hover:bg-slate-700'
                      }`}
                    >
                      {page}
                    </button>
                  </div>
                );
              })}
          </div>

          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-slate-300 bg-slate-800 border border-slate-600 rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
