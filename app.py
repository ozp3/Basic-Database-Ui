from flask import Flask, render_template, request, redirect, url_for, session
import oracledb

# Thick mode'u etkinleştir
oracledb.init_oracle_client(lib_dir="D:\\oraclexe\\instantclient_19_25")  # Oracle Instant Client konumu

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Oturumlar için gizli anahtar

# --------------------------------------------------------------------------------
# 1. Oracle veritabanı bağlantısı
# --------------------------------------------------------------------------------
def get_oracle_connection():
    connection = oracledb.connect(
        user="hr",
        password="hr",
        dsn="localhost:1521/XE"
    )
    return connection

# --------------------------------------------------------------------------------
# 2. Yardımcı fonksiyonlar
# --------------------------------------------------------------------------------
def fetch_tables():
    connection = get_oracle_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT table_name FROM user_tables")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return tables

def fetch_table_data(table_name):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = f"SELECT * FROM {table_name}"
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return columns, rows

def fetch_column_constraints(table_name):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = """
        SELECT column_name, nullable 
        FROM all_tab_columns 
        WHERE table_name = :1 AND owner = USER
    """
    cursor.execute(query, [table_name.upper()])
    constraints = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    connection.close()
    return constraints

def insert_into_table(table_name, data):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    placeholders = ', '.join([':{}'.format(i + 1) for i in range(len(data))])
    query = f"INSERT INTO {table_name} VALUES ({placeholders})"
    cursor.execute(query, data)
    connection.commit()
    cursor.close()
    connection.close()

def delete_from_table(table_name, condition_column, condition_value):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = f"DELETE FROM {table_name} WHERE {condition_column} = :1"
    cursor.execute(query, [condition_value])
    connection.commit()
    cursor.close()
    connection.close()

# --------------------------------------------------------------------------------
# 3. (YENİ) Customers tablosuna yeni müşteri ekleyen fonksiyon
# --------------------------------------------------------------------------------
def create_new_customer(first_name, surname, email, phone):
    print("[DEBUG] create_new_customer params:", first_name, surname, email, phone)
    
    connection = get_oracle_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT NVL(MAX(CUSTOMERID), 100) FROM CUSTOMERS")
    last_id = cursor.fetchone()[0]
    new_id = last_id + 1

    insert_query = """
        INSERT INTO CUSTOMERS (CUSTOMERID, FIRST_NAME, SURNAME, EMAIL, PHONE)
        VALUES (:1, :2, :3, :4, :5)
    """
    cursor.execute(insert_query, [new_id, first_name, surname, email, phone])
    connection.commit()
    cursor.close()
    connection.close()

    return new_id




# --------------------------------------------------------------------------------
# 4. Admin ve tablo işlemleri için rotalar
# --------------------------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "hr" and password == "hr":
            session['admin'] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for("admin_login"))
    tables = fetch_tables()
    return render_template("admin_dashboard.html", tables=tables)

@app.route("/admin/table/<table_name>/add", methods=["GET", "POST"])
def add_data(table_name):
    if not session.get('admin'):
        return redirect(url_for("admin_login"))
    columns, rows = fetch_table_data(table_name)
    constraints = fetch_column_constraints(table_name)
    if request.method == "POST":
        data = [request.form.get(col) for col in columns]
        insert_into_table(table_name, data)
        columns, rows = fetch_table_data(table_name)
        constraints = fetch_column_constraints(table_name)
        return render_template(
            "add_data.html",
            table_name=table_name,
            columns=columns,
            rows=rows,
            constraints=constraints,
            message="Data added successfully!"
        )
    return render_template(
        "add_data.html",
        table_name=table_name,
        columns=columns,
        rows=rows,
        constraints=constraints
    )

@app.route("/admin/table/<table_name>/remove", methods=["GET", "POST"])
def remove_data(table_name):
    if not session.get('admin'):
        return redirect(url_for("admin_login"))
    columns, rows = fetch_table_data(table_name)
    if request.method == "POST":
        condition_column = request.form.get("condition_column")
        condition_value = request.form.get("condition_value")
        delete_from_table(table_name, condition_column, condition_value)
        columns, rows = fetch_table_data(table_name)
        return render_template(
            "remove_data.html",
            table_name=table_name,
            columns=columns,
            rows=rows,
            message="Data removed successfully!"
        )
    return render_template("remove_data.html", table_name=table_name, columns=columns, rows=rows)

# --------------------------------------------------------------------------------
# 5. Movies, Showtimes, Customer Info, Consumables rotaları
# --------------------------------------------------------------------------------
@app.route("/movies", methods=["GET", "POST"])
def movies():
    columns, rows = fetch_table_data("MOVIES")
    # Sadece belirli sütunları göstermek isterseniz
    filtered_columns = ["TITLE", "GENRE", "MDURATION", "RATING"]
    filtered_indices = [columns.index(col) for col in filtered_columns]
    filtered_rows = [[row[i] for i in filtered_indices] for row in rows]

    if request.method == "POST":
        selected_movie = request.form.get("selected_movie")
        return redirect(url_for("showtimes", movie_title=selected_movie))

    return render_template("movies.html", columns=filtered_columns, rows=filtered_rows)

@app.route("/showtimes/<movie_title>", methods=["GET", "POST"])
def showtimes(movie_title):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = """
        SELECT SHOWDATE, STARTTIME, ENDTIME, HALLID
        FROM SHOWTIMES
        WHERE MOVIEID = (
          SELECT MOVIEID FROM MOVIES WHERE TITLE = :1
        )
    """
    cursor.execute(query, [movie_title])
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    columns = ["SHOWDATE", "STARTTIME", "ENDTIME", "HALLID"]

    if request.method == "POST":
        selected_showtime = request.form.get("selected_showtime")
        return redirect(url_for("customer_info", showtime_id=selected_showtime, movie_title=movie_title))

    return render_template("showtimes.html", movie_title=movie_title, columns=columns, rows=rows)

@app.route("/customer_info/<showtime_id>/<movie_title>", methods=["GET", "POST"])
def customer_info(showtime_id, movie_title):
    if request.method == "POST":
        first_name = request.form.get("first_name")
        surname = request.form.get("surname")
        email = request.form.get("email")
        phone = request.form.get("phone")

        # Debug
        print("[DEBUG] customer_info ->", first_name, surname, email, phone)

        session["first_name"] = first_name
        session["surname"] = surname
        session["email"] = email
        session["phone"] = phone

        return redirect(url_for(
            "consumables",
            showtime_id=showtime_id,
            movie_title=movie_title
        ))

    return render_template("customer_info.html", showtime_id=showtime_id, movie_title=movie_title)



@app.route("/consumables/<showtime_id>/<movie_title>", methods=["GET", "POST"])
def consumables(showtime_id, movie_title):
    # Veritabanından tüketilebilir ürünleri çekelim
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = "SELECT CONSNAME, PRICE FROM CONSUMABLES"
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    columns = ["CONSNAME", "PRICE"]

    if request.method == "POST":
        # Form gönderildiyse, seçilen ürünleri session'a kaydedelim
        selected_consumables = request.form.getlist("consumable_name")
        quantities = request.form.getlist("consumable_quantity")

        # Örn: {"Popcorn": 2, "Soda": 1}
        consumable_data = {}
        for name, qty in zip(selected_consumables, quantities):
            if int(qty) > 0:
                consumable_data[name] = int(qty)

        session["consumables"] = consumable_data
        
        # Artık “Next” vb. bir şeyle uğraşmadan direkt payment rotasına yönlendiriyoruz
        return redirect(url_for("payment", showtime_id=showtime_id, movie_title=movie_title))

    # GET isteğinde sayfayı çizelim
    return render_template(
        "consumables.html",
        columns=columns,
        rows=rows,
        showtime_id=showtime_id,
        movie_title=movie_title
    )



# --------------------------------------------------------------------------------
# 6. Payment rotası (tabloya yazma yok, sadece görüntü / özet)
# --------------------------------------------------------------------------------
@app.route("/payment/<showtime_id>/<movie_title>", methods=["GET", "POST"])
def payment(showtime_id, movie_title):
    ticket_price = 10.00

    # Session'daki consumables sözlüğünü al
    consumables = session.get("consumables", {})

    # Showtime detaylarını parse edelim (örn: "2024-12-26 00:00:00|14.30|16.58|11")
    showtime_parts = showtime_id.split('|')
    showtime_table = {
        "SHOWDATE": showtime_parts[0],
        "STARTTIME": showtime_parts[1],
        "ENDTIME": showtime_parts[2],
        "HALLID": showtime_parts[3]
    }

    # Payment sayfasında toplam ücreti hesaplayalım (ticket + consumables)
    connection = get_oracle_connection()
    cursor = connection.cursor()

    total_consumable_price = 0
    consumable_details = []
    for c_name, c_qty in consumables.items():
        cursor.execute("SELECT PRICE FROM CONSUMABLES WHERE CONSNAME = :1", [c_name])
        row = cursor.fetchone()
        if row:
            c_price = float(row[0])
            total_line = c_price * c_qty
            total_consumable_price += total_line
            consumable_details.append((c_name, c_qty, total_line))

    cursor.close()
    connection.close()

    total_price = ticket_price + total_consumable_price

    # Payment sayfası
    if request.method == "POST":
        # "Complete Order" butonuna basınca order_confirmation'a gideceğiz
        # Bu aşamada da tabloya ekleme yapmıyoruz
        return redirect(url_for("order_confirmation"))

    return render_template(
        "payment.html",
        movie_title=movie_title,
        showtime_table=showtime_table,
        total_price=total_price,
        ticket_price=ticket_price,
        consumables=consumable_details,
        total_consumable_price=total_consumable_price
    )

# --------------------------------------------------------------------------------
# 7. Order Confirmation rotası (Sadece CUSTOMERS güncelleniyor)
# --------------------------------------------------------------------------------
@app.route("/order_confirmation")
def order_confirmation():
    first_name = session.get("first_name")
    surname = session.get("surname")
    email = session.get("email")
    phone = session.get("phone")

    # 1) Verileri kontrol etmek için DEBUG çıktısı
    print("[DEBUG] order_confirmation ->", first_name, surname, email, phone)

    if not (first_name and surname and email and phone):
        return "Eksik müşteri bilgisi var, tabloya eklenmedi."

    # 2) Eklerken bir debug daha
    new_customer_id = create_new_customer(first_name, surname, email, phone)
    print("[DEBUG] New customer inserted:", new_customer_id)

    return render_template("order_confirmation.html")




# --------------------------------------------------------------------------------
# Ana sayfa
# --------------------------------------------------------------------------------
@app.route("/")
def index():
    tables = fetch_tables()
    return render_template("index.html", tables=tables)

@app.route("/table/<table_name>")
def table_data(table_name):
    columns, rows = fetch_table_data(table_name)
    return render_template("table_data.html", table_name=table_name, columns=columns, rows=rows)

if __name__ == "__main__":
    app.run(debug=True)
