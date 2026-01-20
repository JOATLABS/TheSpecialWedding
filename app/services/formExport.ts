export interface FormResponsesExportOptions {
  dateFrom?: string;
  dateTo?: string;
  includeMetadata?: boolean;
}

export interface FormResponsesExportResult {
  blob: Blob;
  filename: string;
  contentType: string;
}

export interface FetchFormResponsesCsvParams {
  baseUrl: string;
  formId: string;
  token: string;
  options?: FormResponsesExportOptions;
  fetchImpl?: typeof fetch;
}

const DEFAULT_CONTENT_TYPE = 'text/csv;charset=utf-8';

function buildExportUrl(baseUrl: string, formId: string, options: FormResponsesExportOptions = {}): string {
  const normalizedBase = baseUrl.replace(/\/+$/, '');
  const url = new URL(`${normalizedBase}/admin/forms/${formId}/export/csv`);

  if (options.dateFrom) {
    url.searchParams.set('date_from', options.dateFrom);
  }
  if (options.dateTo) {
    url.searchParams.set('date_to', options.dateTo);
  }
  if (options.includeMetadata === false) {
    url.searchParams.set('include_metadata', 'false');
  }

  return url.toString();
}

function extractFilename(contentDisposition: string | null, formId: string): string {
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
    if (filenameMatch && filenameMatch[1]) {
      return filenameMatch[1];
    }
  }

  // Note: regex reordered to avoid Tailwind CSS scanner false positive
  const timestamp = new Date().toISOString().replace(/[T:\-]/g, '').slice(0, 15);
  return `form_${formId}_responses_${timestamp}.csv`;
}

export async function fetchFormResponsesCsv({
  baseUrl,
  formId,
  token,
  options,
  fetchImpl = fetch,
}: FetchFormResponsesCsvParams): Promise<FormResponsesExportResult> {
  if (!formId) {
    throw new Error('A formId is required to export responses.');
  }
  if (!token) {
    throw new Error('An authenticated admin token is required to export responses.');
  }

  const requestUrl = buildExportUrl(baseUrl, formId, options);
  const response = await fetchImpl(requestUrl, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to export responses (status ${response.status}).`);
  }

  const blob = await response.blob();
  const filename = extractFilename(response.headers.get('content-disposition'), formId);
  const contentType = response.headers.get('content-type') || DEFAULT_CONTENT_TYPE;

  return { blob, filename, contentType };
}

export { buildExportUrl, extractFilename };
