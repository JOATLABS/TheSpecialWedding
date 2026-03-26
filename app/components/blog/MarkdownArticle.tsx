'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownArticleProps {
  content: string;
  className?: string;
}

export default function MarkdownArticle({ content, className = '' }: MarkdownArticleProps) {
  if (!content) {
    return <p className="text-slate-500 italic">Article content is not available.</p>;
  }

  return (
    <div
      className={`prose max-w-none prose-headings:text-slate-900 prose-p:text-slate-700 prose-a:text-wedding-rose prose-strong:text-slate-900 prose-li:text-slate-700 dark:prose-invert dark:prose-headings:text-white dark:prose-p:text-slate-300 dark:prose-strong:text-white dark:prose-li:text-slate-300 ${className}`.trim()}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
