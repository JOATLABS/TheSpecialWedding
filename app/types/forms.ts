// Shared form-related TypeScript types
export type FormFieldType =
  | 'text'
  | 'email'
  | 'phone'
  | 'number'
  | 'date'
  | 'textarea'
  | 'select'
  | 'radio'
  | 'checkbox'
  | 'rating'
  | 'scale';

export type FormResponseValue = string | number | string[] | null;

export interface FormField {
  id: string;
  label: string;
  type: FormFieldType;
  placeholder?: string;
  required: boolean;
  description?: string;
  options?: string[];
  order: number;
}

export interface FormSettingsBase {
  title: string;
  description?: string;
  submit_button_text: string;
  success_message: string;
}

export interface PublicFormSettings extends FormSettingsBase {
  collect_email: boolean;
}

export interface FormPreviewSettings extends FormSettingsBase {
  is_public: boolean;
}

export interface PublicForm {
  id: string;
  settings: PublicFormSettings;
  fields: FormField[];
  is_active: boolean;
}

export interface PreviewForm {
  id: string;
  name: string;
  settings: FormPreviewSettings;
  fields: FormField[];
  is_active: boolean;
}