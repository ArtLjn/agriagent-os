import { Button, Space, message } from 'antd';
import { CopyOutlined } from '@ant-design/icons';

const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const BORDER = '#30363d';
const BG = '#161b22';

interface SkillOutputFormatterProps {
  outputData: string | null;
}

interface ParsedSkillOutput {
  reply_preview?: string;
  status?: string;
  [key: string]: unknown;
}

export default function SkillOutputFormatter({ outputData }: SkillOutputFormatterProps) {
  if (!outputData) return null;

  let parsed: ParsedSkillOutput | null = null;
  try {
    parsed = JSON.parse(outputData) as ParsedSkillOutput;
  } catch {
    // 解析失败，回退到原始展示
  }

  // 解析失败或不含 reply_preview —— 回退到原始 JSON
  if (!parsed || typeof parsed !== 'object' || !parsed.reply_preview) {
    return (
      <pre style={{
        backgroundColor: BG,
        padding: 12,
        borderRadius: 6,
        border: `1px solid ${BORDER}`,
        fontSize: 12,
        margin: 0,
        maxHeight: 300,
        overflow: 'auto',
        whiteSpace: 'pre-wrap',
        color: TEXT,
      }}>
        {outputData}
      </pre>
    );
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(parsed!.reply_preview || '');
      message.success('已复制到剪贴板');
    } catch {
      message.error('复制失败');
    }
  };

  // 分离 reply_preview 和其余字段
  const { reply_preview, ...restFields } = parsed;
  const hasRest = Object.keys(restFields).length > 0;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* reply_preview 高亮展示 */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>执行结果</span>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={handleCopy}
            style={{ background: BG, borderColor: BORDER, color: TEXT_DIM }}
          >
            复制结果
          </Button>
        </div>
        <div style={{
          backgroundColor: '#1a2332',
          padding: 12,
          borderRadius: 6,
          border: `1px solid ${BORDER}`,
          color: TEXT,
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
        }}>
          {reply_preview}
        </div>
      </div>

      {/* 其余字段折叠 */}
      {hasRest && (
        <details style={{ cursor: 'pointer' }}>
          <summary style={{ color: TEXT_DIM, fontSize: 12, userSelect: 'none' }}>
            查看完整输出 ({Object.keys(restFields).length} 个字段)
          </summary>
          <pre style={{
            backgroundColor: BG,
            padding: 12,
            borderRadius: 6,
            border: `1px solid ${BORDER}`,
            fontSize: 12,
            margin: '8px 0 0 0',
            maxHeight: 300,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            color: TEXT,
          }}>
            {JSON.stringify(restFields, null, 2)}
          </pre>
        </details>
      )}
    </Space>
  );
}
