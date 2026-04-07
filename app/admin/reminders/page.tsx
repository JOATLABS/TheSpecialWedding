import { redirect } from 'next/navigation';

import type { CommunicationsTab } from '../communications/components/CommunicationsRemindersView';

const TAB_ROUTE_MAP: Record<CommunicationsTab, string> = {
  invites: '/admin/communications/invites',
  reminders: '/admin/communications/reminders',
  individual: '/admin/communications/individual',
  history: '/admin/communications/history',
};

const VALID_TABS = new Set<CommunicationsTab>(Object.keys(TAB_ROUTE_MAP) as CommunicationsTab[]);

type SearchParams = Record<string, string | string[] | undefined>;

function appendQueryParams(searchParams: SearchParams, omitKeys: string[]) {
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries(searchParams)) {
    if (omitKeys.includes(key) || value === undefined) {
      continue;
    }

    if (Array.isArray(value)) {
      value.forEach((entry) => query.append(key, entry));
      continue;
    }

    query.append(key, value);
  }

  const queryString = query.toString();
  return queryString ? `?${queryString}` : '';
}

export default async function RemindersRedirectPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const resolvedSearchParams = await searchParams;
  const rawTab = resolvedSearchParams.tab;
  const tab = Array.isArray(rawTab) ? rawTab[0] : rawTab;
  const destination =
    tab && VALID_TABS.has(tab as CommunicationsTab)
      ? TAB_ROUTE_MAP[tab as CommunicationsTab]
      : TAB_ROUTE_MAP.invites;

  redirect(`${destination}${appendQueryParams(resolvedSearchParams, ['tab'])}`);
}
