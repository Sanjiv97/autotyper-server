"""
AutoTyper License Server
- Receives Gumroad webhooks
- Generates unique license keys
- Emails keys to customers
- Tracks all licenses in SQLite database
- Server-side trial tracking
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
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

app = Flask(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
SECRET          = "AutoTyper@2024#Sanjiv$Secure!Key"
GMAIL_ADDRESS   = "autotyper.keys@gmail.com"
GMAIL_PASSWORD  = "yfjaevrshnmuicac"   # App password (spaces removed)
GUMROAD_SECRET  = "your_gumroad_webhook_secret"  # Set after Gumroad setup
DB_PATH         = "licenses.db"
PRODUCT_NAME    = "AutoTyper"

# ── Database Setup ─────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT UNIQUE NOT NULL,
            email       TEXT NOT NULL,
            order_id    TEXT UNIQUE,
            device_id   TEXT,
            tier        TEXT DEFAULT "Basic",
            created_at  TEXT NOT NULL,
            activated   INTEGER DEFAULT 0,
            activated_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS trials (
            device_id   TEXT PRIMARY KEY,
            start_time  TEXT NOT NULL,
            ip_address  TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ── License Key Generator ──────────────────────────────────────────────────────
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

# ── Email Sender ───────────────────────────────────────────────────────────────
def send_license_email(email, license_key, order_id):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Your AutoTyper License Key 🎉"
        msg['From']    = f"AutoTyper <{GMAIL_ADDRESS}>"
        msg['To']      = email

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
          <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">

            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0078d4, #00b4d8); padding: 30px; text-align: center;">
              <h1 style="color: white; margin: 0; font-size: 28px;">⌨ AutoTyper</h1>
              <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0;">Thank you for your purchase!</p>
            </div>

            <!-- Body -->
            <div style="padding: 30px;">
              <h2 style="color: #1a1a2e; margin-top: 0;">Your License Key</h2>
              <p style="color: #555;">Here is your unique license key. Keep it safe!</p>

              <!-- Key Box -->
              <div style="background: #1a1a2e; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
                <code style="color: #00d4ff; font-size: 20px; letter-spacing: 2px; font-weight: bold;">
                  {license_key}
                </code>
              </div>

              <!-- Instructions -->
              <h3 style="color: #1a1a2e;">How to Activate:</h3>
              <ol style="color: #555; line-height: 1.8;">
                <li>Open <strong>AutoTyper.exe</strong></li>
                <li>When the activation screen appears, enter your key above</li>
                <li>Click <strong>Activate</strong></li>
                <li>Done! Full access unlocked forever ✓</li>
              </ol>

              <!-- Note -->
              <div style="background: #f0f7ff; border-left: 4px solid #0078d4; padding: 12px 16px; border-radius: 4px; margin: 20px 0;">
                <p style="margin: 0; color: #555; font-size: 14px;">
                  <strong>Note:</strong> This key works on <strong>1 device only</strong>.
                  If you need to transfer to a new device, reply to this email.
                </p>
              </div>

              <p style="color: #555;">Order ID: <code>{order_id}</code></p>
              <p style="color: #555;">Need help? Just reply to this email!</p>
            </div>

            <!-- Footer -->
            <div style="background: #f5f5f5; padding: 20px; text-align: center; border-top: 1px solid #eee;">
              <p style="color: #999; font-size: 13px; margin: 0;">
                AutoTyper — Human-Like Auto Typing App<br>
                One-time purchase • Lifetime license • 1 device
              </p>
            </div>
          </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, email, msg.as_string())

        print(f"✓ Email sent to {email}")
        return True

    except Exception as e:
        print(f"✗ Email failed: {e}")
        return False

# ── Save License to DB ─────────────────────────────────────────────────────────
def save_license(email, key, order_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO licenses (key, email, order_id, created_at)
            VALUES (?, ?, ?, ?)
        ''', (key, email, order_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB error: {e}")
        return False

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "AutoTyper License Server running!", "version": "1.0"})

@app.route('/webhook/gumroad', methods=['POST'])
def gumroad_webhook():
    """Receive Gumroad payment webhook"""
    try:
        # Gumroad sends as form data
        data = request.form.to_dict()
        
        # Also try JSON
        if not data:
            data = request.get_json(silent=True) or {}

        print(f"Webhook received: {json.dumps(data, indent=2)}")

        # Get email and order ID
        email    = data.get('email', '')
        order_id = data.get('sale_id', '') or data.get('order_id', '')
        
        if not email:
            # Try alternate fields
            email = data.get('buyer_email', '')

        if not email:
            print("No email found in webhook data")
            return jsonify({"error": "No email found"}), 200  # Return 200 so Gumroad doesn't retry

        # Check not already processed
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT key FROM licenses WHERE order_id = ?', (order_id,))
        existing = c.fetchone()
        conn.close()

        if existing:
            print(f"Order {order_id} already processed")
            return jsonify({"status": "already_processed"}), 200

        # Generate key
        key = generate_key()

        # Save to DB
        save_license(email, key, order_id)

        # Send email
        send_license_email(email, key, order_id)

        print(f"✓ License issued: {key} → {email}")
        return jsonify({"status": "success", "key": key}), 200

    except Exception as e:
        print(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 200  # Return 200 to prevent Gumroad retries

@app.route('/validate', methods=['POST'])
def validate():
    """Validate a license key + device binding"""
    try:
        data      = request.get_json()
        key       = data.get('key', '').strip().upper()
        device_id = data.get('device_id', '')

        if not validate_key(key):
            return jsonify({"valid": False, "reason": "Invalid key"}), 200

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT device_id, activated FROM licenses WHERE key = ?', (key,))
        row = c.fetchone()

        if not row:
            conn.close()
            return jsonify({"valid": False, "reason": "Key not found"}), 200

        stored_device, activated = row

        # First activation — bind to device
        if not activated:
            c.execute('''
                UPDATE licenses SET device_id=?, activated=1, activated_at=?
                WHERE key=?
            ''', (device_id, datetime.now().isoformat(), key))
            conn.commit()
            conn.close()
            return jsonify({"valid": True, "message": "Activated!"}), 200

        # Already activated — check device
        if stored_device == device_id:
            conn.close()
            return jsonify({"valid": True, "message": "Licensed"}), 200
        else:
            conn.close()
            return jsonify({"valid": False, "reason": "Key already used on another device"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trial/check', methods=['POST'])
def trial_check():
    """Server-side trial tracking — can't be bypassed by deleting local files"""
    try:
        data      = request.get_json()
        device_id = data.get('device_id', '')

        if not device_id:
            return jsonify({"allowed": False}), 200

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT start_time FROM trials WHERE device_id = ?', (device_id,))
        row = c.fetchone()

        if row:
            start     = datetime.fromisoformat(row[0])
            hours     = (datetime.now() - start).total_seconds() / 3600
            allowed   = hours < 48
            conn.close()
            return jsonify({"allowed": allowed, "hours_used": round(hours, 1)}), 200
        else:
            # First time — register trial
            ip = request.remote_addr
            c.execute('INSERT INTO trials (device_id, start_time, ip_address) VALUES (?, ?, ?)',
                     (device_id, datetime.now().isoformat(), ip))
            conn.commit()
            conn.close()
            return jsonify({"allowed": True, "hours_used": 0}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/licenses', methods=['GET'])
def list_licenses():
    """View all licenses — for your eyes only"""
    secret = request.args.get('secret', '')
    if secret != 'autotyper_admin_2024':
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT key, email, order_id, created_at, activated FROM licenses ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()

    licenses = [{"key": r[0], "email": r[1], "order_id": r[2],
                 "created_at": r[3], "activated": bool(r[4])} for r in rows]
    return jsonify({"total": len(licenses), "licenses": licenses})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"✓ AutoTyper License Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

# Initialize DB when running via gunicorn too
init_db()
