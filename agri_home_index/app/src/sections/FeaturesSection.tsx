import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import {
  Sparkles,
  Sprout,
  TrendingUp,
  MessageCircle,
  CloudSun,
  Smartphone,
} from 'lucide-react';

gsap.registerPlugin(ScrollTrigger);

const features = [
  {
    icon: Sparkles,
    title: 'AI 智能记账',
    desc: '用自然语言输入经营记录，AI 自动解析为结构化账务。"今天买了 50 斤化肥 300 块" → 自动生成支出条目。',
    image: '/feature-ai-ledger.jpg',
  },
  {
    icon: Sprout,
    title: '种植周期管理',
    desc: '创建作物模板，管理种植周期，追踪每块田的播种、施肥、灌溉、收获全流程。',
    image: '/feature-crop-cycle.jpg',
  },
  {
    icon: TrendingUp,
    title: '成本利润分析',
    desc: '实时统计收入、支出、人工成本、物资成本，查看周期利润和年度汇总报表。',
    image: '/feature-finance.jpg',
  },
  {
    icon: MessageCircle,
    title: '芽芽 AI 助手',
    desc: '随时向 AI 农场助手"芽芽"提问，获取种植建议、病虫害诊断、市场行情分析。',
    image: '/feature-yaya-ai.jpg',
  },
  {
    icon: CloudSun,
    title: '天气与农事计划',
    desc: '集成多日天气预报，结合农事日历智能推荐最佳作业时间，提前规避天气风险。',
    image: '/feature-weather-plan.jpg',
  },
  {
    icon: Smartphone,
    title: '移动端随时管理',
    desc: '手机 App 随时记录农事、查看账单、与芽芽对话。田间地头和办公室一样高效。',
    image: '/feature-mobile-workbench.jpg',
  },
];

export default function FeaturesSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const cardsRef = useRef<HTMLDivElement[]>([]);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      gsap.from('.features-title', {
        y: 30,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 80%',
        },
      });

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
      id="features"
      ref={sectionRef}
      className="section-padding bg-[#013A33]"
    >
      <div className="container-main">
        {/* Header */}
        <div className="features-title text-center mb-16">
          <p className="text-white/60 text-xs font-medium uppercase tracking-[0.1em] mb-4">
            核心功能
          </p>
          <h2
            className="text-white font-semibold tracking-[-0.01em] mb-4"
            style={{ fontSize: 'clamp(1.75rem, 4vw, 3.5rem)', lineHeight: 1.15, wordBreak: 'keep-all' }}
          >
            AI 赋能，农场经营更智能
          </h2>
          <p className="text-white/60 text-base max-w-[520px] mx-auto leading-relaxed" style={{ wordBreak: 'keep-all' }}>
            从种植到销售，从记账到决策，田掌柜覆盖农场经营的每个环节。
          </p>
        </div>

        {/* Feature Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                ref={(el) => { if (el) cardsRef.current[i] = el; }}
                className="group bg-[#0d2e28] border border-[#1a4540] rounded-card p-8 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg overflow-hidden flex flex-col"
              >
                <div className="w-12 h-12 rounded-xl bg-primary-dark flex items-center justify-center mb-6">
                  <Icon size={24} className="text-accent-lime" />
                </div>
                <h3
                  className="text-white font-semibold tracking-[-0.01em] mb-3"
                  style={{ fontSize: 'clamp(1.25rem, 2vw, 1.75rem)', lineHeight: 1.2, wordBreak: 'keep-all' }}
                >
                  {feature.title}
                </h3>
                <p className="text-white/60 text-sm leading-relaxed mb-6">
                  {feature.desc}
                </p>
                {/* Feature screenshot image */}
                <div className="mt-auto overflow-hidden rounded-xl">
                  <img
                    src={feature.image}
                    alt={feature.title}
                    className="w-full object-cover transition-transform duration-300 group-hover:scale-105 opacity-90"
                    style={{ height: '160px', borderRadius: '12px' }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
