'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import type { ReactNode, ReactElement } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { SparklesIcon, SquaresPlusIcon, DocumentDuplicateIcon } from '@heroicons/react/24/outline';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';
import { Button } from '@/components/ui/Button';
import { formsApi, type DuplicateFormPayload, type BlankFormPayload } from '@/services/formsApi';
import { formatDate as formatUtcDate } from '@/utils/dateFormat';

type CreationMode = 'template' | 'blank' | 'duplicate';

type RoleBreakdown = Record<string, number>;

interface FormTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
}

interface FormSummary {
  id: string;
  name: string;
  settings: {
    title: string;
    description?: string;
    is_public: boolean;
  };
  template_type?: string;
  wedding_id?: string;
  submission_count: number;
  unread_responses: number;
  created_at: string;
}

const CREATION_OPTIONS: Array<{
  id: CreationMode;
  title: string;
  description: string;
  icon: ReactNode;
}> = [
  {
    id: 'template',
    title: 'Start from a proven template',
    description: 'Spin up curated questionnaires grounded in the 2025 planner playbook and Apple glass heuristics.',
    icon: <SparklesIcon className="h-6 w-6" aria-hidden="true" />,
  },
  {
    id: 'blank',
    title: 'Start from scratch',
    description: 'Design a bespoke journey with adaptive sections, accessibility defaults, and privacy controls.',
    icon: <SquaresPlusIcon className="h-6 w-6" aria-hidden="true" />,
  },
  {
    id: 'duplicate',
    title: 'Duplicate an existing form',
    description: 'Replicate proven flows while preserving analytics fidelity and unread badge integrity.',
    icon: <DocumentDuplicateIcon className="h-6 w-6" aria-hidden="true" />,
  },
];

function CreationOptionCard({
  option,
  isActive,
  onSelect,
}: {
  option: (typeof CREATION_OPTIONS)[number];
  isActive: boolean;
  onSelect: () => void;
}): ReactElement {
  const stateClass = isActive
    ? 'border-wedding-rose/80 bg-white/80 shadow-xl'
    : 'border-white/40 bg-white/40 hover:border-white/70 hover:bg-white/60';

  return (
    <label
      className={`relative flex cursor-pointer flex-col gap-3 rounded-3xl border px-4 py-5 shadow-lg transition focus-within:ring-2 focus-within:ring-wedding-rose/60 ${stateClass}`}
    >
      <input
        type="radio"
        name="creation-mode"
        value={option.id}
        checked={isActive}
        onChange={onSelect}
        className="sr-only"
        aria-label={option.title}
      />
      <div className="flex items-center justify-between gap-3 text-wedding-navy">
        <div className={`rounded-2xl p-3 ${isActive ? 'bg-wedding-rose/10 text-wedding-rose' : 'bg-white/50 text-wedding-navy/70'}`}>
          {option.icon}
        </div>
        {isActive && <span className="rounded-full bg-wedding-rose/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white">Selected</span>}
      </div>
      <div className="space-y-2">
        <p className="text-sm font-semibold text-wedding-navy">{option.title}</p>
        <p className="text-xs text-gray-600 dark:text-gray-400">{option.description}</p>
      </div>
    </label>
  );
}

function formatDate(dateString: string): string {
  return (
    formatUtcDate(dateString, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }) || ''
  );
}

type BadgeTone = 'neutral' | 'accent' | 'success';

function FormBadge({
  tone = 'neutral',
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  const toneStyles: Record<BadgeTone, string> = {
    neutral: 'bg-white/70 text-wedding-navy border-white/40',
    accent: 'bg-wedding-rose/90 text-white border-wedding-rose/40 shadow-sm',
    success: 'bg-emerald-500/90 text-white border-emerald-400/60 shadow-sm',
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${toneStyles[tone]}`}>
      {children}
    </span>
  );
}

export default function FormsManagementPage(): ReactElement {
  const router = useRouter();
  const { token, userProfile } = useAdmin();

  const [forms, setForms] = useState<FormSummary[]>([]);
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creationMode, setCreationMode] = useState<CreationMode>('template');
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [duplicateSource, setDuplicateSource] = useState('');
  const [makePublic, setMakePublic] = useState(true);
  const [collectEmail, setCollectEmail] = useState(true);
  const [creating, setCreating] = useState(false);
  const [creationError, setCreationError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    if (!userProfile) {
      return;
    }

    if (!userProfile.is_wedding_planner && !userProfile.is_root_admin) {
      router.push('/admin');
      return;
    }

    const initialise = async () => {
      setLoading(true);
      setError(null);
      try {
        const [formList, templateList] = await Promise.all([
          formsApi.fetchForms(token),
          formsApi.fetchTemplates(token),
        ]);
        setForms(formList);
        setTemplates(templateList);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unable to load form data.';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    initialise();
  }, [token, userProfile, router]);

  const resetCreateModalState = () => {
    setFormName('');
    setFormDescription('');
    setSelectedTemplate('');
    setDuplicateSource('');
    setCreationMode('template');
    setMakePublic(true);
    setCollectEmail(true);
    setCreationError(null);
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    resetCreateModalState();
  };

  const refreshForms = async () => {
    if (!token) {
      return;
    }

    try {
      const formList = await formsApi.fetchForms(token);
      setForms(formList);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to refresh forms list.';
      setError(message);
    }
  };

  const handleCreateForm = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) {
      return;
    }

    const trimmedName = formName.trim();
    if (!trimmedName) {
      setCreationError('Enter a form name to continue.');
      return;
    }

    try {
      setCreating(true);
      setCreationError(null);

      if (creationMode === 'template') {
        if (!selectedTemplate) {
          setCreationError('Select a template to continue.');
          setCreating(false);
          return;
        }

        await formsApi.createFromTemplate(token, {
          templateId: selectedTemplate,
          name: trimmedName,
        });
      } else if (creationMode === 'blank') {
        const blankPayload: BlankFormPayload = {
          name: trimmedName,
          description: formDescription.trim() || undefined,
          isPublic: makePublic,
          collectEmail,
        };
        await formsApi.createBlankForm(token, blankPayload);
      } else {
        if (!duplicateSource) {
          setCreationError('Choose the form you want to duplicate.');
          setCreating(false);
          return;
        }

        const duplicatePayload: DuplicateFormPayload = {
          formId: duplicateSource,
          name: trimmedName,
        };
        await formsApi.duplicateForm(token, duplicatePayload);
      }

      closeCreateModal();
      await refreshForms();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to create form.';
      setCreationError(message);
    } finally {
      setCreating(false);
    }
  };

  const deleteForm = async (formId: string) => {
    if (!token) {
      return;
    }

    const confirmation = window.confirm('Are you sure you want to delete this form? This action cannot be undone.');
    if (!confirmation) {
      return;
    }

    try {
      const response = await fetch(`${formsApi.resolveBaseUrl()}/admin/forms/${formId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete form.');
      }

      await refreshForms();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete form.';
      setError(message);
    }
  };

  const formCounts: RoleBreakdown = useMemo(() => {
    return forms.reduce<RoleBreakdown>((accumulator, form) => {
      const key = form.template_type ?? 'custom';
      accumulator[key] = (accumulator[key] ?? 0) + 1;
      return accumulator;
    }, {});
  }, [forms]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900/5 via-white to-wedding-rose/20">
        <div className="rounded-3xl border border-white/60 bg-white/70 px-8 py-10 text-center shadow-xl backdrop-blur">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-wedding-rose"></div>
          <p className="text-sm font-medium text-wedding-navy">Loading your glass workspace…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10 pb-12">
      <section className="relative overflow-hidden rounded-[36px] border border-white/40 bg-gradient-to-br from-white/80 via-white/40 to-wedding-rose/10 p-8 shadow-2xl backdrop-blur-xl">
        <div className="pointer-events-none absolute -top-20 left-1/3 h-64 w-64 rounded-full bg-wedding-rose/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 right-10 h-72 w-72 rounded-full bg-slate-200/40 blur-3xl" />

        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-5">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-wedding-rose">Planner form studio</p>
            <h1 className="max-w-xl text-3xl font-semibold text-wedding-navy md:text-4xl">
              Curate modern form journeys with glassmorphic polish
            </h1>
            <p className="max-w-2xl text-sm text-slate-600">
              Build questionnaires, vendor workflows, and couple feedback loops that align with 2025 accessibility and Apple Glass
              Human Interface fundamentals. Monitor performance with realtime analytics and unread badges that keep your team in
              sync.
            </p>
            {forms.length > 0 && (
              <div className="flex flex-wrap gap-3">
                {Object.entries(formCounts).map(([key, count]) => (
                  <FormBadge key={key} tone="neutral">
                    {key.replace(/_/g, ' ')} · {count}
                  </FormBadge>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button
              id="create-form-button"
              onClick={() => setShowCreateModal(true)}
              className="shadow-lg shadow-wedding-rose/30"
            >
              Create new form
            </Button>
            <Button
              variant="secondary"
              className="shadow-lg shadow-slate-200/40"
              onClick={() => {
                void refreshForms();
              }}
            >
              Refresh workspace
            </Button>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-3xl border border-red-200/70 bg-red-50/70 px-6 py-4 text-red-700 dark:text-red-300 shadow-sm backdrop-blur">
          {error}
        </div>
      )}

      <section className="rounded-[36px] border border-white/40 bg-white/70 shadow-xl backdrop-blur">
        <header className="flex flex-col gap-4 border-b border-white/40 px-8 py-6 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-wedding-navy">Forms library</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Track what’s live, spot unread insights, and jump into analytics without breaking focus.
            </p>
          </div>
          <FormBadge tone="neutral">{forms.length} total</FormBadge>
        </header>

        {forms.length === 0 ? (
          <div className="px-8 py-20 text-center">
            <div className="mx-auto max-w-md space-y-3">
              <h3 className="text-lg font-semibold text-wedding-navy">Design your first form</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Start from the curated template gallery or open a blank canvas to craft a bespoke workflow.
              </p>
              <Button onClick={() => setShowCreateModal(true)} className="shadow-md shadow-wedding-rose/30">
                Launch creation studio
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid gap-6 p-6 sm:grid-cols-2 xl:grid-cols-3">
            {forms.map((form) => {
              const origin = typeof window !== 'undefined' ? window.location.origin : '';
              const previewHref = origin ? `${origin}/forms/${form.id}` : `https://wedding.app/forms/${form.id}`;

              return (
                <article
                  key={form.id}
                  className="group relative flex h-full flex-col justify-between rounded-3xl border border-white/50 bg-gradient-to-br from-white/70 via-white/40 to-wedding-rose/10 p-6 shadow-lg backdrop-blur transition hover:-translate-y-1 hover:border-wedding-rose/60 hover:shadow-2xl"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-lg font-semibold text-wedding-navy">{form.name}</h3>
                      {form.unread_responses > 0 && <FormBadge tone="accent">{form.unread_responses} unread</FormBadge>}
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {form.settings.description || form.settings.title}
                    </p>
                    <dl className="grid grid-cols-2 gap-3 text-xs text-gray-500 dark:text-gray-400">
                      <div className="space-y-1">
                        <dt className="font-semibold text-wedding-navy/80">Visibility</dt>
                        <dd>{form.settings.is_public ? 'Public link' : 'Planner only'}</dd>
                      </div>
                      <div className="space-y-1">
                        <dt className="font-semibold text-wedding-navy/80">Responses</dt>
                        <dd>{form.submission_count}</dd>
                      </div>
                      <div className="space-y-1">
                        <dt className="font-semibold text-wedding-navy/80">Created</dt>
                        <dd>{formatDate(form.created_at)}</dd>
                      </div>
                      {form.template_type && (
                        <div className="space-y-1">
                          <dt className="font-semibold text-wedding-navy/80">Template</dt>
                          <dd>{form.template_type.replace(/_/g, ' ')}</dd>
                        </div>
                      )}
                    </dl>
                  </div>

                  <div className="mt-6 flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      className="flex-1 min-w-[120px]"
                      onClick={() => router.push(`/admin/forms/${form.id}/edit`)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="secondary"
                      className="flex-1 min-w-[140px]"
                      onClick={() => router.push(`/admin/forms/${form.id}/responses`)}
                    >
                      Responses
                    </Button>
                    <Button
                      variant="secondary"
                      className="flex-1 min-w-[130px]"
                      onClick={() => router.push(`/admin/forms/${form.id}/analytics`)}
                    >
                      Analytics
                    </Button>
                    <Button
                      variant="secondary"
                      className="flex-1 min-w-[110px]"
                      onClick={() => router.push(`/admin/forms/${form.id}/send`)}
                    >
                      Share
                    </Button>
                    <Button
                      variant="secondary"
                      className="flex-1 min-w-[110px]"
                      onClick={() => window.open(previewHref, '_blank', 'noopener')}
                    >
                      Preview
                    </Button>
                    <Button variant="danger" className="flex-1 min-w-[110px]" onClick={() => deleteForm(form.id)}>
                      Delete
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <Transition show={showCreateModal} as={Fragment}>
        <Dialog onClose={closeCreateModal} className="relative z-50">
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center px-4 py-8">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-200"
                enterFrom="opacity-0 translate-y-6"
                enterTo="opacity-100 translate-y-0"
                leave="ease-in duration-150"
                leaveFrom="opacity-100 translate-y-0"
                leaveTo="opacity-0 translate-y-6"
              >
                <Dialog.Panel className="w-full max-w-5xl overflow-hidden rounded-[36px] border border-white/50 bg-white/80 shadow-2xl backdrop-blur-xl">
                  <div className="grid gap-0 lg:grid-cols-[320px,minmax(0,1fr)]">
                    <aside className="relative hidden overflow-hidden border-b border-white/30 bg-gradient-to-br from-wedding-rose/30 via-wedding-rose/10 to-slate-100/40 p-8 text-white lg:block lg:border-r">
                      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.35),_transparent_60%)]" />
                      <div className="relative space-y-6">
                        <p className="text-xs font-semibold uppercase tracking-[0.4em] text-white/80">Creation studio</p>
                        <h2 className="text-2xl font-semibold leading-snug text-white">
                          Choose the launch path that fits this moment
                        </h2>
                        <ul className="space-y-4 text-sm text-white/80">
                          <li className="flex items-start gap-2">
                            <span className="mt-1 h-2.5 w-2.5 rounded-full bg-white/70" aria-hidden="true" />
                            <span>Template flows include 2025 compliance copy, section logic, and Apple Glass elevation tokens.</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="mt-1 h-2.5 w-2.5 rounded-full bg-white/70" aria-hidden="true" />
                            <span>Blank canvases auto-enable accessibility guardrails, grid alignment, and vendor field presets.</span>
                          </li>
                          <li className="flex items-start gap-2">
                            <span className="mt-1 h-2.5 w-2.5 rounded-full bg-white/70" aria-hidden="true" />
                            <span>Duplications preserve analytics integrity, unread badges, and audit history for the original form.</span>
                          </li>
                        </ul>
                        <div className="rounded-3xl border border-white/40 bg-white/20 p-4 text-xs text-white/80 backdrop-blur">
                          <p className="font-semibold uppercase tracking-wide text-white">Best practice insight</p>
                          <p className="mt-2">
                            Align each workflow with a single outcome. Use analytics tagging post-launch to track drop-off and iterate.
                          </p>
                        </div>
                      </div>
                    </aside>

                    <form className="space-y-7 p-8" onSubmit={handleCreateForm}>
                      <div className="space-y-2">
                        <Dialog.Title className="text-2xl font-semibold text-wedding-navy">Create a new form</Dialog.Title>
                        <Dialog.Description className="text-sm text-gray-600 dark:text-gray-400">
                          Pick a starting point and configure visibility. The creation studio applies Apple glass design primitives automatically.
                        </Dialog.Description>
                      </div>

                      <div className="grid gap-4 md:grid-cols-3">
                        {CREATION_OPTIONS.map((option) => (
                          <CreationOptionCard
                            key={option.id}
                            option={option}
                            isActive={creationMode === option.id}
                            onSelect={() => setCreationMode(option.id)}
                          />
                        ))}
                      </div>

                      <div className="space-y-3">
                        <label htmlFor="form-name-input" className="text-sm font-medium text-wedding-navy">
                          Form name
                        </label>
                        <input
                          id="form-name-input"
                          type="text"
                          value={formName}
                          onChange={(event) => setFormName(event.target.value)}
                          placeholder="e.g. Post-event guest feedback"
                          className="w-full rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                        />
                      </div>

                      {creationMode === 'template' && (
                        <div className="space-y-3">
                          <label htmlFor="template-select" className="text-sm font-medium text-wedding-navy">
                            Template
                          </label>
                          <select
                            id="template-select"
                            value={selectedTemplate}
                            onChange={(event) => setSelectedTemplate(event.target.value)}
                            className="w-full rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                          >
                            <option value="">Select a template…</option>
                            {templates.map((template) => (
                              <option key={template.id} value={template.id}>
                                {template.name} — {template.description}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {creationMode === 'blank' && (
                        <div className="space-y-4">
                          <div className="space-y-3">
                            <label htmlFor="form-description" className="text-sm font-medium text-wedding-navy">
                              Description (optional)
                            </label>
                            <textarea
                              id="form-description"
                              value={formDescription}
                              onChange={(event) => setFormDescription(event.target.value)}
                              rows={3}
                              placeholder="Explain what information you’re collecting. This appears below the title."
                              className="w-full rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                            />
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <label className="flex items-center justify-between gap-3 rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-wedding-navy shadow-inner">
                              <span className="flex flex-col">
                                <span className="font-medium">Public access</span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">Generate a link anyone can view.</span>
                              </span>
                              <input
                                type="checkbox"
                                checked={makePublic}
                                onChange={(event) => setMakePublic(event.target.checked)}
                                className="h-4 w-4 rounded border-gray-300 text-wedding-rose focus:ring-wedding-rose/60"
                              />
                            </label>
                            <label className="flex items-center justify-between gap-3 rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-wedding-navy shadow-inner">
                              <span className="flex flex-col">
                                <span className="font-medium">Collect emails</span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">Capture respondent contact details for follow-ups.</span>
                              </span>
                              <input
                                type="checkbox"
                                checked={collectEmail}
                                onChange={(event) => setCollectEmail(event.target.checked)}
                                className="h-4 w-4 rounded border-gray-300 text-wedding-rose focus:ring-wedding-rose/60"
                              />
                            </label>
                          </div>
                        </div>
                      )}

                      {creationMode === 'duplicate' && (
                        <div className="space-y-3">
                          <label htmlFor="duplicate-form-select" className="text-sm font-medium text-wedding-navy">
                            Choose a form to duplicate
                          </label>
                          <select
                            id="duplicate-form-select"
                            value={duplicateSource}
                            onChange={(event) => setDuplicateSource(event.target.value)}
                            className="w-full rounded-2xl border border-white/60 bg-white/70 px-4 py-3 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none focus:ring-2 focus:ring-wedding-rose/50"
                          >
                            <option value="">Select one of your forms…</option>
                            {forms.map((form) => (
                              <option key={form.id} value={form.id}>
                                {form.name} · {form.submission_count} responses
                              </option>
                            ))}
                          </select>
                        </div>
                      )}

                      {creationError && (
                        <p className="rounded-2xl border border-red-200 bg-red-50/90 px-4 py-2 text-sm text-red-700 dark:text-red-300 shadow-inner">
                          {creationError}
                        </p>
                      )}

                      <div className="flex flex-col gap-3 md:flex-row md:justify-end">
                        <Button
                          type="button"
                          variant="secondary"
                          className="md:min-w-[140px]"
                          id="cancel-create-button"
                          onClick={closeCreateModal}
                        >
                          Cancel
                        </Button>
                        <Button
                          id="confirm-create-button"
                          type="submit"
                          disabled={creating}
                          className="md:min-w-[160px] shadow-lg shadow-wedding-rose/30"
                        >
                          {creating ? 'Creating…' : 'Create form'}
                        </Button>
                      </div>
                    </form>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
}
