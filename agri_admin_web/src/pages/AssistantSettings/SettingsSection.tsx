import type { ReactNode } from "react";

interface SettingsSectionProps {
  icon: ReactNode;
  title: string;
  description?: string;
  children: ReactNode;
}

export default function SettingsSection({
  icon,
  title,
  description,
  children,
}: SettingsSectionProps) {
  return (
    <section className="settings-section">
      <header className="settings-section__head">
        <div className="settings-section__icon">{icon}</div>
        <div>
          <div className="settings-section__title">{title}</div>
          {description && <div className="settings-section__desc">{description}</div>}
        </div>
      </header>
      {children}
    </section>
  );
}
