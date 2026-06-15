import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const navLinks = [
  { label: '功能', href: '#features' },
  { label: 'AI助手', href: '#ai-assistant' },
  { label: '下载', href: '#download' },
  { label: 'FAQ', href: '#faq' },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 60);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleAnchorClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    setMobileOpen(false);
    const target = document.querySelector(href);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <>
      <nav
        className="fixed top-0 left-0 right-0 z-50 transition-all duration-300"
        style={{
          transitionTimingFunction: 'cubic-bezier(0.45, 0.05, 0.55, 0.95)',
          backgroundColor: scrolled ? '#013A33' : 'transparent',
          backdropFilter: scrolled ? 'blur(12px)' : 'none',
        }}
      >
        <div className="container-main flex items-center justify-between h-[72px]">
          {/* Brand */}
          <Link to="/" className="flex items-center gap-3 text-white font-semibold text-lg" aria-label="田掌柜首页">
            <img
              src="/app-logo.png"
              alt=""
              className="h-9 w-9 rounded-xl"
            />
            <span className="hidden sm:inline">田掌柜</span>
          </Link>

          {/* Center nav links - desktop */}
          <div className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={(e) => handleAnchorClick(e, link.href)}
                className="text-white/70 hover:text-white text-sm font-medium transition-colors duration-200"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Right CTA - desktop */}
          <a
            href="#download"
            onClick={(e) => handleAnchorClick(e, '#download')}
            className="hidden md:inline-flex items-center px-6 py-2.5 bg-accent-lime text-primary-dark text-sm font-semibold rounded-pill hover:scale-[1.03] hover:brightness-105 transition-all duration-200"
          >
            立即下载
          </a>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden flex flex-col gap-1.5 p-2"
            aria-label="Toggle menu"
          >
            <span className={`block w-6 h-0.5 bg-white transition-transform duration-300 ${mobileOpen ? 'rotate-45 translate-y-2' : ''}`} />
            <span className={`block w-6 h-0.5 bg-white transition-opacity duration-300 ${mobileOpen ? 'opacity-0' : ''}`} />
            <span className={`block w-6 h-0.5 bg-white transition-transform duration-300 ${mobileOpen ? '-rotate-45 -translate-y-2' : ''}`} />
          </button>
        </div>
      </nav>

      {/* Mobile menu overlay */}
      <div
        className={`fixed inset-0 z-40 bg-primary-dark transition-all duration-300 md:hidden ${
          mobileOpen ? 'opacity-100 visible' : 'opacity-0 invisible'
        }`}
        style={{ paddingTop: '72px' }}
      >
        <div className="flex flex-col items-center justify-center h-full gap-8 -mt-20">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={(e) => handleAnchorClick(e, link.href)}
              className="text-white text-2xl font-semibold hover:text-accent-lime transition-colors duration-200"
            >
              {link.label}
            </a>
          ))}
          <a
            href="#download"
            onClick={(e) => handleAnchorClick(e, '#download')}
            className="mt-4 px-8 py-3 bg-accent-lime text-primary-dark text-lg font-semibold rounded-pill"
          >
            立即下载
          </a>
        </div>
      </div>
    </>
  );
}
