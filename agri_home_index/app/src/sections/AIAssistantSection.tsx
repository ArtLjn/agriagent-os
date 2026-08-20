import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const capabilities = [
  '自然语言记账 — 说一句话，记一笔账',
  '智能问答 — 作物病虫害、施肥时机、市场行情',
  '数据分析 — 自动生成经营洞察和趋势报告',
  '农事提醒 — 基于天气和作物周期的智能提醒',
];

export default function AIAssistantSection() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      const isMobile = window.matchMedia('(max-width: 767px)').matches;

      gsap.from('.ai-text-content', {
        x: isMobile ? 0 : -40,
        y: isMobile ? 32 : 0,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 75%',
        },
      });

      gsap.from('.ai-phone-mockup', {
        x: isMobile ? 0 : 40,
        y: isMobile ? 32 : 0,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 75%',
        },
      });
    }, section);

    return () => ctx.revert();
  }, []);

  const scrollToDownload = () => {
    const el = document.querySelector('#download');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section
      id="ai-assistant"
      ref={sectionRef}
      className="section-padding bg-primary-dark"
      style={{ paddingTop: 'clamp(100px, 12vh, 160px)', paddingBottom: 'clamp(80px, 10vh, 140px)' }}
    >
      <div className="container-main">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Left Column - Text */}
          <div className="ai-text-content">
            <p className="text-accent-lime text-xs font-medium uppercase tracking-[0.1em] mb-4">
              AI 助手
            </p>
            <h2
              className="text-white font-semibold tracking-[-0.01em] mb-6 max-w-[600px]"
              style={{ fontSize: 'clamp(1.75rem, 4vw, 3.5rem)', lineHeight: 1.15, wordBreak: 'keep-all', overflowWrap: 'break-word' }}
            >
              认识芽芽，你的智能农场顾问
            </h2>
            <p className="text-white/70 text-base leading-relaxed mb-8 max-w-[520px]" style={{ wordBreak: 'keep-all' }}>
              芽芽是田掌柜内置的 AI 助手，能回答农场经营问题、辅助查询数据、生成种植建议。就像身边有一位 24 小时在线的农业专家。
            </p>

            {/* Capabilities */}
            <div className="flex flex-col gap-4 mb-10">
              {capabilities.map((cap) => (
                <div key={cap} className="flex items-start gap-3">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="mt-0.5 shrink-0">
                    <path d="M10 0C4.48 0 0 4.48 0 10s4.48 10 10 10 10-4.48 10-10S15.52 0 10 0zm-2 15l-5-5 1.41-1.41L8 12.17l7.59-7.59L17 6l-9 9z" fill="#BFFF00"/>
                  </svg>
                  <span className="text-white/80 text-sm">{cap}</span>
                </div>
              ))}
            </div>

            <button
              onClick={scrollToDownload}
              className="px-8 py-4 bg-accent-lime text-primary-dark font-semibold text-base rounded-pill hover:scale-[1.03] hover:brightness-105 transition-all duration-200"
            >
              体验芽芽
            </button>
          </div>

          {/* Right Column - Phone Mockup */}
          <div className="ai-phone-mockup flex items-center justify-center">
            <div
              className="relative"
              style={{
                width: '280px',
                animation: 'floatY 4s ease-in-out infinite',
              }}
            >
              <img
                src="/feature-yaya-ai.jpg"
                alt="芽芽 AI 助手界面"
                className="w-full h-auto rounded-[36px] shadow-2xl"
                style={{ boxShadow: '0 24px 80px rgba(1, 58, 51, 0.4)' }}
              />
              <div
                className="absolute -inset-8 hidden rounded-full opacity-20 blur-3xl pointer-events-none md:block"
                style={{ background: 'radial-gradient(circle, #BFFF00, transparent 70%)' }}
              />
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes floatY {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
      `}</style>
    </section>
  );
}
