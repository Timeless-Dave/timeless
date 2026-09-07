import Lightfall from '@/components/Lightfall';
import { useGpuBudget } from '@/hooks/useGpuBudget';
import { useIsMobile, usePageVisible, useViewportSize } from '@/hooks/useReducedMotion';

/** Full-viewport Lightfall behind the dashboard shell (not boxed inside cards). */
export default function DashboardBackground() {
  const { quiet } = useGpuBudget();
  const mobile = useIsMobile();
  const pageVisible = usePageVisible();
  const { width, height } = useViewportSize();

  // The single most expensive thing on the page: a full-viewport shader that
  // never stops. It yields to the budget, not just to Reduced Motion.
  if (quiet || mobile) return null;

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
