import { DownOutlined } from '@ant-design/icons';
import { Dropdown, Tag, Tooltip } from 'antd';
import type { MenuProps } from 'antd';
import { useBusinesses } from '../businesses/businessContext';
import { iconByName } from '../layouts/menuIcons';

type BusinessStatus = 'active' | 'installed' | 'invalid' | 'unknown';

const STATUS_LABEL: Record<BusinessStatus, string> = {
  active: '当前启用',
  installed: '未启用',
  invalid: '清单异常',
  unknown: '状态未知',
};

const STATUS_COLOR: Record<BusinessStatus, string | undefined> = {
  active: 'success',
  installed: 'warning',
  invalid: 'error',
  unknown: undefined,
};

interface BusinessSwitcherProps {
  collapsed: boolean;
  onSelect: (name: string) => void;
}

export default function BusinessSwitcher({ collapsed, onSelect }: BusinessSwitcherProps) {
  const {
    views,
    selectedView,
    selectedName,
    runtimeItems,
    runtimeActive,
    switchingName,
    runtimeFor,
  } = useBusinesses();
  const busy = Boolean(switchingName);

  const statusFor = (name: string): BusinessStatus => {
    const runtime = runtimeFor(name);
    if (!runtime) return 'unknown';
    if (runtime.error_code) return 'invalid';
    return runtime.name === runtimeActive ? 'active' : 'installed';
  };

  const items: MenuProps['items'] = views.map((view) => {
    const status = statusFor(view.name);
    return {
      key: view.name,
      disabled: status === 'invalid',
      label: (
        <span className="business-switcher-option">
          <span className="business-switcher-option__name">{view.displayName}</span>
          <Tag bordered={false} color={STATUS_COLOR[status]}>
            {STATUS_LABEL[status]}
          </Tag>
        </span>
      ),
    };
  });

  const orphanItems: MenuProps['items'] = runtimeItems
    .filter((item) => !views.some((view) => view.name === item.name))
    .map((item) => ({
      key: item.name,
      disabled: true,
      label: (
        <span className="business-switcher-option">
          <span className="business-switcher-option__name">
            {item.display_name ?? item.name}
          </span>
          <Tag bordered={false}>视图未接入</Tag>
        </span>
      ),
    }));

  const trigger = (
    <button
      type="button"
      className="app-business-switcher"
      aria-label={`切换业务，当前 ${selectedView?.displayName ?? '未选择业务'}`}
      aria-haspopup="menu"
      aria-busy={busy}
      disabled={busy}
    >
      <span className="app-business-switcher__icon">
        {selectedView ? iconByName[selectedView.icon] : iconByName.appstore}
      </span>
      {!collapsed && (
        <span className="app-business-switcher__copy">
          <span className="app-business-switcher__eyebrow">当前业务</span>
          <strong>{selectedView?.displayName ?? '未选择业务'}</strong>
        </span>
      )}
      {!collapsed && <DownOutlined className="app-business-switcher__chevron" />}
    </button>
  );

  return (
    <div
      className={`app-business-switcher-wrap${
        collapsed ? ' app-business-switcher-wrap--collapsed' : ''
      }`}
    >
      <Dropdown
        trigger={['click']}
        placement="bottomLeft"
        disabled={busy}
        menu={{
          items: [...items, ...orphanItems],
          selectable: true,
          selectedKeys: selectedName ? [selectedName] : [],
          onClick: ({ key }) => onSelect(key),
        }}
      >
        {collapsed
          ? <Tooltip title={selectedView?.displayName ?? '切换业务'} placement="right">{trigger}</Tooltip>
          : trigger}
      </Dropdown>
    </div>
  );
}
