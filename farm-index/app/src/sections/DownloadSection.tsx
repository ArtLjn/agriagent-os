import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { Link } from 'react-router-dom';
import {
  FALLBACK_APP_VERSION,
  fetchAppVersion,
  formatVersionLabel,
} from '@/api/appVersion';

gsap.registerPlugin(ScrollTrigger);

export default function DownloadSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [appVersion, setAppVersion] = useState(FALLBACK_APP_VERSION);

  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      gsap.from('.download-title', {
        scale: 0.95,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 80%',
        },
      });

      gsap.utils.toArray<HTMLElement>('.download-card').forEach((card, i) => {
        gsap.from(card, {
          y: 60,
          opacity: 0,
          duration: 0.8,
          delay: i * 0.15,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: section,
            start: 'top 70%',
          },
        });
      });

      gsap.from('.qr-code-card', {
        y: 40,
        opacity: 0,
        duration: 0.8,
        delay: 0.3,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 60%',
        },
      });
    }, section);

    return () => ctx.revert();
  }, []);

  useEffect(() => {
    let ignore = false;

    fetchAppVersion()
      .then((version) => {
        if (!ignore) {
          setAppVersion(version);
        }
      })
      .catch(() => {
        if (!ignore) {
          setAppVersion(FALLBACK_APP_VERSION);
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section
      id="download"
      ref={sectionRef}
      className="section-padding relative overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, #013A33 0%, #0a4f46 50%, #013A33 100%)',
      }}
    >
      {/* Subtle dot pattern overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      <div className="container-main relative z-10">
        {/* Header */}
        <div className="download-title text-center mb-12">
          <p className="text-white/40 text-xs font-medium uppercase tracking-[0.1em] mb-4">
            下载中心
          </p>
          <h2
            className="text-white font-semibold tracking-[-0.01em] mb-4"
            style={{ fontSize: 'clamp(1.75rem, 4vw, 3.5rem)', lineHeight: 1.15, wordBreak: 'keep-all' }}
          >
            立即开始智慧农场管理
          </h2>
          <p className="text-white/60 text-base max-w-[520px] mx-auto leading-relaxed" style={{ wordBreak: 'keep-all' }}>
            下载田掌柜，开启 AI 驱动的农场经营新体验
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_0.85fr] gap-6 max-w-[1040px] mx-auto mb-10 items-stretch">
          <div className="download-card relative min-h-[360px] overflow-hidden rounded-card border border-white/10 bg-[#0d2e28] shadow-[0_24px_80px_rgba(0,0,0,0.28)]">
            <img
              src="/download-poster.jpg"
              alt="田掌柜 Android 版下载海报"
              className="absolute inset-0 h-full w-full object-cover object-[58%_center] md:object-center"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-[#013A33]/80 via-[#013A33]/20 to-transparent" />
            <div className="absolute left-6 top-6 flex items-center gap-3 rounded-full border border-white/18 bg-[#013A33]/45 px-3.5 py-2.5 shadow-[0_12px_36px_rgba(0,0,0,0.22)] backdrop-blur-md">
              <img
                src="/app-logo.png"
                alt=""
                className="h-7 w-7 rounded-lg"
              />
              <span className="text-sm font-semibold tracking-wide text-white">田掌柜</span>
            </div>
            <div className="absolute bottom-6 left-6 max-w-[320px]">
              <p className="mb-3 text-xs font-medium uppercase tracking-[0.12em] text-white/60">
                App Preview
              </p>
              <h3 className="text-2xl font-semibold leading-tight text-white md:text-3xl">
                农场经营状态，一屏看清
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-white/70">
                作物、天气、农事和账本信息同步更新，随时掌握农场进展。
              </p>
            </div>
          </div>

          <div
            className="download-card rounded-card p-8 md:p-10"
            style={{ backgroundColor: '#BFFF00' }}
          >
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center mb-6"
              style={{ backgroundColor: 'rgba(1, 58, 51, 0.1)' }}
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                <path d="M17.523 15.3414C17.523 15.6414 17.2804 15.884 16.9804 15.884H16.4435V18.2218C16.4435 18.8544 15.931 19.3669 15.2984 19.3669C14.6658 19.3669 14.1533 18.8544 14.1533 18.2218V15.884H9.84666V18.2218C9.84666 18.8544 9.33418 19.3669 8.70157 19.3669C8.06896 19.3669 7.55648 18.8544 7.55648 18.2218V15.884H7.01959C6.71955 15.884 6.47699 15.6414 6.47699 15.3414V8.23079H17.523V15.3414ZM5.01348 8.23079C4.38087 8.23079 3.86839 8.74327 3.86839 9.37588V14.4206C3.86839 15.0532 4.38087 15.5657 5.01348 15.5657C5.64609 15.5657 6.15857 15.0532 6.15857 14.4206V9.37588C6.15857 8.74327 5.64609 8.23079 5.01348 8.23079ZM18.9865 8.23079C18.3539 8.23079 17.8414 8.74327 17.8414 9.37588V14.4206C17.8414 15.0532 18.3539 15.5657 18.9865 15.5657C19.6191 15.5657 20.1316 15.0532 20.1316 14.4206V9.37588C20.1316 8.74327 19.6191 8.23079 18.9865 8.23079ZM14.7995 3.44109L15.6697 2.09503C15.7429 1.98131 15.7089 1.83095 15.5952 1.75778C15.4815 1.6846 15.3311 1.71858 15.2579 1.8323L14.3692 3.20698C13.6401 2.89543 12.8386 2.7226 11.9993 2.7226C11.1601 2.7226 10.3585 2.89543 9.62948 3.20698L8.74078 1.8323C8.6676 1.71858 8.51724 1.6846 8.40352 1.75778C8.2898 1.83095 8.25583 1.98131 8.329 2.09503L9.19917 3.44109C7.65127 4.27091 6.57199 5.80657 6.47699 7.60094H17.5217C17.4267 5.80657 16.3474 4.27091 14.7995 3.44109ZM9.62526 5.98185C9.29852 5.98185 9.03369 5.71702 9.03369 5.39028C9.03369 5.06354 9.29852 4.79871 9.62526 4.79871C9.952 4.79871 10.2168 5.06354 10.2168 5.39028C10.2168 5.71702 9.952 5.98185 9.62526 5.98185ZM14.3734 5.98185C14.0467 5.98185 13.7818 5.71702 13.7818 5.39028C13.7818 5.06354 14.0467 4.79871 14.3734 4.79871C14.7002 4.79871 14.965 5.06354 14.965 5.39028C14.965 5.71702 14.7002 5.98185 14.3734 5.98185Z" fill="#013A33"/>
              </svg>
            </div>
            <h3 className="font-semibold text-xl mb-2" style={{ color: '#013A33' }}>
              Android 版
            </h3>
            <p className="font-mono text-xs mb-1" style={{ color: 'rgba(1, 58, 51, 0.6)' }}>
              {formatVersionLabel(appVersion.latestVersion)}
            </p>
            <p className="text-xs mb-6" style={{ color: 'rgba(1, 58, 51, 0.6)' }}>
              Version Code {appVersion.latestVersionCode}
            </p>
            <a
              href={appVersion.downloadUrl}
              className="block w-full text-center px-6 py-3.5 font-semibold text-sm rounded-pill transition-all duration-300 hover:scale-[1.03] hover:shadow-[0_0_24px_rgba(1,58,51,0.35)] active:scale-[0.98]"
              style={{
                backgroundColor: '#013A33',
                color: '#BFFF00',
              }}
            >
              下载 APK
            </a>
            <p className="text-xs mt-3 text-center" style={{ color: 'rgba(1, 58, 51, 0.45)' }}>
              文件大小：约 74 MB
            </p>
            <div className="mt-5 rounded-2xl px-4 py-3" style={{ backgroundColor: 'rgba(1, 58, 51, 0.08)' }}>
              <div className="flex items-center justify-between gap-3 mb-2">
                <span className="text-xs font-semibold" style={{ color: '#013A33' }}>
                  当前后端版本
                </span>
                <span
                  className="rounded-full px-2.5 py-1 text-[11px] font-semibold"
                  style={{
                    backgroundColor: appVersion.forceUpdate ? '#013A33' : 'rgba(1, 58, 51, 0.12)',
                    color: appVersion.forceUpdate ? '#BFFF00' : '#013A33',
                  }}
                >
                  {appVersion.forceUpdate ? '建议更新' : '已是最新'}
                </span>
              </div>
              <p className="line-clamp-2 text-xs leading-relaxed" style={{ color: 'rgba(1, 58, 51, 0.64)' }}>
                {appVersion.changelog}
              </p>
            </div>
          </div>

          <div className="download-card bg-[#0d2e28] border border-[#1a4540] text-white rounded-card p-8 md:p-10 shadow-[0_8px_32px_rgba(0,0,0,0.15)] lg:col-span-2">
            {/* iOS Section */}
            <div className="flex items-start gap-4 mb-4">
              <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" fill="#BFFF00"/>
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-white font-semibold text-xl">iOS 版</h3>
                  <span className="px-3 py-0.5 bg-accent-gold text-primary-dark text-xs font-semibold rounded-pill">
                    即将上线
                  </span>
                </div>
                <p className="text-white/60 text-sm">App Store 审核中，敬请期待</p>
              </div>
            </div>

            {/* Divider */}
            <div className="my-6" style={{ borderTop: '1px solid #1a4540' }} />

            {/* Web Section */}
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#BFFF00" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
                  <line x1="8" y1="21" x2="16" y2="21"/>
                  <line x1="12" y1="17" x2="12" y2="21"/>
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="text-white font-semibold text-xl mb-3">Web 管理后台</h3>
                <Link
                  to="/admin"
                  className="block w-full text-center px-6 py-3.5 border border-white/40 text-white font-semibold text-sm rounded-pill hover:bg-white/10 hover:text-white transition-all duration-200"
                >
                  进入后台
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* QR Code */}
        <div className="qr-code-card flex flex-col items-center gap-3 mb-6">
          <div
            className="rounded-2xl p-4 shadow-[0_8px_32px_rgba(0,0,0,0.2)] bg-[#0d2e28] border border-[#1a4540]"
          >
            <img
              src="/qr-code-download.png"
              alt={`扫码下载 ${formatVersionLabel(appVersion.latestVersion)} Android 版`}
              className="w-36 h-36 rounded-lg"
              style={{ objectFit: 'contain' }}
            />
          </div>
          <p className="text-white/50 text-xs">
            扫码下载 Android 版 · {formatVersionLabel(appVersion.latestVersion)}
          </p>
        </div>

        {/* Changelog Link */}
        <div className="text-center">
          <a
            href="#changelog"
            className="text-white/70 text-sm font-medium hover:text-[#BFFF00] transition-colors duration-300"
          >
            查看更新日志 →
          </a>
        </div>
      </div>
    </section>
  );
}
