import { useEffect, useRef, useState } from 'react';
import type { FormEvent, PointerEvent as ReactPointerEvent } from 'react';
import { Button, ConfigProvider, Input, message, theme } from 'antd';
import type { ThemeConfig } from 'antd';
import {
  ArrowRightOutlined,
  LineChartOutlined,
  LockOutlined,
  MoonOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SunOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { isAxiosError } from 'axios';
import apiClient from '../../api/client';
import { authStore } from '../../stores/authStore';
import { useThemeMode } from '../../theme/themeContext';
import LoginScene from './LoginScene';
import type { LoginTheme } from './LoginScene';
import './login.css';

const FONT_FAMILY =
  "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', Inter, ui-sans-serif, system-ui, sans-serif";

const loginThemes: Record<LoginTheme, ThemeConfig> = {
  light: {
    algorithm: theme.defaultAlgorithm,
    token: {
      colorPrimary: '#2f8f5b',
      colorInfo: '#2f8f5b',
      colorText: '#17271d',
      colorTextSecondary: '#5f7367',
      colorTextPlaceholder: '#9aab9e',
      colorBgContainer: '#ffffff',
      colorBorder: '#dde7dc',
      borderRadius: 12,
      controlHeight: 48,
      fontSize: 14,
      fontFamily: FONT_FAMILY,
    },
    components: {
      Button: {
        controlHeight: 48,
        borderRadius: 12,
        primaryColor: '#ffffff',
        primaryShadow: '0 10px 24px rgba(47, 143, 91, 0.22)',
      },
      Input: {
        controlHeight: 48,
        borderRadius: 12,
        activeBorderColor: '#2f8f5b',
        hoverBorderColor: '#b9cfbb',
        activeShadow: '0 0 0 3px rgba(47, 143, 91, 0.12)',
        paddingInline: 14,
      },
    },
  },
  dark: {
    algorithm: theme.darkAlgorithm,
    token: {
      colorPrimary: '#379f67',
      colorInfo: '#379f67',
      colorText: '#eef6ef',
      colorTextSecondary: '#a3b7a9',
      colorTextPlaceholder: 'rgba(235, 245, 238, 0.36)',
      colorBgContainer: 'rgba(255, 255, 255, 0.06)',
      colorBorder: 'rgba(255, 255, 255, 0.12)',
      borderRadius: 12,
      controlHeight: 48,
      fontSize: 14,
      fontFamily: FONT_FAMILY,
    },
    components: {
      Button: {
        controlHeight: 48,
        borderRadius: 12,
        primaryColor: '#ffffff',
        primaryShadow: '0 10px 26px rgba(0, 0, 0, 0.38)',
      },
      Input: {
        controlHeight: 48,
        borderRadius: 12,
        activeBorderColor: '#379f67',
        hoverBorderColor: 'rgba(255, 255, 255, 0.24)',
        activeShadow: '0 0 0 3px rgba(55, 159, 103, 0.2)',
        paddingInline: 14,
      },
    },
  },
};

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { mode, setMode } = useThemeMode();
  const brandRef = useRef<HTMLElement | null>(null);
  const frameRef = useRef(0);

  useEffect(() => () => cancelAnimationFrame(frameRef.current), []);

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== 'mouse') return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const x = (event.clientX / window.innerWidth) * 2 - 1;
    const y = (event.clientY / window.innerHeight) * 2 - 1;
    cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(() => {
      const brand = brandRef.current;
      if (!brand) return;
      brand.style.setProperty('--login-px', x.toFixed(3));
      brand.style.setProperty('--login-py', y.toFixed(3));
    });
  };

  const handlePointerLeave = () => {
    const brand = brandRef.current;
    if (!brand) return;
    brand.style.setProperty('--login-px', '0');
    brand.style.setProperty('--login-py', '0');
  };

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!phone || !password) {
      message.error('请输入手机号和密码');
      return;
    }
    setLoading(true);
    try {
      const res = await apiClient.post('/auth/login', { phone, password });
      const responseData = res.data as { access_token?: unknown; token?: unknown };
      const token = typeof responseData.access_token === 'string'
        ? responseData.access_token
        : typeof responseData.token === 'string'
          ? responseData.token
          : '';
      if (!token) {
        throw new Error('登录服务未返回有效认证令牌');
      }
      authStore.setToken(token);
      message.success('登录成功');
      onLogin();
    } catch (e: unknown) {
      const detail = isAxiosError(e) ? e.response?.data?.detail : undefined;
      message.error(typeof detail === 'string' ? detail : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ConfigProvider theme={loginThemes[mode]}>
      <div
        className="login-page"
        data-theme={mode}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
      >
        <div className="login-theme-toggle" role="group" aria-label="主题切换">
          <button
            type="button"
            aria-pressed={mode === 'light'}
            onClick={() => setMode('light')}
            title="亮色主题"
          >
            <SunOutlined />
            <span>亮色</span>
          </button>
          <button
            type="button"
            aria-pressed={mode === 'dark'}
            onClick={() => setMode('dark')}
            title="暗色主题"
          >
            <MoonOutlined />
            <span>暗色</span>
          </button>
        </div>

        <aside className="login-brand" ref={brandRef}>
          <div className="login-brand__top">
            <img className="login-brand__mark" src="/logo.png" alt="田掌柜" />
            <div>
              <div className="login-brand__name">田掌柜</div>
              <div className="login-brand__tag">TIAN ZHANGGUI · AI WORKSPACE</div>
            </div>
          </div>

          <div className="login-brand__hero">
            <div className="login-brand__eyebrow">智慧农场 · 经营助手</div>
            <p className="login-brand__title">
              让每一分耕耘，
              <br />
              都长成看得见的答案。
            </p>
            <p className="login-brand__desc">
              从巡田排产到成本结算，把农场的每一天，整理成清晰可读的经营图谱。
            </p>
            <div className="login-brand__features">
              <span>
                <RobotOutlined />
                智能农事
              </span>
              <span>
                <LineChartOutlined />
                经营可视
              </span>
              <span>
                <SafetyCertificateOutlined />
                全程留痕
              </span>
            </div>
          </div>

          <LoginScene theme={mode} />
        </aside>

        <main className="login-panel">
          <div className="login-form-wrap">
            <div className="login-mobile-brand">
              <img src="/logo.png" alt="" />
              <span>田掌柜</span>
            </div>

            <div className="login-form__eyebrow">管理员工作台</div>
            <h1 className="login-form__title">欢迎回来</h1>
            <p className="login-form__desc">登录田掌柜，继续管理你的农场与经营数据。</p>

            <form className="login-form" onSubmit={handleLogin} noValidate>
              <label className="login-field" htmlFor="login-phone">
                <span className="login-field__label">手机号</span>
                <Input
                  id="login-phone"
                  prefix={<UserOutlined className="login-field__icon" />}
                  placeholder="手机号"
                  value={phone}
                  autoComplete="username"
                  inputMode="tel"
                  onChange={(e) => setPhone(e.target.value)}
                />
              </label>

              <label className="login-field" htmlFor="login-password">
                <span className="login-field__label">密码</span>
                <Input.Password
                  id="login-password"
                  prefix={<LockOutlined className="login-field__icon" />}
                  placeholder="密码"
                  value={password}
                  autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>

              <Button
                className="login-submit"
                type="primary"
                htmlType="submit"
                block
                loading={loading}
              >
                登录工作台
                <ArrowRightOutlined className="login-submit__arrow" />
              </Button>
            </form>

            <div className="login-form__note">
              <SafetyCertificateOutlined />
              <span>仅限授权管理员访问，登录与操作全程留痕。</span>
            </div>
          </div>
        </main>
      </div>
    </ConfigProvider>
  );
}
