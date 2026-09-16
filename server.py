"""
AutoTyper License Server v4.0
"""

from flask import Flask, request, jsonify
import hashlib
import hmac
import json
import random
import string
import smtplib
import sqlite3
import os
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Config ─────────────────────────────────────────────────────────────────────
SECRET         = "AutoTyper@2024#Sanjiv$Secure!Key"
GMAIL_ADDRESS  = "autotyper.keys@gmail.com"
GMAIL_PASSWORD = "yfjaevrshnmuicac"
DB_PATH        = "/tmp/licenses.db"

# ── App ────────────────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Database ───────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        email TEXT NOT NULL,
        order_id TEXT UNIQUE,
        device_id TEXT,
        created_at TEXT NOT NULL,
        activated INTEGER DEFAULT 0,
        activated_at TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS trials (
        device_id TEXT PRIMARY KEY,
        start_time TEXT NOT NULL,
        ip_address TEXT
    )''')
    conn.commit()
    return conn

# ── License Key ────────────────────────────────────────────────────────────────
def generate_key():
    chars = string.ascii_uppercase + string.digits
    segments = [''.join(random.choices(chars, k=5)) for _ in range(4)]
    raw_key = '-'.join(segments)
    sig = hmac.new(SECRET.encode(), raw_key.encode(), hashlib.sha256).hexdigest()[:8].upper()
    return f"{raw_key}-{sig}"

def validate_key(full_key):
    try:
        parts = full_key.strip().upper().split('-')
        if len(parts) != 5:
            return False
        raw_key = '-'.join(parts[:4])
        sig = parts[4]
        expected = hmac.new(SECRET.encode(), raw_key.encode(), hashlib.sha256).hexdigest()[:8].upper()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False

# ── Email ──────────────────────────────────────────────────────────────────────
def send_license_email(email, license_key, order_id):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Your AutoTyper License Key"
        msg['From']    = f"AutoTyper <{GMAIL_ADDRESS}>"
        msg['To']      = email

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
          <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #0078d4, #00b4d8); padding: 30px; text-align: center;">
              <h1 style="color: white; margin: 0;">AutoTyper</h1>
              <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0;">Thank you for your purchase!</p>
            </div>
            <div style="padding: 30px;">
              <h2 style="color: #1a1a2e;">Your License Key</h2>
              <div style="background: #1a1a2e; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <code style="color: #00d4ff; font-size: 20px; letter-spacing: 2px; font-weight: bold;">{license_key}</code>
              </div>
              <h3 style="color: #1a1a2e;">How to Activate:</h3>
              <ol style="color: #555; line-height: 1.8;">
                <li>Open AutoTyper.exe</li>
                <li>Enter your key when prompted</li>
                <li>Click Activate</li>
                <li>Done! Full access unlocked forever</li>
              </ol>
              <div style="background: #f0f7ff; border-left: 4px solid #0078d4; padding: 12px 16px; border-radius: 4px; margin: 20px 0;">
                <p style="margin: 0; color: #555; font-size: 14px;">
                  This key works on 1 device only. Need to transfer? Reply to this email.
                </p>
              </div>
              <p style="color: #555;">Order ID: {order_id}</p>
              <p style="color: #555;">Need help? Reply to this email!</p>
            </div>
            <div style="background: #f5f5f5; padding: 20px; text-align: center; border-top: 1px solid #eee;">
              <p style="color: #999; font-size: 13px; margin: 0;">AutoTyper - One-time purchase - Lifetime license - 1 device</p>
            </div>
          </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, email, msg.as_string())
        print(f"Email sent to {email}")
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

def send_email_async(email, key, order_id):
    thread = threading.Thread(target=send_license_email, args=(email, key, order_id))
    thread.daemon = True
    thread.start()

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "AutoTyper License Server running!", "version": "4.0"})

@app.route('/webhook/gumroad', methods=['POST'])
def gumroad_webhook():
    try:
        data = request.form.to_dict()
        if not data:
            data = request.get_json(silent=True) or {}

        print(f"Webhook: {json.dumps(data)}")

        email    = data.get('email', '') or data.get('buyer_email', '')
        order_id = data.get('sale_id', '') or data.get('order_id', 'no_id')

        if not email:
            return jsonify({"error": "No email"}), 200

        conn = get_db()
        existing = conn.execute('SELECT key FROM licenses WHERE order_id = ?', (order_id,)).fetchone()
        if existing:
            conn.close()
            return jsonify({"status": "already_processed"}), 200

        key = generate_key()
        conn.execute(
            'INSERT INTO licenses (key, email, order_id, created_at) VALUES (?, ?, ?, ?)',
            (key, email, order_id, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        send_email_async(email, key, order_id)

        print(f"License issued: {key} to {email}")
        return jsonify({"status": "success", "key": key}), 200

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 200

@app.route('/validate', methods=['POST'])
def validate():
    try:
        data      = request.get_json()
        key       = data.get('key', '').strip().upper()
        device_id = data.get('device_id', '')

        if not validate_key(key):
            return jsonify({"valid": False, "reason": "Invalid key"}), 200

        conn = get_db()
        row = conn.execute('SELECT device_id, activated FROM licenses WHERE key = ?', (key,)).fetchone()

        if not row:
            conn.close()
            return jsonify({"valid": False, "reason": "Key not found"}), 200

        stored_device, activated = row

        if not activated:
            conn.execute(
                'UPDATE licenses SET device_id=?, activated=1, activated_at=? WHERE key=?',
                (device_id, datetime.now().isoformat(), key)
            )
            conn.commit()
            conn.close()
            return jsonify({"valid": True, "message": "Activated!"}), 200

        conn.close()
        if stored_device == device_id:
            return jsonify({"valid": True, "message": "Licensed"}), 200
        else:
            return jsonify({"valid": False, "reason": "Key used on another device"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trial/check', methods=['POST'])
def trial_check():
    try:
        data      = request.get_json()
        device_id = data.get('device_id', '')

        if not device_id:
            return jsonify({"allowed": False}), 200

        conn = get_db()
        row = conn.execute('SELECT start_time FROM trials WHERE device_id = ?', (device_id,)).fetchone()

        if row:
            hours_used = (datetime.now() - datetime.fromisoformat(row[0])).total_seconds() / 3600
            conn.close()
            return jsonify({"allowed": hours_used < 48, "hours_used": round(hours_used, 1)}), 200
        else:
            conn.execute(
                'INSERT INTO trials (device_id, start_time, ip_address) VALUES (?, ?, ?)',
                (device_id, datetime.now().isoformat(), request.remote_addr)
            )
            conn.commit()
            conn.close()
            return jsonify({"allowed": True, "hours_used": 0}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/licenses', methods=['GET'])
def list_licenses():
    if request.args.get('secret') != 'autotyper_admin_2024':
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    rows = conn.execute(
        'SELECT key, email, order_id, created_at, activated FROM licenses ORDER BY created_at DESC'
    ).fetchall()
    conn.close()

    return jsonify({
        "total": len(rows),
        "licenses": [{"key": r[0], "email": r[1], "order_id": r[2],
                      "created_at": r[3], "activated": bool(r[4])} for r in rows]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
