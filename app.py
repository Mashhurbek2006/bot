"""
MikroTik Router Telegram Bot - Render.com Optimized
Webhook-based Flask bot for managing MikroTik RouterOS
"""

from flask import Flask, request, jsonify
import requests
import os
import logging
from routeros_api import RouterOsApiPool

# ============== Configuration ==============
app = Flask(__name__)

# Environment variables
BOT_TOKEN = os.getenv('8166723280:AAHLh5VAs2hxWOHdL7Eyg7I5ypSz-soeSlQ')
ROUTER_HOST = os.getenv('192.168.88.1')
ROUTER_PORT = int(os.getenv('8728'))
ROUTER_USER = os.getenv('admin')
ROUTER_PASS = os.getenv('Mashhurbek_2006@')
ADMIN_IDS = set(map(int, os.getenv('ADMIN_IDS', '5469081053').split(','))) if os.getenv('ADMIN_IDS') else set()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RouterOS API Pool
try:
    pool = RouterOsApiPool(
        ROUTER_HOST,
        username=ROUTER_USER,
        password=ROUTER_PASS,
        port=ROUTER_PORT,
        use_ssl=False,
        plaintext_login=True
    )
    logger.info("RouterOS API initialized")
except Exception as e:
    logger.error(f"RouterOS API error: {e}")
    pool = None

# ============== Keyboards ==============
KB = {
    'keyboard': [
        [{'text': '📊 Speed'}, {'text': '📱 Devices'}],
        [{'text': '⚙️ Status'}, {'text': '🔥 Top5'}],
        [{'text': '🗂️ Backup'}, {'text': '📝 Logs'}],
        [{'text': '📈 Traffic'}, {'text': '❓ Help'}]
    ],
    'resize_keyboard': True
}

ADMIN_KB = {
    'keyboard': [
        [{'text': '📊 Speed'}, {'text': '📱 Devices'}],
        [{'text': '⚙️ Status'}, {'text': '🔥 Top5'}],
        [{'text': '🗂️ Backup'}, {'text': '📝 Logs'}],
        [{'text': '📈 Traffic'}, {'text': '🚫 Firewall'}],
        [{'text': '🔒 Block IP'}, {'text': '✅ Unblock IP'}],
        [{'text': '💻 Terminal'}, {'text': '📋 Checklist'}],
        [{'text': '❓ Help'}]
    ],
    'resize_keyboard': True
}

# ============== Helpers ==============
def format_bytes(b):
    """Convert bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"

def is_admin(chat_id):
    """Check if user is admin"""
    return not ADMIN_IDS or chat_id in ADMIN_IDS

def send_message(chat_id, text, keyboard=None):
    """Send Telegram message"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        if keyboard:
            payload['reply_markup'] = keyboard
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Send message error: {e}")

# ============== Commands ==============
def cmd_speed(chat_id):
    """Get bandwidth usage with device names"""
    if not pool:
        return "❌ Router offline"
    try:
        api = pool.get_api()
        
        # Get all DHCP leases to map IPs to device names
        leases = api.get_resource('/ip/dhcp-server/lease').call('print')
        device_names = {}
        for lease in leases:
            ip = lease.get('address', '')
            name = lease.get('comment', '').strip()
            if not name:
                name = lease.get('host-name', '').strip()
            if name and ip:
                device_names[ip] = name
        
        # Get queues
        q = api.get_resource('/queue/simple').call('print')
        if not q:
            return "📊 No bandwidth data"
        
        msg = "📊 Current Bandwidth:\n\n"
        for i, item in enumerate(q[:10], 1):
            queue_name = item.get('name', '?')
            rate = item.get('rate', '0/0')
            
            # Try to get device name from target IP
            target = item.get('target', '')
            display_name = device_names.get(target, queue_name)
            
            msg += f"{i}. {display_name}: {rate}\n"
        return msg
    except Exception as e:
        logger.error(f"Speed error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_devices(chat_id):
    """Get DHCP devices"""
    if not pool:
        return "❌ Router offline"
    try:
        api = pool.get_api()
        l = api.get_resource('/ip/dhcp-server/lease').call('print')
        a = [i for i in l if i.get('status') == 'bound'][:15]
        if not a:
            return "📱 No devices connected"
        msg = f"📱 Connected Devices ({len(a)}):\n\n"
        for i, d in enumerate(a, 1):
            # Get device name from comment, or use hostname, or fallback to MAC
            name = d.get('comment', '').strip()
            if not name:
                name = d.get('host-name', '').strip()
            if not name:
                name = d.get('mac-address', '?')[:17]
            
            ip = d.get('address', '?')
            msg += f"{i}. {name} → {ip}\n"
        return msg
    except Exception as e:
        logger.error(f"Devices error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_status(chat_id):
    """Get router status"""
    if not pool:
        return "❌ Router offline"
    try:
        api = pool.get_api()
        r = api.get_resource('/system/resource').call('print')[0]
        msg = "⚙️ Router Status:\n\n"
        msg += f"CPU: {r.get('cpu-load','?')}%\n"
        msg += f"Uptime: {r.get('uptime','?')}\n"
        msg += f"Memory: {r.get('total-memory','?')}\n"
        msg += f"Version: {r.get('version','?')}\n"
        return msg
    except Exception as e:
        logger.error(f"Status error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_top5(chat_id):
    """Get top 5 consumers with device names"""
    if not pool:
        return "❌ Router offline"
    try:
        api = pool.get_api()
        
        # Get all DHCP leases to map IPs to device names
        leases = api.get_resource('/ip/dhcp-server/lease').call('print')
        device_names = {}
        for lease in leases:
            ip = lease.get('address', '')
            name = lease.get('comment', '').strip()
            if not name:
                name = lease.get('host-name', '').strip()
            if name and ip:
                device_names[ip] = name
        
        # Get queues and sort by bandwidth
        q = api.get_resource('/queue/simple').call('print')
        t = []
        for i in q:
            try:
                rate = i.get('rate', '0/0')
                b = int(rate.split('/')[1]) if '/' in rate else 0
                queue_name = i.get('name', '?')
                target = i.get('target', '')
                # Use device name if available, otherwise queue name
                display_name = device_names.get(target, queue_name)
                t.append((display_name, b))
            except:
                pass
        
        t.sort(key=lambda x: x[1], reverse=True)
        if not t:
            return "🔥 No data"
        msg = "🔥 Top 5 Consumers:\n\n"
        for idx, (n, b) in enumerate(t[:5], 1):
            msg += f"{idx}. {n}: {format_bytes(b)}\n"
        return msg
    except Exception as e:
        logger.error(f"Top5 error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_traffic(chat_id):
    """Get interface traffic"""
    if not pool:
        return "❌ Router offline"
    try:
        api = pool.get_api()
        ifaces = api.get_resource('/interface').call('print')
        if not ifaces:
            return "📈 No interfaces"
        msg = "📈 Interface Traffic:\n\n"
        for iface in ifaces[:8]:
            name = iface.get('name', '?')
            rx = int(iface.get('rx-byte', '0'))
            tx = int(iface.get('tx-byte', '0'))
            msg += f"{name}: ↓{format_bytes(rx)} ↑{format_bytes(tx)}\n"
        return msg
    except Exception as e:
        logger.error(f"Traffic error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_backup(chat_id):
    """Create backup"""
    if not pool:
        return "❌ Router offline"
    if not is_admin(chat_id):
        return "🔒 Admin only"
    try:
        import time
        api = pool.get_api()
        name = f"bot-{int(time.time())}"
        api.get_resource('/system/backup').call('save', {'name': name})
        logger.warning(f"Backup created by {chat_id}: {name}")
        return f"✅ Backup: {name}.backup"
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_logs(chat_id):
    """Get system logs"""
    if not pool:
        return "❌ Router offline"
    try:
        api = pool.get_api()
        lg = api.get_resource('/log').call('print')
        if not lg:
            return "📝 No logs"
        msg = "📝 Last Logs:\n\n"
        for log in lg[-5:]:
            t = log.get('time', '?')
            m = log.get('message', '?')[:40]
            msg += f"[{t}] {m}\n"
        return msg
    except Exception as e:
        logger.error(f"Logs error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_firewall(chat_id):
    """Show firewall rules"""
    if not pool:
        return "❌ Router offline"
    if not is_admin(chat_id):
        return "🔒 Admin only"
    try:
        api = pool.get_api()
        rules = api.get_resource('/ip/firewall/filter').call('print')[:10]
        if not rules:
            return "🚫 No rules"
        msg = "🚫 Firewall Rules:\n\n"
        for i, r in enumerate(rules, 1):
            proto = r.get('protocol', 'any')
            action = r.get('action', '?').upper()
            comment = r.get('comment', 'rule')[:25]
            msg += f"{i}. [{action}] {proto}: {comment}\n"
        return msg
    except Exception as e:
        logger.error(f"Firewall error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_block(chat_id, ip):
    """Block IP address"""
    if not pool:
        return "❌ Router offline"
    if not is_admin(chat_id):
        return "🔒 Admin only"
    try:
        import re
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', ip):
            return "❌ Invalid IP"
        api = pool.get_api()
        api.get_resource('/ip/firewall/address-list').call('add', {
            'list': 'blocked',
            'address': ip,
            'comment': 'blocked-by-bot'
        })
        logger.warning(f"IP blocked by {chat_id}: {ip}")
        return f"🚫 Blocked {ip}"
    except Exception as e:
        logger.error(f"Block error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_unblock(chat_id, ip):
    """Unblock IP address"""
    if not pool:
        return "❌ Router offline"
    if not is_admin(chat_id):
        return "🔒 Admin only"
    try:
        api = pool.get_api()
        rules = api.get_resource('/ip/firewall/address-list').call('print')
        found = False
        for rule in rules:
            if rule.get('address') == ip and rule.get('list') == 'blocked':
                api.get_resource('/ip/firewall/address-list').call('remove', {'.id': rule['.id']})
                found = True
        if not found:
            return f"❌ {ip} not found"
        logger.warning(f"IP unblocked by {chat_id}: {ip}")
        return f"✅ Unblocked {ip}"
    except Exception as e:
        logger.error(f"Unblock error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_terminal(chat_id, command):
    """Execute terminal command on router"""
    if not pool:
        return "❌ Router offline"
    if not is_admin(chat_id):
        return "🔒 Admin only"
    
    # Block dangerous commands
    dangerous = ['reboot', 'reset', 'shutdown', 'remove', 'delete']
    if any(cmd in command.lower() for cmd in dangerous):
        logger.warning(f"Blocked dangerous command from {chat_id}: {command}")
        return "🔒 Dangerous command blocked. Use WebFig for system changes."
    
    try:
        api = pool.get_api()
        
        # Parse command path and parameters
        # Format: /system/resource or /ip/address print etc.
        parts = command.strip().split()
        if not parts:
            return "❌ Invalid command"
        
        path = parts[0]
        action = parts[1] if len(parts) > 1 else 'print'
        
        # Validate path starts with /
        if not path.startswith('/'):
            return "❌ Command must start with / (e.g., /system/resource)"
        
        # Execute command
        try:
            resource = api.get_resource(path)
            
            if action == 'print':
                result = resource.call('print')
                if isinstance(result, list):
                    if not result:
                        return f"No data from {path}"
                    msg = f"📟 {path}\n\n"
                    # Show first 5 results max
                    for i, item in enumerate(result[:5], 1):
                        msg += f"─ Entry {i}:\n"
                        for key, value in list(item.items())[:5]:
                            if key not in ['.id', '.path']:
                                msg += f"  {key}: {str(value)[:50]}\n"
                        msg += "\n"
                    if len(result) > 5:
                        msg += f"... and {len(result)-5} more entries"
                    return msg
                else:
                    return f"Result: {str(result)[:200]}"
            else:
                return f"❌ Action '{action}' not supported. Use: /path/to/resource print"
                
        except Exception as e:
            return f"❌ Command error: {str(e)[:100]}"
        
    except Exception as e:
        logger.error(f"Terminal error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_daily_checklist(chat_id):
    """Run daily monitoring checklist"""
    if not pool:
        return "❌ Router offline"
    if not is_admin(chat_id):
        return "🔒 Admin only"
    
    try:
        api = pool.get_api()
        msg = "📋 Daily System Checklist\n\n"
        
        # 1. System Health
        msg += "━━━━━ 🔧 SYSTEM HEALTH ━━━━━\n"
        try:
            resource = api.get_resource('/system/resource').call('print')[0]
            cpu = resource.get('cpu-load', '?')
            mem_total = int(resource.get('total-memory', 0))
            mem_free = int(resource.get('free-memory', 0))
            mem_used = mem_total - mem_free
            mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
            uptime = resource.get('uptime', '?')
            
            msg += f"✅ CPU Load: {cpu}%\n"
            msg += f"✅ Memory: {mem_percent:.1f}% used\n"
            msg += f"✅ Uptime: {uptime}\n"
            msg += f"✅ Version: {resource.get('version', '?')}\n\n"
        except Exception as e:
            msg += f"❌ Error: {str(e)[:50]}\n\n"
        
        # 2. Connected Devices
        msg += "━━━━━ 📱 CONNECTED DEVICES ━━━━━\n"
        try:
            leases = api.get_resource('/ip/dhcp-server/lease').call('print')
            bound = [l for l in leases if l.get('status') == 'bound']
            msg += f"✅ Connected: {len(bound)} devices\n"
            for device in bound[:3]:
                name = device.get('comment', device.get('host-name', 'Unknown'))
                ip = device.get('address', '?')
                msg += f"   • {name}: {ip}\n"
            if len(bound) > 3:
                msg += f"   ... and {len(bound)-3} more\n"
            msg += "\n"
        except Exception as e:
            msg += f"❌ Error: {str(e)[:50]}\n\n"
        
        # 3. Bandwidth Status
        msg += "━━━━━ 📊 BANDWIDTH STATUS ━━━━━\n"
        try:
            queues = api.get_resource('/queue/simple').call('print')
            active = [q for q in queues if q.get('rate', '0/0') != '0/0']
            msg += f"✅ Total Queues: {len(queues)}\n"
            msg += f"✅ Active Traffic: {len(active)} queues\n"
            
            # Top consumer
            if active:
                leases = api.get_resource('/ip/dhcp-server/lease').call('print')
                device_names = {}
                for lease in leases:
                    ip = lease.get('address', '')
                    name = lease.get('comment', '').strip()
                    if not name:
                        name = lease.get('host-name', '').strip()
                    if name and ip:
                        device_names[ip] = name
                
                top_rate = max([int(q.get('rate', '0/0').split('/')[1] or 0) for q in active], default=0)
                for q in active:
                    if int(q.get('rate', '0/0').split('/')[1] or 0) == top_rate:
                        target = q.get('target', '?')
                        name = device_names.get(target, q.get('name', '?'))
                        msg += f"✅ Top Consumer: {name}\n"
                        break
            msg += "\n"
        except Exception as e:
            msg += f"❌ Error: {str(e)[:50]}\n\n"
        
        # 4. Security Status
        msg += "━━━━━ 🔒 SECURITY ━━━━━\n"
        try:
            # Check firewall
            rules = api.get_resource('/ip/firewall/filter').call('print')
            msg += f"✅ Firewall Rules: {len(rules)} active\n"
            
            # Check address list (blocked IPs)
            blocked = api.get_resource('/ip/firewall/address-list').call('print')
            blocked_list = [b for b in blocked if b.get('list') == 'blocked']
            msg += f"✅ Blocked IPs: {len(blocked_list)}\n"
            
            # Check recent logs
            logs = api.get_resource('/log').call('print')
            critical = [l for l in logs if 'critical' in l.get('topics', '').lower()]
            msg += f"✅ Critical Logs: {len(critical)}\n\n"
        except Exception as e:
            msg += f"❌ Error: {str(e)[:50]}\n\n"
        
        # 5. Services
        msg += "━━━━━ 🌐 SERVICES ━━━━━\n"
        try:
            services = api.get_resource('/ip/service').call('print')
            enabled = [s for s in services if not s.get('disabled')]
            msg += f"✅ Services Enabled: {len(enabled)}\n"
            for svc in enabled[:4]:
                port = svc.get('port', '?')
                name = svc.get('name', '?')
                msg += f"   • {name}: {port}\n"
            msg += "\n"
        except Exception as e:
            msg += f"❌ Error: {str(e)[:50]}\n\n"
        
        # 6. Summary
        msg += "━━━━━ ✅ SUMMARY ━━━━━\n"
        msg += "All systems operational\n"
        msg += "Check details with /terminal command\n"
        
        return msg
        
    except Exception as e:
        logger.error(f"Daily checklist error: {e}")
        return f"❌ Error: {str(e)[:80]}"

def cmd_help(chat_id):
    """Show help"""
    admin = is_admin(chat_id)
    msg = "📚 MikroTik Bot Commands:\n\n"
    msg += "📊 Speed - Bandwidth\n"
    msg += "📱 Devices - DHCP list\n"
    msg += "⚙️ Status - Router info\n"
    msg += "🔥 Top5 - Top consumers\n"
    msg += "📈 Traffic - Interface stats\n"
    msg += "📝 Logs - System logs\n"
    if admin:
        msg += "\n🔒 Admin:\n"
        msg += "🗂️ Backup - Save config\n"
        msg += "🚫 Firewall - View rules\n"
        msg += "🔒 Block/Unblock IP\n"
        msg += "💻 Terminal - Run commands\n"
        msg += "📋 Checklist - Daily health check\n\n"
        msg += "Format:\n"
        msg += "block 192.168.1.100\n"
        msg += "terminal /system/resource\n"
    return msg

# ============== Main Webhook ==============
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Main webhook handler"""
    try:
        update = request.get_json(force=True)
    except:
        return jsonify({'ok': False})
    
    # Safety checks
    if 'message' not in update:
        return jsonify({'ok': True})
    
    msg = update['message']
    if 'text' not in msg or 'chat' not in msg:
        return jsonify({'ok': True})
    
    chat_id = msg['chat']['id']
    text = msg['text'].strip()
    
    logger.info(f"Message from {chat_id}: {text}")
    
    try:
        admin = is_admin(chat_id)
        keyboard = ADMIN_KB if admin else KB
        reply = ""
        
        # Main commands
        if text in ['Speed', '/speed', '📊 Speed']:
            reply = cmd_speed(chat_id)
        elif text in ['Devices', '/devices', '📱 Devices']:
            reply = cmd_devices(chat_id)
        elif text in ['Status', '/status', '⚙️ Status']:
            reply = cmd_status(chat_id)
        elif text in ['Top5', '/top5', '🔥 Top5']:
            reply = cmd_top5(chat_id)
        elif text in ['Traffic', '/traffic', '📈 Traffic']:
            reply = cmd_traffic(chat_id)
        elif text in ['Logs', '/logs', '📝 Logs']:
            reply = cmd_logs(chat_id)
        elif text in ['Backup', '/backup', '🗂️ Backup']:
            reply = cmd_backup(chat_id)
        elif text in ['Firewall', '/firewall', '🚫 Firewall']:
            reply = cmd_firewall(chat_id)
        elif text in ['Help', '/help', '❓ Help']:
            reply = cmd_help(chat_id)
        elif text in ['Terminal', '/terminal', '💻 Terminal']:
            reply = "💻 Terminal Mode\n\nSend commands like:\n/system/resource\n/ip/address print\n/interface print\n\nExample:\nterminal /system/resource"
        elif text in ['Checklist', '/checklist', '📋 Checklist']:
            reply = cmd_daily_checklist(chat_id)
        
        # Inline commands
        elif text.lower().startswith('block '):
            ip = text.split('block ', 1)[1].strip()
            reply = cmd_block(chat_id, ip)
        elif text.lower().startswith('unblock '):
            ip = text.split('unblock ', 1)[1].strip()
            reply = cmd_unblock(chat_id, ip)
        elif text.lower().startswith('terminal '):
            cmd = text.split('terminal ', 1)[1].strip()
            reply = cmd_terminal(chat_id, cmd)
        
        else:
            reply = cmd_help(chat_id)
        
        send_message(chat_id, reply, keyboard)
        return jsonify({'ok': True})
        
    except Exception as e:
        logger.error(f"Error: {e}")
        send_message(chat_id, "❌ Error occurred", KB)
        return jsonify({'ok': True})

# ============== Health Check ==============
@app.route('/health', methods=['GET'])
def health():
    """Health check for Render"""
    return jsonify({'status': 'ok'})

# ============== Main ==============
if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    logger.info(f"🤖 Bot starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
