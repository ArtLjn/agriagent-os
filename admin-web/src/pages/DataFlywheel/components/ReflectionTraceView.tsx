import { Empty, Space, Tag, Typography } from 'antd';
import type { CSSProperties } from 'react';

import type { TraceDiagnostics, TraceReflectionCheck, TraceReflectionIssue } from '../../../api/admin';
import { palette } from '../../../styles/theme';

interface ReflectionTraceViewProps {
  diagnostics?: TraceDiagnostics | null;
  loading?: boolean;
  compact?: boolean;
}

const decisionColor: Record<string, string> = {
  pass: 'success',
  ask_clarification: 'warning',
  block_write: 'error',
  require_tool: 'error',
  retry_generation: 'processing',
  fallback_response: 'warning',
};

export default function ReflectionTraceView({
  diagnostics,
  loading = false,
  compact = false,
}: ReflectionTraceViewProps) {
  if (loading) {
    return <Typography.Text style={mutedTextStyle}>reflection: 加载中...</Typography.Text>;
  }

  const checks = diagnostics?.reflection_checks ?? [];
  if (checks.length === 0) {
    return (
      <div style={compact ? emptyCompactStyle : emptyStyle}>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 Reflection 检查" />
      </div>
    );
  }

  return (
    <Space direction="vertical" size={compact ? 8 : 10} style={{ width: '100%' }}>
      <Summary diagnostics={diagnostics} />
      {checks.map((check, index) => (
        <ReflectionCheckCard key={`${check.trigger}-${index}`} check={check} compact={compact} />
      ))}
    </Space>
  );
}

function Summary({ diagnostics }: { diagnostics?: TraceDiagnostics | null }) {
  const diagnostic = diagnostics?.reflection_diagnostic;
  return (
    <Space wrap size={6}>
      <Tag color={diagnostic?.blocked ? 'error' : 'success'}>
        blocked: {diagnostic?.blocked ? '是' : '否'}
      </Tag>
      {(diagnostic?.decisions ?? []).map((decision) => (
        <Tag key={decision} color={decisionColor[decision] ?? 'default'}>
          decision: {decision}
        </Tag>
      ))}
      {(diagnostic?.issue_codes ?? []).map((code) => (
        <Tag key={code} color="volcano">
          issue: {code}
        </Tag>
      ))}
    </Space>
  );
}

function ReflectionCheckCard({
  check,
  compact,
}: {
  check: TraceReflectionCheck;
  compact: boolean;
}) {
  return (
    <div style={compact ? checkCompactStyle : checkStyle}>
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Space wrap size={6}>
          <Tag color="blue">trigger: {check.trigger || '-'}</Tag>
          <Tag color={decisionColor[check.decision] ?? 'default'}>
            decision: {check.decision || '-'}
          </Tag>
          {check.checks.map((item) => (
            <Tag key={item} color="purple">
              check: {item}
            </Tag>
          ))}
        </Space>

        <Typography.Text style={bodyTextStyle}>
          reason: {check.reason || '-'}
        </Typography.Text>

        <InputSummary input={check.input} />

        {check.issues.length > 0 ? (
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            {check.issues.map((issue, index) => (
              <IssueRow key={`${issue.code ?? 'issue'}-${index}`} issue={issue} />
            ))}
          </Space>
        ) : (
          <Typography.Text style={mutedTextStyle}>issues: 无</Typography.Text>
        )}
      </Space>
    </div>
  );
}

function IssueRow({ issue }: { issue: TraceReflectionIssue }) {
  return (
    <div style={issueStyle}>
      <Space wrap size={6}>
        <Tag color={issue.severity === 'blocker' ? 'error' : 'warning'}>
          {issue.severity || 'unknown'}
        </Tag>
        <Typography.Text style={bodyTextStyle}>code: {issue.code || '-'}</Typography.Text>
      </Space>
      <Typography.Text style={{ ...bodyTextStyle, display: 'block', marginTop: 4 }}>
        message: {issue.message || '-'}
      </Typography.Text>
      {issue.evidence !== undefined && (
        <Typography.Text style={{ ...mutedTextStyle, display: 'block', marginTop: 4 }}>
          evidence: {formatValue(issue.evidence)}
        </Typography.Text>
      )}
    </div>
  );
}

function InputSummary({ input }: { input: Record<string, unknown> }) {
  const items = [
    ['tool_name', input.tool_name],
    ['tool_names', input.tool_names],
    ['skill_name', input.skill_name],
    ['selected_tools', input.selected_tools],
    ['tool_call_ids', input.tool_call_ids],
    ['plan_id', input.plan_id],
    ['action_id', input.action_id],
  ].filter(([, value]) => hasValue(value));

  if (items.length === 0) {
    return <Typography.Text style={mutedTextStyle}>input: 无关联对象</Typography.Text>;
  }

  return (
    <Space wrap size={6}>
      {items.map(([key, value]) => (
        <Tag key={String(key)} color="default">
          {String(key)}: {formatValue(value)}
        </Tag>
      ))}
    </Space>
  );
}

function hasValue(value: unknown) {
  if (Array.isArray(value)) return value.length > 0;
  return value !== undefined && value !== null && value !== '';
}

function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.map(String).join(', ');
  if (typeof value === 'object' && value !== null) return JSON.stringify(value);
  return String(value);
}

const mutedTextStyle: CSSProperties = {
  color: palette.textMuted,
  fontSize: 12,
};

const bodyTextStyle: CSSProperties = {
  color: palette.text,
  fontSize: 12,
  wordBreak: 'break-word',
};

const emptyStyle: CSSProperties = {
  border: `1px dashed ${palette.borderSoft}`,
  borderRadius: 6,
  background: palette.bg,
  padding: 12,
};

const emptyCompactStyle: CSSProperties = {
  ...emptyStyle,
  padding: 8,
};

const checkStyle: CSSProperties = {
  border: `1px solid ${palette.borderSoft}`,
  borderRadius: 6,
  background: palette.bg,
  padding: 12,
};

const checkCompactStyle: CSSProperties = {
  ...checkStyle,
  padding: 10,
};

const issueStyle: CSSProperties = {
  borderLeft: `2px solid ${palette.warning}`,
  paddingLeft: 8,
};
