#!/bin/bash
# coach_kb_watchdog.sh — 监控 Coach KB v1 站点健康
# launchd: com.aoxia.coach-kb-watchdog，每 5 分钟跑一次
set -euo pipefail

URL="https://www.ai-coach.com.cn/health"
STATE_FILE="$HOME/.cache/coach-kb-watchdog.state"
LOG="$HOME/.cache/coach-kb-watchdog.log"
mkdir -p "$(dirname "$STATE_FILE")"

now() { date '+%Y-%m-%d %H:%M:%S'; }
prev_state=$(cat "$STATE_FILE" 2>/dev/null || echo "ok")

# 双 check 防误报：第一次 down 后等 15s 再 ping 一次确认
check_once() { curl -sk -m 30 "$URL" 2>&1; }
body=$(check_once)
ok=$([ "$body" = '{"status":"ok"}' ] && echo "ok" || echo "down")

if [ "$ok" = "down" ]; then
    # 重要：不立刻报警/重启 —— 等 15s 再 ping 一次，避免扫站期 TLS 握手堵塞误判
    sleep 15
    body2=$(check_once)
    ok2=$([ "$body2" = '{"status":"ok"}' ] && echo "ok" || echo "down")
    if [ "$ok2" = "ok" ]; then
        echo "[$(now)] flaky probe (1st down, 2nd ok) - 忽略，不告警不重启" >> "$LOG"
        ok="ok"
    else
        body="1st: $body | 2nd: $body2"
    fi
fi

if [ "$ok" = "down" ] && [ "$prev_state" = "ok" ]; then
    # 双 check 都 down，真崩了 — 告警 + 重启
    echo "[$(now)] DOWN confirmed (double-check): $body" >> "$LOG"
    fix=$(ssh -i ~/.ssh/id_ed25519 -o ConnectTimeout=8 CoachPro_AI_Aoxia@111.230.233.145 'sudo docker restart coach-kb-backend coach-kb-caddy' 2>&1 | tail -2 || echo "ssh failed")
    "$HOME/.claude/scripts/feishu_notify.sh" "🚨 Coach KB 站点 DOWN — $body | 自愈尝试: $fix" 2>/dev/null || true
    echo "down" > "$STATE_FILE"
elif [ "$ok" = "ok" ] && [ "$prev_state" = "down" ]; then
    echo "[$(now)] RECOVERED" >> "$LOG"
    "$HOME/.claude/scripts/feishu_notify.sh" "✅ Coach KB 站点恢复" 2>/dev/null || true
    echo "ok" > "$STATE_FILE"
elif [ "$ok" = "ok" ]; then
    echo "ok" > "$STATE_FILE"
fi
