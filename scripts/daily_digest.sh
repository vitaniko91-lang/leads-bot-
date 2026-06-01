#!/bin/sh
# Daily health digest for the owner — gathers 24h stats from journalctl + bot.db
# and pings the existing aiogram bot via Telegram Bot API directly.
#
# Run by /etc/cron.d/leads-bot-daily-digest at 19:00 UTC (22:00 Europe/Kyiv).
# No SMTP / no OAuth — reuses BOT_TOKEN and OWNER_TG_ID from /opt/leads-bot/.env.

set -e

ENV_FILE="/opt/leads-bot/.env"
DB="/opt/leads-bot/data/bot.db"

BOT_TOKEN=$(grep '^BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- | sed 's/^"//;s/"$//')
OWNER_ID=$(grep '^OWNER_TG_ID=' "$ENV_FILE" | head -1 | cut -d= -f2- | sed 's/^"//;s/"$//')

if [ -z "$BOT_TOKEN" ] || [ -z "$OWNER_ID" ]; then
    echo "ERROR: BOT_TOKEN or OWNER_TG_ID missing in $ENV_FILE" >&2
    exit 1
fi

ACTIVE=$(systemctl is-active leads-bot)
RESTARTS=$(systemctl show leads-bot -p NRestarts --value)
SINCE=$(systemctl show leads-bot -p ActiveEnterTimestamp --value | cut -d' ' -f2-3)
MEM_FREE=$(free -m | awk '/Mem:/ {print $7}')
LOAD=$(cut -d' ' -f1-3 /proc/loadavg)

# event counts from journal
LAST24=$(journalctl -u leads-bot --since "24 hours ago" --no-pager -o cat)
STARTS=$(printf '%s\n' "$LAST24" | grep -c 'Starting leads-bot' || true)
SHUT=$(printf '%s\n' "$LAST24" | grep -c 'Shutdown complete' || true)
FILT=$(printf '%s\n' "$LAST24" | grep -c 'filtered out' || true)
DRAFT=$(printf '%s\n' "$LAST24" | grep -c 'Drafted reply' || true)
ERR=$(printf '%s\n' "$LAST24" | grep -cE 'Exception|Traceback|Invalid JSON from Claude' || true)
HCF=$(printf '%s\n' "$LAST24" | grep -c 'Healthcheck failed' || true)

# DB stats via stdlib python (no leads_bot import — light on memory)
DB_STATS=$(/usr/bin/python3 - <<PY
import sqlite3
c = sqlite3.connect('$DB')
recent = dict(c.execute("SELECT status, COUNT(*) FROM leads WHERE posted_at > datetime('now','-24 hours') GROUP BY status"))
total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
active = c.execute("SELECT COUNT(*) FROM sources WHERE status='active'").fetchone()[0]
top = c.execute("""
  SELECT substr(s.title,1,30), COUNT(l.id)
  FROM sources s LEFT JOIN leads l
    ON l.source_id=s.id AND l.posted_at > datetime('now','-24 hours')
  WHERE s.status='active'
  GROUP BY s.id ORDER BY 2 DESC LIMIT 4
""").fetchall()
print(f"leads_24h: {recent or '{}'}")
print(f"leads_total: {total} | active_sources: {active}")
print("per-source 24h:")
for title, n in top:
    print(f"  {n:>3}  {title}")
PY
)

MSG=$(cat <<EOF
📊 leads-bot daily digest

Service: $ACTIVE  | restarts=$RESTARTS  since=$SINCE
Resources: mem_free=${MEM_FREE}MB  load=$LOAD

Last 24h:
• starts=$STARTS  shutdowns=$SHUT
• filtered=$FILT  drafted=$DRAFT
• errors=$ERR  healthcheck_fail=$HCF

DB:
$DB_STATS
EOF
)

# Send. Use --data-urlencode so multi-line text and special chars work.
curl -s -o /dev/null -w "%{http_code}\n" \
    "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${OWNER_ID}" \
    --data-urlencode "text=${MSG}" \
    --data-urlencode "disable_web_page_preview=true"
