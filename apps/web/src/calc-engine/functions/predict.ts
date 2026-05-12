export type PredictResolver = (featureValues: unknown[]) => unknown;

export function buildPredictKey(workflowId: string, featureValues: unknown[]): string {
  return `${workflowId}::${JSON.stringify(featureValues)}`;
}

export function predictFn(
  workflowId: string | null,
  args: unknown[],
  cache: Map<string, unknown>,
  resolver?: PredictResolver,
): unknown {
  if (!workflowId) {
    return '#PREDICT_ERR';
  }
  const key = buildPredictKey(workflowId, args);
  if (cache.has(key)) {
    return cache.get(key);
  }
  if (!resolver) {
    return '#PENDING';
  }
  const value = resolver(args);
  cache.set(key, value);
  return value;
}
