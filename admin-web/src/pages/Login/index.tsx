import { useState } from 'react';
import { Button, Input, Card, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import apiClient from '../../api/client';
import { authStore } from '../../stores/authStore';

const BG_PRIMARY = '#0d1117';
const BG_CARD = '#21262d';
const BORDER = '#30363d';
const TEXT_PRIMARY = '#c9d1d9';
const ACCENT = '#58a6ff';

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
    } catch (e: any) {
      message.error(e.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        height: '100vh',
        background: BG_PRIMARY,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Card
        style={{
          width: 360,
          background: BG_CARD,
          borderColor: BORDER,
        }}
        styles={{ body: { padding: '32px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <img
            src="/logo.png"
            alt="农博社"
            style={{ width: 64, height: 64, marginBottom: 16 }}
          />
          <h2 style={{ color: TEXT_PRIMARY, margin: 0, fontSize: 22 }}>农博社</h2>
          <p style={{ color: '#8b949e', margin: '8px 0 0' }}>智能种植管理平台</p>
        </div>

        <Input
          prefix={<UserOutlined style={{ color: '#8b949e' }} />}
          placeholder="手机号"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onPressEnter={handleLogin}
          style={{ marginBottom: 16, background: '#161b22', borderColor: BORDER, color: TEXT_PRIMARY }}
        />
        <Input.Password
          prefix={<LockOutlined style={{ color: '#8b949e' }} />}
          placeholder="密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onPressEnter={handleLogin}
          style={{ marginBottom: 24, background: '#161b22', borderColor: BORDER, color: TEXT_PRIMARY }}
        />

        <Button
          type="primary"
          block
          loading={loading}
          onClick={handleLogin}
          style={{ background: ACCENT, height: 40 }}
        >
          登录
        </Button>
      </Card>
    </div>
  );
}
