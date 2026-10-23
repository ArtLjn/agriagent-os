import { useEffect, useState } from 'react';
import { Alert, Button, Empty, Spin } from 'antd';
import { ArrowRightOutlined, CloudOutlined, EnvironmentOutlined, FieldTimeOutlined, FileTextOutlined, ReloadOutlined, TeamOutlined } from '@ant-design/icons';
import * as dashboardApi from '../../api/dashboard';
import { PageShell } from '../../components/PageShell';
import './dashboard.css';

const currencyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency', currency: 'CNY', maximumFractionDigits: 2,
});

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState<dashboardApi.DashboardSummary | null>(null);
  const [error, setError] = useState('');

  const loadData = async (force = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      setSummary(await dashboardApi.getSummary());
    } catch {
      // 刷新失败保留上次成功的快照，避免经营数据整页消失。
      setError('农场概览加载失败，请重试（DASHBOARD_LOAD_FAILED）');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { void loadData(); }, []);

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!summary) return error
    ? <Alert type="error" message={error} action={<Button onClick={() => void loadData()}>重试</Button>} />
    : <Empty description="暂无农场概览数据" />;

  const { weather_today: weather, workers_summary: workers, cost_summary: costs } = summary;
  const balance = costs.month_income - costs.month_cost;
  // 收支对比仅表示当月金额占比，不暗示接口未提供的历史趋势。
  const moneyScale = Math.max(Math.abs(costs.month_income), Math.abs(costs.month_cost), 1);

  return (
    <div className="farm-dashboard">
      <PageShell title="农场仪表板" description="把田间进展与经营状况，放在同一张桌面上。" actions={
        <div className="dashboard-actions"><time>{summary.today}</time><Button icon={<ReloadOutlined />} loading={refreshing} onClick={() => void loadData(true)}>刷新</Button></div>
      }>
        {error && <Alert className="dashboard-error" type="warning" showIcon message={error} description="以下保留上次成功加载的数据。" />}
        <section className="dashboard-overview" aria-label="农场经营概览">
          <div className="dashboard-overview__intro">
            <span className="dashboard-eyebrow">田掌柜 · 农场经营概览</span>
            <h2>{summary.name}</h2>
            <p><EnvironmentOutlined /> {summary.location || '位置未设置'}</p>
            <a href="/cycles">查看田间进展 <ArrowRightOutlined /></a>
          </div>
          <div className="dashboard-profit"><span>年度利润</span><strong>{currencyFormatter.format(costs.year_profit)}</strong><small>本年度累计收入 − 累计成本</small></div>
          <div className="dashboard-overview__balance"><span>本月结余</span><strong>{currencyFormatter.format(balance)}</strong><small>本月收入 − 本月成本</small></div>
        </section>

        <div className="dashboard-metrics">
          <a href="/cycles" className="dashboard-metric"><FieldTimeOutlined /><span>进行中周期<strong>{summary.active_cycles.length}<small> 个</small></strong><em>关注当前种植阶段</em></span><ArrowRightOutlined /></a>
          <a href="/logs" className="dashboard-metric"><FileTextOutlined /><span>近期农事日志<strong>{summary.recent_logs_count}<small> 条</small></strong><em>最近 7 天的田间记录</em></span><ArrowRightOutlined /></a>
          <div className="dashboard-metric"><TeamOutlined /><span>活跃工人<strong>{workers.active}<small> / {workers.total} 人</small></strong><em>当前农场用工概况</em></span></div>
        </div>

        <div className="dashboard-grid">
          <section className="dashboard-panel dashboard-cycles">
            <header><div><span className="dashboard-eyebrow">田间管理</span><h2>进行中的种植周期</h2></div><a href="/cycles">全部周期 <ArrowRightOutlined /></a></header>
            {summary.active_cycles.length ? <div className="dashboard-cycle-list">
              {summary.active_cycles.map(cycle => <a className="dashboard-cycle" href={`/cycles/${cycle.cycle_id}`} key={cycle.cycle_id}>
                <span className="dashboard-cycle__icon"><FieldTimeOutlined /></span>
                <span className="dashboard-cycle__name"><strong>{cycle.crop}</strong><small>{cycle.field_name || '地块未设置'} · {cycle.area_mu == null ? '面积未记录' : `${cycle.area_mu} 亩`}</small></span>
                <span className="dashboard-stage">{cycle.current_stage || '阶段待确认'}</span>
                <span className="dashboard-cycle__date">{cycle.start_date ? `${cycle.start_date} 开始` : '开始日期未设置'}</span><ArrowRightOutlined />
              </a>)}
            </div> : <Empty description="暂无进行中的种植周期" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </section>

          <section className="dashboard-panel dashboard-weather">
            <header><div><span className="dashboard-eyebrow">田间环境</span><h2>今日天气</h2></div><a href="/weather">天气详情 <ArrowRightOutlined /></a></header>
            {weather ? <><div className="dashboard-weather__main"><CloudOutlined /><div><strong>{weather.min_c}° — {weather.max_c}°</strong><span>{weather.desc}</span></div></div><div className="dashboard-weather__details"><div><span>降水</span><strong>{weather.precip_mm} <small>mm</small></strong></div><div><span>风速</span><strong>{weather.wind_mps} <small>m/s</small></strong></div></div></> : <Empty description="暂无天气数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </section>

          <section className="dashboard-panel">
            <header><div><span className="dashboard-eyebrow">经营账本</span><h2>本月收支</h2></div><a href="/costs">查看账本 <ArrowRightOutlined /></a></header>
            <div className="dashboard-money"><span>本月收入</span><strong>{currencyFormatter.format(costs.month_income)}</strong><div><i style={{ width: `${Math.abs(costs.month_income) / moneyScale * 100}%` }} /></div></div>
            <div className="dashboard-money dashboard-money--cost"><span>本月成本</span><strong>{currencyFormatter.format(costs.month_cost)}</strong><div><i style={{ width: `${Math.abs(costs.month_cost) / moneyScale * 100}%` }} /></div></div>
            <div className="dashboard-wages"><span>待结工资</span><strong>{currencyFormatter.format(workers.unsettled_wages)}</strong></div>
          </section>

          <section className="dashboard-panel">
            <header><div><span className="dashboard-eyebrow">最近 7 天</span><h2>农事动态</h2></div><a href="/logs">全部记录 <ArrowRightOutlined /></a></header>
            {summary.recent_logs_preview.length ? <ul className="dashboard-activity">{summary.recent_logs_preview.map(log => <li key={log.id}><span className="dashboard-activity__dot" /><div><strong>{log.operation_type}</strong><p>{log.note || '未填写备注'}</p></div><time>{log.operation_date || '日期未记录'}</time></li>)}</ul> : <Empty description="近 7 天暂无农事记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
          </section>
        </div>
      </PageShell>
    </div>
  );
}
