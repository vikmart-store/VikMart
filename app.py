from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        image TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        total REAL NOT NULL,
        created_at TEXT NOT NULL
    )""")
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        products = [
            ("Smart Watch", 1999, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=600&q=80", "Electronics", "Modern smart watch for everyday fitness and notifications."),
            ("Bluetooth Speaker", 899, "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=600&q=80", "Electronics", "Portable speaker with powerful sound."),
            ("Running Shoes", 1499, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=600&q=80", "Fashion", "Lightweight shoes for running and daily use."),
            ("Backpack", 999, "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80", "Fashion", "Durable backpack for school, work and travel."),
            ("Coffee Mug", 399, "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=600&q=80", "Home", "Simple ceramic mug for tea and coffee.")
        ]
        conn.executemany(
            "INSERT INTO products(name,price,image,category,description) VALUES(?,?,?,?,?)",
            products
        )
    conn.commit()
    conn.close()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


def cart_items():
    cart = session.get("cart", {})
    conn = db()
    items = []
    total = 0
    for pid, qty in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p:
            subtotal = p["price"] * qty
            items.append({"product": p, "qty": qty, "subtotal": subtotal})
            total += subtotal
    conn.close()
    return items, total


@app.route("/")
def home():
    category = request.args.get("category", "All")
    q = request.args.get("q", "").strip()
    conn = db()
    if category != "All" and q:
        products = conn.execute(
            "SELECT * FROM products WHERE category=? AND (name LIKE ? OR description LIKE ?)",
            (category, f"%{q}%", f"%{q}%")
        ).fetchall()
    elif category != "All":
        products = conn.execute(
            "SELECT * FROM products WHERE category=?", (category,)
        ).fetchall()
    elif q:
        products = conn.execute(
            "SELECT * FROM products WHERE name LIKE ? OR description LIKE ?",
            (f"%{q}%", f"%{q}%")
        ).fetchall()
    else:
        products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template("index.html", products=products, category=category, q=q)


@app.post("/add/<int:product_id>")
def add(product_id):
    cart = session.get("cart", {})
    key = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    session["cart"] = cart
    return redirect(request.referrer or url_for("home"))


@app.route("/cart")
def cart():
    items, total = cart_items()
    return render_template("cart.html", items=items, total=total)


@app.post("/cart/update/<int:product_id>")
def update_cart(product_id):
    try:
        qty = max(0, int(request.form.get("qty", 1)))
    except (TypeError, ValueError):
        qty = 1
    cart = session.get("cart", {})
    if qty == 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = qty
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:product_id>")
def remove(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    items, total = cart_items()
    if not items:
        return redirect(url_for("cart"))
    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        address = request.form["address"].strip()
        if not name or not phone or not address:
            return render_template(
                "checkout.html", items=items, total=total,
                error="Please fill all fields."
            )
        conn = db()
        cur = conn.execute(
            "INSERT INTO orders(customer_name,phone,address,total,created_at) VALUES(?,?,?,?,?)",
            (name, phone, address, total, datetime.now().isoformat(timespec="seconds"))
        )
        order_id = cur.lastrowid
        conn.commit()
        conn.close()
        session["cart"] = {}
        return render_template("success.html", order_id=order_id, total=total, name=name)
    return render_template("checkout.html", items=items, total=total)


@app.get("/api/cart-count")
def cart_count():
    return jsonify(sum(session.get("cart", {}).values()))


# ---------------- ADMIN PANEL ----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
       print(
    "LOGIN CHECK:",
    repr(username),
    repr(ADMIN_USERNAME),
    len(password),
    len(ADMIN_PASSWORD or ""),
    username == ADMIN_USERNAME,
    password == ADMIN_PASSWORD
)
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid username or password."
    return render_template("admin_login.html", error=error)


@app.post("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = db()
    products = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    return render_template(
        "admin_dashboard.html",
        products=products,
        orders=orders,
        product_count=product_count,
        order_count=order_count
    )


@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def admin_add_product():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price_text = request.form.get("price", "").strip()
        image = request.form.get("image", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        if not all([name, price_text, image, category, description]):
            error = "All fields are required."
        else:
            try:
                price = float(price_text)
                if price < 0:
                    raise ValueError
            except ValueError:
                error = "Price must be a valid non-negative number."

        if error is None:
            conn = db()
            conn.execute(
                "INSERT INTO products(name,price,image,category,description) VALUES(?,?,?,?,?)",
                (name, price, image, category, description)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("admin_dashboard"))

    return render_template("admin_product_form.html", product=None, error=error)


@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_product(product_id):
    conn = db()
    product = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    conn.close()
    if not product:
        return "Product not found", 404

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price_text = request.form.get("price", "").strip()
        image = request.form.get("image", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        try:
            price = float(price_text)
            if price < 0:
                raise ValueError
        except (TypeError, ValueError):
            price = 0
            error = "Price must be a valid non-negative number."

        if not all([name, image, category, description]):
            error = "All fields are required."

        if error is None:
            conn = db()
            conn.execute(
                "UPDATE products SET name=?, price=?, image=?, category=?, description=? WHERE id=?",
                (name, price, image, category, description, product_id)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("admin_dashboard"))

        product = dict(product)
        product.update({
            "name": name, "price": price_text, "image": image,
            "category": category, "description": description
        })

    return render_template("admin_product_form.html", product=product, error=error)


@app.post("/admin/products/delete/<int:product_id>")
@admin_required
def admin_delete_product(product_id):
    conn = db()
    conn.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


# Initialize tables when running directly or through Gunicorn.
init_db()

if __name__ == "__main__":
    app.run(debug=False)
