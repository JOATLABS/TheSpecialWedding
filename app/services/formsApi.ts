export interface BlankFormPayload {
  name: string;
  description?: string;
  isPublic: boolean;
  collectEmail: boolean;
}

export interface DuplicateFormPayload {
  formId: string;
  name: string;
}

export interface FormSummaryResponse {
  id: string;
  name: string;
  settings: {
    title: string;
    description?: string;
    is_public: boolean;
  };
  template_type?: string;
  wedding_id?: string;
  submission_count?: number;
  unread_responses?: number;
  created_at?: string;
}

export interface FormTemplateResponse {
  id: string;
  name: string;
  description: string;
  category: string;
}

interface RequestOptions {
  token: string;
  init?: RequestInit;
}

const FALLBACK_BASE_URL = 'http://localhost:8000';

function normaliseHeaders(headers: HeadersInit = {}): Record<string, string> {
  if (headers instanceof Headers) {
    const result: Record<string, string> = {};
    headers.forEach((value, key) => {
      result[key] = value;
    });
    return result;
  }

  return Array.isArray(headers)
    ? headers.reduce<Record<string, string>>((accumulator, [key, value]) => {
        accumulator[key] = value;
        return accumulator;
      }, {})
    : { ...headers };
}

async function authorisedFetch(path: string, { token, init }: RequestOptions) {
  const headers = normaliseHeaders(init?.headers);
  headers.Authorization = `Bearer ${token}`;
  headers['Content-Type'] = headers['Content-Type'] ?? 'application/json';

  const response = await fetch(`${formsApi.resolveBaseUrl()}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request to ${path} failed`);
  }

  return response;
}

export const formsApi = {
  resolveBaseUrl(): string {
    return process.env.NEXT_PUBLIC_API_BASE_URL || FALLBACK_BASE_URL;
  },

  async fetchForms(token: string): Promise<FormSummaryResponse[]> {
    const response = await authorisedFetch('/admin/forms', { token });
    const data = await response.json();

    if (!Array.isArray(data)) {
      throw new Error('Unexpected response while loading forms');
    }

    return data.map((form) => {
      const settings = form.settings ?? {};

      return {
        id: form.id,
        name: form.name,
        settings: {
          title: typeof settings.title === 'string' ? settings.title : form.name,
          description: typeof settings.description === 'string' ? settings.description : undefined,
          is_public: Boolean(settings.is_public),
        },
        template_type: form.template_type ?? undefined,
        wedding_id: form.wedding_id ?? undefined,
        submission_count: typeof form.submission_count === 'number' ? form.submission_count : 0,
        unread_responses: typeof form.unread_responses === 'number' ? form.unread_responses : 0,
        created_at: form.created_at ?? new Date().toISOString(),
      };
    });
  },

  async fetchTemplates(token: string): Promise<FormTemplateResponse[]> {
    const response = await authorisedFetch('/admin/form-templates', { token });
    const data = await response.json();

    if (!data || !Array.isArray(data.templates)) {
      return [];
    }

    return data.templates.map((template: FormTemplateResponse) => ({
      id: template.id,
      name: template.name,
      description: template.description,
      category: template.category,
    }));
  },

  async createBlankForm(token: string, payload: BlankFormPayload) {
    const response = await authorisedFetch('/admin/forms', {
      token,
      init: {
        method: 'POST',
        body: JSON.stringify({
          name: payload.name,
          settings: {
            title: payload.name,
            description: payload.description,
            submit_button_text: 'Submit',
            success_message: 'Thank you for your response!',
            allow_multiple_submissions: false,
            collect_email: payload.collectEmail,
            is_public: payload.isPublic,
            requires_auth: false,
          },
          fields: [],
        }),
      },
    });

    return response.json();
  },

  async createFromTemplate(
    token: string,
    payload: { templateId: string; name: string; weddingId?: string },
  ) {
    const query = new URLSearchParams({ form_name: payload.name });
    if (payload.weddingId) {
      query.set('wedding_id', payload.weddingId);
    }

    const response = await authorisedFetch(`/admin/forms/from-template/${payload.templateId}?${query.toString()}`, {
      token,
      init: {
        method: 'POST',
      },
    });

    return response.json();
  },

  async duplicateForm(token: string, payload: DuplicateFormPayload) {
    const response = await authorisedFetch(`/admin/forms/${payload.formId}/duplicate`, {
      token,
      init: {
        method: 'POST',
        body: JSON.stringify({ new_name: payload.name }),
      },
    });

    return response.json();
  },

  async markScopeViewed(
    token: string,
    formId: string,
    scope: 'responses' | 'analytics',
    submissionCount?: number,
  ) {
    const response = await authorisedFetch(`/admin/forms/${formId}/views`, {
      token,
      init: {
        method: 'POST',
        body: JSON.stringify({
          scope,
          submission_count: typeof submissionCount === 'number' ? submissionCount : undefined,
        }),
      },
    });

    return response.json();
  },
};
