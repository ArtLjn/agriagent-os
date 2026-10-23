import { DatabaseOutlined, SmileOutlined } from "@ant-design/icons";
import { Tabs } from "antd";
import PersonalizationPanel from "./PersonalizationPanel";
import MemoryPanel from "./MemoryPanel";
import "./assistant-settings.css";

export default function AssistantSettings() {
  return (
    <section className="assistant-settings">
      <header className="assistant-hero">
        <div className="assistant-hero__main">
          <div className="assistant-hero__orb" aria-hidden="true">
            田
          </div>
          <div>
            <div className="assistant-hero__eyebrow">PERSONAL ASSISTANT</div>
            <h1>让助手更懂你</h1>
            <p>
              称呼、表达方式与长期记忆都在这里。把习惯告诉田掌柜一次，之后不用反复解释。
            </p>
          </div>
        </div>
        <div className="assistant-hero__meta">
          <span className="assistant-hero__status">
            <span className="assistant-hero__status-dot" />
            个性化工作台
          </span>
          <span className="assistant-hero__hint">设置从下一轮对话生效</span>
        </div>
      </header>

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
    </section>
  );
}
