import { DatabaseOutlined, SmileOutlined } from "@ant-design/icons";
import { Tabs } from "antd";
import { PageShell } from "../../components/PageShell";
import PersonalizationPanel from "./PersonalizationPanel";
import MemoryPanel from "./MemoryPanel";

export default function AssistantSettings() {
  return (
    <PageShell
      title="助手设置"
      description="设置助手如何称呼你、如何回答，以及它记住了什么。设置保存后从下一轮对话生效。"
    >
      <Tabs
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
