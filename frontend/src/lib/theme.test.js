import { describe, expect, it } from 'vitest';
import { readableAccent } from '@/lib/theme';

function luminance(hex) {
  const raw = hex.replace('#', '');
  const r = parseInt(raw.slice(0, 2), 16);
  const g = parseInt(raw.slice(2, 4), 16);
  const b = parseInt(raw.slice(4, 6), 16);
  const channel = c => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastOnWhite(hex) {
  const fg = luminance(hex);
  const bg = luminance('#ffffff');
  const lighter = Math.max(fg, bg);
  const darker = Math.min(fg, bg);
  return (lighter + 0.05) / (darker + 0.05);
}

describe('readableAccent', () => {
  it('preserves the chosen accent while darkening readable variants when needed', () => {
    const tones = readableAccent([208, 135, 38]);
    expect(tones.accent).toBe('#d08726');
    expect(contrastOnWhite(tones.readable)).toBeGreaterThanOrEqual(3);
    expect(contrastOnWhite(tones.focus)).toBeGreaterThanOrEqual(3);
  });

  it('keeps white accents decorative but makes focus and small text legible', () => {
    const tones = readableAccent([255, 255, 255]);
    expect(tones.accent).toBe('#ffffff');
    expect(contrastOnWhite(tones.readable)).toBeGreaterThanOrEqual(3);
    expect(contrastOnWhite(tones.focus)).toBeGreaterThanOrEqual(3);
  });
});
