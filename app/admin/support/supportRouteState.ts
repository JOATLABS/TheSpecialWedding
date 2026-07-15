export type SupportCategory =
  | 'technical'
  | 'billing'
  | 'feature_request'
  | 'bug_report'
  | 'general';

export type SupportPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface SupportCreatePrefill {
  subject: string;
  description: string;
  category: SupportCategory;
  priority: SupportPriority;
}

const CATEGORIES = new Set<SupportCategory>([
  'technical',
  'billing',
  'feature_request',
  'bug_report',
  'general',
]);
const PRIORITIES = new Set<SupportPriority>(['low', 'medium', 'high', 'urgent']);

export function getSupportCreatePrefill(
  searchParams: URLSearchParams,
  isRootAdmin: boolean,
): SupportCreatePrefill | null {
  if (isRootAdmin || searchParams.get('action') !== 'create') return null;

  const requestedCategory = searchParams.get('category') as SupportCategory | null;
  const requestedPriority = searchParams.get('priority') as SupportPriority | null;

  return {
    subject: searchParams.get('subject') || '',
    description: searchParams.get('description') || '',
    category: requestedCategory && CATEGORIES.has(requestedCategory)
      ? requestedCategory
      : 'general',
    priority: requestedPriority && PRIORITIES.has(requestedPriority)
      ? requestedPriority
      : 'medium',
  };
}
