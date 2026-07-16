'use client';

import {
  Activity,
  AlertTriangle,
  Calendar,
  Globe2,
  Shield,
  Zap,
} from 'lucide-react';
import { KeyboardEvent, useRef } from 'react';

export type PlatformTabId =
  | 'health'
  | 'errors'
  | 'performance'
  | 'scheduler'
  | 'storefront'
  | 'backups';

const tabs = [
  { id: 'health' as const, label: 'System Health', icon: Activity },
  { id: 'errors' as const, label: 'Errors', icon: AlertTriangle },
  { id: 'performance' as const, label: 'Performance', icon: Zap },
  { id: 'scheduler' as const, label: 'Scheduler', icon: Calendar },
  { id: 'storefront' as const, label: 'Storefront domains', icon: Globe2 },
  { id: 'backups' as const, label: 'Backups', icon: Shield },
];

export function platformTabId(tab: PlatformTabId): string {
  return `platform-tab-${tab}`;
}

export function platformPanelId(tab: PlatformTabId): string {
  return `platform-panel-${tab}`;
}

interface PlatformTabsProps {
  activeTab: PlatformTabId;
  onChange: (tab: PlatformTabId) => void;
}

export default function PlatformTabs({ activeTab, onChange }: PlatformTabsProps) {
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const selectAt = (index: number) => {
    const tab = tabs[index];
    if (!tab) return;
    onChange(tab.id);
    buttonRefs.current[index]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    selectAt(nextIndex);
  };

  return (
    <div className="overflow-x-auto border-b border-gray-200 dark:border-gray-700">
      <div
        role="tablist"
        aria-label="Platform infrastructure sections"
        className="flex min-w-max gap-1 sm:gap-4"
      >
        {tabs.map((tab, index) => {
          const Icon = tab.icon;
          const selected = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              ref={(element) => {
                buttonRefs.current[index] = element;
              }}
              id={platformTabId(tab.id)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={platformPanelId(tab.id)}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(tab.id)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={`flex min-h-11 shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 sm:px-4 ${
                selected
                  ? 'border-primary-500 text-primary-700 dark:text-primary-300'
                  : 'border-transparent text-gray-600 hover:text-gray-800 dark:text-gray-300 dark:hover:text-gray-100'
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
