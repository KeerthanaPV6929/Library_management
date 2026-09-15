from flask import Flask,render_template,request,redirect,url_for,session,flash
from datetime import date,timedelta
from functools import wraps

app=Flask(__name__)                       # create application
app.secret_key="classroom_secret_key"      #Required for session management

#in-memory "database"
books=[
    {"id": 1, "title": "Clean Code", "author": "Robert C. Martin",
     "category": "Programming", "total_copies": 3, "available_copies": 3},
    {"id": 2, "title": "The Hobbit", "author": "J.R.R. Tolkien",
     "category": "Fiction", "total_copies": 2, "available_copies": 2},
    {"id": 3, "title": "A Brief History of Time", "author": "Stephen Hawking",
     "category": "Science", "total_copies": 1, "available_copies": 1}
]
next_book_id= 4 
  #counter need to assign the next book id
members={}
    #username:{name,email,password}


issued_records=[]  #each:{record_id,book_id,username,issue_date,due_date,return_date,fine}
next_record_id= 1  # counnter used to assign the next issue record id

ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin123"

FINE_PER_DAY=5
LOAN_PERIOD_DAYS=14   #books are due 14 days after issue


'''small reusable wrappers so we dont repeat if not logged in everywhere'''

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):                          #accept all and pass along,if it is not the orginal fn expected 
        if "username" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)               #if the person was logged in. then run the original function they want
    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access only.")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


#---------small helper function--------
def find_book(book_id):
    """Return the book dict with this id, or None."""
    return next((b for b in books if b["id"] == book_id), None)


def find_record(record_id):
    """Return the issue-record dict with this id, or None."""
    return next((r for r in issued_records if r["record_id"] == record_id), None)


def active_records_for(username):
    """All books currently borrowed (not yet returned) by this member."""
    return [r for r in issued_records if r["username"] == username and r["return_date"] is None]

'''-------------login and logout--------------------'''

@app.route('/')              #landing page
def home():
    if "username" not in session:
        return redirect(url_for("login"))
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("dashboard"))

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username=request.form['username']
        name=request.form['name']
        email=request.form['email']
        password=request.form['password']
        confirm=request.form['confirm']

        if username in members:
            flash('Username already exists. Try logging in.')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.')
            return redirect(url_for('register'))
        if username in members or username == ADMIN_USERNAME:
            flash("That username is already taken.")
            return redirect(url_for("register"))

        members[username] = {"name": name, "email": email, "password": password}
        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))
    return render_template('register.html')                              #run if the request was GET


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']

      #check admin----------
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["username"] = username
            session["is_admin"] = True
            flash("Welcome back, admin!")
            return redirect(url_for("admin_dashboard"))

      # Then check members-------
        user = members.get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["is_admin"] = False
            flash(f"Welcome back, {user['name']}!")
            return redirect(url_for("dashboard"))
       
        flash('Invalid username or password.')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

#------open to any logged-in user
@app.route("/catalog")                               #for search
@login_required                                      #only logged in users can access it
def catalog():
    query = request.args.get("q", "").lower()         #this is for searching the book,if it is uppercase or lowercase it give the same result
    if query:
        results = [
            b for b in books
            if query in b["title"].lower() or query in b["author"].lower()
        ]
    else:
        results = books
    return render_template("catalog.html", books=results, query=query)


#----------member dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    username = session["username"]
    my_records = active_records_for(username)

    
    today = date.today()
    for r in my_records:
        r["book"] = find_book(r["book_id"])
        r["is_overdue"] = r["due_date"] < today

    total_fine_due = sum(
        max(0, (today - r["due_date"]).days) * FINE_PER_DAY
        for r in my_records if r["due_date"] < today
    )

    return render_template("dashboard.html", records=my_records, total_fine_due=total_fine_due)



#--------Admin Dashboard
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    today = date.today()
    currently_issued = [r for r in issued_records if r["return_date"] is None]
    overdue = [r for r in currently_issued if r["due_date"] < today]

    # attach display info for the overdue table
    for r in overdue:
        r["book"] = find_book(r["book_id"])
        r["days_late"] = (today - r["due_date"]).days

    return render_template(
        "admin_dashboard.html",
        total_books=len(books),
        total_members=len(members),
        issued_count=len(currently_issued),
        overdue_records=overdue
    )


#-------book info

@app.route("/admin/books/add", methods=["GET", "POST"])
@admin_required
def add_book():
    global next_book_id
    if request.method == "POST":
        title = request.form["title"]
        author = request.form["author"]
        category = request.form["category"]
        try:
            copies = int(request.form["copies"])
        except ValueError:
            copies = 1

        books.append({
            "id": next_book_id,
            "title": title,
            "author": author,
            "category": category,
            "total_copies": copies,
            "available_copies": copies
        })
        next_book_id += 1
        flash(f'"{title}" was added to the catalog.')
        return redirect(url_for("catalog"))

    return render_template("admin_add_book.html")


@app.route("/admin/books/edit/<int:book_id>", methods=["GET", "POST"])
@admin_required
def edit_book(book_id):
    book = find_book(book_id)
    if not book:
        flash("Book not found.")
        return redirect(url_for("catalog"))

    if request.method == "POST":
        # work out how many copies are currently on loan, so we don't lose track of them
        copies_on_loan = book["total_copies"] - book["available_copies"]

        book["title"] = request.form["title"]
        book["author"] = request.form["author"]
        book["category"] = request.form["category"]
        try:
            new_total = int(request.form["copies"])
        except ValueError:
            new_total = book["total_copies"]

        book["total_copies"] = new_total
        book["available_copies"] = max(0, new_total - copies_on_loan)

        flash(f'"{book["title"]}" was updated.')
        return redirect(url_for("catalog"))

    return render_template("admin_edit_book.html", book=book)


@app.route("/admin/books/delete/<int:book_id>")
@admin_required
def delete_book(book_id):
    global books
    book = find_book(book_id)
    if not book:
        flash("Book not found.")
    else:
        books = [b for b in books if b["id"] != book_id]
        flash(f'"{book["title"]}" was removed from the catalog.')
    return redirect(url_for("catalog"))





@app.route("/admin/issue", methods=["GET", "POST"])
@admin_required
def issue_book():
    global next_record_id
    if request.method == "POST":
        book_id = int(request.form["book_id"])
        username = request.form["username"]

        book = find_book(book_id)
        if not book:
            flash("Selected book does not exist.")
            return redirect(url_for("issue_book"))
        if username not in members:
            flash("Selected member does not exist.")
            return redirect(url_for("issue_book"))
        if book["available_copies"] < 1:
            flash(f'No copies of "{book["title"]}" are available right now.')
            return redirect(url_for("issue_book"))

        book["available_copies"] -= 1
        issue_date = date.today()
        due_date = issue_date + timedelta(days=LOAN_PERIOD_DAYS)

        issued_records.append({
            "record_id": next_record_id,
            "book_id": book_id,
            "username": username,
            "issue_date": issue_date,
            "due_date": due_date,
            "return_date": None,
            "fine": 0
        })
        next_record_id += 1

        flash(f'"{book["title"]}" issued to {username}. Due back on {due_date}.')
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_issue.html", books=books, members=members)


@app.route("/admin/return/<int:record_id>")
@admin_required
def return_book(record_id):
    record = find_record(record_id)
    if not record:
        flash("Loan record not found.")
        return redirect(url_for("admin_dashboard"))

    if record["return_date"] is not None:
        flash("This book has already been returned.", "error")
        return redirect(url_for("admin_dashboard"))

    record["return_date"] = date.today()
    days_late = (record["return_date"] - record["due_date"]).days
    record["fine"] = max(0, days_late) * FINE_PER_DAY

    book = find_book(record["book_id"])
    if book:
        book["available_copies"] += 1
        title = book["title"]
    else:
        title = "book"

    if record["fine"] > 0:
        flash(
            f'"{title}" returned. It was {days_late} day(s) overdue - fine: Rs. {record["fine"]}.'
        )
    else:
        flash(f'"{title}" returned on time. No fine.')

    return redirect(url_for("admin_dashboard"))



if __name__ == "__main__":
    app.run(debug=True)