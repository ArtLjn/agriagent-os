import { useState, useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { motion, AnimatePresence } from 'framer-motion';

gsap.registerPlugin(ScrollTrigger);

const faqs = [
  {
    q: '田掌柜适合谁使用？',
    a: '农场主、农业经营者、合作社、种植管理人员。无论你管理几亩地还是几千亩，田掌柜都能帮你数字化管理农场经营。',
  },
  {
    q: '是否支持手机端？',
    a: '支持。田掌柜提供 Android 版 App，iOS 版正在开发中。你可以随时在手机上记录农事、查看账单、咨询芽芽助手。',
  },
  {
    q: '下载后如何安装？',
    a: 'Android 用户下载 APK 文件后，在文件管理器中点击安装即可。如果系统提示"未知来源"，请在设置中允许安装未知来源应用。',
  },
  {
    q: '是否需要联网？',
    a: '基础功能支持离线使用，数据会在联网后自动同步。AI 助手和天气功能需要网络连接。',
  },
  {
    q: '数据是否安全？',
    a: '你的数据存储在加密的服务器上，采用行业标准的 TLS 加密传输。我们承诺不会将农场数据用于任何商业目的或分享给第三方。',
  },
  {
    q: 'AI 助手能做什么？',
    a: '芽芽可以帮你：用自然语言记账、回答农业技术问题、分析经营数据生成报告、根据天气推荐农事安排、诊断作物病虫害。',
  },
];

function FAQItem({ item }: { item: typeof faqs[0] }) {
  const [open, setOpen] = useState(false);
  const answerRef = useRef<HTMLDivElement>(null);

  return (
    <div
      className="faq-item transition-all duration-300"
      style={{
        borderBottom: '1px solid #1a4540',
        borderLeft: open ? '3px solid #BFFF00' : '3px solid transparent',
        paddingLeft: open ? '13px' : '16px',
        marginLeft: open ? '0' : '0',
        backgroundColor: open ? 'rgba(191, 255, 0, 0.05)' : 'transparent',
        borderRadius: '0 4px 4px 0',
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between py-6 text-left group"
      >
        <h3
          className="text-white font-semibold pr-4 transition-transform duration-300 ease-out group-hover:translate-x-1"
          style={{ fontSize: 'clamp(1rem, 1.5vw, 1.25rem)' }}
        >
          {item.q}
        </h3>
        <svg
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
          className="shrink-0 text-white transition-transform duration-300 ease-in-out"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        >
          <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            ref={answerRef}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              height: { duration: 0.35, ease: [0.4, 0, 0.2, 1] },
              opacity: { duration: 0.25, ease: 'easeInOut' },
            }}
            className="overflow-hidden"
          >
            <div className="flex gap-4 pb-6">
              {/* Subtle vertical line */}
              <div
                className="shrink-0 w-px mt-1"
                style={{
                  background: 'linear-gradient(to bottom, #BFFF00, rgba(191,255,0,0.1))',
                  marginLeft: '4px',
                }}
              />
              <motion.p
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.25, delay: 0.1 }}
                className="text-white/60 text-sm leading-relaxed pr-8"
              >
                {item.a}
              </motion.p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function FAQSection() {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      gsap.from('.faq-title', {
        y: 30,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 80%',
        },
      });

      gsap.utils.toArray<HTMLElement>('.faq-item').forEach((item, i) => {
        gsap.from(item, {
          y: 20,
          opacity: 0,
          duration: 0.5,
          delay: i * 0.08,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: item,
            start: 'top 90%',
          },
        });
      });
    }, section);

    return () => ctx.revert();
  }, []);

  return (
    <section
      id="faq"
      ref={sectionRef}
      className="section-padding bg-[#013A33]"
    >
      <div className="container-main">
        {/* Header */}
        <div className="faq-title text-center mb-12">
          <p className="text-white/60 text-xs font-medium uppercase tracking-[0.1em] mb-4">
            常见问题
          </p>
          <h2
            className="text-white font-semibold tracking-[-0.01em] mb-4"
            style={{ fontSize: 'clamp(1.75rem, 4vw, 3.5rem)', lineHeight: 1.15, wordBreak: 'keep-all' }}
          >
            有疑问？我们来解答
          </h2>
        </div>

        {/* Accordion */}
        <div className="max-w-[800px] mx-auto">
          {faqs.map((faq) => (
            <FAQItem key={faq.q} item={faq} />
          ))}
        </div>
      </div>
    </section>
  );
}
