export const standardIconSizes = [16, 24, 32, 48, 64, 128, 256];

export function parseIconSizes(value: string): number[] | null {
  if (value.length > 2048 || !/^\s*[0-9]{1,3}\s*(,\s*[0-9]{1,3}\s*)*$/.test(value)) return null;
  const sizes = [...new Set(value.split(",").map(Number))].sort((a, b) => a - b);
  return sizes.every((size) => size >= 1 && size <= 256) ? sizes : null;
}
