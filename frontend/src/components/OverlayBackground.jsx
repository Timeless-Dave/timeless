import Lightfall from '@/components/Lightfall';
import { useIsMobile, usePageVisible, useReducedMotion, useViewportSize } from '@/hooks/useReducedMotion';

/** Ambient background for gate, recap, and other overlay routes. */
export default function OverlayBackground({ variant = 'warm' }) {
  const reduce = useReducedMotion();
  const mobile = useIsMobile();
  const pageVisible = usePageVisible();
  const { width, height } = useViewportSize();

  if (reduce || mobile) return null;

  const palettes = {
    warm: {
      colors: ['#f8debd', '#d08726', '#fbf0f3'],
      backgroundColor: '#14161a',
    },
    recap: {
      colors: ['#d0fbff', '#7294c2', '#f8debd'],
      backgroundColor: '#120f17',
    },
  };
  const palette = palettes[variant] || palettes.warm;
  const sizeKey = `${Math.round(width / 50)}-${Math.round(height / 50)}`;

  return (
    <div className="overlay-bg overlay-bg--full" aria-hidden="true">
      <Lightfall
        key={sizeKey}
        dpr={typeof window !== 'undefined' ? Math.min(window.devicePixelRatio || 1, 1.5) : 1}
        paused={!pageVisible}
        colors={palette.colors}
        backgroundColor={palette.backgroundColor}
        speed={0.32}
        streakCount={4}
        mouseInteraction={false}
        opacity={0.94}
      />
    </div>
  );
}
