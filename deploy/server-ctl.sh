#!/usr/bin/env bash
# 服务器后端管理 — 启动/停止/重启/状态/日志（systemd）
# 用法:
#   bash deploy/server-ctl.sh start    # 启动
#   bash deploy/server-ctl.sh stop     # 停止
#   bash deploy/server-ctl.sh restart  # 重启
#   bash deploy/server-ctl.sh status   # 状态 + 最近日志
#   bash deploy/server-ctl.sh logs     # 查看日志（最近50行）
#   bash deploy/server-ctl.sh logs 100 # 查看最近100行
#   bash deploy/server-ctl.sh tail     # 实时跟踪日志
set -euo pipefail

SERVER="root@47.98.253.236"
SERVICE="farm-manager"
ACTION="${1:-status}"

usage() {
    echo "用法: bash deploy/server-ctl.sh <命令>"
    echo ""
    echo "命令:"
    echo "  start      启动后端服务"
    echo "  stop       停止后端服务"
    echo "  restart    重启后端服务"
    echo "  status     查看运行状态"
    echo "  logs [N]   查看最近 N 行日志（默认50）"
    echo "  tail       实时跟踪日志"
    exit 1
}

case "$ACTION" in
    start)
        echo "==> 启动后端服务..."
        ssh "${SERVER}" "systemctl start ${SERVICE} && echo '  ✅ 已启动' || echo '  ❌ 启动失败，查看: systemctl status ${SERVICE}'"
        ;;

    stop)
        echo "==> 停止后端服务..."
        ssh "${SERVER}" "systemctl stop ${SERVICE} && echo '  ✅ 已停止' || echo '  ❌ 停止失败'"
        ;;

    restart)
        echo "==> 重启后端服务..."
        ssh "${SERVER}" "systemctl restart ${SERVICE} && echo '  ✅ 已重启' || echo '  ❌ 重启失败'"
        ;;

    status)
        echo "==> 查看服务状态..."
        ssh "${SERVER}" "systemctl status ${SERVICE} --no-pager -l"
        ;;

    logs)
        LINES="${2:-50}"
        echo "==> 最近 ${LINES} 行日志..."
        ssh "${SERVER}" "journalctl -u ${SERVICE} -n ${LINES} --no-pager"
        ;;

    tail)
        echo "==> 实时跟踪日志 (Ctrl+C 退出)..."
        ssh "${SERVER}" "journalctl -u ${SERVICE} -f --no-pager"
        ;;

    *)
        usage
        ;;
esac
