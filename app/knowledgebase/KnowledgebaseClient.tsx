'use client';

import { useEffect, useMemo, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { BookOpen, Clock, Eye, Search } from 'lucide-react';

import MarkdownArticle from '@/components/blog/MarkdownArticle';
import { getApiBaseUrl } from '@/utils/env';
import type {
  PublicKBArticle,
  PublicKBArticlesResponse,
  PublicKBCategory,
} from './types';

const articleLimit = 12;

function normalizeHeadingText(value: string): string {
  return value
    .replace(/\s+#+\s*$/, '')
    .replace(/[`*_~[\]()]/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

function stripDuplicateArticleTitleHeading(title: string, content?: string | null): string {
  if (!content) {
    return '';
  }

  const leadingWhitespaceLength = content.length - content.trimStart().length;
  const body = content.slice(leadingWhitespaceLength);
  const headingMatch = body.match(/^#\s+(.+?)\s*#*\s*(?:\r?\n|$)/);

  if (!headingMatch || normalizeHeadingText(headingMatch[1]) !== normalizeHeadingText(title)) {
    return content;
  }

  return `${content.slice(0, leadingWhitespaceLength)}${body
    .slice(headingMatch[0].length)
    .replace(/^\r?\n/, '')}`;
}

function buildKnowledgebaseUrl({
  category,
  query,
  article,
}: {
  category?: string;
  query?: string;
  article?: string;
}): string {
  const params = new URLSearchParams();

  if (category && category !== 'all') {
    params.set('category', category);
  }
  if (query && query.length >= 2) {
    params.set('q', query);
  }
  if (article) {
    params.set('article', article);
  }

  const text = params.toString();
  return text ? `/knowledgebase?${text}` : '/knowledgebase';
}

function categoryLabel(categories: PublicKBCategory[], category: string): string {
  return categories.find((item) => item.category === category)?.display_name || category;
}

function ArticleCard({
  article,
  categories,
  onOpen,
}: {
  article: PublicKBArticle;
  categories: PublicKBCategory[];
  onOpen: (article: PublicKBArticle) => void;
}) {
  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] transition hover:border-wedding-rose/40 hover:bg-white/[0.06]">
      {article.card_image ? (
        <div className="relative aspect-[16/9] overflow-hidden bg-slate-900">
          <img
            src={article.card_image}
            alt=""
            loading="lazy"
            decoding="async"
            className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105"
          />
        </div>
      ) : null}
      <div className="flex flex-1 flex-col p-5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-wedding-rose">
          {categoryLabel(categories, article.category)}
        </p>
        <h2 className="mt-3 text-lg font-semibold leading-snug text-white">{article.title}</h2>
        <p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-400">{article.excerpt}</p>
        <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {article.estimated_read_minutes} min
          </span>
          <span className="inline-flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            {article.view_count} views
          </span>
          {article.is_official ? <span>Official</span> : null}
        </div>
        <button
          type="button"
          onClick={() => onOpen(article)}
          className="mt-auto pt-5 text-left text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush"
        >
          Read article
        </button>
      </div>
    </article>
  );
}

type KnowledgebaseClientProps = {
  initialArticles: PublicKBArticlesResponse | null;
  initialCategories: PublicKBCategory[];
  initialArticle: PublicKBArticle | null;
  initialCategory: string;
  initialQuery: string;
  initialUnavailable: boolean;
};

export default function KnowledgebaseClient({
  initialArticles,
  initialCategories,
  initialArticle,
  initialCategory,
  initialQuery,
  initialUnavailable,
}: KnowledgebaseClientProps) {
  const router = useRouter();
  const [articles, setArticles] = useState<PublicKBArticle[]>(initialArticles?.articles ?? []);
  const [categories] = useState<PublicKBCategory[]>(initialCategories);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [selectedArticle, setSelectedArticle] = useState<PublicKBArticle | null>(initialArticle);
  const [unavailable, setUnavailable] = useState(initialUnavailable);
  const [articleTotal, setArticleTotal] = useState(initialArticles?.total ?? articles.length);
  const [isPending, startTransition] = useTransition();

  const allCategory = useMemo(
    () => ({
      category: 'all',
      display_name: 'All',
      article_count: categories.reduce((total, category) => total + category.article_count, 0),
    }),
    [categories],
  );
  const visibleCategories = [allCategory, ...categories.filter((category) => category.article_count > 0)];

  useEffect(() => {
    const trimmedQuery = searchQuery.trim();
    if (trimmedQuery.length === 1) {
      return;
    }

    const timer = window.setTimeout(() => {
      const params = new URLSearchParams();
      params.set('limit', String(articleLimit));
      if (selectedCategory !== 'all') {
        params.set('category', selectedCategory);
      }
      if (trimmedQuery.length >= 2) {
        params.set('search', trimmedQuery);
      }

      startTransition(() => {
        router.replace(
          buildKnowledgebaseUrl({
            category: selectedCategory,
            query: trimmedQuery,
          }),
          { scroll: false },
        );
      });

      void fetch(`${getApiBaseUrl()}/public/kb/articles?${params.toString()}`)
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Knowledgebase API ${response.status}`);
          }
          return response.json();
        })
        .then((data: PublicKBArticlesResponse) => {
          setArticles(Array.isArray(data.articles) ? data.articles : []);
          setArticleTotal(data.total ?? 0);
          setUnavailable(false);
        })
        .catch(() => {
          setArticles([]);
          setUnavailable(true);
        });
    }, 250);

    return () => window.clearTimeout(timer);
  }, [router, searchQuery, selectedCategory]);

  const openArticle = async (article: PublicKBArticle) => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/public/kb/articles/slug/${encodeURIComponent(article.slug)}`);
      if (!response.ok) {
        throw new Error(`Knowledgebase article API ${response.status}`);
      }

      const fullArticle: PublicKBArticle = await response.json();
      setSelectedArticle(fullArticle);
      setUnavailable(false);
      router.replace(
        buildKnowledgebaseUrl({
          category: selectedCategory,
          query: searchQuery.trim(),
          article: fullArticle.slug,
        }),
        { scroll: false },
      );
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch {
      setUnavailable(true);
    }
  };

  const closeArticle = () => {
    setSelectedArticle(null);
    router.replace(
      buildKnowledgebaseUrl({
        category: selectedCategory,
        query: searchQuery.trim(),
      }),
      { scroll: false },
    );
  };

  if (selectedArticle) {
    const articleBody = stripDuplicateArticleTitleHeading(selectedArticle.title, selectedArticle.content);

    return (
      <>
        <section className="border-b border-white/10 px-6 pb-8 pt-28 sm:px-8 lg:px-12">
          <div className="mx-auto max-w-4xl">
            <button
              type="button"
              onClick={closeArticle}
              className="text-sm font-semibold text-wedding-rose transition hover:text-wedding-blush"
            >
              Back to knowledgebase
            </button>
            <p className="mt-8 text-[11px] font-semibold uppercase tracking-[0.36em] text-wedding-rose">
              {categoryLabel(categories, selectedArticle.category)}
            </p>
            <h1 className="mt-4 text-3xl font-semibold leading-tight text-white sm:text-5xl">
              {selectedArticle.title}
            </h1>
            <div className="mt-5 flex flex-wrap items-center gap-4 text-sm text-slate-400">
              <span>{selectedArticle.estimated_read_minutes} min read</span>
              <span>{selectedArticle.view_count} views</span>
              {selectedArticle.author_name ? <span>{selectedArticle.author_name}</span> : null}
            </div>
          </div>
        </section>
        <article className="mx-auto max-w-4xl px-6 py-10 sm:px-8 lg:px-12">
          <MarkdownArticle content={articleBody} theme="dark" />
        </article>
      </>
    );
  }

  return (
    <>
      <section className="relative overflow-hidden px-6 pb-10 pt-32 text-center sm:px-8 lg:px-12">
        <div
          className="absolute inset-0 opacity-60"
          style={{
            background:
              'radial-gradient(800px 500px at 20% -10%, rgba(212,165,165,0.28), transparent 70%), radial-gradient(1000px 600px at 85% -10%, rgba(232,196,106,0.18), transparent 65%)',
          }}
          aria-hidden="true"
        />
        <div className="relative mx-auto max-w-4xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.5em] text-wedding-rose/80">
            Knowledgebase
          </p>
          <h1 className="mt-4 text-3xl font-semibold text-white sm:text-5xl">
            Public docs for planner workflows.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-slate-300">
            Read published setup guides, calendar help, billing notes, and planner workflow documentation without signing in.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-8 sm:px-8 lg:px-12">
        <div className="grid gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-4 sm:grid-cols-[1fr_auto] sm:items-center">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" aria-hidden="true" />
            <span className="sr-only">Search knowledgebase articles</span>
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search articles..."
              className="w-full rounded-xl border border-white/10 bg-slate-950/60 py-3 pl-10 pr-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-wedding-rose/50"
            />
          </label>
          <p className="text-sm text-slate-500">
            {isPending ? 'Updating...' : `${articleTotal} published articles`}
          </p>
        </div>

        <div className="mt-5 flex gap-2 overflow-x-auto pb-2">
          {visibleCategories.map((category) => {
            const active = selectedCategory === category.category;
            return (
              <button
                key={category.category}
                type="button"
                onClick={() => {
                  setSelectedCategory(category.category);
                  setSelectedArticle(null);
                }}
                className={`shrink-0 rounded-full border px-4 py-2 text-xs font-semibold transition ${
                  active
                    ? 'border-wedding-rose/50 bg-wedding-rose/15 text-wedding-rose'
                    : 'border-white/10 text-slate-400 hover:border-white/25 hover:text-white'
                }`}
              >
                {category.display_name} ({category.article_count})
              </button>
            );
          })}
        </div>

        {unavailable ? (
          <div className="mt-8 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-6 py-10 text-center">
            <p className="text-base font-medium text-amber-200">Knowledgebase articles are temporarily unavailable.</p>
            <p className="mt-2 text-sm text-amber-100/80">Public support and policy links are still available in the footer.</p>
          </div>
        ) : articles.length > 0 ? (
          <div className="mt-8 grid items-stretch gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {articles.map((article) => (
              <ArticleCard
                key={article.id || article.slug}
                article={article}
                categories={categories}
                onOpen={openArticle}
              />
            ))}
          </div>
        ) : (
          <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.04] px-6 py-16 text-center">
            <BookOpen className="mx-auto h-10 w-10 text-slate-500" aria-hidden="true" />
            <p className="mt-4 text-base font-medium text-white">No published articles match this view.</p>
            <p className="mt-2 text-sm text-slate-500">Try a broader search or another category.</p>
          </div>
        )}
      </section>
    </>
  );
}
