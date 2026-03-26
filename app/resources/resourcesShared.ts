import { getMarketingBlogCategory } from '@/data/blogCategories';

export type BlogPost = {
  id?: string;
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  readTime: string;
  date: string;
  featured?: boolean;
  image?: string;
  content?: string;
  author_name?: string;
};

export type FAQ = {
  question: string;
  answer: string;
  category: string;
};

export interface PublicBlogApiArticle {
  id?: string;
  slug: string;
  title: string;
  content?: string;
  excerpt: string;
  category: string;
  date?: string;
  created_at?: string;
  published_at?: string;
  estimated_read_minutes?: number;
  readTime?: number;
  featured?: boolean;
  og_image?: string;
  card_image?: string;
  author_name?: string;
  meta_title?: string;
  meta_description?: string;
  ogDescription?: string;
}

export const BLOG_CATEGORIES = ['All', 'Business', 'Workflow', 'Tools', 'Industry'];
export const FAQ_CATEGORIES = ['All', 'Getting Started', 'Pricing & Billing', 'Features', 'Day-of Support', 'Security & Data'];
export const allowStaticFallback = process.env.NODE_ENV !== 'production';

export const fallbackBlogCards: BlogPost[] = [
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

export const faqs: FAQ[] = [
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

export function apiArticleToBlogPost(article: PublicBlogApiArticle): BlogPost {
  const readMinutes = article.estimated_read_minutes || article.readTime || 5;
  const createdAt = article.created_at || article.published_at || article.date || '';
  const displayCategory = getMarketingBlogCategory(article.category);

  return {
    id: article.id,
    slug: article.slug,
    title: article.title,
    excerpt: article.excerpt,
    category: displayCategory,
    readTime: `${readMinutes} min`,
    date: createdAt
      ? new Date(createdAt).toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })
      : '',
    featured: article.featured || false,
    image: article.card_image || undefined,
    content: article.content || undefined,
    author_name: article.author_name || 'The Special Wedding',
  };
}
