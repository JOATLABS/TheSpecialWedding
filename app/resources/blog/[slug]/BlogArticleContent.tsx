'use client';

import MarkdownArticle from '@/components/blog/MarkdownArticle';

export default function BlogArticleContent({ content }: { content: string }) {
  return <MarkdownArticle content={content} theme="dark" />;
}
