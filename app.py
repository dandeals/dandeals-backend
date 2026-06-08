from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
import requests  # This is safely imported up here at the very top!

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

DB_NAME = "data_hub.db"

def get_db_connection():
    """Opens a clean connection and sets a timeout to prevent Windows locking errors."""
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;') 
    return conn

def deliver_data_bundle(phone, network, size):
    """
    Handles sending the background delivery signal to the data wholesaler.
    For now, it cleanly simulates a perfect API delivery loop.
    """
    print(f"\n📡 [VENDOR API]: Initializing data dispatch pipeline...")
    print(f"📡 [VENDOR API]: Sending {size}GB ({network}) to customer target: {phone}...")
    
    # This is exactly where your real vendor API integration will sit later:
    # API_URL = "https://api.datavendor.com/v1/dispatches"
    # payload = {"phone": phone, "network": network, "bundle": size, "api_key": "YOUR_SECRET"}
    # response = requests.post(API_URL, json=payload)
    
    return {"status": "success", "vendor_ref": f"VEND-API-{int(datetime.utcnow().timestamp())}"}

@app.route('/api/create-order', methods=['POST'])
def create_order():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data received"}), 400

        phone = data.get('phone')
        network = data.get('network', '').upper()
        size_key = data.get('size') 

        # 📊 COMPLETE RETAIL CONFIGURATION MATRIX FOR DAN DEALS
        RETAIL_PRICING = {
            "MTN": {
                "1": 5.00, "2": 9.00, "3": 13.50, "4": 18.00, "5": 22.00, "6": 25.50,
                "8": 34.00, "10": 41.00, "15": 60.00, "20": 79.50, "25": 99.50, "30": 119.50,
                "40": 157.00, "50": 196.00
            },
            "AT": {
                "1": 5.00, "2": 9.00, "3": 13.00, "4": 17.50, "5": 22.00, "6": 26.00,
                "8": 32.50, "9": 36.00, "10": 40.00, "12": 48.00, "15": 60.00, "20": 80.00,
                "25": 97.00
            },
            "TELECEL": {
                "10": 38.00, "15": 56.00, "20": 75.00, "30": 110.00, "40": 146.00, "50": 182.00,
                "100": 366.00
            }
        }

        # 🎯 COMPLETE WHOLESALE COST MATRIX (EXACT RATES UPDATED FROM SOURCE)
        WHOLESALE_PRICING = {
            "MTN": {
                "1": 3.80, "2": 7.65, "3": 11.50, "4": 15.50, "5": 19.50, "6": 23.00,
                "8": 30.50, "10": 38.50, "15": 58.00, "20": 76.50, "25": 98.00, "30": 115.00,
                "40": 153.00, "50": 190.00
            },
            "AT": {
                "1": 3.90, "2": 7.80, "3": 11.70, "4": 15.50, "5": 19.50, "6": 23.50,
                "8": 30.60, "9": 34.50, "10": 38.50, "12": 46.40, "15": 58.50, "20": 78.00,
                "25": 95.50
            },
            "TELECEL": {
                "10": 36.50, "15": 54.00, "20": 73.00, "30": 108.00, "40": 144.00, "50": 180.00,
                "100": 360.00
            }
        }

        # Input safety validations
        if network not in RETAIL_PRICING or size_key not in RETAIL_PRICING[network]:
            return jsonify({"success": False, "error": "Invalid network package structure request."}), 400

        # Pull exact figures matching the user's bundle selection
        amount_to_charge = RETAIL_PRICING[network][size_key]
        wholesale_cost = WHOLESALE_PRICING[network][size_key]
        
        # Paystack flat fee calculations (1.9% processing flat fee in Ghana)
        gateway_fee = amount_to_charge * 0.019
        estimated_profit = amount_to_charge - wholesale_cost - gateway_fee
        
        tx_ref = f"DHUB-{int(datetime.utcnow().timestamp())}-{phone[-4:]}"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_ref TEXT UNIQUE NOT NULL,
                recipient_phone TEXT NOT NULL,
                network TEXT NOT NULL,
                data_size REAL NOT NULL,
                amount_paid REAL NOT NULL,
                profit_made REAL NOT NULL,
                payment_status TEXT DEFAULT 'pending',
                delivery_status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            INSERT INTO sales (tx_ref, recipient_phone, network, data_size, amount_paid, profit_made, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (tx_ref, phone, network, float(size_key), amount_to_charge, estimated_profit, current_time))
        
        conn.commit()
        conn.close()
        
        print(f"📈 [DAN DEALS TRANSACTION LOGGED]")
        print(f"   Operator: {network} | Plan: {size_key}GB")
        print(f"   Customer Charged: GH₵ {amount_to_charge:.2f}")
        print(f"   Wholesale Cost:   GH₵ {wholesale_cost:.2f}")
        print(f"   Paystack Fee:     GH₵ {gateway_fee:.2f}")
        print(f"   Net Pure Profit:  GH₵ {estimated_profit:.2f}\n")
        
        return jsonify({
            "success": True,
            "tx_ref": tx_ref,
            "amount": amount_to_charge
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/webhook-payment-success', methods=['POST'])
def payment_success_webhook():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "No data received"}), 400
            
        tx_ref = data.get('tx_ref')
        gateway_status = data.get('status')
        
        if gateway_status == 'success':
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Look up the pending phone number, network, and bundle size from our database
            cursor.execute('SELECT recipient_phone, network, data_size FROM sales WHERE tx_ref = ?', (tx_ref,))
            order = cursor.fetchone()
            
            if order:
                phone, network, size = order
                
                # Trigger the automated data vendor dispatch simulation
                delivery_result = deliver_data_bundle(phone, network, size)
                
                if delivery_result["status"] == "success":
                    cursor.execute('''
                        UPDATE sales 
                        SET payment_status = "success", delivery_status = "delivered" 
                        WHERE tx_ref = ?
                    ''', (tx_ref,))
                    conn.commit()
                    conn.close()
                    
                    print(f"🎉 [SUCCESS]: Order {tx_ref} fully paid and data delivered automatically!\n")
                    return jsonify({"success": True, "message": "Payment verified and data bundle deployed."}), 200
            
            conn.close()
            return jsonify({"success": False, "message": "Order reference lookup mismatch."}), 404
            
        return jsonify({"success": False, "message": "Invalid status."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
      import os
      port = int(os.environ.get("PORT", 5000))
      app.run(host='0.0.0.0', port=port)
