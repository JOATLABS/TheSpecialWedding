'use client';

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react';
import { getApiBaseUrl } from '@/utils/env';
import { useParams, useSearchParams } from 'next/navigation';
import {
  filterResponsesToVisible,
  isFieldVisible,
} from '@/utils/formConditionalLogic';

// Mirrors backend constants in app/services/form_upload_service.py.
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ALLOWED_UPLOAD_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
  'image/heic',
  'image/heif',
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'text/plain',
];

interface FileUploadValue {
  file_id: string;
  filename: string;
  url: string;
  content_type: string;
  size_bytes: number;
}

interface FileUploadFieldProps {
  field: { id: string; label: string; required: boolean };
  value: unknown;
  disabled: boolean;
  formId: string;
  distributionId?: string;
  accessToken?: string;
  onChange: (value: FileUploadValue | null) => void;
}

// Batch 8 (R2 audit): replace fetch with XHR so upload progress, cancel,
// and retry are visible. Inline upload state machine: idle → uploading →
// done | error. A file replacement aborts an in-flight xhr first to avoid
// races.
type UploadStatus = 'idle' | 'uploading' | 'done' | 'error';

function FileUploadField({
  field,
  value,
  disabled,
  formId,
  distributionId,
  accessToken,
  onChange,
}: FileUploadFieldProps) {
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const xhrRef = useRef<XMLHttpRequest | null>(null);

  const current =
    value && typeof value === 'object' && 'file_id' in (value as Record<string, unknown>)
      ? (value as FileUploadValue)
      : null;

  const startUpload = useCallback(
    (file: File) => {
      setErrorMsg(null);
      if (!distributionId || !accessToken) {
        setErrorMsg('This form must be opened from your email link to attach files.');
        setStatus('error');
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        setErrorMsg(`File too large. Max ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB.`);
        setStatus('error');
        return;
      }
      if (file.type && !ALLOWED_UPLOAD_MIME_TYPES.includes(file.type)) {
        setErrorMsg(`File type "${file.type}" is not allowed.`);
        setStatus('error');
        return;
      }

      // Abort any in-flight upload before starting a new one.
      if (xhrRef.current) {
        try {
          xhrRef.current.abort();
        } catch {
          /* ignore */
        }
      }

      const baseUrl = getApiBaseUrl();
      const fd = new FormData();
      fd.append('distribution_id', distributionId);
      fd.append('access_token', accessToken);
      fd.append('field_id', field.id);
      fd.append('upload', file);

      const xhr = new XMLHttpRequest();
      xhrRef.current = xhr;
      setStatus('uploading');
      setProgress(0);
      setPendingFile(file);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          setProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () => {
        xhrRef.current = null;
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText) as FileUploadValue;
            onChange(data);
            setStatus('done');
            setProgress(100);
            setPendingFile(null);
          } catch {
            setErrorMsg('Upload succeeded but response was malformed.');
            setStatus('error');
          }
        } else {
          let detail: string | undefined;
          try {
            detail = JSON.parse(xhr.responseText)?.detail;
          } catch {
            /* ignore */
          }
          setErrorMsg(detail || 'Upload failed. Please try again.');
          setStatus('error');
        }
      };
      xhr.onerror = () => {
        xhrRef.current = null;
        setErrorMsg('Upload failed. Please check your connection.');
        setStatus('error');
      };
      xhr.onabort = () => {
        xhrRef.current = null;
        // If user cancelled, reset to idle quietly.
        setStatus('idle');
        setProgress(0);
      };

      xhr.open('POST', `${baseUrl}/public/forms/${formId}/uploads`);
      xhr.send(fd);
    },
    [accessToken, distributionId, field.id, formId, onChange],
  );

  const handleFilePick = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) startUpload(file);
  };

  const handleCancel = () => {
    if (xhrRef.current) {
      try {
        xhrRef.current.abort();
      } catch {
        /* ignore */
      }
    }
  };

  const handleRetry = () => {
    if (pendingFile) startUpload(pendingFile);
  };

  return (
    <div className="space-y-2">
      <input
        type="file"
        accept={ALLOWED_UPLOAD_MIME_TYPES.join(',')}
        disabled={disabled || status === 'uploading'}
        onChange={handleFilePick}
        className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-white focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
      />
      {disabled && !current && (
        <p className="text-xs text-gray-500">
          Open this form from your email link to attach files.
        </p>
      )}
      {status === 'uploading' && (
        <div className="space-y-1" data-testid="upload-progress">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <span>Uploading… {progress}%</span>
            <button
              type="button"
              onClick={handleCancel}
              className="text-red-600 hover:underline"
            >
              Cancel
            </button>
          </div>
          <div className="h-2 w-full overflow-hidden rounded bg-gray-200">
            <div
              className="h-full bg-indigo-600 transition-all"
              style={{ width: `${progress}%` }}
              role="progressbar"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
        </div>
      )}
      {current && status !== 'uploading' && (
        <div className="flex items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm">
          <span className="truncate text-gray-700">{current.filename}</span>
          <button
            type="button"
            onClick={() => onChange(null)}
            className="ml-2 text-xs text-red-600 hover:underline"
          >
            Remove
          </button>
        </div>
      )}
      {status === 'error' && errorMsg && (
        <div className="flex items-center justify-between rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm">
          <span className="text-red-700">{errorMsg}</span>
          {pendingFile && (
            <button
              type="button"
              onClick={handleRetry}
              className="ml-2 text-xs font-medium text-red-700 hover:underline"
              data-testid="upload-retry"
            >
              Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}

interface FormField {
  id: string;
  label: string;
  type: string;
  placeholder?: string;
  required: boolean;
  description?: string;
  options: string[];
  order: number;
  conditional_logic?: Record<string, unknown> | null;
}

interface FormSettings {
  title: string;
  description?: string;
  submit_button_text: string;
  success_message: string;
  collect_email: boolean;
}

interface Form {
  id: string;
  settings: FormSettings;
  fields: FormField[];
  is_active: boolean;
}

type LinkState =
  | 'unknown'
  | 'valid'
  | 'already_submitted'
  | 'expired'
  | 'invalid'
  | 'rotated';

// Batch 9 (R3 audit): a stable, per-mount idempotency key so a flaky
// network or double-click during submission yields exactly one row in
// form_responses. The backend dedupes on (form_id, idempotency_key).
function generateIdempotencyKey(): string {
  if (typeof window !== 'undefined' && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  // Fallback: 16 random hex chars + timestamp suffix.
  const rand = Math.random().toString(36).slice(2, 12);
  return `${rand}-${Date.now()}`;
}

export default function PublicFormPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const formId = params.id as string;
  const distributionId = searchParams?.get('dist') || undefined;
  const accessToken = searchParams?.get('t') || undefined;

  const [form, setForm] = useState<Form | null>(null);
  const [responses, setResponses] = useState<{ [key: string]: any }>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [linkState, setLinkState] = useState<LinkState>('unknown');

  // Batch 7 (R1, R8 audit): per-field validation state.
  const [invalidFieldIds, setInvalidFieldIds] = useState<Set<string>>(new Set());

  // Batch 10 (R4 audit): track newly-revealed required fields between
  // renders so we can scroll them into view + flash-highlight them.
  const previousVisibleIdsRef = useRef<Set<string>>(new Set());
  const [flashFieldIds, setFlashFieldIds] = useState<Set<string>>(new Set());

  // Refs to each field row so we can scrollIntoView() the offending one.
  const fieldRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const idempotencyKey = useMemo(() => generateIdempotencyKey(), []);

  const fetchForm = useCallback(async () => {
    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/public/forms/${formId}`);

      if (response.ok) {
        const data = await response.json();
        setForm(data);
        if (!data.is_active) {
          setError('This form is no longer accepting responses.');
        }
      } else {
        setError('Form not found or no longer available.');
      }

      if (distributionId && accessToken) {
        try {
          const checkRes = await fetch(
            `${baseUrl}/public/forms/${formId}/distributions/${encodeURIComponent(distributionId)}/check?t=${encodeURIComponent(accessToken)}`,
          );
          if (checkRes.ok) {
            const checkData = await checkRes.json();
            if (checkData.already_submitted) setLinkState('already_submitted');
            else if (checkData.expired) setLinkState('expired');
            else setLinkState('valid');
          } else {
            setLinkState('invalid');
          }
        } catch {
          setLinkState('invalid');
        }
      } else {
        setLinkState('valid');
      }
    } catch {
      setError('Failed to load form. Please try again later.');
    } finally {
      setLoading(false);
    }
  }, [formId, distributionId, accessToken]);

  useEffect(() => {
    if (formId) {
      fetchForm();
    }
  }, [fetchForm, formId]);

  const handleInputChange = (fieldId: string, value: any) => {
    setResponses((prev) => ({ ...prev, [fieldId]: value }));
    // Batch 7: clear the per-field invalid state on edit.
    setInvalidFieldIds((prev) => {
      if (!prev.has(fieldId)) return prev;
      const next = new Set(prev);
      next.delete(fieldId);
      return next;
    });
  };

  // Batch 7 (R1, R8): collect all failing required fields rather than
  // bailing on the first one. Returns the list of invalid ids (visible
  // + required + empty) so the caller can scroll/focus the first one.
  const collectInvalidFields = useCallback((): string[] => {
    if (!form) return [];
    const invalid: string[] = [];
    for (const field of form.fields) {
      if (!isFieldVisible(field, responses)) continue;
      if (!field.required) continue;
      const value = responses[field.id];
      const isEmpty =
        value === undefined ||
        value === null ||
        (typeof value === 'string' && value.trim() === '') ||
        (Array.isArray(value) && value.length === 0);
      if (isEmpty) invalid.push(field.id);
    }
    return invalid;
  }, [form, responses]);

  // Batch 10: detect newly-revealed required fields between renders.
  useEffect(() => {
    if (!form) return;
    const currentlyVisible = new Set(
      form.fields.filter((f) => isFieldVisible(f, responses)).map((f) => f.id),
    );
    const previous = previousVisibleIdsRef.current;
    const newlyRevealed = [...currentlyVisible].filter((id) => !previous.has(id));
    if (newlyRevealed.length && previous.size > 0) {
      const newlyRequired = newlyRevealed.filter((id) => {
        const field = form.fields.find((f) => f.id === id);
        return field?.required;
      });
      if (newlyRequired.length) {
        const firstId = newlyRequired[0];
        const node = fieldRefs.current[firstId];
        if (node) {
          node.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        setFlashFieldIds(new Set(newlyRequired));
        // Clear the flash after the keyframe completes.
        const timer = window.setTimeout(() => {
          setFlashFieldIds(new Set());
        }, 1600);
        previousVisibleIdsRef.current = currentlyVisible;
        return () => window.clearTimeout(timer);
      }
    }
    previousVisibleIdsRef.current = currentlyVisible;
  }, [form, responses]);

  const submitForm = async () => {
    setError('');
    const invalid = collectInvalidFields();
    if (invalid.length) {
      setInvalidFieldIds(new Set(invalid));
      const firstNode = fieldRefs.current[invalid[0]];
      if (firstNode) {
        firstNode.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const focusable = firstNode.querySelector<HTMLElement>(
          'input, textarea, select, button',
        );
        focusable?.focus();
      }
      setError(
        invalid.length === 1
          ? 'Please fill in the required field highlighted below.'
          : `Please fill in ${invalid.length} required fields highlighted below.`,
      );
      return;
    }

    setSubmitting(true);

    try {
      const baseUrl = getApiBaseUrl();
      const visibleResponses = form
        ? filterResponsesToVisible(form.fields, responses)
        : responses;

      const submissionData = {
        responses: visibleResponses,
        submitted_by_email:
          (visibleResponses.email as string | undefined) ||
          (visibleResponses.guest_email as string | undefined) ||
          (visibleResponses.contact_email as string | undefined),
        submitted_by_name:
          (visibleResponses.name as string | undefined) ||
          (visibleResponses.guest_name as string | undefined) ||
          (visibleResponses.contact_name as string | undefined),
        distribution_id: distributionId,
        access_token: accessToken,
        idempotency_key: idempotencyKey,
      };

      const response = await fetch(`${baseUrl}/public/forms/${formId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submissionData),
      });

      if (response.ok) {
        const data = await response.json();
        setSuccessMessage(
          data.message ||
            form?.settings.success_message ||
            'Thank you for your submission!',
        );
        setSubmitted(true);
        if (data.redirect_url) {
          setTimeout(() => {
            window.location.href = data.redirect_url;
          }, 3000);
        }
        return;
      }

      // Batch 9 / Batch 12: route 403/409/410 onto the friendly link-state
      // screens instead of a generic toast.
      const errorData = await response.json().catch(() => ({}));
      if (response.status === 410) {
        setLinkState('expired');
        return;
      }
      if (response.status === 409) {
        setLinkState('already_submitted');
        return;
      }
      if (response.status === 403) {
        const detail = errorData?.detail;
        const reason =
          detail && typeof detail === 'object'
            ? (detail as { reason?: string }).reason
            : undefined;
        if (reason === 'token_rotated_or_revoked') {
          setLinkState('rotated');
          return;
        }
      }

      const detailMessage =
        typeof errorData?.detail === 'string'
          ? errorData.detail
          : errorData?.detail?.message || 'Failed to submit form. Please try again.';
      setError(detailMessage);
    } catch {
      setError('Failed to submit form. Please check your connection and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const renderField = (field: FormField) => {
    const isInvalid = invalidFieldIds.has(field.id);
    const baseInputClass = `w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
      isInvalid ? 'border-red-500 bg-red-50' : 'border-gray-300'
    }`;
    const commonProps = {
      id: field.id,
      required: field.required,
      'aria-required': field.required ? true : undefined,
      'aria-invalid': isInvalid || undefined,
      onChange: (
        e: React.ChangeEvent<
          HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
        >,
      ) => handleInputChange(field.id, e.target.value),
    };

    switch (field.type) {
      case 'text':
      case 'email':
      case 'phone':
        return (
          <input
            type={field.type}
            placeholder={field.placeholder}
            className={baseInputClass}
            {...commonProps}
          />
        );

      case 'number':
        return (
          <input
            type="number"
            placeholder={field.placeholder}
            className={baseInputClass}
            {...commonProps}
          />
        );

      case 'date':
        return <input type="date" className={baseInputClass} {...commonProps} />;

      case 'textarea':
        return (
          <textarea
            rows={4}
            placeholder={field.placeholder}
            className={`${baseInputClass} resize-vertical`}
            {...commonProps}
          />
        );

      case 'select':
        return (
          <select className={baseInputClass} {...commonProps}>
            <option value="">Select an option...</option>
            {field.options.map((option, index) => (
              <option key={index} value={option}>
                {option}
              </option>
            ))}
          </select>
        );

      case 'radio':
        return (
          <div className={`space-y-3 ${isInvalid ? 'rounded-lg border border-red-500 bg-red-50 p-3' : ''}`}>
            {field.options.map((option, index) => (
              <label key={index} className="flex items-center">
                <input
                  type="radio"
                  name={field.id}
                  value={option}
                  onChange={() => handleInputChange(field.id, option)}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300"
                />
                <span className="ml-3 text-gray-700">{option}</span>
              </label>
            ))}
          </div>
        );

      case 'checkbox':
        return (
          <div className={`space-y-3 ${isInvalid ? 'rounded-lg border border-red-500 bg-red-50 p-3' : ''}`}>
            {field.options.map((option, index) => (
              <label key={index} className="flex items-center">
                <input
                  type="checkbox"
                  value={option}
                  onChange={(e) => {
                    const currentValues = responses[field.id] || [];
                    if (e.target.checked) {
                      handleInputChange(field.id, [...currentValues, option]);
                    } else {
                      handleInputChange(
                        field.id,
                        currentValues.filter((v: string) => v !== option),
                      );
                    }
                  }}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <span className="ml-3 text-gray-700">{option}</span>
              </label>
            ))}
          </div>
        );

      case 'rating':
        return (
          <div className={`flex space-x-2 ${isInvalid ? 'rounded-lg border border-red-500 bg-red-50 p-3' : ''}`}>
            {[1, 2, 3, 4, 5].map((rating) => (
              <button
                key={rating}
                type="button"
                onClick={() => handleInputChange(field.id, rating)}
                className={`text-2xl ${
                  responses[field.id] >= rating ? 'text-yellow-400' : 'text-gray-300'
                } hover:text-yellow-400 transition-colors`}
              >
                ★
              </button>
            ))}
            <span className="ml-2 text-sm text-gray-600">
              {responses[field.id]
                ? `${responses[field.id]} star${responses[field.id] !== 1 ? 's' : ''}`
                : 'Click to rate'}
            </span>
          </div>
        );

      case 'file_upload':
        return (
          <FileUploadField
            field={field}
            value={responses[field.id]}
            disabled={!distributionId || !accessToken || linkState !== 'valid'}
            distributionId={distributionId}
            accessToken={accessToken}
            formId={formId}
            onChange={(val) => handleInputChange(field.id, val)}
          />
        );

      case 'scale':
        return (
          <div className={`space-y-3 ${isInvalid ? 'rounded-lg border border-red-500 bg-red-50 p-3' : ''}`}>
            <div className="flex justify-between text-sm text-gray-600">
              <span>1 (Poor)</span>
              <span>10 (Excellent)</span>
            </div>
            <div className="grid grid-cols-10 gap-2">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((rating) => (
                <button
                  key={rating}
                  type="button"
                  onClick={() => handleInputChange(field.id, rating)}
                  className={`h-10 w-10 rounded-lg border ${
                    responses[field.id] === rating
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  } transition-colors`}
                >
                  {rating}
                </button>
              ))}
            </div>
            {responses[field.id] && (
              <p className="text-sm text-gray-600 text-center">
                Selected: {responses[field.id]}/10
              </p>
            )}
          </div>
        );

      default:
        return (
          <input
            type="text"
            placeholder={field.placeholder}
            className={baseInputClass}
            {...commonProps}
          />
        );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading form...</p>
        </div>
      </div>
    );
  }

  if (error && !form) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Unable to Load Form
          </h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Thank You!</h2>
          <p className="text-gray-600">{successMessage}</p>
        </div>
      </div>
    );
  }

  if (linkState === 'already_submitted') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Response Already Submitted
          </h2>
          <p className="text-gray-600">
            We&rsquo;ve already received a response for this link. If you need to
            update your answer, please contact the planner.
          </p>
        </div>
      </div>
    );
  }

  if (linkState === 'expired') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Link Expired</h2>
          <p className="text-gray-600">
            This form link has expired. Please reach out to the planner for a fresh
            link.
          </p>
        </div>
      </div>
    );
  }

  if (linkState === 'rotated') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Link Was Refreshed
          </h2>
          <p className="text-gray-600">
            Your planner sent you a fresh link for this form, so this older one is
            no longer valid. Please open the most recent email link, or contact
            them for a new copy.
          </p>
        </div>
      </div>
    );
  }

  if (linkState === 'invalid') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center bg-white p-8 rounded-lg shadow-sm max-w-md">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Invalid Form Link
          </h2>
          <p className="text-gray-600">
            This form link could not be verified. It may have been mistyped or
            already been used.
          </p>
        </div>
      </div>
    );
  }

  if (!form) return null;

  const sortedFields = [...form.fields]
    .sort((a, b) => a.order - b.order)
    .filter((field) => isFieldVisible(field, responses));

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          {/* Form Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              {form.settings.title}
            </h1>
            {form.settings.description && (
              <p className="text-gray-600 text-lg leading-relaxed">
                {form.settings.description}
              </p>
            )}
          </div>

          {error && (
            <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-600">{error}</p>
            </div>
          )}

          <div className="space-y-6">
            {sortedFields.map((field) => {
              const isInvalid = invalidFieldIds.has(field.id);
              const isFlashing = flashFieldIds.has(field.id);
              return (
                <div
                  key={field.id}
                  ref={(el) => {
                    fieldRefs.current[field.id] = el;
                  }}
                  className={`space-y-2 rounded-md p-2 -m-2 ${
                    isFlashing ? 'animate-flash' : ''
                  }`}
                  data-field-id={field.id}
                  data-field-invalid={isInvalid || undefined}
                >
                  <label
                    htmlFor={field.id}
                    className="block text-sm font-medium text-gray-700"
                  >
                    {field.label}
                    {field.required && (
                      <span
                        className="text-red-500 ml-1"
                        aria-label="required"
                      >
                        *
                      </span>
                    )}
                  </label>
                  {field.description && (
                    <p className="text-sm text-gray-500">{field.description}</p>
                  )}
                  {renderField(field)}
                  {isInvalid && (
                    <p
                      className="text-xs text-red-600"
                      data-testid={`field-error-${field.id}`}
                    >
                      This field is required.
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200">
            <button
              onClick={submitForm}
              disabled={submitting}
              className="w-full bg-indigo-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? 'Submitting...' : form.settings.submit_button_text}
            </button>
          </div>

          <div className="mt-6 text-center text-sm text-gray-500">
            Powered by Special Wedding Platform
          </div>
        </div>
      </div>
    </div>
  );
}
