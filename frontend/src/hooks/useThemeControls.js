import { useEffect, useState } from 'react';
import { loadTheme } from '@/lib/theme';

export function useThemeControls() {
  const [rgb, setRgb] = useState(() => loadTheme());

  const setChannel = (index, value) => {
    setRgb(prev => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  };

  useEffect(() => {
    import('@/lib/theme').then(({ saveTheme }) => saveTheme(rgb));
  }, [rgb]);

  const reset = () => {
    import('@/lib/theme').then(({ resetTheme }) => setRgb(resetTheme()));
  };

  const hex =
    '#' +
    rgb.map(n => Number(n).toString(16).padStart(2, '0')).join('');

  return { rgb, setChannel, reset, hex };
}
