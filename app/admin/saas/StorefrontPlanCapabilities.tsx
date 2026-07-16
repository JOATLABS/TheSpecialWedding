'use client';

import {
  STOREFRONT_PLAN_FEATURE_OPTIONS,
  type PlanFeatureState,
} from './planFeatureConfig';

interface StorefrontPlanCapabilitiesProps {
  features: PlanFeatureState;
  onChange: (key: string, enabled: boolean) => void;
}

export function StorefrontPlanCapabilities({
  features,
  onChange,
}: StorefrontPlanCapabilitiesProps) {
  return (
    <fieldset className="rounded-lg border border-wedding-rose/30 bg-wedding-rose/5 p-4 dark:border-wedding-rose/40 dark:bg-wedding-rose/10">
      <legend className="px-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
        Storefront capabilities
      </legend>
      <p className="mb-3 text-xs leading-5 text-gray-600 dark:text-gray-300">
        These plan flags are the backend source of truth for access. Changing them
        does not change a planner&apos;s subscription, publication state, or storefront URL.
      </p>
      <div className="space-y-3">
        {STOREFRONT_PLAN_FEATURE_OPTIONS.map(({ key, label, description }) => (
          <label
            key={key}
            className="flex cursor-pointer items-start gap-3 rounded-md border border-gray-200 bg-white p-3 dark:border-gray-600 dark:bg-slate-800"
          >
            <input
              type="checkbox"
              checked={features[key] === true}
              disabled={key === 'custom_domain' && features.planner_storefront !== true}
              onChange={(event) => onChange(key, event.target.checked)}
              className="mt-0.5 rounded disabled:cursor-not-allowed disabled:opacity-50"
            />
            <span>
              <span className="block text-sm font-medium text-gray-900 dark:text-gray-100">
                {label}
              </span>
              <span className="mt-0.5 block text-xs leading-5 text-gray-600 dark:text-gray-300">
                {description}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
