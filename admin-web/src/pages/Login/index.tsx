import { useState } from 'react';
import { Button, Input, Card, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { isAxiosError } from 'axios';
import apiClient from '../../api/client';
import { authStore } from '../../stores/authStore';
import { palette } from '../../styles/theme';

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!phone || !password) {
      message.error('请输入手机号和密码');
      return;
    }
    setLoading(true);
    try {
      const res = await apiClient.post('/auth/login', { phone, password });
      const { access_token } = res.data;
      authStore.setToken(access_token);
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
    <div
      style={{
        height: '100vh',
        background: `radial-gradient(circle at 20% 18%, rgba(88, 166, 255, 0.16), transparent 28%), ${palette.bg}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <Card
        style={{
          width: 'min(400px, 100%)',
          background: palette.bgElevated,
          borderColor: palette.border,
          boxShadow: '0 24px 80px rgba(1, 4, 9, 0.46)',
        }}
        styles={{ body: { padding: '32px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <img
            src="/logo.png"
            alt="田掌柜"
            style={{ width: 64, height: 64, marginBottom: 16 }}
          />
          <Typography.Title level={3} style={{ color: palette.text, margin: 0 }}>田掌柜</Typography.Title>
          <p style={{ color: palette.textMuted, margin: '8px 0 0' }}>智能种植运营助手</p>
          <div style={{ color: palette.textSubtle, fontSize: 12, marginTop: 10 }}>
            <SafetyCertificateOutlined style={{ marginRight: 6 }} />
            管理员安全入口
          </div>
        </div>

        <Input
          prefix={<UserOutlined style={{ color: '#8b949e' }} />}
          placeholder="手机号"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onPressEnter={handleLogin}
          style={{ marginBottom: 16, background: palette.bg, borderColor: palette.border, color: palette.text }}
        />
        <Input.Password
          prefix={<LockOutlined style={{ color: '#8b949e' }} />}
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onPressEnter={handleLogin}
          style={{ marginBottom: 24, background: palette.bg, borderColor: palette.border, color: palette.text }}
        />

        <Button
          type="primary"
          block
          loading={loading}
          onClick={handleLogin}
          style={{ height: 40 }}
        >
          登录
        </Button>
      </Card>
    </div>
  );
}
