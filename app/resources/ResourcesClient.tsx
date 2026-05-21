'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import Link from 'next/link';
import SaasNav from '../components/saas/SaasNav';
import { getApiBaseUrl } from '@/utils/env';
import {
  apiArticleToBlogPost,
  BLOG_CATEGORIES,
  FAQ_CATEGORIES,
  faqs,
} from './resourcesShared';
import type { BlogPost } from './resourcesShared';
import TemplatesClient from './templates/TemplatesClient';
import { MARKETING_TEMPLATES } from './templates/manifest';

type ResourcesTab = 'blog' | 'templates' | 'faq';

const RESOURCE_TAB_PATHS: Record<ResourcesTab, string> = {
  blog: '/resources/blog',
  templates: '/resources/templates',
  faq: '/resources/faq',
};

const CARD_GRADIENTS: Record<string, string> = {
  Business: 'from-amber-600/30 to-orange-800/20',
  Workflow: 'from-blue-600/30 to-cyan-800/20',
  Tools: 'from-violet-600/30 to-purple-800/20',
  Industry: 'from-wedding-rose/30 to-rose-800/20',
};

function BlogCard({
  post,
  isSelected,
  compact = false,
}: {
  post: BlogPost;
  isSelected: boolean;
  compact?: boolean;
}) {
  const gradient = CARD_GRADIENTS[post.category] || 'from-slate-600/30 to-slate-800/20';
  const articleHref = `/resources/blog/${post.slug}`;

  return (
    <article
      className={`group block w-full overflow-hidden rounded-2xl border text-left transition ${
        isSelected
          ? 'border-wedding-rose/40 bg-white/[0.06] ring-2 ring-wedding-rose/30'
          : 'border-white/8 bg-white/[0.03] hover:border-wedding-rose/30'
      }`}
    >
      <Link href={articleHref} className="block w-full text-left">
        {isSelected && <div className="h-1 bg-wedding-rose" />}

        {!compact && (
          <div className={`relative h-36 overflow-hidden bg-gradient-to-br ${gradient}`}>
            {post.image ? (
              <img
                src={post.image}
                alt={post.title}
                loading="lazy"
                decoding="async"
                className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
              />
            ) : (
              <div className="flex h-full items-center justify-center">
                <span className="text-[10px] font-semibold uppercase tracking-[0.4em] text-white/40">
                  {post.category}
                </span>
              </div>
            )}
          </div>
        )}

        <div className="p-6">
          <span className="text-[10px] uppercase tracking-[0.3em] text-wedding-rose">
            {post.category}
          </span>
          <h3 className="mt-2 text-base font-semibold leading-snug text-white transition-colors group-hover:text-wedding-rose">
            {post.title}
          </h3>
          <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-slate-400">
            {post.excerpt}
          </p>
          <p className="mt-4 text-xs text-slate-500">
            {post.readTime} read &middot; {post.date}
          </p>
        </div>
      </Link>

      {!compact && (
        <div className="px-6 pb-6 pt-0">
          <Link
            href={articleHref}
            className="text-xs font-medium text-wedding-rose transition hover:text-wedding-blush"
          >
            Read article
          </Link>
        </div>
      )}
    </article>
  );
}

function FeaturedBlogCard({
  post,
}: {
  post: BlogPost;
}) {
  const articleHref = `/resources/blog/${post.slug}`;

  return (
    <article className="group col-span-full overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] transition hover:border-wedding-rose/30">
      <Link href={articleHref} className="block w-full text-left">
        <div className="grid md:grid-cols-[1.2fr_1fr]">
          <div className="relative min-h-[220px] overflow-hidden md:min-h-[280px]">
            <img
              src={post.image || '/og-image.png'}
              alt={post.title}
              decoding="async"
              className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
          </div>
          <div className="flex flex-col justify-center p-8">
            <span className="text-[10px] uppercase tracking-[0.3em] text-wedding-rose">
              {post.category} &middot; Featured
            </span>
            <h3 className="mt-3 text-xl font-semibold leading-snug text-white transition-colors group-hover:text-wedding-rose">
              {post.title}
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              {post.excerpt}
            </p>
            <p className="mt-4 text-xs text-slate-500">
              {post.readTime} read &middot; {post.date}
            </p>
          </div>
        </div>
      </Link>
      <div className="px-8 pb-8 pt-0 md:pt-2">
        <Link
          href={articleHref}
          className="text-sm font-medium text-wedding-rose transition hover:text-wedding-blush"
        >
          Read article
        </Link>
      </div>
    </article>
  );
}

function FAQItem({
  faq,
  isOpen,
  onToggle,
}: {
  faq: { question: string; answer: string };
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03]">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-4 p-6 text-left"
      >
        <span className="text-base font-semibold text-white">{faq.question}</span>
        <span
          className="flex-shrink-0 text-xl text-wedding-rose transition-transform duration-200"
          style={{ transform: isOpen ? 'rotate(45deg)' : 'rotate(0deg)' }}
        >
          +
        </span>
      </button>
      {isOpen && (
        <div className="px-6 pb-6">
          <div className="border-t border-white/5 pt-4">
            <p className="text-sm leading-relaxed text-slate-400">{faq.answer}</p>
          </div>
        </div>
      )}
    </div>
  );
}

interface ResourcesClientProps {
  initialTab?: ResourcesTab;
  initialBlogPosts: BlogPost[];
  initialBlogUnavailable?: boolean;
}

export default function ResourcesClient({
  initialTab = 'blog',
  initialBlogPosts,
  initialBlogUnavailable = false,
}: ResourcesClientProps) {
  const [activeTab, setActiveTab] = useState<ResourcesTab>(initialTab);
  const [blogFilter, setBlogFilter] = useState('All');
  const [faqFilter, setFaqFilter] = useState('All');
  const [openFaqIdx, setOpenFaqIdx] = useState<number | null>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [loadingBlogList, setLoadingBlogList] = useState(false);
  const [blogUnavailable, setBlogUnavailable] = useState(initialBlogUnavailable);
  const [blogPosts, setBlogPosts] = useState(initialBlogPosts);

  const refreshBlogPosts = useCallback(async () => {
    setLoadingBlogList(true);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/api/v1/blog/articles?limit=50`);
      if (!response.ok) {
        throw new Error(`API ${response.status}`);
      }

      const data = await response.json();
      if (!Array.isArray(data?.articles)) {
        throw new Error('Malformed blog article response');
      }

      setBlogPosts(data.articles.map(apiArticleToBlogPost));
      setBlogUnavailable(false);
    } catch {
      setBlogUnavailable(true);
    } finally {
      setLoadingBlogList(false);
    }
  }, []);

  const filteredPosts = useMemo(() => {
    let posts = blogPosts;

    if (blogFilter !== 'All') {
      posts = posts.filter((post) => post.category === blogFilter);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      posts = posts.filter(
        (post) =>
          post.title.toLowerCase().includes(query) ||
          post.excerpt.toLowerCase().includes(query)
      );
    }

    return posts;
  }, [blogPosts, blogFilter, searchQuery]);

  const filteredFaqs = useMemo(() => {
    if (faqFilter === 'All') {
      return faqs;
    }

    return faqs.filter((faq) => faq.category === faqFilter);
  }, [faqFilter]);

  const featured = filteredPosts.find((post) => post.featured);
  const regularPosts = filteredPosts.filter((post) => !post.featured);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (initialBlogUnavailable && initialBlogPosts.length === 0) {
      void refreshBlogPosts();
    }
  }, [initialBlogUnavailable, initialBlogPosts.length, refreshBlogPosts]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />

      <section className="relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-50"
          style={{
            background:
              'radial-gradient(800px 500px at 20% -10%, rgba(212,165,165,0.3), transparent 70%), radial-gradient(1000px 600px at 85% -10%, rgba(232,196,106,0.2), transparent 65%)',
          }}
        />
        <div className="relative mx-auto max-w-5xl px-6 pb-10 pt-32 text-center sm:px-10">
          <p className="mb-4 text-[11px] uppercase tracking-[0.5em] text-wedding-rose/80">
            The Special Wedding
          </p>
          <h1 className="text-3xl font-semibold text-white sm:text-4xl">
            Resources for professional planners
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base text-slate-300">
            Pricing strategies, workflow tips, free templates, and answers to every question.
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-6 sm:px-10">
        <nav aria-label="Resource categories" className="flex gap-1 border-b border-white/10">
          <Link
            href={RESOURCE_TAB_PATHS.blog}
            scroll={false}
            aria-current={activeTab === 'blog' ? 'page' : undefined}
            className={`border-b-2 px-6 py-3 text-sm font-semibold transition ${
              activeTab === 'blog'
                ? 'border-wedding-rose text-wedding-rose'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            Blog
          </Link>
          <Link
            href={RESOURCE_TAB_PATHS.templates}
            scroll={false}
            aria-current={activeTab === 'templates' ? 'page' : undefined}
            className={`border-b-2 px-6 py-3 text-sm font-semibold transition ${
              activeTab === 'templates'
                ? 'border-wedding-rose text-wedding-rose'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            Templates
          </Link>
          <Link
            href={RESOURCE_TAB_PATHS.faq}
            scroll={false}
            aria-current={activeTab === 'faq' ? 'page' : undefined}
            className={`border-b-2 px-6 py-3 text-sm font-semibold transition ${
              activeTab === 'faq'
                ? 'border-wedding-rose text-wedding-rose'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            FAQ
          </Link>
        </nav>
      </div>

      {activeTab === 'blog' && (
        <section>
          <div className="mx-auto max-w-5xl px-6 py-10 sm:px-10">
              <div className="mb-8 flex flex-wrap items-center gap-3">
                <input
                  type="text"
                  placeholder="Search articles..."
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none focus:border-wedding-rose/40 sm:w-64"
                />
                <div className="flex flex-wrap gap-2">
                  {BLOG_CATEGORIES.map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setBlogFilter(category)}
                      className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                        blogFilter === category
                          ? 'border border-wedding-rose/40 bg-wedding-rose/15 text-wedding-rose'
                          : 'border border-white/10 text-slate-400 hover:text-white'
                      }`}
                    >
                      {category}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {featured && blogFilter === 'All' && !searchQuery && (
                  <FeaturedBlogCard post={featured} />
                )}
                {regularPosts.map((post) => (
                  <BlogCard
                    key={post.slug}
                    post={post}
                    isSelected={false}
                  />
                ))}
                {blogUnavailable && blogPosts.length === 0 && !loadingBlogList && (
                  <div className="col-span-full rounded-2xl border border-amber-500/20 bg-amber-500/10 px-6 py-10 text-center">
                    <p className="text-base font-medium text-amber-200">
                      Blog articles are temporarily unavailable.
                    </p>
                    <p className="mt-2 text-sm text-amber-100/80">
                      The FAQ tab is still available. You can also retry the blog feed now.
                    </p>
                    <button
                      type="button"
                      onClick={() => void refreshBlogPosts()}
                      className="mt-4 rounded-full border border-wedding-rose/30 px-4 py-2 text-sm font-medium text-wedding-rose transition hover:border-wedding-rose/50 hover:text-wedding-blush"
                    >
                      Retry loading articles
                    </button>
                  </div>
                )}
                {loadingBlogList && blogPosts.length === 0 && (
                  <div className="col-span-full py-16 text-center">
                    <p className="text-slate-500">Loading articles...</p>
                  </div>
                )}
                {!blogUnavailable && !loadingBlogList && filteredPosts.length === 0 && (
                  <div className="col-span-full py-16 text-center">
                    <p className="text-slate-500">No articles match your search.</p>
                  </div>
                )}
              </div>
          </div>
        </section>
      )}

      {activeTab === 'templates' && (
        <section className="mx-auto max-w-6xl px-6 py-10 sm:px-10">
          <div className="mb-10 max-w-3xl">
            <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-wedding-rose">
              Free download
            </p>
            <h2 className="mt-3 text-3xl font-semibold text-white">
              Templates wedding planners can use today
            </h2>
            <p className="mt-3 text-sm leading-7 text-slate-300 sm:text-base">
              Nine production-ready PDFs for intake, timelines, vendor onboarding,
              guest needs, shot lists, and day-of contacts. Each download is emailed
              to the address entered in the modal.
            </p>
          </div>

          <TemplatesClient templates={MARKETING_TEMPLATES} surface="dark" />
        </section>
      )}

      {activeTab === 'faq' && (
        <section className="mx-auto max-w-3xl px-6 py-10 sm:px-10">
          <div className="mb-8 flex flex-wrap justify-center gap-2">
            {FAQ_CATEGORIES.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => {
                  setFaqFilter(category);
                  setOpenFaqIdx(null);
                }}
                className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                  faqFilter === category
                    ? 'border border-wedding-rose/40 bg-wedding-rose/15 text-wedding-rose'
                    : 'border border-white/10 text-slate-400 hover:text-white'
                }`}
              >
                {category}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {filteredFaqs.map((faq, index) => (
              <FAQItem
                key={faq.question}
                faq={faq}
                isOpen={openFaqIdx === index}
                onToggle={() => setOpenFaqIdx(openFaqIdx === index ? null : index)}
              />
            ))}
          </div>

          <div className="mt-16 text-center">
            <h3 className="mb-3 text-2xl font-semibold text-white">Still have questions?</h3>
            <p className="mb-6 text-slate-400">
              Our team responds within 2 hours on business days.
            </p>
            <a
              href="mailto:hello@thespecialwedding.io?subject=Question about The Special Wedding"
              className="inline-flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/20 transition hover:bg-wedding-blush"
            >
              Contact support
            </a>
          </div>
        </section>
      )}

      <footer className="mt-16 border-t border-white/5 bg-slate-950">
          <div className="mx-auto max-w-6xl px-6 py-6">
            <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
              <p className="text-xs text-slate-500">
                © {new Date().getFullYear()} The Special Wedding. All rights reserved.
              </p>
              <div className="flex items-center gap-4">
                <a
                  href="mailto:hello@thespecialwedding.io"
                  className="text-xs text-slate-500 transition hover:text-slate-300"
                >
                  Contact
                </a>
                <p className="text-xs text-slate-500">
                  Built by{' '}
                  <a
                    href="https://joatlabs.dev"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-slate-400 transition hover:text-white"
                  >
                    JOATLABS LLC
                  </a>
                </p>
              </div>
            </div>
          </div>
      </footer>
    </main>
  );
}
