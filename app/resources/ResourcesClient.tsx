'use client';

import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import SaasNav from '../components/saas/SaasNav';
import MarkdownArticle from '@/components/blog/MarkdownArticle';
import { getApiBaseUrl } from '@/utils/env';
import {
  apiArticleToBlogPost,
  BLOG_CATEGORIES,
  FAQ_CATEGORIES,
  faqs,
} from './resourcesShared';
import type { BlogPost } from './resourcesShared';

const CARD_GRADIENTS: Record<string, string> = {
  Business: 'from-amber-600/30 to-orange-800/20',
  Workflow: 'from-blue-600/30 to-cyan-800/20',
  Tools: 'from-violet-600/30 to-purple-800/20',
  Industry: 'from-wedding-rose/30 to-rose-800/20',
};

function BlogCard({
  post,
  isSelected,
  onSelect,
  compact = false,
}: {
  post: BlogPost;
  isSelected: boolean;
  onSelect: (slug: string) => void;
  compact?: boolean;
}) {
  const gradient = CARD_GRADIENTS[post.category] || 'from-slate-600/30 to-slate-800/20';

  return (
    <article
      className={`group block w-full overflow-hidden rounded-2xl border text-left transition ${
        isSelected
          ? 'border-wedding-rose/40 bg-white/[0.06] ring-2 ring-wedding-rose/30'
          : 'border-white/8 bg-white/[0.03] hover:border-wedding-rose/30'
      }`}
    >
      <button type="button" onClick={() => onSelect(post.slug)} className="block w-full text-left">
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
      </button>

      {!compact && (
        <div className="px-6 pb-6 pt-0">
          <Link
            href={`/resources/blog/${post.slug}`}
            className="text-xs font-medium text-wedding-rose transition hover:text-wedding-blush"
          >
            Open article page
          </Link>
        </div>
      )}
    </article>
  );
}

function FeaturedBlogCard({
  post,
  onSelect,
}: {
  post: BlogPost;
  onSelect: (slug: string) => void;
}) {
  return (
    <article className="group col-span-full overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] transition hover:border-wedding-rose/30">
      <button type="button" onClick={() => onSelect(post.slug)} className="block w-full text-left">
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
      </button>
      <div className="px-8 pb-8 pt-0 md:pt-2">
        <Link
          href={`/resources/blog/${post.slug}`}
          className="text-sm font-medium text-wedding-rose transition hover:text-wedding-blush"
        >
          Open article page
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
  initialBlogPosts: BlogPost[];
}

export default function ResourcesClient({ initialBlogPosts }: ResourcesClientProps) {
  const [activeTab, setActiveTab] = useState<'blog' | 'faq'>('blog');
  const [blogFilter, setBlogFilter] = useState('All');
  const [faqFilter, setFaqFilter] = useState('All');
  const [openFaqIdx, setOpenFaqIdx] = useState<number | null>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPost, setSelectedPost] = useState<string | null>(null);
  const [selectedPostData, setSelectedPostData] = useState<BlogPost | null>(null);
  const [loadingArticle, setLoadingArticle] = useState(false);
  const rightPanelRef = useRef<HTMLDivElement>(null);

  const blogPosts = initialBlogPosts;

  const selectPost = useCallback(
    async (slug: string) => {
      setSelectedPost(slug);
      setLoadingArticle(true);
      setSelectedPostData(null);

      try {
        const baseUrl = getApiBaseUrl();
        const response = await fetch(`${baseUrl}/api/v1/blog/articles/slug/${slug}`);
        if (!response.ok) {
          throw new Error(`API ${response.status}`);
        }

        const article = await response.json();
        setSelectedPostData(apiArticleToBlogPost(article));
      } catch {
        const cardData = blogPosts.find((post) => post.slug === slug);
        if (cardData) {
          setSelectedPostData({
            ...cardData,
            content:
              cardData.content ||
              '*Full article content is not available right now. Please try again later.*',
          });
        }
      } finally {
        setLoadingArticle(false);
      }
    },
    [blogPosts]
  );

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
    if (rightPanelRef.current && selectedPost) {
      rightPanelRef.current.scrollTop = 0;
    }
  }, [selectedPost]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />

      {!selectedPost && (
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
              Pricing strategies, workflow tips, industry trends, and answers to every question.
            </p>
          </div>
        </section>
      )}

      <div className={`mx-auto max-w-5xl px-6 sm:px-10 ${selectedPost ? 'pt-20' : ''}`}>
        <div className="flex gap-1 border-b border-white/10">
          <button
            type="button"
            onClick={() => {
              setActiveTab('blog');
              setSelectedPost(null);
              setSelectedPostData(null);
            }}
            className={`border-b-2 px-6 py-3 text-sm font-semibold transition ${
              activeTab === 'blog'
                ? 'border-wedding-rose text-wedding-rose'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            Blog
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('faq');
              setSelectedPost(null);
              setSelectedPostData(null);
            }}
            className={`border-b-2 px-6 py-3 text-sm font-semibold transition ${
              activeTab === 'faq'
                ? 'border-wedding-rose text-wedding-rose'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            FAQ
          </button>
        </div>
      </div>

      {activeTab === 'blog' && (
        <section>
          {selectedPost ? (
            <div className="flex h-[calc(100vh-130px)] overflow-hidden">
              <div className="w-full overflow-y-auto border-r border-white/10 bg-slate-950/50 md:w-[35%]">
                <div className="space-y-3 p-6">
                  <div className="sticky top-0 z-10 space-y-3 bg-slate-950 pb-4">
                    <input
                      type="text"
                      placeholder="Search articles..."
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none focus:border-wedding-rose/40"
                    />
                    <div className="flex flex-wrap gap-2">
                      {BLOG_CATEGORIES.map((category) => (
                        <button
                          key={category}
                          type="button"
                          onClick={() => setBlogFilter(category)}
                          className={`rounded-full px-3 py-1 text-xs font-medium transition ${
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

                  <div className="space-y-2">
                    {filteredPosts.map((post) => (
                      <BlogCard
                        key={post.slug}
                        post={post}
                        isSelected={selectedPost === post.slug}
                        compact
                        onSelect={selectPost}
                      />
                    ))}
                    {filteredPosts.length === 0 && (
                      <div className="py-8 text-center">
                        <p className="text-sm text-slate-500">No articles match your search.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div
                ref={rightPanelRef}
                className="hidden overflow-y-auto md:flex md:w-[65%] md:flex-col"
              >
                {loadingArticle ? (
                  <div className="flex flex-1 items-center justify-center">
                    <div className="text-center">
                      <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-wedding-rose/30 border-t-wedding-rose" />
                      <p className="text-sm text-slate-500">Loading article...</p>
                    </div>
                  </div>
                ) : selectedPostData ? (
                  <>
                    <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-slate-950/80 p-6 backdrop-blur">
                      <div className="min-w-0 flex-1">
                        <h2 className="truncate text-xl font-semibold text-white">
                          {selectedPostData.title}
                        </h2>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedPost(null);
                          setSelectedPostData(null);
                        }}
                        className="ml-4 text-2xl font-light text-slate-400 transition hover:text-white"
                      >
                        ✕
                      </button>
                    </div>

                    <div className="flex-1 overflow-y-auto">
                      <article className="p-6">
                        <div className="mb-8">
                          <div className="mb-4 inline-block">
                            <span className="rounded-full bg-wedding-rose/20 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-wedding-rose">
                              {selectedPostData.category}
                            </span>
                          </div>
                          <div className="mb-6 flex items-center gap-4 text-sm text-slate-400">
                            <time>{selectedPostData.date}</time>
                            <span>•</span>
                            <span>{selectedPostData.readTime} read</span>
                            {selectedPostData.author_name && (
                              <>
                                <span>•</span>
                                <span>{selectedPostData.author_name}</span>
                              </>
                            )}
                          </div>
                        </div>

                        {selectedPostData.content ? (
                          <MarkdownArticle content={selectedPostData.content} />
                        ) : (
                          <p className="italic text-slate-500">
                            Article content is not available.
                          </p>
                        )}
                      </article>
                    </div>
                  </>
                ) : null}
              </div>

              {selectedPost && selectedPostData && (
                <div className="fixed inset-0 z-40 overflow-y-auto bg-slate-950 md:hidden">
                  <div className="flex items-center gap-4 border-b border-white/10 p-4">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedPost(null);
                        setSelectedPostData(null);
                      }}
                      className="text-slate-400 transition hover:text-white"
                    >
                      ← Back
                    </button>
                    <h2 className="truncate text-lg font-semibold text-white">
                      {selectedPostData.title}
                    </h2>
                  </div>
                  <article className="mx-auto max-w-3xl p-6">
                    <div className="mb-8">
                      <div className="mb-4 inline-block">
                        <span className="rounded-full bg-wedding-rose/20 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-wedding-rose">
                          {selectedPostData.category}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-slate-400">
                        <time>{selectedPostData.date}</time>
                        <span>•</span>
                        <span>{selectedPostData.readTime} read</span>
                      </div>
                    </div>

                    {selectedPostData.content ? (
                      <MarkdownArticle content={selectedPostData.content} />
                    ) : (
                      <p className="italic text-slate-500">Article content is not available.</p>
                    )}
                  </article>
                </div>
              )}
            </div>
          ) : (
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
                  <FeaturedBlogCard post={featured} onSelect={selectPost} />
                )}
                {regularPosts.map((post) => (
                  <BlogCard
                    key={post.slug}
                    post={post}
                    isSelected={false}
                    onSelect={selectPost}
                  />
                ))}
                {filteredPosts.length === 0 && (
                  <div className="col-span-full py-16 text-center">
                    <p className="text-slate-500">No articles match your search.</p>
                  </div>
                )}
              </div>
            </div>
          )}
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

      {!selectedPost && (
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
      )}
    </main>
  );
}
