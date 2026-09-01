import GlassIcons from '@/components/GlassIcons';

/** Wrapper so jumper icons can scroll without editing generated GlassIcons. */
export default function GlassJumper({ items, className }) {
  return (
    <div className={`glass-jumper-wrap${className ? ` ${className}` : ''}`}>
      {items.map((item, index) => (
        <div key={item.label || index} className="glass-jumper-item">
          <GlassIcons items={[item]} />
          {item.label ? <span className="glass-jumper-caption">{item.label}</span> : null}
          {item.onClick ? (
            <button type="button" className="glass-jumper-hit" aria-label={item.label} onClick={item.onClick} />
          ) : null}
        </div>
      ))}
    </div>
  );
}
