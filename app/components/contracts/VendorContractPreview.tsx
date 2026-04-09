'use client';

import ContractMarkdownRenderer from '@/components/contracts/ContractMarkdownRenderer';

export interface VendorContractPreviewSection {
  id: string;
  title: string;
  content: string;
  order: number;
}

interface VendorContractPreviewProps {
  sections: VendorContractPreviewSection[];
  termsAndConditions?: string | null;
  cancellationPolicy?: string | null;
  customClauses?: string | null;
  placeholderValues?: Record<string, string>;
  theme?: 'light' | 'dark';
  className?: string;
  emptyMessage?: string;
}

interface PreviewBlock {
  key: string;
  title: string;
  content: string;
}

function resolvePlaceholderValue(value: string | undefined): string {
  return value ?? '';
}

export function applyContractPreviewPlaceholders(
  content: string | null | undefined,
  placeholderValues?: Record<string, string>
): string {
  if (!content) {
    return '';
  }

  if (!placeholderValues) {
    return content;
  }

  return Object.entries(placeholderValues).reduce((resolved, [placeholder, value]) => {
    if (!placeholder) {
      return resolved;
    }

    return resolved.split(placeholder).join(resolvePlaceholderValue(value));
  }, content);
}

export function sortVendorContractPreviewSections<T extends VendorContractPreviewSection>(
  sections: T[]
): T[] {
  return [...sections].sort((left, right) => {
    if (left.order !== right.order) {
      return left.order - right.order;
    }

    return left.title.localeCompare(right.title);
  });
}

function buildPreviewBlocks({
  sections,
  termsAndConditions,
  cancellationPolicy,
  customClauses,
  placeholderValues,
}: Pick<
  VendorContractPreviewProps,
  'sections' | 'termsAndConditions' | 'cancellationPolicy' | 'customClauses' | 'placeholderValues'
>): PreviewBlock[] {
  const orderedSections = sortVendorContractPreviewSections(sections).map((section) => ({
    key: section.id,
    title: section.title,
    content: applyContractPreviewPlaceholders(section.content, placeholderValues),
  }));

  const additionalBlocks: PreviewBlock[] = [
    {
      key: 'terms-and-conditions',
      title: 'Terms & Conditions',
      content: applyContractPreviewPlaceholders(termsAndConditions, placeholderValues),
    },
    {
      key: 'cancellation-policy',
      title: 'Cancellation Policy',
      content: applyContractPreviewPlaceholders(cancellationPolicy, placeholderValues),
    },
    {
      key: 'custom-clauses',
      title: 'Custom Clauses',
      content: applyContractPreviewPlaceholders(customClauses, placeholderValues),
    },
  ].filter((block) => block.content.trim().length > 0);

  return [...orderedSections, ...additionalBlocks];
}

export default function VendorContractPreview({
  sections,
  termsAndConditions,
  cancellationPolicy,
  customClauses,
  placeholderValues,
  theme = 'light',
  className = '',
  emptyMessage = 'No contract content is available yet.',
}: VendorContractPreviewProps) {
  const blocks = buildPreviewBlocks({
    sections,
    termsAndConditions,
    cancellationPolicy,
    customClauses,
    placeholderValues,
  });

  const shellClasses =
    theme === 'dark'
      ? 'border-white/10 text-slate-100'
      : 'border-slate-200 text-slate-900 dark:border-white/10 dark:text-slate-100';
  const blockMutedClasses =
    theme === 'dark'
      ? 'text-slate-400 border-white/10'
      : 'text-slate-500 border-slate-200 dark:text-slate-400 dark:border-white/10';

  if (blocks.length === 0) {
    return (
      <div className={`rounded-2xl border border-dashed p-6 text-sm italic ${blockMutedClasses} ${className}`.trim()}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={`space-y-5 ${className}`.trim()}>
      {blocks.map((block) => (
        <article
          key={block.key}
          className={`rounded-2xl border bg-white/70 p-5 shadow-sm dark:bg-slate-900/40 ${shellClasses}`.trim()}
        >
          <header className={`mb-4 border-b pb-3 ${blockMutedClasses}`.trim()}>
            <h3 className="text-base font-semibold tracking-tight">{block.title}</h3>
          </header>
          <ContractMarkdownRenderer
            content={block.content}
            theme={theme}
            emptyFallback={null}
          />
        </article>
      ))}
    </div>
  );
}
