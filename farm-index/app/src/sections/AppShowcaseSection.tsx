import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const showcases = [
  { src: '/feature-mobile-workbench.jpg', alt: '移动工作台', label: '移动工作台' },
  { src: '/feature-crop-cycle.jpg', alt: '作物管理', label: '种植周期' },
  { src: '/feature-finance.jpg', alt: '账单财务', label: '成本利润' },
  { src: '/feature-yaya-ai.jpg', alt: '芽芽助手', label: '芽芽助手' },
];

export default function AppShowcaseSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      gsap.from('.showcase-title', {
        y: 30,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 80%',
        },
      });

      gsap.utils.toArray<HTMLElement>('.showcase-card').forEach((card, i) => {
        gsap.from(card, {
          y: 48,
          opacity: 0,
          duration: 0.7,
          delay: i * 0.08,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: card,
            start: 'top 85%',
          },
        });
      });
    });

    return () => ctx.revert();
  }, []);

  return (
    <section
      id="showcase"
      ref={sectionRef}
      className="section-padding bg-[#013A33] overflow-hidden"
    >
      <div className="container-main">
        {/* Header */}
        <div className="showcase-title text-center mb-16">
          <p className="text-white/60 text-xs font-medium uppercase tracking-[0.1em] mb-4">
            产品预览
          </p>
          <h2
            className="text-white font-semibold tracking-[-0.01em] mb-4"
            style={{ fontSize: 'clamp(1.75rem, 4vw, 3.5rem)', lineHeight: 1.15, wordBreak: 'keep-all' }}
          >
            手机在手，农场尽在掌控
          </h2>
          <p className="text-white/60 text-base max-w-[520px] mx-auto leading-relaxed" style={{ wordBreak: 'keep-all' }}>
            田掌柜移动端 App，让你随时随地管理农场。记录农事、查看账单、咨询芽芽，一切尽在指尖。
          </p>
        </div>

        {/* Product Posters */}
        <div
          ref={containerRef}
          className="grid grid-cols-1 gap-6 md:grid-cols-2"
        >
          {showcases.map((showcase) => (
            <div
              key={showcase.alt}
              className="showcase-card group overflow-hidden rounded-card border border-[#1a4540] bg-[#0d2e28]"
            >
              <div className="relative aspect-[16/10] overflow-hidden">
                <img
                  src={showcase.src}
                  alt={showcase.alt}
                  className="h-full w-full object-cover opacity-90 transition-transform duration-500 group-hover:scale-[1.04]"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#013A33]/80 via-transparent to-transparent" />
                <span className="absolute bottom-5 left-5 rounded-full bg-[#BFFF00] px-4 py-1.5 text-xs font-semibold text-[#013A33]">
                  {showcase.label}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
