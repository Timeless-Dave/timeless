import ClickSpark from '@/components/ClickSpark';
import { useReducedMotion } from '@/hooks/useReducedMotion';

export default function EffectsShell({ children, sparkColor }) {
  const reduce = useReducedMotion();

  const inner = <div className="effects-shell__content">{children}</div>;

  if (reduce) return inner;

  const color = sparkColor || 'var(--accent)';

  return (
    <ClickSpark sparkColor={color} sparkCount={7} sparkSize={12} sparkRadius={22} duration={380} extraScale={1.1}>
      {inner}
    </ClickSpark>
  );
}
