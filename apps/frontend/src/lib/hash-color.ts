export function hashToHue(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % 360;
}

export function hashColor(value: string): string {
  const hue = hashToHue(value);
  return `hsl(${hue} 70% 42%)`;
}

export function hashColorDim(value: string): string {
  const hue = hashToHue(value);
  return `hsl(${hue} 60% 18%)`;
}
