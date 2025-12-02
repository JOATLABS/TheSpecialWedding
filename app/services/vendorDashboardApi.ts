export type VendorDashboardResponse = {
  profile: {
    email: string;
    wedding_count: number;
    services: string[];
  };
  stats: {
    total_tasks: number;
    completed_tasks: number;
    open_tasks: number;
    pending_forms: number;
    completed_forms: number;
  };
  weddings: Array<{
    id: string;
    name: string;
    date?: string | null;
    status: string;
    location?: string | null;
    tasks_total: number;
    tasks_completed: number;
  }>;
  tasks: Array<{
    id: string;
    wedding_id: string;
    wedding_name: string;
    category: string;
    task: string;
    status: 'pending' | 'in_progress' | 'completed';
    due_date?: string | null;
    notes?: string | null;
    updated_at?: string | null;
  }>;
  forms: {
    pending: Array<{
      id: string;
      form_name: string;
      status: string;
      vendor_type: string;
      sent_at?: string | null;
      submitted_at?: string | null;
      wedding_id: string;
      wedding_name: string;
      fields_count: number;
      access_token?: string | null;
      latest_submission_id?: string | null;
    }>;
    completed: Array<{
      id: string;
      form_name: string;
      status: string;
      vendor_type: string;
      sent_at?: string | null;
      submitted_at?: string | null;
      wedding_id: string;
      wedding_name: string;
      fields_count: number;
      access_token?: string | null;
      latest_submission_id?: string | null;
    }>;
  };
};

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function fetchVendorDashboard(token: string): Promise<VendorDashboardResponse> {
  const response = await fetch(`${BASE_URL}/vendor/dashboard`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || 'Failed to load vendor dashboard');
  }

  return response.json() as Promise<VendorDashboardResponse>;
}

export async function updateVendorTaskStatus(
  token: string,
  taskId: string,
  status: 'pending' | 'in_progress' | 'completed',
): Promise<VendorDashboardResponse['tasks'][number]> {
  const url = new URL(`${BASE_URL}/vendor/tasks/${taskId}`);
  url.searchParams.set('status', status);

  const response = await fetch(url.toString(), {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = payload?.detail || 'Failed to update task status';
    throw new Error(message);
  }

  return response.json();
}
