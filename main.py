from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import qrcode
import os
from datetime import datetime
import cv2

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DB_NAME = 'attendance.db'

# Ensure QR codes directory exists
os.makedirs('static/qr_codes', exist_ok=True)

# Initialize the database
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            office TEXT NOT NULL,
                            designation TEXT NOT NULL
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            status TEXT NOT NULL,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                          )''')
    conn.close()

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Add user route
@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name']
        office = request.form['office']
        designation = request.form['designation']
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO users (name, office, designation) VALUES (?, ?, ?)', (name, office, designation))
                conn.commit()

                # Generate QR code
                user_id = cursor.lastrowid
                qr = qrcode.QRCode()
                qr.add_data(f'user_id:{user_id}')
                qr.make(fit=True)
                img = qr.make_image(fill='black', back_color='white')
                img_path = f'static/qr_codes/user_{user_id}.png'
                img.save(img_path)

                flash('User added and QR code generated successfully!', 'success')
            except sqlite3.IntegrityError:
                flash('Error adding user!', 'danger')
        return redirect(url_for('add_user'))
    return render_template('add_user.html')

# Attendance route
@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if request.method == 'POST':
        qr_data = request.form.get('qr_data')
        if qr_data and qr_data.startswith('user_id:'):
            try:
                user_id = int(qr_data.split(':')[1])
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()

                    # Check the last status for this user
                    cursor.execute('''SELECT status FROM attendance 
                                      WHERE user_id = ? 
                                      ORDER BY timestamp DESC LIMIT 1''', (user_id,))
                    last_status = cursor.fetchone()

                    # Determine the next status
                    status = 'time-in' if last_status is None or last_status[0] == 'time-out' else 'time-out'

                    # Insert the attendance record
                    cursor.execute('INSERT INTO attendance (user_id, status) VALUES (?, ?)', (user_id, status))
                    conn.commit()

                    flash(f'Attendance marked as {status} successfully!', 'success')
            except (ValueError, sqlite3.Error):
                flash('Invalid QR code data or database error!', 'danger')
        else:
            flash('Invalid QR code format!', 'danger')
        return redirect(url_for('attendance'))

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT users.name, users.office, users.designation, attendance.timestamp, attendance.status 
                          FROM attendance 
                          JOIN users ON attendance.user_id = users.id
                          ORDER BY attendance.timestamp DESC''')
        records = cursor.fetchall()
    return render_template('attendance.html', records=records)

# Generate QR codes route
@app.route('/generate_qr', methods=['GET'])
def generate_qr():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, office, designation FROM users')
        users = cursor.fetchall()
    return render_template('generate_qr.html', users=users)

# Scan QR code using OpenCV
@app.route('/scan_qr', methods=['POST'])
def scan_qr():
    cap = cv2.VideoCapture(0)
    detector = cv2.QRCodeDetector()

    while True:
        ret, frame = cap.read()
        if not ret:
            flash('Failed to access the camera', 'danger')
            break

        data, bbox, _ = detector.detectAndDecode(frame)
        if data:
            cap.release()
            cv2.destroyAllWindows()
            return jsonify({'qr_data': data})

        cv2.imshow('Scan QR Code', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    flash('No QR code detected', 'danger')
    return redirect(url_for('attendance'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
