import { useMemo } from 'react';
import { Alert, Button, Empty, Tag } from 'antd';
import {
  ArrowRightOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PageShell, StateBlock } from '../../components/PageShell';
import { useBusinesses } from '../../businesses/businessContext';
import type { BusinessRuntimeItem } from '../../api/businesses';
import type { BusinessView } from '../../businesses/registry';
import { iconByName } from '../../layouts/menuIcons';
import './business-center.css';

type BusinessStatus = 'active' | 'installed' | 'invalid' | 'unknown';

const STATUS_LABEL: Record<BusinessStatus, string> = {
  active: '当前启用',
  installed: '已安装未启用',
  invalid: '清单异常',
  unknown: '状态未知',
};

const STATUS_COLOR: Record<BusinessStatus, string | undefined> = {
  active: 'success',
  installed: 'warning',
  invalid: 'error',
  unknown: undefined,
};

function statusFor(
  runtime: BusinessRuntimeItem | undefined,
  runtimeActive: string | null,
): BusinessStatus {
  if (!runtime) return 'unknown';
  if (runtime.error_code) return 'invalid';
  return runtime.name === runtimeActive ? 'active' : 'installed';
}

function StatusTag({ status }: { status: BusinessStatus }) {
  return (
    <Tag bordered={false} color={STATUS_COLOR[status]}>
      {STATUS_LABEL[status]}
    </Tag>
  );
}

interface BusinessCard {
  name: string;
  runtime?: BusinessRuntimeItem;
  view?: BusinessView;
  status: BusinessStatus;
}

export default function BusinessCenter() {
  const navigate = useNavigate();
  const {
    views,
    selectedView,
    selectedName,
    runtimeItems,
    runtimeActive,
    loading,
    switchingName,
    error,
    selectBusiness,
    refresh,
    runtimeFor,
  } = useBusinesses();

  const cards = useMemo<BusinessCard[]>(() => {
    const installed = runtimeItems.map((runtime) => ({
      name: runtime.name,
      runtime,
      view: views.find((view) => view.name === runtime.name),
      status: statusFor(runtime, runtimeActive),
    }));
    const offline = views
      .filter((view) => !runtimeItems.some((item) => item.name === view.name))
      .map((view) => ({
        name: view.name,
        view,
        status: 'unknown' as const,
      }));
    return [...installed, ...offline];
  }, [runtimeActive, runtimeItems, views]);

  const activeCount = runtimeItems.filter(
    (item) => item.name === runtimeActive && !item.error_code,
  ).length;
  const selectedRuntime = selectedView ? runtimeFor(selectedView.name) : undefined;
  const selectedStatus = statusFor(selectedRuntime, runtimeActive);
  const canEnter = (name: string, status: BusinessStatus) => (
    status !== 'invalid' && (!runtimeActive || name === runtimeActive)
  );
  const selectedCanEnter = Boolean(
    selectedView && canEnter(selectedView.name, selectedStatus),
  );
  const entryCount = selectedView
    ? selectedView.groups.reduce((total, group) => total + group.children.length, 0)
    : 0;

  return (
    <PageShell
      title="业务中心"
      description="统一查看已接入的业务，并切换当前 Agent 运行的业务插件。切换在当前进程内生效，重启后恢复部署配置。"
    >
      {error && (
        <Alert
          className="business-center__error"
          type="warning"
          showIcon
          message={error}
          description="导航仍按管理端注册的业务展示；请确认 Agent 服务可用后重试。"
          action={<Button size="small" onClick={refresh}>重试</Button>}
        />
      )}

      {selectedView ? (
        <section className="business-center__hero" aria-label="当前业务视角">
          <div className="business-center__identity">
            <span className="business-center__icon">
              {iconByName[selectedView.icon]}
            </span>
            <div className="business-center__intro">
              <span className="business-center__eyebrow">当前业务</span>
              <div className="business-center__title-row">
                <h2>{selectedView.displayName}</h2>
                <StatusTag status={selectedStatus} />
              </div>
              <p>{selectedView.description}</p>
              <div className="business-center__meta">
                <span>插件 {selectedView.name}</span>
                <span>技能目录 {selectedRuntime?.skill_count ?? '—'}</span>
                <span>{entryCount} 个业务入口</span>
              </div>
            </div>
          </div>
          <div className="business-center__aside">
            <div className="business-center__stats">
              <div>
                <strong>{error ? '—' : runtimeItems.length}</strong>
                <span>已安装业务</span>
              </div>
              <div>
                <strong>{error ? '—' : activeCount}</strong>
                <span>当前启用</span>
              </div>
            </div>
            <div className="business-center__actions">
              <Button icon={<ReloadOutlined />} loading={loading} onClick={refresh}>
                刷新清单
              </Button>
              <Button
                type="primary"
                icon={<ArrowRightOutlined />}
                disabled={!selectedCanEnter}
                onClick={() => navigate(selectedView.homePath)}
              >
                进入业务
              </Button>
            </div>
          </div>
        </section>
      ) : (
        <Empty description="管理端尚未注册任何业务视图" />
      )}

      <section className="business-center__section">
        <div className="business-center__section-head">
          <h3>已安装业务</h3>
          <span>清单来自 Agent 的 businesses 目录，状态以当前进程启用的业务为准。</span>
        </div>
        <StateBlock loading={loading && cards.length === 0} empty={!loading && cards.length === 0} emptyText="暂无业务">
          <div className="business-center__grid">
            {cards.map((card) => {
              const title = card.view?.displayName
                ?? card.runtime?.display_name
                ?? card.name;
              const description = card.view?.description
                ?? card.runtime?.description
                ?? '该业务清单暂不可用。';
              const isSelected = card.name === selectedName;
              const isActive = card.status === 'active';
              const canSwitch = Boolean(card.view)
                && card.status !== 'invalid'
                && !(isSelected && isActive);
              const canOpen = Boolean(card.view)
                && canEnter(card.name, card.status);
              return (
                <article
                  key={card.name}
                  className={`business-center__card${isSelected ? ' business-center__card--selected' : ''}`}
                  data-testid={`business-card-${card.name}`}
                >
                  <div className="business-center__card-head">
                    <span className="business-center__card-icon">
                      {card.view ? iconByName[card.view.icon] : iconByName.appstore}
                    </span>
                    <div className="business-center__card-title">
                      <strong>{title}</strong>
                      <span>{card.name}</span>
                    </div>
                    <div className="business-center__card-tags">
                      <StatusTag status={card.status} />
                      {!card.view && <Tag bordered={false}>视图未接入</Tag>}
                    </div>
                  </div>
                  <p className="business-center__card-description">
                    {description}
                  </p>
                  <div className="business-center__card-meta">
                    <span>技能目录 {card.runtime?.skill_count ?? '—'}</span>
                    {!card.view && <span>管理端视图未接入</span>}
                    {card.runtime?.error_code && <span>{card.runtime.error_code}</span>}
                  </div>
                  <div className="business-center__card-actions">
                    <Button
                      size="small"
                      loading={switchingName === card.name}
                      disabled={!canSwitch || Boolean(switchingName)}
                      onClick={() => {
                        void selectBusiness(card.name);
                      }}
                    >
                      {isSelected && isActive
                        ? '当前视角'
                        : isSelected
                          ? '启用此业务'
                          : '切换业务'}
                    </Button>
                    <Button
                      size="small"
                      type="primary"
                      disabled={!canOpen}
                      onClick={() => {
                        if (card.view) navigate(card.view.homePath);
                      }}
                    >
                      进入业务
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        </StateBlock>
      </section>

      <section className="business-center__onboarding">
        <div>
          <h3>接入新业务</h3>
          <p>后端按目录发现业务，管理端按注册表提供导航；两边使用同一个业务名。</p>
        </div>
        <ol>
          <li><code>businesses/&lt;name&gt;/</code> 提供 <code>plugin.yaml</code>、<code>prompts/</code> 和 <code>skills/</code>。</li>
          <li>部署时设置 <code>PLUGINS__ACTIVE=&lt;name&gt;</code>，一次只启用一个业务。</li>
          <li>在 <code>src/businesses/registry.ts</code> 注册该业务的导航与入口。</li>
        </ol>
      </section>
    </PageShell>
  );
}
