import Link from 'next/link';

import { PUBLIC_LOGIN_PATH } from '@/seo/crawlPolicy';

const footerGroups = [
  {
    title: 'Help',
    links: [
      { label: 'Knowledgebase', href: '/knowledgebase' },
      { label: 'Support email', href: 'mailto:support@thespecialwedding.io' },
      { label: 'Sales/onboarding', href: 'mailto:hello@thespecialwedding.io' },
      { label: 'Google Calendar help', href: '/google-calendar' },
      { label: 'Google data deletion', href: '/google-data-deletion' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'Free templates', href: '/resources/templates' },
      { label: 'Blog', href: '/resources/blog' },
      { label: 'Support', href: '/support' },
      { label: 'Login', href: PUBLIC_LOGIN_PATH },
    ],
  },
  {
    title: 'Legal & Social',
    links: [
      { label: 'Privacy', href: '/privacy' },
      { label: 'Terms', href: '/terms' },
      { label: 'Instagram', href: 'https://www.instagram.com/thespecialwedding' },
      { label: 'TikTok', href: 'https://www.tiktok.com/@thespecialwedding1' },
    ],
  },
];

function FooterLink({ href, label }: { href: string; label: string }) {
  const isExternal = href.startsWith('http');
  const isMail = href.startsWith('mailto:');

  if (isExternal || isMail) {
    return (
      <a
        href={href}
        target={isExternal ? '_blank' : undefined}
        rel={isExternal ? 'noreferrer' : undefined}
        className="text-slate-400 transition hover:text-white"
      >
        {label}
      </a>
    );
  }

  return (
    <Link href={href} className="text-slate-400 transition hover:text-white">
      {label}
    </Link>
  );
}

export default function MarketingFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-white/10 bg-black px-6 py-10 text-sm sm:px-8 lg:px-12">
      <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[1.1fr_2fr]">
        <div>
          <p className="font-semibold text-white">The Special Wedding</p>
          <p className="mt-3 max-w-sm leading-6 text-slate-500">
            Planner-owned support, documentation, and policies for the teams running weddings on the platform.
          </p>
          <p className="mt-5 text-slate-500">&copy; {year} The Special Wedding. All rights reserved.</p>
        </div>
        <div className="grid gap-8 sm:grid-cols-3">
          {footerGroups.map((group) => (
            <div key={group.title}>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">{group.title}</p>
              <div className="mt-4 grid gap-3">
                {group.links.map((link) => (
                  <FooterLink key={`${group.title}-${link.label}`} href={link.href} label={link.label} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </footer>
  );
}
