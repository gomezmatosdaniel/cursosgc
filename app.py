import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    flash,
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
    DATABASE=os.path.join(app.instance_path, "cursosgc.sqlite"),
)

os.makedirs(app.instance_path, exist_ok=True)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            is_subscribed INTEGER NOT NULL DEFAULT 0,
            subscription_plan TEXT,
            subscription_start TIMESTAMP,
            subscription_end TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS question (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            FOREIGN KEY(test_id) REFERENCES test(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS choice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(question_id) REFERENCES question(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS result (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            test_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            taken_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE,
            FOREIGN KEY(test_id) REFERENCES test(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS answer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            selected_choice_id INTEGER,
            FOREIGN KEY(result_id) REFERENCES result(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES question(id) ON DELETE CASCADE,
            FOREIGN KEY(selected_choice_id) REFERENCES choice(id) ON DELETE SET NULL
        );
        """
    )

    existing_tests = db.execute("SELECT COUNT(*) FROM test").fetchone()[0]
    if existing_tests == 0:
        seed_tests(db)
    db.commit()


def seed_tests(db):
    professional_skills_id = db.execute(
        "INSERT INTO test (title, description) VALUES (?, ?)",
        (
            "Fundamentos de habilidades profesionales",
            "Evalúa tus conocimientos en comunicación, gestión del tiempo y trabajo en equipo.",
        ),
    ).lastrowid

    project_management_id = db.execute(
        "INSERT INTO test (title, description) VALUES (?, ?)",
        (
            "Gestión de proyectos ágiles",
            "Comprueba tu entendimiento de Scrum, Kanban y métricas ágiles.",
        ),
    ).lastrowid

    insert_question(
        db,
        professional_skills_id,
        "¿Cuál es el primer paso para resolver un conflicto en el equipo?",
        [
            ("Ignorar el problema y esperar a que se resuelva solo", False),
            ("Analizar la situación y escuchar a las partes involucradas", True),
            ("Asignar responsabilidades sin consultar", False),
            ("Escalar inmediatamente a la dirección", False),
        ],
    )

    insert_question(
        db,
        professional_skills_id,
        "¿Qué herramienta ayuda a priorizar tareas urgentes e importantes?",
        [
            ("Diagrama de Gantt", False),
            ("Matriz de Eisenhower", True),
            ("Gráfico de Pareto", False),
            ("Método de Montecarlo", False),
        ],
    )

    insert_question(
        db,
        project_management_id,
        "¿Cuál es la duración recomendada de una Daily Scrum?",
        [
            ("5 minutos", False),
            ("15 minutos", True),
            ("45 minutos", False),
            ("Depende del número de historias", False),
        ],
    )

    insert_question(
        db,
        project_management_id,
        "¿Qué tablero visual se asocia comúnmente con Kanban?",
        [
            ("Eisenhower", False),
            ("Burndown", False),
            ("Tres columnas: Pendiente, En progreso, Hecho", True),
            ("Mapa de calor", False),
        ],
    )


def insert_question(db, test_id, prompt, choices):
    question_id = db.execute(
        "INSERT INTO question (test_id, prompt) VALUES (?, ?)", (test_id, prompt)
    ).lastrowid
    db.executemany(
        "INSERT INTO choice (question_id, label, is_correct) VALUES (?, ?, ?)",
        [(question_id, label, 1 if is_correct else 0) for label, is_correct in choices],
    )


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Inicia sesión para continuar", "warning")
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


def subscription_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Inicia sesión para continuar", "warning")
            return redirect(url_for("login", next=request.path))

        user = get_current_user()
        if not user:
            flash("Inicia sesión para continuar", "warning")
            return redirect(url_for("login"))

        subscription_end = user["subscription_end"]
        if isinstance(subscription_end, str):
            try:
                subscription_end = datetime.fromisoformat(subscription_end)
            except ValueError:
                subscription_end = None

        if subscription_end and subscription_end < datetime.utcnow():
            db = get_db()
            db.execute(
                "UPDATE user SET is_subscribed = 0 WHERE id = ?", (user["id"],)
            )
            db.commit()
            flash("Tu suscripción ha expirado. Renueva para acceder a los tests", "warning")
            return redirect(url_for("subscribe"))

        if not user["is_subscribed"]:
            flash("Activa tu suscripción para acceder a los tests", "info")
            return redirect(url_for("subscribe"))
        return view(**kwargs)

    return wrapped_view


def get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    db = get_db()
    return db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


@app.route("/")
def index():
    return render_template("index.html", user=get_current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()

        error = None
        if not full_name:
            error = "El nombre completo es obligatorio"
        elif not email:
            error = "El correo electrónico es obligatorio"
        elif not password or len(password) < 6:
            error = "La contraseña debe tener al menos 6 caracteres"

        if error is None:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO user (email, password_hash, full_name) VALUES (?, ?, ?)",
                    (email, generate_password_hash(password), full_name),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = "Ya existe una cuenta con ese correo"
            else:
                flash("Cuenta creada. Ahora puedes iniciar sesión", "success")
                return redirect(url_for("login"))

        flash(error, "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()

        error = None
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Credenciales inválidas"

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            flash("Bienvenido de nuevo", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))

        flash(error, "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    db = get_db()
    rows = db.execute(
        """
        SELECT r.id, r.score, r.total_questions, r.taken_at, t.title
        FROM result r
        JOIN test t ON t.id = r.test_id
        WHERE r.user_id = ?
        ORDER BY r.taken_at DESC
        LIMIT 5
        """,
        (user["id"],),
    ).fetchall()
    recent_results = []
    for row in rows:
        taken_at = row["taken_at"]
        if isinstance(taken_at, str):
            try:
                taken_at = datetime.fromisoformat(taken_at)
            except ValueError:
                taken_at = None
        formatted_date = taken_at.strftime("%d/%m/%Y %H:%M") if taken_at else ""
        data = dict(row)
        data["formatted_date"] = formatted_date
        recent_results.append(data)
    return render_template("dashboard.html", user=user, recent_results=recent_results)


@app.route("/subscribe", methods=["GET", "POST"])
@login_required
def subscribe():
    user = get_current_user()
    if user["is_subscribed"]:
        flash("Ya tienes una suscripción activa", "info")
        return redirect(url_for("tests"))

    if request.method == "POST":
        plan = request.form.get("plan")
        if plan not in {"mensual", "anual"}:
            flash("Selecciona un plan válido", "danger")
            return render_template("subscribe.html", user=user)
        db = get_db()
        subscription_days = 30 if plan == "mensual" else 365
        now = datetime.utcnow()
        db.execute(
            """
            UPDATE user
            SET is_subscribed = 1,
                subscription_plan = ?,
                subscription_start = ?,
                subscription_end = ?
            WHERE id = ?
            """,
            (plan, now, now + timedelta(days=subscription_days), user["id"]),
        )
        db.commit()
        flash("Suscripción activada. ¡Disfruta tus cursos tipo test!", "success")
        return redirect(url_for("tests"))

    return render_template("subscribe.html", user=user)


@app.route("/tests")
@subscription_required
def tests():
    db = get_db()
    available_tests = db.execute(
        "SELECT id, title, description FROM test ORDER BY id"
    ).fetchall()
    return render_template("tests.html", tests=available_tests, user=get_current_user())


@app.route("/tests/<int:test_id>", methods=["GET", "POST"])
@subscription_required
def take_test(test_id):
    db = get_db()
    test = db.execute("SELECT * FROM test WHERE id = ?", (test_id,)).fetchone()
    if test is None:
        flash("El test solicitado no existe", "warning")
        return redirect(url_for("tests"))

    questions = db.execute(
        "SELECT * FROM question WHERE test_id = ? ORDER BY id", (test_id,)
    ).fetchall()
    choices = {
        question["id"]: db.execute(
            "SELECT * FROM choice WHERE question_id = ? ORDER BY id",
            (question["id"],),
        ).fetchall()
        for question in questions
    }

    if request.method == "POST":
        score = 0
        total_questions = len(questions)
        user_answers = []
        for question in questions:
            selected_choice_id = request.form.get(f"question-{question['id']}")
            if selected_choice_id is not None:
                choice_row = db.execute(
                    "SELECT id, is_correct FROM choice WHERE id = ?",
                    (selected_choice_id,),
                ).fetchone()
                if choice_row and choice_row["is_correct"]:
                    score += 1
                user_answers.append((question["id"], selected_choice_id))
            else:
                user_answers.append((question["id"], None))

        db.execute(
            "INSERT INTO result (user_id, test_id, score, total_questions) VALUES (?, ?, ?, ?)",
            (session["user_id"], test_id, score, total_questions),
        )
        result_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        db.executemany(
            "INSERT INTO answer (result_id, question_id, selected_choice_id) VALUES (?, ?, ?)",
            [(result_id, question_id, selected_choice_id) for question_id, selected_choice_id in user_answers],
        )
        db.commit()

        flash("Test enviado. Consulta tus resultados a continuación", "success")
        return redirect(url_for("view_result", test_id=test_id, result_id=result_id))

    return render_template(
        "take_test.html",
        test=test,
        questions=questions,
        choices=choices,
        user=get_current_user(),
    )


@app.route("/tests/<int:test_id>/result/<int:result_id>")
@subscription_required
def view_result(test_id, result_id):
    db = get_db()
    result = db.execute(
        """
        SELECT r.*, t.title
        FROM result r
        JOIN test t ON t.id = r.test_id
        WHERE r.id = ? AND r.user_id = ? AND r.test_id = ?
        """,
        (result_id, session["user_id"], test_id),
    ).fetchone()

    if result is None:
        flash("No se encontró el resultado solicitado", "warning")
        return redirect(url_for("tests"))

    questions = db.execute(
        "SELECT * FROM question WHERE test_id = ? ORDER BY id",
        (test_id,),
    ).fetchall()

    answers = db.execute(
        """
        SELECT a.question_id, a.selected_choice_id, c.label AS selected_label,
               c.is_correct AS selected_is_correct
        FROM answer a
        LEFT JOIN choice c ON c.id = a.selected_choice_id
        WHERE a.result_id = ?
        """,
        (result_id,),
    ).fetchall()
    answers_by_question = {answer["question_id"]: answer for answer in answers}

    correct_choices = db.execute(
        """
        SELECT question_id, label
        FROM choice
        WHERE question_id IN (
            SELECT id FROM question WHERE test_id = ?
        ) AND is_correct = 1
        """,
        (test_id,),
    ).fetchall()
    correct_by_question = {}
    for choice in correct_choices:
        correct_by_question.setdefault(choice["question_id"], []).append(choice["label"])

    return render_template(
        "result.html",
        result=result,
        questions=questions,
        answers=answers_by_question,
        correct_answers=correct_by_question,
        user=get_current_user(),
    )


@app.context_processor
def inject_now():
    return {"current_year": datetime.utcnow().year}


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
