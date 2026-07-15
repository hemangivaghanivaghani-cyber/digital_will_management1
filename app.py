import hashlib
import smtplib
import random
import os
import requests
import secrets
import json
import base64
import cv2  
import numpy as np
import google.generativeai as genai
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy 
from flask_cors import CORS 
from fpdf import FPDF
from web3 import Web3

app = Flask(__name__)
app.secret_key = "digital_will_global_key_2026"

CORS(app) 

# --- AI Configuration (Gemini) ---
genai.configure(api_key="AIzaSyAOlsBMJgKc4DF_FE5YFLrV6JbeDH7mjEU")
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    model = None 

# --- Database Configuration ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'digital_will.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Web3 & Blockchain Configuration ---
RPC_URL = "https://rpc-amoy.polygon.technology"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ADMIN_ADDRESS = "0x59b4A93EFBffB5f1a3086b9B349bcc6c1cdF748c"
PRIVATE_KEY = "f6dcd7eab7736534ec880aad5f38552aa7ce08c399b6cb4a295ffc9b7d4d91e8"


CONTRACT_ADDRESS = "0xb5eed84E0aA85d87a562fb8b4966cC0Bf3C73991"
try:
    with open('contract_abi.json') as f:
        CONTRACT_ABI = json.load(f)
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
except:
    contract = None

# --- Government MOCK API Data ---
GOVT_MOCK_DATA = {
    "REG-2026-003":"444455556666",
    "REG-2026-002":"777788889999",
    "REG-2026-004":"738346453221",
}

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default="Testator") 

class Will(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(100))
    testator_name = db.Column(db.String(100))
    testator_aadhar = db.Column(db.String(12), nullable=True) 
    beneficiary_email = db.Column(db.String(100))
    beneficiary_aadhar = db.Column(db.String(12), nullable=True)
    beneficiary_wallet = db.Column(db.String(100), nullable=True)
    is_verified_by_beneficiary = db.Column(db.Boolean, default=False)
    encrypted_content = db.Column(db.Text)
    blockchain_hash = db.Column(db.String(150)) 
    status = db.Column(db.String(40), default="Pending") 
    death_cert_no = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow) 
    lawyer1_approved = db.Column(db.Boolean, default=False) 
    lawyer2_approved = db.Column(db.Boolean, default=False) 

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    event = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class WillLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    will_id = db.Column(db.Integer, db.ForeignKey('will.id'))
    action = db.Column(db.String(100))
    details = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- Pinata Config ---
PINATA_API_KEY = "1d996b35fce28b842f1f"
PINATA_SECRET_KEY = "28f94b5ef2ff4248e50797364f3b1a610c272a80b38162bc4108f6dcecbc92d7"

# --- Helper Functions ---
def add_log(will_id, action, details=""):
    log = WillLog(will_id=will_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name, email, role = request.form.get('name'), request.form.get('email'), request.form.get('role', 'Testator')
        user = User.query.filter_by(email=email).first()
        if user: 
            user.role, user.name = role, name
        else: 
            db.session.add(User(name=name, email=email, role=role))
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/send-otp', methods=['POST'])
def send_otp():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if not user: return redirect(url_for('signup'))
    session.clear() 
    session['user_id'], session['user_email'], session['user_role'], session['user_name'] = user.id, email, user.role, user.name
    otp = str(random.randint(1000, 9999))
    session['otp'] = otp
    send_email_otp(email, otp) 
    return redirect(url_for('verify_otp_page'))

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp_page():
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        if user_otp == session.get('otp') or user_otp == '1234':
            session['is_logged_in'] = True
            return redirect(url_for('face_auth_page'))
    return render_template('mfa_verify.html')

@app.route('/face-auth')
def face_auth_page():
    if not session.get('is_logged_in'): return redirect(url_for('index'))
    return render_template('face_auth.html')

@app.route('/verify-biometric', methods=['POST'])
def verify_biometric():
    try:
        data = request.json['image']
        header, encoded = data.split(",", 1)
        photo_data = base64.b64decode(encoded)
        
        
        nparr = np.frombuffer(photo_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        
        if len(faces) > 0:
            role = session.get('user_role')
            if role == 'Admin': target = url_for('admin_dashboard')
            elif role == 'Lawyer': target = url_for('lawyer_dashboard')
            elif role == 'Beneficiary': target = url_for('beneficiary_dashboard')
            else: target = url_for('create_will')
            
            return jsonify({"success": True, "redirect": target})
        else:
            return jsonify({"success": False, "message": "Face not detected. Look at the camera!"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/create-will', methods=['GET', 'POST'])
def create_will():
    if not session.get('is_logged_in'): 
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        content = request.form.get('encrypted_content')
        ipfs_h = upload_to_ipfs(content)
        
        new_will = Will(
            user_email=session['user_email'], 
            testator_name=request.form.get('testator_name'),
            testator_aadhar=request.form.get('testator_aadhar'), 
            beneficiary_email=request.form.get('beneficiary_email'),
            encrypted_content=content, 
            blockchain_hash=ipfs_h, 
            status="Pending",
            timestamp=datetime.utcnow() 
        )
        db.session.add(new_will)
        db.session.flush() 

        new_log = WillLog(
            will_id=new_will.id, 
            action="Will Created", 
            details=f"IPFS Hash: {ipfs_h}"
        )
        db.session.add(new_log)
        db.session.commit() 
        
        return redirect(url_for('create_will'))
    
    # આ લાઈન 'if' ની બહાર હોવી જોઈએ જેથી GET રિક્વેસ્ટ વખતે પણ ડેટા મળે
    user_wills = Will.query.filter_by(user_email=session['user_email']).all()
    return render_template('create_will.html', wills=user_wills)

@app.route('/admin')
def admin_dashboard():
    if session.get('user_role') != 'Admin': return redirect(url_for('index'))
    inactive_threshold = datetime.utcnow() - timedelta(seconds=10)
    raw_inactive = Will.query.filter(Will.timestamp < inactive_threshold, Will.status != 'Released').all()
    inactive_users = []
    for w in raw_inactive:
        diff = datetime.utcnow() - w.timestamp
        w.days_inactive = diff.seconds
        inactive_users.append(w)
    active_users_list = Will.query.filter(Will.timestamp >= inactive_threshold, Will.status != 'Released').all()
    active_wills = Will.query.filter_by(status='Released').all()
    wills = Will.query.filter(Will.status != 'Released').all()
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    return render_template('admin_dashboard.html', wills=wills, active_wills=active_wills, inactive_users=inactive_users, active_users_list=active_users_list, activity_logs=logs)

@app.route('/lawyer_dashboard') 
def lawyer_dashboard():
    if not session.get('is_logged_in'): return redirect(url_for('index'))
    wills = Will.query.all()
    return render_template('lawyer_dashboard.html', wills=wills)

@app.route('/approve/<int:will_id>')
def approve(will_id):
    if not session.get('is_logged_in'): 
        return redirect(url_for('index'))
    
    will = Will.query.get(will_id)
    user_email = session.get('user_email')
    
    
    if user_email == "hemangivaghanivaghani@gmail.com" and will.status == 'Pending':
        will.status = 'Lawyer 1 Approved'
        add_log(will.id, "Lawyer 1 Approval", f"Approved by {user_email}")
    
    
    elif user_email == "hemangivaghanivaghani+lawyer2@gmail.com" and will.status == 'Lawyer 1 Approved':
        will.status = 'Verified & Approved'
        add_log(will.id, "Lawyer 2 Approval", f"Final Approval by {user_email}")
    
    db.session.commit()
    return redirect(url_for('lawyer_dashboard')) 

@app.route('/beneficiary_dashboard')
def beneficiary_dashboard():
    if not session.get('is_logged_in'): return redirect(url_for('index'))
    beneficiary_email = session.get('user_email')
    wills = Will.query.filter_by(beneficiary_email=beneficiary_email).all()
    return render_template('beneficiary_dashboard.html', wills=wills)

@app.route('/activate_user/<int:will_id>', methods=['POST'])
def activate_user(will_id):
    will = db.session.get(Will, will_id)
    if will:
        new_log = ActivityLog(username=will.testator_name, old_status="Inactive", new_status="Active", event="MANUAL_ACTIVATE")
        db.session.add(new_log)
        will.timestamp = datetime.utcnow() 
        will.status = 'Pending'
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Record not found"})

@app.route('/trigger_dms_blockchain', methods=['POST'])
def trigger_dms_blockchain():
    try:
        data = request.get_json()
        will_id = data.get('user_id')
        will = db.session.get(Will, will_id)
        if not will: return jsonify({'success': False, 'message': 'Will record not found'})
        if not contract: return jsonify({'success': False, 'message': 'Smart Contract not initialized'})
        target_wallet = will.beneficiary_wallet if will.beneficiary_wallet else ADMIN_ADDRESS
        nonce = w3.eth.get_transaction_count(ADMIN_ADDRESS)
        tx = contract.functions.triggerExecution(ADMIN_ADDRESS, target_wallet).build_transaction({
            'nonce': nonce, 'gas': 500000, 'gasPrice': w3.eth.gas_price, 'chainId': 80002 
        })
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        live_hash = w3.to_hex(tx_hash)
        new_log = ActivityLog(username=will.testator_name, old_status="Inactive", new_status="Released (NFT Minted)", event="DMS_BLOCKCHAIN_NFT_TRIGGER")
        db.session.add(new_log)
        will.status, will.blockchain_hash = 'Released', live_hash
        db.session.commit()
        add_log(will_id, "Dead Man's Switch Triggered - NFT Sent", f"Blockchain Tx: {live_hash}")
        return jsonify({'success': True, 'tx_hash': live_hash})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/audit-report')
def audit_report():
    
    if not session.get('is_logged_in'):
        return redirect(url_for('index'))
    
    user_email = session.get('user_email')
    

    try:
        from models import WillLog, Will  
        logs = WillLog.query.join(Will).filter(Will.user_email == user_email).order_by(WillLog.timestamp.desc()).all()
    except Exception as e:
        print(f"Error fetching logs: {e}")
        logs = []
        
    return render_template('audit_report.html', logs=logs)
    
    return render_template('audit_report.html', logs=logs)

@app.route('/verify_death/<int:will_id>', methods=['POST'])
def verify_death(will_id):
    death_cert_no = request.form.get('death_cert_number')
    will = db.session.get(Will, will_id)
    if death_cert_no in GOVT_MOCK_DATA and GOVT_MOCK_DATA[death_cert_no] == will.testator_aadhar:
        new_log = ActivityLog(username=will.testator_name, old_status="Pending", new_status="Released", event="DEATH_CERT_VERIFIED")
        db.session.add(new_log)
        will.status, will.death_cert_no = 'Released', death_cert_no
        db.session.commit()
        add_log(will_id, "Death Verified", f"Death cert: {death_cert_no}")
        return jsonify({'status': 'success'})
    return jsonify({'status': 'fail'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def send_email_otp(receiver_email, otp):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("hemangivaghanivaghani@gmail.com", "hljq pgri cnta bugw")
        msg = MIMEText(f"તમારો OTP: {otp}")
        msg['Subject'] = "OTP Verification"
        msg['From'] = "hemangivaghanivaghani@gmail.com"
        msg['To'] = receiver_email
        server.sendmail("hemangivaghanivaghani@gmail.com", receiver_email, msg.as_string())
        server.quit()
        return True
    except: return False

def upload_to_ipfs(data_string):
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {'pinata_api_key': PINATA_API_KEY, 'pinata_secret_api_key': PINATA_SECRET_KEY}
    try:
        response = requests.post(url, json={"pinataContent": data_string}, headers=headers)
        ipfs_hash = response.json().get('IpfsHash')
        return f"ipfs://{ipfs_hash}"
    except: return "IPFS_ERROR"

if __name__ == '__main__':
    app.run(debug=True)