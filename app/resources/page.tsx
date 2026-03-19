'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';

/* ═══════════════════════════════════════════════════════════
   Types & Data
   ═══════════════════════════════════════════════════════════ */

type BlogPost = {
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  readTime: string;
  date: string;
  featured?: boolean;
};

type FAQ = {
  question: string;
  answer: string;
  category: string;
};

const BLOG_CATEGORIES = ['All', 'Business', 'Workflow', 'Tools', 'Industry'];

const blogPosts: BlogPost[] = [
  {
    slug: 'how-to-price-wedding-planning-services',
    title: 'How to Price Your Wedding Planning Services in 2026',
    excerpt:
      'Most planners underprice. Here\u2019s a framework for building tiered packages that reflect your value \u2014 plus how AI can validate your pricing against market data.',
    category: 'Business',
    readTime: '8 min',
    date: 'March 12, 2026',
    featured: true,
  },
  {
    slug: 'managing-200-guests',
    title: 'Managing 200+ Guests Without Losing Your Mind',
    excerpt:
      'RSVP tracking, plus-one headaches, dietary requirements \u2014 a practical system for large-scale guest management.',
    category: 'Workflow',
    readTime: '6 min',
    date: 'March 5, 2026',
  },
  {
    slug: 'honeybook-vs-aisle-planner',
    title: 'HoneyBook vs Aisle Planner: Which Is Better for Wedding Planners?',
    excerpt:
      'A side-by-side comparison of two popular tools, including where they fall short for event-specific workflows.',
    category: 'Tools',
    readTime: '10 min',
    date: 'Feb 26, 2026',
  },
  {
    slug: 'wedding-planner-contract-essentials',
    title: 'Wedding Planner Contract Essentials: What to Include in 2026',
    excerpt:
      'Protect your business and your clients. The clauses every planner contract needs \u2014 with templates you can customize.',
    category: 'Business',
    readTime: '7 min',
    date: 'Feb 19, 2026',
  },
  {
    slug: 'ai-changing-wedding-planning',
    title: 'How AI Is Changing Wedding Planning (And What Planners Should Actually Use)',
    excerpt:
      'Beyond the hype: practical AI applications for pricing, contracts, and cash flow that save planners real time.',
    category: 'Industry',
    readTime: '9 min',
    date: 'Feb 12, 2026',
  },
  {
    slug: 'seating-chart-strategy',
    title: 'Seating Chart Strategy: Beyond Drag-and-Drop',
    excerpt:
      'Family dynamics, vendor placement, accessibility \u2014 the art and science of orchestrating 200 seats across 5 sections.',
    category: 'Workflow',
    readTime: '5 min',
    date: 'Feb 5, 2026',
  },
];

const FAQ_CATEGORIES = ['All', 'Getting Started', 'Pricing & Billing', 'Features', 'Day-of Support', 'Security & Data'];

const faqs: FAQ[] = [
  {
    question: 'Can I manage multiple weddings at once?',
    answer:
      'Yes. Each wedding gets its own workspace with separate guest lists, budgets, seating, and branding \u2014 all managed from a single dashboard. The Agency tier supports unlimited weddings with team member assignments.',
    category: 'Getting Started',
  },
  {
    question: 'How is this different from HoneyBook or Dubsado?',
    answer:
      'HoneyBook and Dubsado are CRM tools built for all creative professionals. The Special Wedding is built specifically for wedding planners with event-specific tools they don\u2019t offer: seating charts, guest management with RSVPs, day-of timelines, touchless check-in, and AI-powered pricing, contracts, and cash flow predictions.',
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
      'When you create a service package, our AI analyzes your market, services, and costs to suggest competitive pricing tiers \u2014 saving you hours of research.',
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
      'Yes. All plans come with a 14-day free trial \u2014 no credit card required. You get full access to every feature in your chosen tier.',
    category: 'Pricing & Billing',
  },
  {
    question: 'Can I import my guest list from a spreadsheet?',
    answer:
      'Absolutely. Upload a CSV or Excel file and we\u2019ll map columns to guest fields automatically. You can also paste directly from Google Sheets.',
    category: 'Getting Started',
  },
  {
    question: 'How does the seating orchestrator handle dietary requirements?',
    answer:
      'Dietary needs are tracked per guest and per plus-one. The seating view highlights dietary flags on each table so you can ensure the caterer has the right counts per section.',
    category: 'Features',
  },
  {
    question: 'Is my clients\u2019 data secure and GDPR compliant?',
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
    question: 'What\u2019s included in the Agency tier?',
    answer:
      'The Agency tier is built for planning firms managing multiple weddings with teams. It includes unlimited weddings, SSO, custom domains, role provisioning, a dedicated success architect, and compliance reporting.',
    category: 'Pricing & Billing',
  },
];

/* ═══════════════════════════════════════════════════════════
   Components
   ═══════════════════════════════════════════════════════════ */

function BlogCard({ post }: { post: BlogPost }) {
  return (
    <article className="group overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] transition hover:border-wedding-rose/30">
      {/* Color accent bar */}
      <div className="h-1 bg-gradient-to-r from-wedding-rose/40 to-wedding-gold/20" />
      <div className="p-6">
        <span className="text-[10px] uppercase tracking-[0.3em] text-wedding-rose">
          {post.category}
        </span>
        <h3 className="mt-2 text-base font-semibold text-white leading-snug group-hover:text-wedding-rose transition-colors">
          {post.title}
        </h3>
        <p className="mt-2 text-sm text-slate-400 leading-relaxed line-clamp-3">
          {post.excerpt}
        </p>
        <p className="mt-4 text-xs text-slate-500">
          {post.readTime} read &middot; {post.date}
        </p>
      </div>
    </article>
  );
}

function FeaturedBlogCard({ post }: { post: BlogPost }) {
  return (
    <article className="group col-span-full overflow-hidden rounded-2xl border border-white/8 bg-white/[0.03] transition hover:border-wedding-rose/30">
      <div className="grid md:grid-cols-[1.2fr_1fr]">
        {/* Visual placeholder */}
        <div className="relative bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center min-h-[220px] md:min-h-[280px]">
          <div className="absolute inset-0 bg-gradient-to-br from-wedding-rose/10 via-transparent to-wedding-gold/5" />
          <span className="relative text-5xl opacity-30">📊</span>
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
        <span className="text-wedding-rose text-xl flex-shrink-0 transition-transform duration-200"
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
   Main Page
   ═══════════════════════════════════════════════════════════ */

export default function ResourcesPage() {
  const [activeTab, setActiveTab] = useState<'blog' | 'faq'>('blog');
  const [blogFilter, setBlogFilter] = useState('All');
  const [faqFilter, setFaqFilter] = useState('All');
  const [openFaqIdx, setOpenFaqIdx] = useState<number | null>(0);
  const [searchQuery, setSearchQuery] = useState('');

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
  }, [blogFilter, searchQuery]);

  const filteredFaqs = useMemo(() => {
    if (faqFilter === 'All') return faqs;
    return faqs.filter((f) => f.category === faqFilter);
  }, [faqFilter]);

  const featured = filteredPosts.find((p) => p.featured);
  const regularPosts = filteredPosts.filter((p) => !p.featured);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* ── Hero ── */}
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

      {/* ── Tabs ── */}
      <div className="mx-auto max-w-5xl px-6 sm:px-10">
        <div className="flex gap-1 border-b border-white/10">
          <button
            type="button"
            onClick={() => setActiveTab('blog')}
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
            onClick={() => setActiveTab('faq')}
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
        <section className="mx-auto max-w-5xl px-6 py-10 sm:px-10">
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
              <FeaturedBlogCard post={featured} />
            )}
            {regularPosts.map((post) => (
              <BlogCard key={post.slug} post={post} />
            ))}
            {filteredPosts.length === 0 && (
              <div className="col-span-full py-16 text-center">
                <p className="text-slate-500">No articles match your search.</p>
              </div>
            )}
          </div>
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
                onClick={() => { setFaqFilter(cat); setOpenFaqIdx(null); }}
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

      {/* ── Footer ── */}
      <footer className="bg-slate-950 border-t border-white/5 mt-16">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <nav className="flex flex-wrap justify-center gap-x-8 gap-y-3 mb-8">
            <Link href="/" className="text-sm text-slate-400 transition hover:text-white">Home</Link>
            <Link href="/features" className="text-sm text-slate-400 transition hover:text-white">Features</Link>
            <Link href="/vendors" className="text-sm text-slate-400 transition hover:text-white">Vendor directory</Link>
            <Link href="/admin/login" className="text-sm text-slate-400 transition hover:text-white">Sign in</Link>
            <a href="mailto:hello@thespecialwedding.io" className="text-sm text-slate-400 transition hover:text-white">Contact</a>
          </nav>
          <div className="h-px bg-white/5 mb-6" />
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
            <p className="text-xs text-slate-500">© {new Date().getFullYear()} The Special Wedding. All rights reserved.</p>
            <p className="text-xs text-slate-500">
              Built by{' '}
              <a href="https://joatlabs.dev" target="_blank" rel="noopener noreferrer" className="text-slate-400 transition hover:text-white">
                JOATLABS LLC
              </a>
              {' '}© 2026
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
