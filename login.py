from flask import Flask, request, jsonify, render_template, render_template_string, session, redirect, url_for
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for sessions

# Database connection function
def get_connection():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='1234',
        database='bakery_busness'
    )

# --- LOGIN PAGE TEMPLATE ---
login_page_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login Page</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f5f5f5; }
        .vh-100 { height: 100vh; }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center align-items-center vh-100">
            <div class="col-md-4">
                <div class="card p-4 shadow-lg">
                    <h3 class="text-center mb-3">Login</h3>
                    <form id="loginForm" method="POST" action="/login">
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Login</button>
                        <p id="errorMsg" class="text-danger mt-2" style="display:none;">Invalid username or password</p>
                    </form>
                </div>
            </div>
        </div>
    </div>

<script>
const loginForm = document.getElementById('loginForm');
const errorMsg = document.getElementById('errorMsg');

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(loginForm);
    const response = await fetch('/login', { method: 'POST', body: formData });
    const result = await response.json();
    if (result.success) {
        window.location.href = '/dashboard';
    } else {
        errorMsg.style.display = 'block';
    }
});
</script>
</body>
</html>
"""

@app.route('/')
def login_page():
    return render_template_string(login_page_html)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM `user` WHERE user_name=%s AND user_password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        # Save user session
        session['user_id'] = user['user_id']
        session['user_name'] = user['user_name']
        session['personal_name'] = user['personal_name']
        session['job_desc'] = user['job_desc']
        return jsonify({"success": True})

    return jsonify({"success": False})

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    # Get user info from session
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }

    # Fetch products
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('dashboard.html', user=user_info, products=products)

@app.route('/activity_billing_queue')
def activity_billing_queue():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }

    return render_template('activity_billing_queue.html',user=user_info)

@app.route('/activity_Tables')
def activity_Tables():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
    SELECT 
        t.Table_db_id,
        t.Table_number,
        t.table_floor,
        CASE 
            WHEN tr.table_reservation_number IS NOT NULL THEN 'reserved'
            ELSE 'available'
        END AS table_status,
        tr.Date_reserved,
        tr.number_of_guests
    FROM tables AS t
    LEFT JOIN table_reservations AS tr
        ON t.Table_db_id = tr.Table_db_id
    ORDER BY t.table_floor, t.Table_number;
    """)


    all_tables = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('activity_Tables.html', user=user_info, tables=all_tables)

@app.route('/update_tables', methods=['POST'])
def update_tables():
    data = request.json
    changes = data.get('changes', [])

    conn = get_connection()
    cursor = conn.cursor()

    try:
        for change in changes:
            table_id = change['table_id']
            status = change['status']
            date_reserved = change.get('date_reserved') or None
            number_of_guests = int(change.get('number_of_guests')) if change.get('number_of_guests') else None

            # 1️⃣ Update the status for all tables
            cursor.execute("""
                UPDATE table_status
                SET status = %s
                WHERE table_id = %s
            """, (status, table_id))

            # 2️⃣ Handle reservations table
            if status == 'reserved':
                # Insert or update reservation
                cursor.execute("""
                    INSERT INTO table_reservations (table_id, Date_reserved, number_of_guests)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        Date_reserved = VALUES(Date_reserved),
                        number_of_guests = VALUES(number_of_guests)
                """, (table_id, date_reserved, number_of_guests))
            else:
                # Delete reservation if table is no longer reserved
                cursor.execute("""
                    DELETE FROM table_reservations WHERE table_id = %s
                """, (table_id,))

        conn.commit()
        return jsonify({'success': True, 'updated': len(changes)})

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cursor.close()
        conn.close()



@app.route('/activity_Order_history')
def activity_Order_history():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    user_info = {
        "user_name": session.get('user_name'),
        "personal_name": session.get('personal_name'),
        "job_desc": session.get('job_desc')
    }

    return render_template('activity_Order_history.html',user=user_info)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == "__main__":
 app.run(debug=True)