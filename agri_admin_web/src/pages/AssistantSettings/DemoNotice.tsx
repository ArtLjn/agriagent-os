import { InfoCircleOutlined } from "@ant-design/icons";

export default function DemoNotice({ description }: { description: string }) {
  return (
    <div className="demo-notice" role="status">
      <InfoCircleOutlined />
      <span>
        <strong>演示数据</strong> · {description}
      </span>
    </div>
  );
}
