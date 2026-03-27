'use client';

import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';

interface MarkdownArticleProps {
  content: string;
  className?: string;
}

const UNSAFE_HTML_BLOCK_PATTERN = /<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi;
const HTML_COMMENT_PATTERN = /<!--[\s\S]*?-->/g;

const blogSanitizeSchema = {
  ...defaultSchema,
  tagNames: Array.from(
    new Set([
      ...(defaultSchema.tagNames || []),
      'blockquote',
      'br',
      'code',
      'del',
      'em',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'hr',
      'input',
      'li',
      'ol',
      'p',
      'pre',
      'strong',
      'table',
      'tbody',
      'td',
      'tfoot',
      'th',
      'thead',
      'tr',
      'ul',
    ])
  ),
  attributes: {
    ...defaultSchema.attributes,
    a: ['href', 'title', 'rel', 'target'],
    code: ['className'],
    input: [['type', 'checkbox'], 'checked', 'disabled'],
    td: ['align'],
    th: ['align'],
  },
  protocols: {
    ...defaultSchema.protocols,
    href: ['http', 'https', 'mailto', 'tel', '#'],
  },
};

function normalizeArticleContent(content: string): string {
  return content
    .replace(HTML_COMMENT_PATTERN, '')
    .replace(UNSAFE_HTML_BLOCK_PATTERN, '')
    .trim();
}

export default function MarkdownArticle({ content, className = '' }: MarkdownArticleProps) {
  const normalizedContent = normalizeArticleContent(content || '');

  if (!normalizedContent) {
    return <p className="text-slate-500 italic">Article content is not available.</p>;
  }

  return (
    <div
      className={`prose max-w-none prose-headings:text-slate-900 prose-p:text-slate-700 prose-a:text-wedding-rose prose-strong:text-slate-900 prose-li:text-slate-700 prose-blockquote:border-wedding-rose/30 prose-blockquote:text-slate-600 prose-code:text-slate-800 prose-pre:bg-slate-900 prose-hr:border-white/10 dark:prose-invert dark:prose-headings:text-white dark:prose-p:text-slate-300 dark:prose-strong:text-white dark:prose-li:text-slate-300 dark:prose-blockquote:text-slate-300 dark:prose-code:text-slate-100 dark:prose-pre:bg-slate-950 ${className}`.trim()}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw, [rehypeSanitize, blogSanitizeSchema]]}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  );
}
