import { useEffect, useState } from 'react';
import { Typography, Tag, Empty, Spin, Switch, message } from 'antd';
import { AppstoreOutlined } from '@ant-design/icons';
import {
  listSkills,
  updateSkillEnabled,
  type SkillItem,
  type SkillSummary,
} from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const DISABLE_REASON = '管理员手动禁用';

const EMPTY_SUMMARY: SkillSummary = {
  total: 0,
  enabled: 0,
  disabled: 0,
  admin_only: 0,
};

export default function SkillRegistry() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [summary, setSummary] = useState<SkillSummary>(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(false);
  const [updatingSkill, setUpdatingSkill] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await listSkills();
        setSkills(res.items);
        setSummary(res.summary);
      } catch {
        // 错误已在 api client 中处理
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleToggle = async (skill: SkillItem, enabled: boolean) => {
    setUpdatingSkill(skill.name);
    try {
      const updated = await updateSkillEnabled(skill.name, {
        enabled,
        disabled_reason: enabled ? undefined : DISABLE_REASON,
      });
      setSkills((current) =>
        current.map((item) => (item.name === updated.name ? updated : item))
      );
      setSummary((current) => ({
        ...current,
        enabled: current.enabled + (enabled ? 1 : -1),
        disabled: current.disabled + (enabled ? -1 : 1),
      }));
      message.success(enabled ? 'Skill 已启用' : 'Skill 已禁用');
    } catch {
      // 错误已在 api client 中处理
    } finally {
      setUpdatingSkill(null);
    }
  };

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
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: 12,
              marginBottom: 16,
            }}
          >
            <SummaryCard label="全部 Skill" value={summary.total} />
            <SummaryCard label="已启用" value={summary.enabled} accent="#2ea043" />
            <SummaryCard label="已禁用" value={summary.disabled} accent="#f85149" />
            <SummaryCard label="Admin Only" value={summary.admin_only} accent="#58a6ff" />
          </div>

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
                    gap: 12,
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
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <Tag color={statusColor(skill.status)}>
                      {skill.status}
                    </Tag>
                    <Switch
                      aria-label={`${skill.metadata.enabled ? '禁用' : '启用'} ${skill.name}`}
                      checked={skill.metadata.enabled}
                      loading={updatingSkill === skill.name}
                      size="small"
                      onChange={(checked) => handleToggle(skill, checked)}
                    />
                  </div>
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

                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    marginBottom: 12,
                  }}
                >
                  <Tag color="blue">{skill.metadata.permission_level}</Tag>
                  <Tag color={riskColor(skill.metadata.risk_level)}>
                    {skill.metadata.risk_level}
                  </Tag>
                </div>

                {skill.metadata.disabled_reason && (
                  <div
                    style={{
                      color: '#f85149',
                      marginBottom: 12,
                      fontSize: 13,
                      lineHeight: 1.5,
                    }}
                  >
                    {skill.metadata.disabled_reason}
                  </div>
                )}

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
        </>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  accent = '#8b949e',
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div
      style={{
        backgroundColor: CARD_BG,
        border: `1px solid ${BORDER}`,
        borderTop: `2px solid ${accent}`,
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ color: TEXT_DIM, fontSize: 13, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ color: TEXT, fontSize: 26, fontWeight: 700 }}>
        {value}
      </div>
    </div>
  );
}

function statusColor(status: string) {
  if (status === 'active') {
    return 'success';
  }
  if (status === 'disabled') {
    return 'error';
  }
  if (status === 'admin_only') {
    return 'processing';
  }
  return 'default';
}

function riskColor(risk: string) {
  if (risk === 'high') {
    return 'red';
  }
  if (risk === 'medium') {
    return 'orange';
  }
  return 'green';
}
