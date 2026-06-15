import { useState, useEffect } from 'react';
import { Heart, ArrowUp } from 'lucide-react';

const footerLinks = {
  product: [
    { label: '核心功能', href: '#features' },
    { label: '芽芽 AI 助手', href: '#ai-assistant' },
    { label: '下载中心', href: '#download' },
    { label: '更新日志', href: '#changelog' },
  ],
  support: [
    { label: '使用帮助', href: '#help' },
    { label: '隐私政策', href: '#privacy' },
    { label: '服务条款', href: '#terms' },
    { label: '联系我们', href: '#contact' },
  ],
};

export default function Footer() {
  const [showBackToTop, setShowBackToTop] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setShowBackToTop(window.scrollY > 600);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (href.startsWith('#')) {
      e.preventDefault();
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer
      className="bg-primary-dark text-white relative"
      style={{ paddingTop: '80px', paddingBottom: '40px' }}
    >
      {/* Top border / gradient fade from section above */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background: 'linear-gradient(to right, transparent, rgba(255,255,255,0.1) 20%, rgba(255,255,255,0.1) 80%, transparent)',
        }}
      />

      <div className="container-main">
        {/* Top Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8">
          {/* Brand */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <img
                src="/app-logo.png"
                alt=""
                className="h-10 w-10 rounded-xl"
              />
              <span className="text-lg font-semibold">田掌柜</span>
            </div>
            <p className="text-white/60 text-sm">AI 驱动的智慧农场经营管理平台</p>
            <p className="text-white/40 text-xs mt-2">&copy; 2026 田掌柜. All rights reserved.</p>
          </div>

          {/* Product Links */}
          <div className="flex flex-col gap-4">
            <h4 className="text-white/40 text-xs uppercase tracking-wider font-medium">产品</h4>
            <div className="flex flex-col gap-3">
              {footerLinks.product.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={(e) => handleClick(e, link.href)}
                  className="group relative text-white/70 hover:text-[#BFFF00] text-sm transition-all duration-300 inline-flex items-center hover:translate-x-1"
                >
                  <span className="relative">
                    {link.label}
                    <span className="absolute left-0 -bottom-0.5 w-0 h-px bg-[#BFFF00] transition-all duration-300 group-hover:w-full" />
                  </span>
                </a>
              ))}
            </div>
          </div>

          {/* Support Links */}
          <div className="flex flex-col gap-4">
            <h4 className="text-white/40 text-xs uppercase tracking-wider font-medium">支持</h4>
            <div className="flex flex-col gap-3">
              {footerLinks.support.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={(e) => handleClick(e, link.href)}
                  className="group relative text-white/70 hover:text-[#BFFF00] text-sm transition-all duration-300 inline-flex items-center hover:translate-x-1"
                >
                  <span className="relative">
                    {link.label}
                    <span className="absolute left-0 -bottom-0.5 w-0 h-px bg-[#BFFF00] transition-all duration-300 group-hover:w-full" />
                  </span>
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom Row */}
        <div
          className="mt-10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4"
          style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}
        >
          <span className="text-white/70 text-xs font-mono font-medium">Farm Manager</span>
          <span className="text-white/70 text-xs">联系方式: contact@farm.lllcnm.cn</span>
          <span className="text-white/70 text-xs inline-flex items-center gap-1">
            Made with
            <Heart className="w-3 h-3 text-[#BFFF00] fill-[#BFFF00] inline" />
            for farmers
          </span>
        </div>
      </div>

      {/* Back to Top Button */}
      <button
        onClick={scrollToTop}
        aria-label="回到顶部"
        className={`
          fixed bottom-6 right-6 z-50
          w-12 h-12 rounded-full
          flex items-center justify-center
          bg-[#BFFF00] text-[#013A33]
          shadow-[0_4px_16px_rgba(191,255,0,0.35)]
          transition-all duration-300 ease-out
          hover:scale-110 hover:shadow-[0_6px_24px_rgba(191,255,0,0.5)]
          active:scale-95
          focus:outline-none focus:ring-2 focus:ring-[#BFFF00] focus:ring-offset-2 focus:ring-offset-[#013A33]
          ${showBackToTop ? 'opacity-100 translate-y-0 pointer-events-auto' : 'opacity-0 translate-y-4 pointer-events-none'}
        `}
      >
        <ArrowUp className="w-5 h-5" />
      </button>
    </footer>
  );
}
