import { Alert, Button, Space, Switch, Typography } from "antd";
import {
  MessageOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import type { PersonalizationSettings } from "../../api/personalization";
import SettingsSection from "./SettingsSection";

interface MemoryControlsProps {
  preferences: PersonalizationSettings | null;
  settingsError: string | null;
  savingControl: boolean;
  onToggleAutoLearn: (checked: boolean) => void;
  onToggleSavedMemories: (checked: boolean) => void;
  onRetrySettings: () => void;
}

export default function MemoryControls({
  preferences,
  settingsError,
  savingControl,
  onToggleSavedMemories,
  onToggleAutoLearn,
  onRetrySettings,
}: MemoryControlsProps) {
  return (
    <>
      <SettingsSection
        icon={<SafetyCertificateOutlined />}
        title="记忆控制"
        description="决定助手是否使用已保存的记忆，以及是否从新对话中学习。"
      >
        <div className="memory-control-grid">
          <div className="memory-control">
            <div className="memory-control__head">
              <Switch
                aria-label="使用已保存记忆"
                checked={preferences?.use_saved_memories ?? false}
                loading={savingControl}
                disabled={!preferences || savingControl}
                onChange={onToggleSavedMemories}
              />
              <Typography.Text strong>使用已保存记忆</Typography.Text>
            </div>
            <div className="memory-control__desc">
              关闭后，助手不再读取下方记忆；手工填写的个性化设置仍然生效。
            </div>
            {settingsError && (
              <Alert
                type="error"
                showIcon
                message="记忆控制加载或更新失败"
                description={settingsError}
                action={
                  <Button size="small" onClick={onRetrySettings}>
                    重试
                  </Button>
                }
              />
            )}
          </div>

          <div className="memory-control">
            <div className="memory-control__head">
              <Switch aria-label="自动学习偏好" checked={preferences?.auto_learn_enabled ?? false} disabled={!preferences || savingControl} loading={savingControl} onChange={onToggleAutoLearn} />
              <Typography.Text strong>自动学习偏好</Typography.Text>

            </div>
            <div className="memory-control__desc">
              开启后，助手会在每轮对话结束后观察长期偏好，无需使用特定说法。同义表达会累计证据，临时要求与引用会被跳过；证据不足、出现矛盾或涉及农事习惯的记忆先等待你确认。
            </div>
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        icon={<MessageOutlined />}
        title="临时对话"
        description="临时对话不读取个性化与记忆，也不会产生学习事件或持久化偏好。"
      >
        <Space align="start" size={16} wrap>
          <Button icon={<MessageOutlined />} href="/agent?temporary=1">
            发起临时对话
          </Button>
          <div className="memory-control__desc" style={{ maxWidth: 620 }}>
            临时对话使用独立会话，不读取或写入长期记忆。聊天记录仍按会话历史策略保存。
          </div>
        </Space>
      </SettingsSection>
    </>
  );
}
