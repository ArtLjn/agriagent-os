interface ProfileCardProps {
  nickname: string;
  assistantName: string;
  revision: number;
}

export default function ProfileCard({
  nickname,
  assistantName,
  revision,
}: ProfileCardProps) {
  const safeNickname = nickname.trim() || "农友";
  const safeAssistantName = assistantName.trim() || "田掌柜";
  const initial = safeAssistantName.slice(0, 1);

  return (
    <div className="settings-profile">
      <div className="settings-profile__orb" aria-hidden="true">
        {initial}
      </div>
      <div>
        <div className="settings-profile__greeting">你好，{safeNickname}</div>
        <div className="settings-profile__sub">
          我是{safeAssistantName}，会按你的表达习惯回答。
        </div>
      </div>
      <div className="settings-profile__meta">
        <span className="settings-profile__pill">个性化已开启</span>
        <span>v{revision}</span>
      </div>
    </div>
  );
}
