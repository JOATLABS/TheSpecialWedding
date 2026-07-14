/** Accept an owner-scoped billing-plan response only for the expected plan. */
export function normalizeOwnedPlanForBilling<T extends { id: string }>(
  plan: T,
  expectedPlanId: string,
): (T & { _id: string }) | null {
  if (plan.id !== expectedPlanId) {
    return null;
  }
  return { ...plan, _id: plan.id };
}
