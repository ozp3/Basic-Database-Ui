from flask import Flask, render_template, request, redirect, url_for, session
import oracledb

# Thick mode'u etkinleştir
oracledb.init_oracle_client(lib_dir="D:\\oraclexe\\instantclient_19_25")  # Oracle Instant Client'ın yeri

# Flask uygulamasını başlat
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Oturumlar için gizli anahtar

# Oracle veritabanı bağlantı bilgileri
def get_oracle_connection():
    connection = oracledb.connect(
        user="hr",
        password="hr",
        dsn="localhost:1521/XE"
    )
    return connection

# Tabloları listeleme fonksiyonu
def fetch_tables():
    connection = get_oracle_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT table_name FROM user_tables")  # Mevcut kullanıcıya ait tabloları çeker
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    connection.close()
    return tables

# Belirli bir tablodan veri çekme fonksiyonu
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

# Tablodaki sütunların NULL/NOT NULL bilgilerini çekme fonksiyonu
def fetch_column_constraints(table_name):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = f"""
        SELECT column_name, nullable 
        FROM all_tab_columns 
        WHERE table_name = :1 AND owner = USER
    """
    cursor.execute(query, [table_name.upper()])
    constraints = {row[0]: row[1] for row in cursor.fetchall()}  # {'COLUMN_NAME': 'Y/N'}
    cursor.close()
    connection.close()
    return constraints

# Veri ekleme fonksiyonu
def insert_into_table(table_name, data):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    placeholders = ', '.join([':{}'.format(i + 1) for i in range(len(data))])
    query = f"INSERT INTO {table_name} VALUES ({placeholders})"
    cursor.execute(query, data)
    connection.commit()
    cursor.close()
    connection.close()

# Veri silme fonksiyonu
def delete_from_table(table_name, condition_column, condition_value):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = f"DELETE FROM {table_name} WHERE {condition_column} = :1"
    cursor.execute(query, [condition_value])
    connection.commit()
    cursor.close()
    connection.close()

# Admin giriş sayfası
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

# Admin dashboard
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for("admin_login"))
    tables = fetch_tables()
    return render_template("admin_dashboard.html", tables=tables)

# Veri ekleme sayfası
@app.route("/admin/table/<table_name>/add", methods=["GET", "POST"])
def add_data(table_name):
    if not session.get('admin'):
        return redirect(url_for("admin_login"))
    columns, rows = fetch_table_data(table_name)
    constraints = fetch_column_constraints(table_name)
    if request.method == "POST":
        data = [request.form.get(col) for col in columns]
        insert_into_table(table_name, data)
        columns, rows = fetch_table_data(table_name)  # Tabloyu güncelleme
        constraints = fetch_column_constraints(table_name)
        return render_template("add_data.html", table_name=table_name, columns=columns, rows=rows, constraints=constraints, message="Data added successfully!")
    return render_template("add_data.html", table_name=table_name, columns=columns, rows=rows, constraints=constraints)

# Veri silme sayfası
@app.route("/admin/table/<table_name>/remove", methods=["GET", "POST"])
def remove_data(table_name):
    if not session.get('admin'):
        return redirect(url_for("admin_login"))
    columns, rows = fetch_table_data(table_name)
    if request.method == "POST":
        condition_column = request.form.get("condition_column")
        condition_value = request.form.get("condition_value")
        delete_from_table(table_name, condition_column, condition_value)
        columns, rows = fetch_table_data(table_name)  # Tabloyu güncelleme
        return render_template("remove_data.html", table_name=table_name, columns=columns, rows=rows, message="Data removed successfully!")
    return render_template("remove_data.html", table_name=table_name, columns=columns, rows=rows)

# Movies
@app.route("/movies", methods=["GET", "POST"])
def movies():
    columns, rows = fetch_table_data("MOVIES")
    filtered_columns = ["TITLE", "GENRE", "MDURATION", "RATING"]
    filtered_indices = [columns.index(col) for col in filtered_columns]
    filtered_rows = [[row[i] for i in filtered_indices] for row in rows]

    if request.method == "POST":
        selected_movie = request.form.get("selected_movie")
        return redirect(url_for("showtimes", movie_title=selected_movie))

    return render_template("movies.html", columns=filtered_columns, rows=filtered_rows)

# Showtimes
@app.route("/showtimes/<movie_title>", methods=["GET", "POST"])
def showtimes(movie_title):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = """
        SELECT SHOWDATE, STARTTIME, ENDTIME, HALLID
        FROM SHOWTIMES
        WHERE MOVIEID = (SELECT MOVIEID FROM MOVIES WHERE TITLE = :1)
    """
    cursor.execute(query, [movie_title])
    rows = cursor.fetchall()
    columns = ["SHOWDATE", "STARTTIME", "ENDTIME", "HALLID"]
    cursor.close()
    connection.close()

    if request.method == "POST":
        selected_showtime = request.form.get("selected_showtime")
        return redirect(url_for("customer_info", showtime_id=selected_showtime, movie_title=movie_title))

    return render_template("showtimes.html", movie_title=movie_title, columns=columns, rows=rows)

# Customer Info
@app.route("/customer_info/<showtime_id>/<movie_title>", methods=["GET", "POST"])
def customer_info(showtime_id, movie_title):
    if request.method == "POST":
        first_name = request.form.get("first_name")
        surname = request.form.get("surname")
        email = request.form.get("email")
        phone = request.form.get("phone")
        return redirect(url_for("consumables", showtime_id=showtime_id, movie_title=movie_title, first_name=first_name, surname=surname, email=email, phone=phone))

    return render_template("customer_info.html", showtime_id=showtime_id, movie_title=movie_title)

# Consumables
@app.route("/consumables/<showtime_id>/<movie_title>", methods=["GET", "POST"])
def consumables(showtime_id, movie_title):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    query = "SELECT CONSNAME, PRICE FROM CONSUMABLES"
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = ["CONSNAME", "PRICE"]
    cursor.close()
    connection.close()

    if request.method == "POST":
        selected_consumables = request.form.getlist("consumable_name")
        quantities = request.form.getlist("consumable_quantity")
        consumable_data = {name: int(quantity) for name, quantity in zip(selected_consumables, quantities) if int(quantity) > 0}
        return redirect(url_for("payment", showtime_id=showtime_id, movie_title=movie_title, consumables=str(consumable_data)))

    return render_template("consumables.html", columns=columns, rows=rows, showtime_id=showtime_id, movie_title=movie_title)

# Payment
@app.route("/payment/<showtime_id>/<movie_title>", methods=["GET", "POST"])
def payment(showtime_id, movie_title):
    ticket_price = 10.00

    consumables = request.args.get("consumables")
    consumables = eval(consumables) if consumables else {}

    total_consumable_price = 0
    connection = get_oracle_connection()
    cursor = connection.cursor()

    consumable_details = []
    for consumable, quantity in consumables.items():
        cursor.execute("SELECT PRICE FROM CONSUMABLES WHERE CONSNAME = :1", [consumable])
        price = float(cursor.fetchone()[0])
        total = price * int(quantity)
        total_consumable_price += total
        consumable_details.append((consumable, quantity, total))

    cursor.close()
    connection.close()

    total_price = ticket_price + total_consumable_price

    # Showtime detaylarını tablo formatına ayır
    showtime_details = showtime_id.split('|')
    showtime_table = {
        "SHOWDATE": showtime_details[0],
        "STARTTIME": showtime_details[1],
        "ENDTIME": showtime_details[2],
        "HALLID": showtime_details[3],
    }

    if request.method == "POST":
        return render_template(
            "order_summary.html",
            movie_title=movie_title,
            showtime_table=showtime_table,
            total_price=total_price,
            ticket_price=ticket_price,
            consumables=consumable_details,
            total_consumable_price=total_consumable_price
        )

    return render_template(
        "payment.html",
        movie_title=movie_title,
        showtime_table=showtime_table,
        total_price=total_price,
        ticket_price=ticket_price,
        consumables=consumable_details,
        total_consumable_price=total_consumable_price
    )


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
