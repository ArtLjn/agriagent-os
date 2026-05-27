import { useEffect, useState } from 'react';
import { Typography, Tag, Empty, Spin } from 'antd';
import { AppstoreOutlined } from '@ant-design/icons';
import { listSkills, type SkillItem } from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';

export default function SkillRegistry() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await listSkills();
        setSkills(res.items);
      } catch {
        // 错误已在 api client 中处理
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>
        <AppstoreOutlined style={{ marginRight: 8 }} />
        Skill 注册表
      </Typography.Title>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <Spin size="large" />
        </div>
      ) : skills.length === 0 ? (
        <Empty description="暂无 Skill 数据" style={{ marginTop: 64 }} />
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: 16,
          }}
        >
          {skills.map((skill) => (
            <div
              key={skill.name}
              style={{
                backgroundColor: CARD_BG,
                border: `1px solid ${BORDER}`,
                borderRadius: 8,
                padding: 20,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 12,
                }}
              >
                <Typography.Text
                  strong
                  style={{ color: TEXT, fontSize: 16 }}
                >
                  {skill.name}
                </Typography.Text>
                <Tag color={skill.status === 'active' ? 'success' : 'default'}>
                  {skill.status}
                </Tag>
              </div>

              <div
                style={{
                  color: TEXT_DIM,
                  marginBottom: 12,
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                {skill.description}
              </div>

              <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 4 }}>
                参数 schema:
              </div>
              <pre
                style={{
                  backgroundColor: '#0d1117',
                  border: `1px solid ${BORDER}`,
                  borderRadius: 4,
                  padding: 12,
                  color: TEXT,
                  fontSize: 12,
                  overflow: 'auto',
                  maxHeight: 240,
                  margin: 0,
                }}
              >
                {JSON.stringify(skill.parameters_schema, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
