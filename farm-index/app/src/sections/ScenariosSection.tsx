import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { Tractor, ClipboardList, BarChart3, Brain } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const scenarios = [
  {
    icon: Tractor,
    iconColor: '#BFFF00',
    iconBgColor: '#013A33',
    title: '农场主',
    desc: '全方位掌控农场运营，实时查看成本利润、作物生长状态和天气变化，做出更明智的经营决策。',
    image: '/feature-finance.jpg',
  },
  {
    icon: ClipboardList,
    iconColor: '#22AED1',
    iconBgColor: '#0d2e28',
    title: '田间作业人员',
    desc: '在田间地头用手机快速记录农事活动，拍照上传作物状况，随时查看当天的作业安排。',
    image: '/feature-mobile-workbench.jpg',
  },
  {
    icon: BarChart3,
    iconColor: '#FFD15C',
    iconBgColor: '#0d2e28',
    title: '合作社管理者',
    desc: '管理多个农场的经营数据，生成汇总报表，统筹物资采购和人员调度，提升整体运营效率。',
    image: '/feature-crop-cycle.jpg',
  },
  {
    icon: Brain,
    iconColor: '#345E58',
    iconBgColor: '#0d2e28',
    title: 'AI 辅助决策',
    desc: '通过芽芽 AI 助手获取种植建议、病虫害诊断、市场行情分析，让数据驱动的决策替代经验猜测。',
    image: '/feature-yaya-ai.jpg',
  },
];

export default function ScenariosSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement[]>([]);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      // Title animation
      gsap.from('.scenarios-title', {
        y: 30,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 80%',
        },
      });

      // Cards stagger animation
      cardsRef.current.forEach((card, i) => {
        if (!card) return;
        gsap.from(card, {
          y: 40,
          opacity: 0,
          duration: 0.6,
          delay: i * 0.1,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: card,
            start: 'top 85%',
          },
        });
      });
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section
      id="scenarios"
      ref={sectionRef}
      className="section-padding bg-[#013A33]"
    >
      <div className="container-main">
        {/* Header */}
        <div className="scenarios-title text-center mb-16">
          <p className="text-white/60 text-xs font-medium uppercase tracking-[0.1em] mb-4">
            适用场景
          </p>
          <h2
            className="text-white font-semibold tracking-[-0.01em] mb-4"
            style={{ fontSize: 'clamp(1.75rem, 4vw, 3.5rem)', lineHeight: 1.15, wordBreak: 'keep-all' }}
          >
            谁在使用 田掌柜
          </h2>
          <p className="text-white/60 text-base max-w-[520px] mx-auto leading-relaxed" style={{ wordBreak: 'keep-all' }}>
            从个体农户到大型合作社，田掌柜适配多种经营场景
          </p>
        </div>

        {/* Scenario Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {scenarios.map((scenario, i) => {
            const Icon = scenario.icon;
            return (
              <div
                key={scenario.title}
                ref={(el) => { if (el) cardsRef.current[i] = el; }}
                className="group bg-[#0d2e28] border border-[#1a4540] rounded-card p-8 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg overflow-hidden"
              >
                <div className="flex flex-col h-full">
                  {/* Top row: Icon + Title + Description */}
                  <div className="flex items-start gap-5 mb-6">
                    {/* Icon circle */}
                    <div
                      className="w-14 h-14 rounded-2xl flex items-center justify-center shrink-0"
                      style={{ backgroundColor: scenario.iconBgColor }}
                    >
                      <Icon size={28} style={{ color: scenario.iconColor }} />
                    </div>
                    {/* Text content */}
                    <div className="flex-1 min-w-0">
                      <h3
                        className="text-white font-semibold tracking-[-0.01em] mb-2"
                        style={{ fontSize: 'clamp(1.25rem, 2vw, 1.5rem)', lineHeight: 1.2, wordBreak: 'keep-all' }}
                      >
                        {scenario.title}
                      </h3>
                      <p className="text-white/60 text-sm leading-relaxed">
                        {scenario.desc}
                      </p>
                    </div>
                  </div>

                  {/* Image */}
                  <div className="mt-auto overflow-hidden rounded-xl">
                    <img
                      src={scenario.image}
                      alt={scenario.title}
                      className="w-full object-cover transition-transform duration-300 group-hover:scale-105 opacity-90"
                      style={{ maxHeight: '180px', borderRadius: '12px' }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
