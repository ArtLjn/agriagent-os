import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const words = [
  { text: 'AI', viewBox: '0 0 300 100' },
  { text: 'NATURE', viewBox: '0 0 600 100' },
  { text: 'GROWTH', viewBox: '0 0 500 100' },
];

export default function SVGStrokeSection() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      const svgs = gsap.utils.toArray<SVGElement>('.word-svg');
      svgs.forEach((svg, i) => {
        ScrollTrigger.create({
          trigger: svg,
          start: 'top 80%',
          toggleClass: 'drawn',
          toggleActions: 'play none none none',
          onToggle: () => {
            // Stagger effect - delay based on index
            setTimeout(() => {
              svg.classList.add('drawn');
            }, i * 300);
          },
        });
      });
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={sectionRef}
      className="bg-primary-dark flex items-center justify-center overflow-hidden"
      style={{ minHeight: '60vh', padding: 'clamp(80px, 12vh, 160px) 24px' }}
    >
      <div className="flex flex-col items-center gap-4 sm:gap-6">
        {words.map((word, i) => (
          <svg
            key={word.text}
            className="word-svg"
            viewBox={word.viewBox}
            style={{
              width: 'min(90vw, ' + (i === 0 ? '300' : i === 1 ? '500' : '450') + 'px)',
              height: 'auto',
            }}
          >
            <text
              textAnchor="middle"
              x={i === 0 ? '150' : i === 1 ? '300' : '250'}
              y="80"
              style={{
                fontSize: '90px',
                fontFamily: 'Inter, sans-serif',
                fontWeight: 700,
                fill: 'none',
                stroke: '#BFFF00',
                strokeWidth: '2px',
                strokeLinecap: 'round',
                strokeLinejoin: 'round',
              }}
            >
              {word.text}
            </text>
          </svg>
        ))}
      </div>
    </section>
  );
}
