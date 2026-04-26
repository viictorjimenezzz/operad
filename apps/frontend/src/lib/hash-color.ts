export function hashToHue(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % 360;
}

export function hashToColor(value: string, alpha = 0.25): string {
  const hue = hashToHue(value);
  return `hsla(${hue}, 72%, 55%, ${alpha})`;
}
