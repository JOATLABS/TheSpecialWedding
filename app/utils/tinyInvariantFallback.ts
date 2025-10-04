/**
 * Minimal fallback implementation of `tiny-invariant` so the development
 * server can start even if the package has not been installed yet. The real
 * library is extremely small, so we mirror its behaviour here.
 */
export type Invariant = (condition: unknown, message?: string) => asserts condition;

type InvariantWithExports = Invariant & {
  default?: Invariant;
  invariant?: Invariant;
};

const invariant: InvariantWithExports = ((condition: unknown, message?: string): asserts condition => {
  if (condition) {
    return;
  }

  const prefix = 'Invariant failed';
  const finalMessage = message ? `${prefix}: ${message}` : prefix;
  const error = new Error(finalMessage);
  error.name = 'Invariant Violation';
  throw error;
}) as InvariantWithExports;

Object.assign(invariant, {
  default: invariant,
  invariant,
});

export default invariant;
export { invariant };
