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
}

export default function TemplatesClient({ templates }: TemplatesClientProps) {
  const [active, setActive] = useState<TemplateCard | null>(null);

  return (
    <>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => (
          <article
            key={template.id}
            id={template.id}
            className="bg-white rounded-2xl shadow-sm border border-[#eee5d8] p-6 flex flex-col scroll-mt-24"
          >
            <div className="text-xs font-semibold uppercase tracking-wider text-[#9a8f82] mb-2">
              {template.category}
            </div>
            <h3 className="font-serif text-xl text-[#1a1a1a] mb-2 leading-snug">
              {template.name}
            </h3>
            <p className="text-sm text-[#555] mb-4 flex-grow">
              {template.description}
            </p>
            <div className="text-xs text-[#9a8f82] mb-4">
              {template.fieldCount} fields · A4 PDF
            </div>
            <button
              type="button"
              onClick={() => setActive(template)}
              className="self-start rounded-full bg-[#6b5d4f] text-white px-5 py-2 text-sm font-medium hover:bg-[#574a3e] transition-colors"
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
        surface="light"
        testIdPrefix="templates-card"
      />
    </>
  );
}
