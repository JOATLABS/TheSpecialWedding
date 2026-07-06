'use client';

/**
 * Phase C client component: catalog cards + email-gated download modal.
 *
 * Each card opens the shared TemplateDownloadModal (used here and on
 * the homepage starter-pack band) which POSTs to
 * /public/marketing/template-download with any UTM params lifted from
 * the current URL. The endpoint records the lead and emails the PDF.
 *
 * Lean choices
 * - Modal logic + Resend link live in one shared component to avoid
 *   drift between the homepage band and this catalog page.
 * - No new client deps; small useState for the active card only.
 */

import React, { useState } from 'react';
import TemplateDownloadModal from '@/components/saas/TemplateDownloadModal';

interface TemplateCard {
  id: string;
  name: string;
  description: string;
  category: string;
  fieldCount: number;
}

interface TemplatesClientProps {
  templates: TemplateCard[];
  surface?: 'light' | 'dark';
}

export default function TemplatesClient({ templates, surface = 'light' }: TemplatesClientProps) {
  const [active, setActive] = useState<TemplateCard | null>(null);
  const isDark = surface === 'dark';

  return (
    <>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => (
          <article
            key={template.id}
            id={template.id}
            className={`flex scroll-mt-28 flex-col rounded-2xl border p-6 transition ${
              isDark
                ? 'border-white/10 bg-white/[0.04] hover:border-wedding-rose/40'
                : 'border-[#eee5d8] bg-white shadow-sm'
            }`}
          >
            <div
              className={`mb-2 text-xs font-semibold uppercase tracking-wider ${
                isDark ? 'text-wedding-rose' : 'text-[#9a8f82]'
              }`}
            >
              {template.category}
            </div>
            <h3
              className={`mb-2 font-serif text-xl leading-snug ${
                isDark ? 'text-white' : 'text-[#1a1a1a]'
              }`}
            >
              {template.name}
            </h3>
            <p
              className={`mb-4 flex-grow text-sm leading-relaxed ${
                isDark ? 'text-slate-300' : 'text-[#555]'
              }`}
            >
              {template.description}
            </p>
            <div className={`mb-4 text-xs ${isDark ? 'text-slate-500' : 'text-[#9a8f82]'}`}>
              {template.fieldCount} fields · A4 PDF
            </div>
            <button
              type="button"
              onClick={() => setActive(template)}
              className={`self-start rounded-full px-5 py-2 text-sm font-medium transition-colors ${
                isDark
                  ? 'bg-wedding-rose text-slate-950 hover:bg-wedding-blush'
                  : 'bg-[#6b5d4f] text-white hover:bg-[#574a3e]'
              }`}
            >
              Download as PDF
            </button>
          </article>
        ))}
      </div>

      <TemplateDownloadModal
        open={active !== null}
        onClose={() => setActive(null)}
        templateId={active?.id ?? ''}
        headline={active?.name ?? ''}
        subhead="Drop your email and we'll send the PDF straight to your inbox."
        surface={surface}
        testIdPrefix="templates-card"
        successCtaHref="/features#showcase"
        successCtaLabel="Watch product demos"
      />
    </>
  );
}
