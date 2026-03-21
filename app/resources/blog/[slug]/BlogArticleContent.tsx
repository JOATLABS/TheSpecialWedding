'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function BlogArticleContent({ content }: { content: string }) {
  if (!content) {
    return <p className="text-slate-500 italic">Article content is not available.</p>;
  }

  return (
    <div className="prose prose-invert max-w-none prose-headings:text-white prose-p:text-slate-300 prose-a:text-wedding-rose prose-strong:text-white prose-li:text-slate-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
