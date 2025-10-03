'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '../ui/Button';
import type { CreateBudgetTemplatePayload, BudgetTemplateCategoryInput } from '../../types/budget';

interface CreateTemplateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (payload: CreateBudgetTemplatePayload) => Promise<void> | void;
  isSubmitting?: boolean;
  errorMessage?: string;
}

interface CategoryRow extends BudgetTemplateCategoryInput {
  id: string;
}

interface TemplateFormState {
  name: string;
  description: string;
  weddingType: string;
  targetBudgetMin: string;
  targetBudgetMax: string;
  guestCountMin: string;
  guestCountMax: string;
  isPublic: boolean;
  categories: CategoryRow[];
}

const generateId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2, 10);
};

const defaultCategories = (): CategoryRow[] => [
  { id: generateId(), name: 'Venue & Catering', percentage: 45, priority: 1 },
  { id: generateId(), name: 'Photography & Video', percentage: 12, priority: 2 },
  { id: generateId(), name: 'Design & Decor', percentage: 15, priority: 2 },
  { id: generateId(), name: 'Entertainment', percentage: 10, priority: 3 },
  { id: generateId(), name: 'Planner & Staffing', percentage: 8, priority: 2 },
  { id: generateId(), name: 'Attire & Beauty', percentage: 5, priority: 3 },
  { id: generateId(), name: 'Transportation & Misc', percentage: 5, priority: 4 },
];

const defaultFormState = (): TemplateFormState => ({
  name: '',
  description: '',
  weddingType: 'traditional',
  targetBudgetMin: '25000',
  targetBudgetMax: '65000',
  guestCountMin: '80',
  guestCountMax: '180',
  isPublic: false,
  categories: defaultCategories(),
});

const priorityOptions = [
  { value: 1, label: 'Essential' },
  { value: 2, label: 'High' },
  { value: 3, label: 'Standard' },
  { value: 4, label: 'Flexible' },
  { value: 5, label: 'Optional' },
];

const weddingTypeOptions = [
  'traditional',
  'modern',
  'destination',
  'intimate',
  'outdoor',
  'luxury',
  'cultural',
];

export function CreateTemplateModal({
  isOpen,
  onClose,
  onCreate,
  isSubmitting = false,
  errorMessage,
}: CreateTemplateModalProps) {
  const [formState, setFormState] = useState<TemplateFormState>(defaultFormState);
  const [localError, setLocalError] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setFormState(defaultFormState());
      setLocalError('');
    }
  }, [isOpen]);

  const totalPercentage = useMemo(
    () => formState.categories.reduce((sum, category) => sum + Number(category.percentage || 0), 0),
    [formState.categories]
  );

  const remainingPercentage = useMemo(() => Math.max(0, Math.round((100 - totalPercentage) * 100) / 100), [totalPercentage]);

  if (!isOpen) {
    return null;
  }

  const updateCategory = (id: string, patch: Partial<CategoryRow>) => {
    setFormState((prev) => ({
      ...prev,
      categories: prev.categories.map((category) =>
        category.id === id
          ? {
              ...category,
              ...patch,
            }
          : category
      ),
    }));
  };

  const removeCategory = (id: string) => {
    setFormState((prev) => ({
      ...prev,
      categories: prev.categories.filter((category) => category.id !== id),
    }));
  };

  const addCategory = () => {
    setFormState((prev) => ({
      ...prev,
      categories: [
        ...prev.categories,
        { id: generateId(), name: '', percentage: remainingPercentage || 10, priority: 3 },
      ],
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLocalError('');

    const trimmedName = formState.name.trim();
    if (!trimmedName) {
      setLocalError('Enter a template name to continue.');
      return;
    }

    if (!formState.weddingType) {
      setLocalError('Select the wedding style this template supports.');
      return;
    }

    if (formState.categories.length === 0) {
      setLocalError('Add at least one budget category.');
      return;
    }

    const percentagesTotal = formState.categories.reduce((sum, category) => sum + Number(category.percentage || 0), 0);
    if (Math.abs(percentagesTotal - 100) > 0.5) {
      setLocalError('Category percentages must add up to 100%.');
      return;
    }

    const names = new Set<string>();
    for (const category of formState.categories) {
      const name = category.name.trim();
      if (!name) {
        setLocalError('Each category needs a descriptive name.');
        return;
      }
      const key = name.toLowerCase();
      if (names.has(key)) {
        setLocalError('Use unique names for each category.');
        return;
      }
      names.add(key);
    }

    const minBudget = Number(formState.targetBudgetMin || 0);
    const maxBudget = Number(formState.targetBudgetMax || 0);
    if (maxBudget < minBudget) {
      setLocalError('The maximum budget should be greater than or equal to the minimum budget.');
      return;
    }

    const guestMin = Number(formState.guestCountMin || 0);
    const guestMax = Number(formState.guestCountMax || 0);
    if (guestMax < guestMin) {
      setLocalError('Guest count max must be greater than or equal to guest count min.');
      return;
    }

    const payload: CreateBudgetTemplatePayload = {
      name: trimmedName,
      description: formState.description.trim() || undefined,
      wedding_type: formState.weddingType,
      target_budget_min: minBudget,
      target_budget_max: maxBudget,
      guest_count_range: {
        min: guestMin,
        max: guestMax,
      },
      is_public: formState.isPublic,
      categories: formState.categories.map(({ name, percentage, priority }) => ({
        name: name.trim(),
        percentage: Number(percentage),
        priority: Number(priority) as BudgetTemplateCategoryInput['priority'],
      })),
    };

    try {
      await onCreate(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create template.';
      setLocalError(message);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-sm px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-template-title"
    >
      <div className="relative w-full max-w-4xl">
        <div className="absolute inset-0 rounded-[36px] bg-white/60 dark:bg-slate-900/40 blur-3xl" aria-hidden="true" />
        <div className="relative rounded-[36px] border border-white/40 bg-white/80 p-10 shadow-2xl backdrop-blur-2xl">
          <div className="flex items-start justify-between gap-6">
            <div>
              <h2 id="create-template-title" className="text-3xl font-semibold text-wedding-navy">
                Craft a custom budget template
              </h2>
              <p className="mt-2 text-sm text-slate-600">
                Start with your ideal allocation and share the frosted template with your planning team instantly.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-2 text-slate-500 transition hover:text-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose focus:ring-offset-2"
              aria-label="Close template modal"
              disabled={isSubmitting}
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>

          <form className="mt-8 space-y-8" onSubmit={handleSubmit}>
            <div className="grid gap-6 md:grid-cols-2">
              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-slate-700">Template name *</span>
                <input
                  type="text"
                  value={formState.name}
                  onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
                  className="w-full rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                  placeholder="Luxury Seaside Celebration"
                  required
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-slate-700">Wedding style *</span>
                <select
                  value={formState.weddingType}
                  onChange={(event) => setFormState((prev) => ({ ...prev, weddingType: event.target.value }))}
                  className="w-full rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                >
                  {weddingTypeOptions.map((option) => (
                    <option key={option} value={option}>
                      {option.charAt(0).toUpperCase() + option.slice(1)}
                    </option>
                  ))}
                </select>
              </label>

              <label className="md:col-span-2 flex flex-col gap-2">
                <span className="text-sm font-medium text-slate-700">Short description</span>
                <textarea
                  value={formState.description}
                  onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
                  className="w-full min-h-[96px] rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                  placeholder="Designed for oceanfront ceremonies with elevated culinary moments and bespoke decor."
                />
              </label>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-3xl border border-white/40 bg-white/50 p-6 shadow-inner">
                <span className="text-sm font-medium text-slate-600">Recommended total budget</span>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-1">
                    <span className="text-xs uppercase tracking-wide text-slate-500">Minimum *</span>
                    <input
                      type="number"
                      min={0}
                      value={formState.targetBudgetMin}
                      onChange={(event) => setFormState((prev) => ({ ...prev, targetBudgetMin: event.target.value }))}
                      className="rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                      placeholder="25000"
                      required
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-xs uppercase tracking-wide text-slate-500">Maximum *</span>
                    <input
                      type="number"
                      min={0}
                      value={formState.targetBudgetMax}
                      onChange={(event) => setFormState((prev) => ({ ...prev, targetBudgetMax: event.target.value }))}
                      className="rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                      placeholder="65000"
                      required
                    />
                  </label>
                </div>
              </div>

              <div className="rounded-3xl border border-white/40 bg-white/50 p-6 shadow-inner">
                <span className="text-sm font-medium text-slate-600">Guest count guidance</span>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-1">
                    <span className="text-xs uppercase tracking-wide text-slate-500">Minimum *</span>
                    <input
                      type="number"
                      min={0}
                      value={formState.guestCountMin}
                      onChange={(event) => setFormState((prev) => ({ ...prev, guestCountMin: event.target.value }))}
                      className="rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                      placeholder="80"
                      required
                    />
                  </label>
                  <label className="flex flex-col gap-1">
                    <span className="text-xs uppercase tracking-wide text-slate-500">Maximum *</span>
                    <input
                      type="number"
                      min={0}
                      value={formState.guestCountMax}
                      onChange={(event) => setFormState((prev) => ({ ...prev, guestCountMax: event.target.value }))}
                      className="rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                      placeholder="180"
                      required
                    />
                  </label>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-wedding-navy">Category allocations</h3>
                  <p className="text-sm text-slate-600">
                    The remaining {remainingPercentage.toFixed(2)}% will be distributed manually as you tune each line item.
                  </p>
                </div>
                <div className="rounded-full bg-white/60 px-4 py-2 text-xs font-medium uppercase tracking-wide text-slate-600 shadow-inner">
                  {totalPercentage.toFixed(2)}% of 100% allocated
                </div>
              </div>

              <div className="space-y-3">
                {formState.categories.map((category, index) => (
                  <div
                    key={category.id}
                    className="grid gap-3 rounded-3xl border border-white/40 bg-white/50 p-4 shadow-inner md:grid-cols-12 md:items-center"
                  >
                    <div className="md:col-span-5">
                      <label className="flex flex-col gap-1">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Category {index + 1}
                        </span>
                        <input
                          type="text"
                          value={category.name}
                          onChange={(event) => updateCategory(category.id, { name: event.target.value })}
                          className="rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                          placeholder="Venue & Catering"
                          required
                        />
                      </label>
                    </div>

                    <div className="md:col-span-3">
                      <label className="flex flex-col gap-1">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Percentage *</span>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step="0.1"
                          value={category.percentage}
                          onChange={(event) => updateCategory(category.id, { percentage: Number(event.target.value) })}
                          className="rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                          required
                        />
                      </label>
                    </div>

                    <div className="md:col-span-3">
                      <label className="flex flex-col gap-1">
                        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Priority *</span>
                        <select
                          value={category.priority}
                          onChange={(event) => updateCategory(category.id, { priority: Number(event.target.value) })}
                          className="rounded-2xl border border-white/60 bg-white/60 px-4 py-3 text-slate-900 shadow-inner outline-none transition focus:border-wedding-rose focus:ring-2 focus:ring-wedding-rose/60"
                        >
                          {priorityOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <div className="md:col-span-1 flex items-center justify-end">
                      {formState.categories.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeCategory(category.id)}
                          className="rounded-full p-2 text-slate-400 transition hover:text-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose"
                          aria-label={`Remove ${category.name || `Category ${index + 1}`}`}
                          disabled={isSubmitting}
                        >
                          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                            <path
                              fillRule="evenodd"
                              d="M5.22 5.22a.75.75 0 011.06 0L10 8.94l3.72-3.72a.75.75 0 111.06 1.06L11.06 10l3.72 3.72a.75.75 0 11-1.06 1.06L10 11.06l-3.72 3.72a.75.75 0 11-1.06-1.06L8.94 10 5.22 6.28a.75.75 0 010-1.06z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex flex-col items-start justify-between gap-3 md:flex-row md:items-center">
                <button
                  type="button"
                  onClick={addCategory}
                  className="inline-flex items-center gap-2 rounded-full border border-white/50 bg-white/50 px-4 py-2 text-sm font-medium text-wedding-navy shadow-inner transition hover:border-wedding-rose hover:text-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                  disabled={isSubmitting}
                >
                  <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" />
                  </svg>
                  Add another category
                </button>
                <div className="text-sm text-slate-600">
                  Keep allocations within 0.5% of 100% to pass automated validation.
                </div>
              </div>
            </div>

            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={formState.isPublic}
                onChange={(event) => setFormState((prev) => ({ ...prev, isPublic: event.target.checked }))}
                className="h-4 w-4 rounded border border-white/60 bg-white/70 text-wedding-rose focus:ring-wedding-rose"
              />
              <span className="text-sm text-slate-600">
                Share this template with the entire planner team (otherwise it will stay private to your account).
              </span>
            </label>

            {(localError || errorMessage) && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                {localError || errorMessage}
              </div>
            )}

            <div className="flex flex-col-reverse gap-3 md:flex-row md:items-center md:justify-end">
              <Button
                type="button"
                variant="secondary"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting} className="bg-wedding-navy text-white hover:bg-wedding-rose">
                {isSubmitting ? 'Saving template…' : 'Save template'}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
