import Lightfall from '@/components/Lightfall';
import { useIsMobile, usePageVisible, useReducedMotion, useViewportSize } from '@/hooks/useReducedMotion';

/** Full-viewport Lightfall behind the dashboard shell (not boxed inside cards). */
export default function DashboardBackground() {
  const reduce = useReducedMotion();
  const mobile = useIsMobile();
  const pageVisible = usePageVisible();
  const { width, height } = useViewportSize();

  if (reduce || mobile) return null;

  const sizeKey = `${Math.round(width / 50)}-${Math.round(height / 50)}`;

  return (
    <div className="app-shell__bg" aria-hidden="true">
      <Lightfall
        key={sizeKey}
        dpr={typeof window !== 'undefined' ? Math.min(window.devicePixelRatio || 1, 1.5) : 1}
        paused={!pageVisible}
        colors={['#f8debd', '#d08726', '#fbf0f3']}
        backgroundColor="#14161a"
        speed={0.35}
        streakCount={3}
        mouseInteraction
        opacity={0.92}
      />
    </div>
  );
}
