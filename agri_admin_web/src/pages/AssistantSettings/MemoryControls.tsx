import {
  Alert,
  Button,
  Card,
  Col,
  Row,
  Space,
  Switch,
  Tag,
  Typography,
} from "antd";
import { MessageOutlined } from "@ant-design/icons";
import { cardStyle, palette } from "../../styles/theme";
import type { PersonalizationSettings } from "../../api/personalization";

const captionStyle = { color: palette.textMuted, fontSize: 12 };

interface MemoryControlsProps {
  preferences: PersonalizationSettings | null;
  settingsError: string | null;
  savingControl: boolean;
  onToggleSavedMemories: (checked: boolean) => void;
  onRetrySettings: () => void;
}

export default function MemoryControls({
  preferences,
  settingsError,
  savingControl,
  onToggleSavedMemories,
  onRetrySettings,
}: MemoryControlsProps) {
  return (
    <>
      <Card title="记忆控制" style={cardStyle}>
        <Row gutter={[24, 16]}>
          <Col xs={24} lg={12}>
            <Space align="center" size={10}>
              <Switch
                aria-label="使用已保存记忆"
                checked={preferences?.use_saved_memories ?? false}
                loading={savingControl}
                disabled={!preferences || savingControl}
                onChange={onToggleSavedMemories}
              />
              <Typography.Text strong>使用已保存记忆</Typography.Text>
            </Space>
            <div style={{ ...captionStyle, marginTop: 6 }}>
              关闭后，助手不再读取下方记忆；手工填写的个性化设置仍然生效。
            </div>
            {settingsError && (
              <Alert
                type="error"
                showIcon
                message="记忆控制加载或更新失败"
                description={settingsError}
                style={{ marginTop: 10 }}
                action={
                  <Button size="small" onClick={onRetrySettings}>
                    重试
                  </Button>
                }
              />
            )}
          </Col>
          <Col xs={24} lg={12}>
            <Space align="center" size={10}>
              <Switch aria-label="自动学习偏好" checked={false} disabled />
              <Typography.Text strong>自动学习偏好</Typography.Text>
              <Tag>第二期开放</Tag>
            </Space>
            <div style={{ ...captionStyle, marginTop: 6 }}>
              开启后，助手会从多次对话中学习稳定偏好。当前版本暂不开放自动学习，你仍可手动纠正下方的记忆。
            </div>
          </Col>
        </Row>
      </Card>

      <Card title="临时对话" style={cardStyle}>
        <Space align="start" size={16} wrap>
          <Button icon={<MessageOutlined />} disabled>
            发起临时对话
          </Button>
          <div style={{ maxWidth: 680 }}>
            <div>临时对话不读取个性化与记忆，也不会产生学习事件或持久化偏好。</div>
            <div style={{ ...captionStyle, marginTop: 4 }}>
              对话端入口将在后端支持临时模式后开放；当前版本请使用普通对话。
            </div>
          </div>
        </Space>
      </Card>
    </>
  );
}
