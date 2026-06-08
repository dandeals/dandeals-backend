from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allows your Netlify frontend to send data here safely

# Get the exact folder where app.py sits to avoid file system path errors
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'orders.db')

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                network TEXT NOT NULL,
                size TEXT NOT NULL,
                amount REAL NOT NULL,
                tx_ref TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'PENDING',
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        print("Database structure verified and live!")
    except Exception as e:
        print(f"Database initialization error: {e}")

# Run the database verification immediately when the server boots up
init_db()

@app.route('/api/create-order', methods=['POST'])
def create_order():
    try:
        data = request.json
        phone = data.get('phone')
        network = data.get('network')
        size = data.get('size')

        if not phone or not network or not size:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Dynamic Retail Pricing Matching your exact dashboard pricing rules
        prices = {
            'MTN': {'1': 5, '2': 9, '3': 13.5, '4': 18, '5': 22, '6': 25.5, '8': 34, '10': 41, '15': 60, '20': 79.5, '25': 99.5, '30': 119.5, '40': 157, '50': 196},
            'AT': {'1': 5, '2': 9, '3': 13, '4': 17.5, '5': 22, '6': 26, '8': 32.5, '9': 36, '10': 40, '12': 48, '15': 60, '20': 80, '25': 97},
            'TELECEL': {'10': 38, '15': 56, '20': 75, '30': 110, '40': 146, '50': 182, '100': 366}
        }

        amount = prices.get(network.upper(), {}).get(str(size), 0)
        if amount == 0:
            return jsonify({'success': False, 'error': 'Invalid bundle structure option selected'}), 400

        # Generate unique Paystack tracking reference
        tx_ref = f"DAN-{int(datetime.utcnow().timestamp())}"
        created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        # Insert new pending bundle order into SQLite database file
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (phone, network, size, amount, tx_ref, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
        ''', (phone, network.upper(), size, amount, tx_ref, created_at))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'amount': amount,
            'tx_ref': tx_ref
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/orders', methods=['GET'])
def view_orders():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, phone, network, size, tx_ref, status, created_at FROM orders ORDER BY id DESC LIMIT 50")
        orders = cursor.fetchall()
        conn.close()
        
        html = """
        <html>
        <head>
            <title>Dan Deals Admin Portal</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body { font-family: sans-serif; background: #111827; color: #fff; padding: 20px; }
                h2 { color: #10b981; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #1f2937; }
                th, td { padding: 12px; text-align: left; border-bottom: 1px solid #374151; }
                th { background: #111827; color: #9ca3af; }
                .SUCCESS { color: #10b981; font-weight: bold; }
                .PENDING { color: #f59e0b; }
            </style>
        </head>
        <body>
            <h2>📊 Dan Deals Live Order Logs</h2>
            <p>Refresh this page to see new incoming data orders.</p>
            <div style="overflow-x:auto;">
                <table>
                    <tr>
                        <th>ID</th>
                        <th>Recipient Phone</th>
                        <th>Network</th>
                        <th>Size (GB)</th>
                        <th>Status</th>
                        <th>Time (UTC)</th>
                    </tr>
        """
        for order in orders:
            html += f"""
            <tr>
                <td>{order[0]}</td>
                <td><strong>{order[1]}</strong></td>
                <td>{order[2]}</td>
                <td>{order[3]} GB</td>
                <td class="{order[5]}">{order[5]}</td>
                <td>{order[6]}</td>
            </tr>
            """
        html += """</table></div></body></html>"""
        return html
    except Exception as e:
        return f"Admin Portal Error: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
