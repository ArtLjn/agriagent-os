import { DatabaseOutlined, SmileOutlined } from "@ant-design/icons";
import { Tabs } from "antd";
import PersonalizationPanel from "./PersonalizationPanel";
import MemoryPanel from "./MemoryPanel";
import { PageShell } from "../../components/PageShell";
import "./assistant-settings.css";

export default function AssistantSettings() {
  return (
    <PageShell
      className="assistant-settings"
      title="助手设置"
      description="管理称呼、表达方式与长期记忆；助手设置按业务保存，长期记忆与记忆开关全局共享。"
    >

      <Tabs
        className="assistant-tabs"
        defaultActiveKey="personalization"
        items={[
          {
            key: "personalization",
            label: (
              <span>
                <SmileOutlined /> 个性化设置
              </span>
            ),
            children: <PersonalizationPanel />,
          },
          {
            key: "memories",
            label: (
              <span>
                <DatabaseOutlined /> 记忆管理
              </span>
            ),
            children: <MemoryPanel />,
          },
        ]}
      />
    </PageShell>
  );
}
