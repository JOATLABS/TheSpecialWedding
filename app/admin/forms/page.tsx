'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAdmin } from '@/contexts/AdminContext';

type CreationMode = 'template' | 'blank' | 'duplicate';

interface Form {
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
  created_at: string;
  is_active: boolean;
}

interface FormTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
}

export default function FormsManagementPage(): JSX.Element {
  const router = useRouter();
  const { token, userProfile } = useAdmin();

  const [forms, setForms] = useState<Form[]>([]);
  const [templates, setTemplates] = useState<FormTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creationMode, setCreationMode] = useState<CreationMode>('template');
  const [formName, setFormName] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [duplicateSourceId, setDuplicateSourceId] = useState('');
  const [creating, setCreating] = useState(false);
  const [creationError, setCreationError] = useState('');

  const [formTitle, setFormTitle] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [submitButtonText, setSubmitButtonText] = useState('Submit');
  const [successMessage, setSuccessMessage] = useState('Thank you for your submission!');
  const [allowMultipleSubmissions, setAllowMultipleSubmissions] = useState(false);
  const [collectEmail, setCollectEmail] = useState(true);
  const [isPublic, setIsPublic] = useState(true);
  const [requiresAuth, setRequiresAuth] = useState(false);
  const [titleEdited, setTitleEdited] = useState(false);

  const apiBaseUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
    [],
  );

  useEffect(() => {
    if (!token) {
      router.push('/admin/login');
      return;
    }

    if (!userProfile || (!userProfile.is_wedding_planner && !userProfile.is_root_admin)) {
      router.push('/admin');
      return;
    }

    void fetchForms();
    void fetchTemplates();
  }, [token, userProfile, router]);

  useEffect(() => {
    if (creationMode === 'blank' && !titleEdited) {
      setFormTitle(formName);
    }
  }, [creationMode, formName, titleEdited]);

  const fetchForms = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/admin/forms`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch forms');
      }

      const data = await response.json();
      setForms(data);
    } catch (err) {
      console.error(err);
      setError('Failed to fetch forms');
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/admin/form-templates`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        return;
      }

      const data = await response.json();
      setTemplates(data.templates);
    } catch (err) {
      console.warn('Form template fetch failed', err);
    }
  };

  const resetCreationState = () => {
    setCreationMode('template');
    setFormName('');
    setSelectedTemplate('');
    setDuplicateSourceId('');
    setFormTitle('');
    setFormDescription('');
    setSubmitButtonText('Submit');
    setSuccessMessage('Thank you for your submission!');
    setAllowMultipleSubmissions(false);
    setCollectEmail(true);
    setIsPublic(true);
    setRequiresAuth(false);
    setTitleEdited(false);
    setCreationError('');
  };

  const handleCreateForm = async () => {
    if (!token) {
      return;
    }

    setCreating(true);
    setCreationError('');

    try {
      if (creationMode === 'template') {
        if (!selectedTemplate || !formName.trim()) {
          setCreationError('Select a template and enter a form name.');
          return;
        }

        const response = await fetch(
          `${apiBaseUrl}/admin/forms/from-template/${selectedTemplate}?form_name=${encodeURIComponent(formName.trim())}`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          },
        );

        if (!response.ok) {
          throw new Error('Template creation failed');
        }
      }

      if (creationMode === 'blank') {
        const effectiveName = formName.trim();
        const effectiveTitle = (formTitle || formName).trim();

        if (!effectiveName || !effectiveTitle) {
          setCreationError('Form name and display title are required.');
          return;
        }

        const payload = {
          name: effectiveName,
          settings: {
            title: effectiveTitle,
            description: formDescription.trim() || undefined,
            submit_button_text: submitButtonText.trim() || 'Submit',
            success_message: successMessage.trim() || 'Thank you for your submission!',
            allow_multiple_submissions: allowMultipleSubmissions,
            collect_email: collectEmail,
            is_public: isPublic,
            requires_auth: requiresAuth,
          },
          fields: [],
        };

        const response = await fetch(`${apiBaseUrl}/admin/forms`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || 'Blank form creation failed');
        }
      }

      if (creationMode === 'duplicate') {
        if (!duplicateSourceId || !formName.trim()) {
          setCreationError('Choose a form to duplicate and provide a name.');
          return;
        }

        const response = await fetch(
          `${apiBaseUrl}/admin/forms/duplicate/${duplicateSourceId}?new_name=${encodeURIComponent(formName.trim())}`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          },
        );

        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || 'Form duplication failed');
        }
      }

      setShowCreateModal(false);
      resetCreationState();
      await fetchForms();
    } catch (err) {
      console.error(err);
      setCreationError(err instanceof Error ? err.message : 'Unable to create form.');
    } finally {
      setCreating(false);
    }
  };

  const deleteForm = async (formId: string) => {
    if (!confirm('Are you sure you want to delete this form?')) {
      return;
    }

    try {
      const response = await fetch(`${apiBaseUrl}/admin/forms/${formId}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete form');
      }

      await fetchForms();
    } catch (err) {
      console.error(err);
      setError('Failed to delete form');
    }
  };

  const formatDate = (value: string) =>
    new Date(value).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });

  const previewUrlFor = (formId: string) => {
    if (typeof window === 'undefined') {
      return `/forms/${formId}`;
    }

    return `${window.location.origin}/forms/${formId}`;
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-indigo-600" />
          <p className="text-gray-600">Loading forms…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-white/30 bg-white/70 p-6 shadow-xl backdrop-blur-xl">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-wedding-navy">Form Builder</h1>
            <p className="text-sm text-wedding-navy/70">
              Create bespoke feedback, intake, and RSVP experiences for each wedding.
            </p>
          </div>
          <button
            id="create-form-button"
            onClick={() => {
              setShowCreateModal(true);
              setCreationMode('template');
            }}
            className="rounded-full bg-wedding-rose px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:bg-wedding-rose/80"
          >
            Create New Form
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>
      )}

      <div className="rounded-3xl border border-white/30 bg-white/70 shadow-xl backdrop-blur-xl">
        <div className="border-b border-white/40 px-6 py-4">
          <h2 className="text-lg font-semibold text-wedding-navy">Your Forms</h2>
        </div>
        <div className="divide-y divide-white/40">
          {forms.length === 0 ? (
            <div className="px-6 py-10 text-center text-wedding-navy/70">
              <h3 className="text-lg font-semibold text-wedding-navy">No forms created yet</h3>
              <p className="mt-2 text-sm">
                Launch a blank canvas, duplicate an existing workflow, or start from a curated template.
              </p>
            </div>
          ) : (
            forms.map((form) => (
              <div key={form.id} className="flex flex-col gap-4 px-6 py-5 transition hover:bg-white/60">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-wedding-navy">{form.name}</h3>
                    <p className="text-sm text-wedding-navy/70">
                      {form.settings.description || form.settings.title}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-wedding-navy/60">
                      <span>Responses: {form.submission_count}</span>
                      <span>Created: {formatDate(form.created_at)}</span>
                      {form.template_type && (
                        <span className="rounded-full bg-white/70 px-3 py-1 text-[11px] uppercase tracking-wide text-wedding-navy/80">
                          {form.template_type.replace(/_/g, ' ')}
                        </span>
                      )}
                      <span
                        className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
                          form.settings.is_public
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-slate-200 text-slate-700'
                        }`}
                      >
                        {form.settings.is_public ? 'Public' : 'Private'}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      id={`edit-form-${form.id}`}
                      onClick={() => router.push(`/admin/forms/${form.id}/edit`)}
                      className="rounded-full bg-purple-100 px-3 py-1 text-sm font-medium text-purple-700 transition hover:bg-purple-200"
                    >
                      Edit
                    </button>
                    <button
                      id={`duplicate-form-${form.id}`}
                      onClick={() => {
                        setShowCreateModal(true);
                        setCreationMode('duplicate');
                        setDuplicateSourceId(form.id);
                        setFormName(`${form.name} Copy`);
                      }}
                      className="rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-700 transition hover:bg-amber-200"
                    >
                      Duplicate
                    </button>
                    <button
                      onClick={() => router.push(`/admin/forms/${form.id}/responses`)}
                      className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-700 transition hover:bg-blue-200"
                    >
                      View Responses ({form.submission_count})
                    </button>
                    <button
                      onClick={() => router.push(`/admin/forms/${form.id}/send`)}
                      className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-700 transition hover:bg-emerald-200"
                    >
                      Send Form
                    </button>
                    <button
                      onClick={() => router.push(`/admin/forms/${form.id}/analytics`)}
                      className="rounded-full bg-indigo-100 px-3 py-1 text-sm font-medium text-indigo-700 transition hover:bg-indigo-200"
                    >
                      Analytics
                    </button>
                    <a
                      href={previewUrlFor(form.id)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700 transition hover:bg-slate-200"
                    >
                      Preview
                    </a>
                    <button
                      id={`delete-form-${form.id}`}
                      onClick={() => deleteForm(form.id)}
                      className="rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700 transition hover:bg-red-200"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4 py-10">
          <div className="w-full max-w-2xl rounded-3xl border border-white/30 bg-white/75 p-6 shadow-2xl backdrop-blur-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-semibold text-wedding-navy">Create a new form</h3>
                <p className="text-sm text-wedding-navy/70">Choose how you would like to begin collecting responses.</p>
              </div>
              <button
                aria-label="Close create form modal"
                onClick={() => {
                  setShowCreateModal(false);
                  resetCreationState();
                }}
                className="rounded-full bg-white/60 px-3 py-1 text-sm font-medium text-wedding-navy/70 transition hover:bg-white/80"
              >
                Close
              </button>
            </div>

            <div className="mt-6 flex flex-col gap-4" role="radiogroup" aria-label="Form creation method">
              <div className="grid gap-3 md:grid-cols-3">
                <button
                  id="creation-type-template"
                  type="button"
                  aria-pressed={creationMode === 'template'}
                  onClick={() => setCreationMode('template')}
                  className={`rounded-2xl border px-4 py-4 text-left transition ${
                    creationMode === 'template'
                      ? 'border-wedding-rose bg-white/90 shadow-lg'
                      : 'border-white/40 bg-white/60 hover:bg-white/80'
                  }`}
                >
                  <span className="block text-sm font-semibold text-wedding-navy">Template</span>
                  <span className="mt-1 block text-xs text-wedding-navy/70">
                    Start with a curated structure designed for popular workflows.
                  </span>
                </button>
                <button
                  id="creation-type-blank"
                  type="button"
                  aria-pressed={creationMode === 'blank'}
                  onClick={() => setCreationMode('blank')}
                  className={`rounded-2xl border px-4 py-4 text-left transition ${
                    creationMode === 'blank'
                      ? 'border-wedding-rose bg-white/90 shadow-lg'
                      : 'border-white/40 bg-white/60 hover:bg-white/80'
                  }`}
                >
                  <span className="block text-sm font-semibold text-wedding-navy">Blank</span>
                  <span className="mt-1 block text-xs text-wedding-navy/70">
                    Craft a form from scratch with full control of sections and copy.
                  </span>
                </button>
                <button
                  id="creation-type-duplicate"
                  type="button"
                  aria-pressed={creationMode === 'duplicate'}
                  onClick={() => setCreationMode('duplicate')}
                  className={`rounded-2xl border px-4 py-4 text-left transition ${
                    creationMode === 'duplicate'
                      ? 'border-wedding-rose bg-white/90 shadow-lg'
                      : 'border-white/40 bg-white/60 hover:bg-white/80'
                  }`}
                >
                  <span className="block text-sm font-semibold text-wedding-navy">Duplicate</span>
                  <span className="mt-1 block text-xs text-wedding-navy/70">
                    Reuse the structure of a proven form and tweak the details.
                  </span>
                </button>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="flex flex-col text-sm font-medium text-wedding-navy">
                  Form name
                  <input
                    id="form-name-input"
                    type="text"
                    value={formName}
                    onChange={(event) => {
                      setFormName(event.target.value);
                      if (!titleEdited && creationMode === 'blank') {
                        setFormTitle(event.target.value);
                      }
                    }}
                    className="mt-1 rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none"
                    placeholder="e.g. Vendor Intake"
                  />
                </label>

                {creationMode === 'template' && (
                  <label className="flex flex-col text-sm font-medium text-wedding-navy">
                    Template
                    <select
                      id="template-select"
                      value={selectedTemplate}
                      onChange={(event) => setSelectedTemplate(event.target.value)}
                      className="mt-1 rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none"
                    >
                      <option value="">Select a template…</option>
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name} — {template.description}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {creationMode === 'duplicate' && (
                  <label className="flex flex-col text-sm font-medium text-wedding-navy">
                    Duplicate existing form
                    <select
                      id="duplicate-form-select"
                      value={duplicateSourceId}
                      onChange={(event) => setDuplicateSourceId(event.target.value)}
                      className="mt-1 rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none"
                    >
                      <option value="">Choose a form…</option>
                      {forms.map((form) => (
                        <option key={form.id} value={form.id}>
                          {form.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {creationMode === 'blank' && (
                  <>
                    <label className="flex flex-col text-sm font-medium text-wedding-navy">
                      Display title
                      <input
                        type="text"
                        value={formTitle}
                        onChange={(event) => {
                          setFormTitle(event.target.value);
                          setTitleEdited(true);
                        }}
                        className="mt-1 rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none"
                        placeholder="Shown on the public form"
                      />
                    </label>
                    <label className="flex flex-col text-sm font-medium text-wedding-navy">
                      Description
                      <textarea
                        value={formDescription}
                        onChange={(event) => setFormDescription(event.target.value)}
                        className="mt-1 h-24 rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none"
                        placeholder="Explain the purpose or audience"
                      />
                    </label>
                    <label className="flex flex-col text-sm font-medium text-wedding-navy">
                      Submit button label
                      <input
                        type="text"
                        value={submitButtonText}
                        onChange={(event) => setSubmitButtonText(event.target.value)}
                        className="mt-1 rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none"
                        placeholder="Submit"
                      />
                    </label>
                    <label className="flex flex-col text-sm font-medium text-wedding-navy">
                      Success message
                      <input
                        type="text"
                        value={successMessage}
                        onChange={(event) => setSuccessMessage(event.target.value)}
                        className="mt-1 rounded-xl border border-white/40 bg-white/80 px-3 py-2 text-sm text-wedding-navy shadow-inner focus:border-wedding-rose focus:outline-none"
                        placeholder="Thank you for your submission!"
                      />
                    </label>
                    <div className="col-span-full grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <label className="flex items-center gap-2 text-sm font-medium text-wedding-navy">
                        <input
                          type="checkbox"
                          checked={allowMultipleSubmissions}
                          onChange={(event) => setAllowMultipleSubmissions(event.target.checked)}
                          className="h-4 w-4 rounded border-white/50 bg-white/80 text-wedding-rose focus:ring-wedding-rose"
                        />
                        Allow multiple submissions
                      </label>
                      <label className="flex items-center gap-2 text-sm font-medium text-wedding-navy">
                        <input
                          type="checkbox"
                          checked={collectEmail}
                          onChange={(event) => setCollectEmail(event.target.checked)}
                          className="h-4 w-4 rounded border-white/50 bg-white/80 text-wedding-rose focus:ring-wedding-rose"
                        />
                        Collect email addresses
                      </label>
                      <label className="flex items-center gap-2 text-sm font-medium text-wedding-navy">
                        <input
                          type="checkbox"
                          checked={isPublic}
                          onChange={(event) => setIsPublic(event.target.checked)}
                          className="h-4 w-4 rounded border-white/50 bg-white/80 text-wedding-rose focus:ring-wedding-rose"
                        />
                        Publicly accessible
                      </label>
                      <label className="flex items-center gap-2 text-sm font-medium text-wedding-navy">
                        <input
                          type="checkbox"
                          checked={requiresAuth}
                          onChange={(event) => setRequiresAuth(event.target.checked)}
                          className="h-4 w-4 rounded border-white/50 bg-white/80 text-wedding-rose focus:ring-wedding-rose"
                        />
                        Require login to respond
                      </label>
                    </div>
                  </>
                )}
              </div>
            </div>

            {creationError && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{creationError}</div>
            )}

            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
              <button
                id="cancel-create-button"
                onClick={() => {
                  setShowCreateModal(false);
                  resetCreationState();
                }}
                className="rounded-full border border-white/40 bg-white/70 px-4 py-2 text-sm font-medium text-wedding-navy/80 transition hover:bg-white/90"
              >
                Cancel
              </button>
              <button
                id="confirm-create-button"
                onClick={() => void handleCreateForm()}
                disabled={creating}
                className="rounded-full bg-wedding-rose px-5 py-2 text-sm font-semibold text-white shadow-lg transition hover:bg-wedding-rose/80 disabled:cursor-not-allowed disabled:bg-wedding-rose/40"
              >
                {creating ? 'Creating…' : 'Create form'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
