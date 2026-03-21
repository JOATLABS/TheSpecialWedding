'use client';

import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import SaasNav from '../components/saas/SaasNav';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getApiBaseUrl } from '@/utils/env';

/* ═══════════════════════════════════════════════════════════
   Types & Data
   ═══════════════════════════════════════════════════════════ */

type BlogPost = {
  id?: string;
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  readTime: string;
  date: string;
  featured?: boolean;
  image?: string;
  content?: string;        // Markdown content (fetched on select)
  author_name?: string;
};

type FAQ = {
  question: string;
  answer: string;
  category: string;
};

// Category mapping: API categories → display categories
const CATEGORY_MAP: Record<string, string> = {
  'platform-updates': 'Industry',
  'pricing-strategy': 'Business',
  'guest-management': 'Workflow',
  'industry-comparison': 'Tools',
  'contracts-legal': 'Business',
  'ai-technology': 'Industry',
  'event-logistics': 'Workflow',
  'tips-guides': 'Workflow',
  'general': 'Industry',
};

const BLOG_CATEGORIES = ['All', 'Business', 'Workflow', 'Tools', 'Industry'];

// Hardcoded fallback data — used when API returns no articles
const fallbackBlogCards: BlogPost[] = [
  {
    slug: 'introducing-the-special-wedding',
    title: 'Introducing The Special Wedding: One Platform to Replace Your Entire Tool Stack',
    excerpt:
      'Stop jumping between 8+ tools. We built The Special Wedding to give professional wedding planners everything they need in one purpose-built platform — powered by AI.',
    category: 'Industry',
    readTime: '7 min',
    date: 'March 19, 2026',
    featured: true,
    image: '/blog/introducing-the-special-wedding.png',
  },
  {
    slug: 'how-to-price-wedding-planning-services',
    title: 'How to Price Your Wedding Planning Services in 2026',
    excerpt:
      "Most planners underprice. Here's a framework for building tiered packages that reflect your value — plus how AI can validate your pricing against market data.",
    category: 'Business',
    readTime: '8 min',
    date: 'March 12, 2026',
    image: '/blog/how-to-price-wedding-planning-services.png',
  },
  {
    slug: 'managing-200-guests',
    title: 'Managing 200+ Guests Without Losing Your Mind',
    excerpt:
      'RSVP tracking, plus-one headaches, dietary requirements — a practical system for large-scale guest management.',
    category: 'Workflow',
    readTime: '6 min',
    date: 'March 5, 2026',
    image: '/blog/managing-200-guests.png',
  },
  {
    slug: 'honeybook-vs-aisle-planner',
    title: 'HoneyBook vs Aisle Planner: Which Is Better for Wedding Planners?',
    excerpt:
      'A side-by-side comparison of two popular tools, including where they fall short for event-specific workflows.',
    category: 'Tools',
    readTime: '10 min',
    date: 'Feb 26, 2026',
    image: '/blog/honeybook-vs-aisle-planner.png',
  },
  {
    slug: 'wedding-planner-contract-essentials',
    title: 'Wedding Planner Contract Essentials: What to Include in 2026',
    excerpt:
      'Protect your business and your clients. The clauses every planner contract needs — with templates you can customize.',
    category: 'Business',
    readTime: '7 min',
    date: 'Feb 19, 2026',
    image: '/blog/wedding-planner-contract-essentials.png',
  },
  {
    slug: 'ai-changing-wedding-planning',
    title: 'How AI Is Changing Wedding Planning (And What Planners Should Actually Use)',
    excerpt:
      'Beyond the hype: practical AI applications for pricing, contracts, and cash flow that save planners real time.',
    category: 'Industry',
    readTime: '9 min',
    date: 'Feb 12, 2026',
    image: '/blog/ai-changing-wedding-planning.png',
  },
  {
    slug: 'seating-chart-strategy',
    title: 'Seating Chart Strategy: Beyond Drag-and-Drop',
    excerpt:
      'Family dynamics, vendor placement, accessibility — the art and science of orchestrating 200 seats across 5 sections.',
    category: 'Workflow',
    readTime: '5 min',
    date: 'Feb 5, 2026',
    image: '/blog/seating-chart-strategy.png',
  },
];

const FAQ_CATEGORIES = ['All', 'Getting Started', 'Pricing & Billing', 'Features', 'Day-of Support', 'Security & Data'];

const faqs: FAQ[] = [
  {
    question: 'Can I manage multiple weddings at once?',
    answer:
      'Yes. Each wedding gets its own workspace with separate guest lists, budgets, seating, and branding — all managed from a single dashboard. The Agency tier supports unlimited weddings with team member assignments.',
    category: 'Getting Started',
  },
  {
    question: 'How is this different from HoneyBook or Dubsado?',
    answer:
      "HoneyBook and Dubsado are CRM tools built for all creative professionals. The Special Wedding is built specifically for wedding planners with event-specific tools they don't offer: seating charts, guest management with RSVPs, day-of timelines, touchless check-in, and AI-powered pricing, contracts, and cash flow predictions.",
    category: 'Getting Started',
  },
  {
    question: 'Is there support on the wedding day?',
    answer:
      'Signature and Agency plans include live chat with our success team plus on-call escalation for critical day-of moments.',
    category: 'Day-of Support',
  },
  {
    question: 'How do AI pricing suggestions work?',
    answer:
      'When you create a service package, our AI analyzes your market, services, and costs to suggest competitive pricing tiers — saving you hours of research.',
    category: 'Features',
  },
  {
    question: 'Can vendors collaborate in the platform?',
    answer:
      'Yes. Invite photographers, caterers, and venues into dedicated workspaces with role-based access to timelines, contracts, and file exchanges.',
    category: 'Features',
  },
  {
    question: 'What happens to my data if I cancel?',
    answer:
      'You can export all your data at any time. After cancellation, we retain your data for 30 days in case you change your mind, then permanently delete it.',
    category: 'Security & Data',
  },
  {
    question: 'Do you offer a free trial?',
    answer:
      'Yes. All plans come with a 14-day free trial — no credit card required. You get full access to every feature in your chosen tier.',
    category: 'Pricing & Billing',
  },
  {
    question: 'Can I import my guest list from a spreadsheet?',
    answer:
      "Absolutely. Upload a CSV or Excel file and we'll map columns to guest fields automatically. You can also paste directly from Google Sheets.",
    category: 'Getting Started',
  },
  {
    question: 'How does the seating orchestrator handle dietary requirements?',
    answer:
      'Dietary needs are tracked per guest and per plus-one. The seating view highlights dietary flags on each table so you can ensure the caterer has the right counts per section.',
    category: 'Features',
  },
  {
    question: "Is my clients' data secure and GDPR compliant?",
    answer:
      'Yes. All data is encrypted at rest and in transit. We process data in compliance with GDPR, and you can execute data subject requests (access, deletion) directly from the platform.',
    category: 'Security & Data',
  },
  {
    question: 'Can I switch plans later?',
    answer:
      'Yes. Upgrade or downgrade at any time from your billing page. Changes take effect at the start of your next billing cycle, with prorated credits applied automatically.',
    category: 'Pricing & Billing',
  },
  {
    question: "What's included in the Agency tier?",
    answer:
      'The Agency tier is built for planning firms managing multiple weddings with teams. It includes unlimited weddings, SSO, custom domains, role provisioning, a dedicated success architect, and compliance reporting.',
    category: 'Pricing & Billing',
  },
];

/* ═══════════════════════════════════════════════════════════
   Helper: Convert API article to BlogPost
   ═══════════════════════════════════════════════════════════ */

function apiArticleToBlogPost(article: Record<string, unknown>): BlogPost {
  const readMinutes = (article.estimated_read_minutes as number) || 5;
  const createdAt = article.created_at as string || article.published_at as string || '';
  const displayCategory = CATEGORY_MAP[article.category as string] || 'Industry';

  return {
    id: article.id as string,
    slug: article.slug as string,
    title: article.title as string,
    excerpt: article.excerpt as string,
    category: displayCategory,
    readTime: `${readMinutes} min`,
    date: createdAt
      ? new Date(createdAt).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
      : '',
    featured: article.featured as boolean || false,
    image: article.card_image as string || undefined,
    content: article.content as string || undefined,
    author_name: article.author_name as string || 'The Special Wedding',
  };
}

/* ═══════════════════════════════════════════════════════════
   Components
   ═══════════════════════════════════════════════════════════ */

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
    <button
      onClick={() => onSelect(post.slug)}
      className={`group w-full text-left block overflow-hidden rounded-2xl border transition ${
        isSelected
          ? 'border-wedding-rose/40 bg-white/[0.06] ring-2 ring-wedding-rose/30'
          : 'border-white/8 bg-white/[0.03] hover:border-wedding-rose/30'
      }`}
    >
      {/* Left border accent for selected */}
      {isSelected && <div className="h-1 bg-wedding-rose" />}
      {/* Card image area */}
      {!compact && (
        <div className={`relative h-36 bg-gradient-to-br ${gradient} overflow-hidden`}>
          {post.image ? (
            <img
              src={post.image}
              alt={post.title}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <span className="text-[10px] uppercase tracking-[0.4em] text-white/40 font-semibold">
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
        <h3 className="mt-2 text-base font-semibold text-white leading-snug group-hover:text-wedding-rose transition-colors">
          {post.title}
        </h3>
        <p className="mt-2 text-sm text-slate-400 leading-relaxed line-clamp-2">
          {post.excerpt}
        </p>
        <p className="mt-4 text-xs text-slate-500">
          {post.readTime} read &middot; {post.date}
        </p>
      </div>
    </button>
  );
}

function FeaturedBlogCard({ post, onSelect }: { post: BlogPost; onSelect: (slug: string) => void }) {
  return (
    <button onClick={() => onSelect(post.slug)} className="block col-span-full w-full text-left">
      <article className="group overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] transition hover:border-wedding-rose/30">
        <div className="grid md:grid-cols-[1.2fr_1fr]">
          {/* Featured image */}
          <div className="relative min-h-[220px] md:min-h-[280px] overflow-hidden">
            <img
              src={post.image || '/og-image.png'}
              alt={post.title}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
          </div>
          <div className="p-8 flex flex-col justify-center">
            <span className="text-[10px] uppercase tracking-[0.3em] text-wedding-rose">
              {post.category} &middot; Featured
            </span>
            <h3 className="mt-3 text-xl font-semibold text-white leading-snug group-hover:text-wedding-rose transition-colors">
              {post.title}
            </h3>
            <p className="mt-3 text-sm text-slate-400 leading-relaxed">
              {post.excerpt}
            </p>
            <p className="mt-4 text-xs text-slate-500">
              {post.readTime} read &middot; {post.date}
            </p>
          </div>
        </div>
      </article>
    </button>
  );
}

function FAQItem({ faq, isOpen, onToggle }: { faq: FAQ; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-4 p-6 text-left"
      >
        <span className="text-base font-semibold text-white">{faq.question}</span>
        <span
          className="text-wedding-rose text-xl flex-shrink-0 transition-transform duration-200"
          style={{ transform: isOpen ? 'rotate(45deg)' : 'rotate(0deg)' }}
        >
          +
        </span>
      </button>
      {isOpen && (
        <div className="px-6 pb-6">
          <div className="border-t border-white/5 pt-4">
            <p className="text-sm text-slate-400 leading-relaxed">{faq.answer}</p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Markdown Article Renderer
   ═══════════════════════════════════════════════════════════ */

function MarkdownArticle({ content }: { content: string }) {
  return (
    <div className="prose prose-invert max-w-none prose-headings:text-white prose-p:text-slate-300 prose-a:text-wedding-rose prose-strong:text-white prose-li:text-slate-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Main Page
   ═══════════════════════════════════════════════════════════ */

export default function ResourcesPage() {
  const [activeTab, setActiveTab] = useState<'blog' | 'faq'>('blog');
  const [blogFilter, setBlogFilter] = useState('All');
  const [faqFilter, setFaqFilter] = useState('All');
  const [openFaqIdx, setOpenFaqIdx] = useState<number | null>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPost, setSelectedPost] = useState<string | null>(null);
  const [selectedPostData, setSelectedPostData] = useState<BlogPost | null>(null);
  const [loadingArticle, setLoadingArticle] = useState(false);
  const rightPanelRef = useRef<HTMLDivElement>(null);

  // Blog posts state (fetched from API or fallback)
  const [blogPosts, setBlogPosts] = useState<BlogPost[]>(fallbackBlogCards);
  const [postsLoaded, setPostsLoaded] = useState(false);

  // Fetch blog articles from API on mount
  useEffect(() => {
    let cancelled = false;

    async function fetchArticles() {
      try {
        const baseUrl = getApiBaseUrl();
        const res = await fetch(`${baseUrl}/api/v1/blog/articles?limit=50`);
        if (!res.ok) throw new Error(`API ${res.status}`);
        const data = await res.json();

        if (!cancelled && data.articles && data.articles.length > 0) {
          const mapped = data.articles.map(apiArticleToBlogPost);
          setBlogPosts(mapped);
        }
        // If API returns 0 articles, keep the fallback data
      } catch (err) {
        console.warn('Blog API unavailable, using fallback data:', err);
        // Keep fallback data — no-op
      } finally {
        if (!cancelled) setPostsLoaded(true);
      }
    }

    fetchArticles();
    return () => { cancelled = true; };
  }, []);

  // Fetch full article content when a post is selected
  const selectPost = useCallback(async (slug: string) => {
    setSelectedPost(slug);
    setLoadingArticle(true);
    setSelectedPostData(null);

    try {
      const baseUrl = getApiBaseUrl();
      const res = await fetch(`${baseUrl}/api/v1/blog/articles/slug/${slug}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const article = await res.json();

      setSelectedPostData(apiArticleToBlogPost(article));
    } catch {
      // Fallback: use whatever we already have from the card data
      const cardData = blogPosts.find(p => p.slug === slug);
      if (cardData) {
        setSelectedPostData({
          ...cardData,
          content: cardData.content || '*Full article content is not available right now. Please try again later.*',
        });
      }
    } finally {
      setLoadingArticle(false);
    }
  }, [blogPosts]);

  const filteredPosts = useMemo(() => {
    let posts = blogPosts;
    if (blogFilter !== 'All') {
      posts = posts.filter((p) => p.category === blogFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      posts = posts.filter(
        (p) =>
          p.title.toLowerCase().includes(q) || p.excerpt.toLowerCase().includes(q)
      );
    }
    return posts;
  }, [blogPosts, blogFilter, searchQuery]);

  const filteredFaqs = useMemo(() => {
    if (faqFilter === 'All') return faqs;
    return faqs.filter((f) => f.category === faqFilter);
  }, [faqFilter]);

  const featured = filteredPosts.find((p) => p.featured);
  const regularPosts = filteredPosts.filter((p) => !p.featured);

  // Scroll right panel to top when post changes
  useEffect(() => {
    if (rightPanelRef.current && selectedPost) {
      rightPanelRef.current.scrollTop = 0;
    }
  }, [selectedPost]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <SaasNav />
      {/* ── Hero (hidden when post is selected on desktop) ── */}
      {!selectedPost && (
        <section className="relative overflow-hidden">
          <div
            className="absolute inset-0 opacity-50"
            style={{
              background:
                'radial-gradient(800px 500px at 20% -10%, rgba(212,165,165,0.3), transparent 70%), radial-gradient(1000px 600px at 85% -10%, rgba(232,196,106,0.2), transparent 65%)',
            }}
          />
          <div className="relative mx-auto max-w-5xl px-6 pt-32 pb-10 text-center sm:px-10">
            <p className="text-[11px] uppercase tracking-[0.5em] text-wedding-rose/80 mb-4">
              The Special Wedding
            </p>
            <h1 className="text-3xl font-semibold text-white sm:text-4xl">
              Resources for professional planners
            </h1>
            <p className="mt-4 text-base text-slate-300 max-w-xl mx-auto">
              Pricing strategies, workflow tips, industry trends, and answers to every question.
            </p>
          </div>
        </section>
      )}

      {/* ── Tabs ── */}
      <div className={`mx-auto max-w-5xl px-6 sm:px-10 ${selectedPost ? 'pt-20' : ''}`}>
        <div className="flex gap-1 border-b border-white/10">
          <button
            type="button"
            onClick={() => {
              setActiveTab('blog');
              setSelectedPost(null);
              setSelectedPostData(null);
            }}
            className={`px-6 py-3 text-sm font-semibold border-b-2 transition ${
              activeTab === 'blog'
                ? 'text-wedding-rose border-wedding-rose'
                : 'text-slate-400 border-transparent hover:text-white'
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
            className={`px-6 py-3 text-sm font-semibold border-b-2 transition ${
              activeTab === 'faq'
                ? 'text-wedding-rose border-wedding-rose'
                : 'text-slate-400 border-transparent hover:text-white'
            }`}
          >
            FAQ
          </button>
        </div>
      </div>

      {/* ── Blog Tab ── */}
      {activeTab === 'blog' && (
        <section>
          {/* Split-panel layout when post is selected */}
          {selectedPost ? (
            <div className="flex h-[calc(100vh-130px)] overflow-hidden">
              {/* Left panel - compact card list */}
              <div className="w-full md:w-[35%] border-r border-white/10 overflow-y-auto bg-slate-950/50">
                <div className="p-6 space-y-3">
                  {/* Search + filters (sticky) */}
                  <div className="sticky top-0 bg-slate-950 z-10 pb-4 space-y-3">
                    <input
                      type="text"
                      placeholder="Search articles..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none focus:border-wedding-rose/40"
                    />
                    <div className="flex flex-wrap gap-2">
                      {BLOG_CATEGORIES.map((cat) => (
                        <button
                          key={cat}
                          type="button"
                          onClick={() => setBlogFilter(cat)}
                          className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                            blogFilter === cat
                              ? 'bg-wedding-rose/15 border border-wedding-rose/40 text-wedding-rose'
                              : 'border border-white/10 text-slate-400 hover:text-white'
                          }`}
                        >
                          {cat}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Compact card list */}
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
                        <p className="text-slate-500 text-sm">No articles match your search.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Right panel - article content */}
              <div
                ref={rightPanelRef}
                className="hidden md:flex md:w-[65%] md:flex-col overflow-y-auto"
              >
                {loadingArticle ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <div className="w-8 h-8 border-2 border-wedding-rose/30 border-t-wedding-rose rounded-full animate-spin mx-auto mb-4" />
                      <p className="text-slate-500 text-sm">Loading article...</p>
                    </div>
                  </div>
                ) : selectedPostData ? (
                  <>
                    {/* Sticky header */}
                    <div className="sticky top-0 bg-slate-950/80 backdrop-blur border-b border-white/10 z-10 p-6 flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <h2 className="text-xl font-semibold text-white truncate">
                          {selectedPostData.title}
                        </h2>
                      </div>
                      <button
                        onClick={() => { setSelectedPost(null); setSelectedPostData(null); }}
                        className="ml-4 text-slate-400 hover:text-white transition text-2xl font-light"
                      >
                        ✕
                      </button>
                    </div>

                    {/* Article content */}
                    <div className="flex-1 overflow-y-auto">
                      <article className="p-6">
                        {/* Category and metadata */}
                        <div className="mb-8">
                          <div className="inline-block mb-4">
                            <span className="text-xs font-semibold uppercase tracking-wide px-3 py-1 bg-wedding-rose/20 text-wedding-rose rounded-full">
                              {selectedPostData.category}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 text-sm text-slate-400 mb-6">
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

                        {/* Article body — render Markdown */}
                        {selectedPostData.content ? (
                          <MarkdownArticle content={selectedPostData.content} />
                        ) : (
                          <p className="text-slate-500 italic">Article content is not available.</p>
                        )}
                      </article>
                    </div>
                  </>
                ) : null}
              </div>

              {/* Mobile: full-width article with back button */}
              {selectedPost && selectedPostData && (
                <div className="fixed inset-0 bg-slate-950 z-40 md:hidden overflow-y-auto">
                  <div className="p-4 border-b border-white/10 flex items-center gap-4">
                    <button
                      onClick={() => { setSelectedPost(null); setSelectedPostData(null); }}
                      className="text-slate-400 hover:text-white transition"
                    >
                      ← Back
                    </button>
                    <h2 className="text-lg font-semibold text-white truncate">
                      {selectedPostData.title}
                    </h2>
                  </div>
                  <article className="p-6 max-w-3xl mx-auto">
                    {/* Category and metadata */}
                    <div className="mb-8">
                      <div className="inline-block mb-4">
                        <span className="text-xs font-semibold uppercase tracking-wide px-3 py-1 bg-wedding-rose/20 text-wedding-rose rounded-full">
                          {selectedPostData.category}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-slate-400">
                        <time>{selectedPostData.date}</time>
                        <span>•</span>
                        <span>{selectedPostData.readTime} read</span>
                      </div>
                    </div>

                    {/* Article body — render Markdown */}
                    {selectedPostData.content ? (
                      <MarkdownArticle content={selectedPostData.content} />
                    ) : (
                      <p className="text-slate-500 italic">Article content is not available.</p>
                    )}
                  </article>
                </div>
              )}
            </div>
          ) : (
            // Full-width grid layout (no post selected)
            <div className="mx-auto max-w-5xl px-6 py-10 sm:px-10">
              {/* Search + filters */}
              <div className="flex flex-wrap items-center gap-3 mb-8">
                <input
                  type="text"
                  placeholder="Search articles..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm text-white placeholder:text-slate-500 outline-none focus:border-wedding-rose/40 w-full sm:w-64"
                />
                <div className="flex flex-wrap gap-2">
                  {BLOG_CATEGORIES.map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setBlogFilter(cat)}
                      className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                        blogFilter === cat
                          ? 'bg-wedding-rose/15 border border-wedding-rose/40 text-wedding-rose'
                          : 'border border-white/10 text-slate-400 hover:text-white'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {/* Posts grid */}
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

      {/* ── FAQ Tab ── */}
      {activeTab === 'faq' && (
        <section className="mx-auto max-w-3xl px-6 py-10 sm:px-10">
          {/* Category pills */}
          <div className="flex flex-wrap gap-2 mb-8 justify-center">
            {FAQ_CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => {
                  setFaqFilter(cat);
                  setOpenFaqIdx(null);
                }}
                className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                  faqFilter === cat
                    ? 'bg-wedding-rose/15 border border-wedding-rose/40 text-wedding-rose'
                    : 'border border-white/10 text-slate-400 hover:text-white'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* FAQ accordion */}
          <div className="space-y-3">
            {filteredFaqs.map((faq, idx) => (
              <FAQItem
                key={faq.question}
                faq={faq}
                isOpen={openFaqIdx === idx}
                onToggle={() => setOpenFaqIdx(openFaqIdx === idx ? null : idx)}
              />
            ))}
          </div>

          {/* Support CTA */}
          <div className="mt-16 text-center">
            <h3 className="text-2xl font-semibold text-white mb-3">Still have questions?</h3>
            <p className="text-slate-400 mb-6">Our team responds within 2 hours on business days.</p>
            <a
              href="mailto:hello@thespecialwedding.io?subject=Question about The Special Wedding"
              className="inline-flex items-center justify-center rounded-full bg-wedding-rose px-6 py-3 text-base font-semibold text-slate-900 shadow-lg shadow-wedding-rose/20 transition hover:bg-wedding-blush"
            >
              Contact support
            </a>
          </div>
        </section>
      )}

      {/* ── Footer (hidden when split-panel is open) ── */}
      {!selectedPost && (
      <footer className="bg-slate-950 border-t border-white/5 mt-16">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
            <p className="text-xs text-slate-500">© {new Date().getFullYear()} The Special Wedding. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <a href="mailto:hello@thespecialwedding.io" className="text-xs text-slate-500 transition hover:text-slate-300">Contact</a>
              <p className="text-xs text-slate-500">
                Built by{' '}
                <a href="https://joatlabs.dev" target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
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
