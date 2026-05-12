export function randFn(random: () => number): number {
  return random();
}

export function randBetweenFn(bottom: unknown, top: unknown, random: () => number): unknown {
  const min = Math.floor(Number(bottom));
  const max = Math.floor(Number(top));
  if (!Number.isFinite(min) || !Number.isFinite(max) || max < min) {
    return '#VALUE!';
  }
  return Math.floor(random() * (max - min + 1)) + min;
}
