/**
 * Frontend evaluator for FormField.conditional_logic.
 *
 * Mirrors `app/utils/form_conditional_logic.py` so the planner sees the
 * same hide/show semantic in the renderer and the server-side
 * required-field check.
 *
 * Schema:
 *
 *   { show_when: { all: Condition[] } | { any: Condition[] } }
 *
 * Condition: { field_id: string, operator: Operator, value?: unknown }
 *
 * Operators: equals | not_equals | in | not_in | contains | is_empty | is_not_empty
 *
 * Unknown operators / malformed logic default to "field is visible" so a
 * typo never silently hides a required question.
 */

export type ConditionOperator =
  | 'equals'
  | 'not_equals'
  | 'in'
  | 'not_in'
  | 'contains'
  | 'is_empty'
  | 'is_not_empty';

export interface FieldCondition {
  field_id: string;
  operator: ConditionOperator;
  value?: unknown;
}

export interface ConditionalLogic {
  show_when?:
    | { all: FieldCondition[] }
    | { any: FieldCondition[] };
}

interface FieldLike {
  id: string;
  conditional_logic?: ConditionalLogic | Record<string, unknown> | null;
}

const VALID_OPERATORS: ReadonlySet<string> = new Set([
  'equals',
  'not_equals',
  'in',
  'not_in',
  'contains',
  'is_empty',
  'is_not_empty',
]);

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as object).length === 0;
  return false;
}

function evaluateCondition(
  condition: FieldCondition,
  responses: Record<string, unknown>,
): boolean {
  if (!condition || typeof condition !== 'object') return true;
  const { field_id: fieldId, operator } = condition;
  if (!fieldId || typeof fieldId !== 'string') return true;
  if (!VALID_OPERATORS.has(operator)) return true;

  const actual = responses[fieldId];
  const expected = condition.value;

  switch (operator) {
    case 'equals':
      return actual === expected;
    case 'not_equals':
      return actual !== expected;
    case 'is_empty':
      return isEmpty(actual);
    case 'is_not_empty':
      return !isEmpty(actual);
    case 'in':
      return Array.isArray(expected) && (expected as unknown[]).includes(actual);
    case 'not_in':
      return !(Array.isArray(expected) && (expected as unknown[]).includes(actual));
    case 'contains':
      if (typeof actual === 'string' && typeof expected === 'string') {
        return actual.includes(expected);
      }
      if (Array.isArray(actual)) {
        return (actual as unknown[]).includes(expected);
      }
      return false;
    default:
      return true;
  }
}

export function isFieldVisible(
  field: FieldLike,
  responses: Record<string, unknown>,
): boolean {
  const logic = field?.conditional_logic;
  if (!logic || typeof logic !== 'object') return true;

  const showWhen = (logic as ConditionalLogic).show_when;
  if (!showWhen || typeof showWhen !== 'object') return true;

  if ('all' in showWhen && Array.isArray(showWhen.all) && showWhen.all.length > 0) {
    return showWhen.all.every((c) => evaluateCondition(c, responses));
  }
  if ('any' in showWhen && Array.isArray(showWhen.any) && showWhen.any.length > 0) {
    return showWhen.any.some((c) => evaluateCondition(c, responses));
  }
  return true;
}

export function filterResponsesToVisible<T extends FieldLike>(
  fields: T[],
  responses: Record<string, unknown>,
): Record<string, unknown> {
  const fieldIds = new Set(fields.map((f) => f.id));
  const visibleIds = new Set(
    fields.filter((f) => isFieldVisible(f, responses)).map((f) => f.id),
  );
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(responses)) {
    if (!fieldIds.has(key) || visibleIds.has(key)) {
      out[key] = value;
    }
  }
  return out;
}
