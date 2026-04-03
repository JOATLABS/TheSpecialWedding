export const BLOG_MARKETING_CATEGORY_MAP: Record<string, string> = {
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

export function getMarketingBlogCategory(category?: string): string {
  if (!category) {
    return 'Industry';
  }

  return BLOG_MARKETING_CATEGORY_MAP[category] || category;
}
