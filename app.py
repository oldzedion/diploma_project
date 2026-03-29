import random
import os
import datetime

from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

# PDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Шляхи
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# Flask app
app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = 'secret123'

# Admin
ADMIN_EMAIL = "admin@site.com"
ADMIN_PASSWORD_HASH = generate_password_hash("Admin2026!")

# Підключення до БД
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
if not app.config['SQLALCHEMY_DATABASE_URI']:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'results.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Моделі
class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120))
    fullname = db.Column(db.String(200))
    score = db.Column(db.Integer)
    total = db.Column(db.Integer)
    time_spent = db.Column(db.Integer)
    violations = db.Column(db.Integer, default=0)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    options = db.relationship('Option', backref='question', cascade="all, delete")

    type = db.Column(db.String(20), default="single")  # single, multiple, matching, open

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # для open питань (текст)
    text_answer = db.Column(db.Text)

    # для multiple (кілька варіантів)
    selected_options = db.Column(db.Text)  # JSON або "1,3,4"

    # для matching (відповідності) (не реалізовано)
    matching_data = db.Column(db.Text)  # JSON

    # зв'язки
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    result_id = db.Column(db.Integer, db.ForeignKey('result.id'))

# Питання
questions = [
    {"question": "Столиця України?", "options": ["Київ", "Львів", "Одеса"], "answer": "Київ"},
    {"question": "2 + 2 = ?", "options": ["3", "4", "5"], "answer": "4"},
    {"question": "Яка мова програмування використовується у Flask?", "options": ["Java", "Python", "C++"], "answer": "Python"},
    {"question": "HTML використовується для?", "options": ["Створення структури веб-сторінки", "Роботи з базами даних", "Обчислень"], "answer": "Створення структури веб-сторінки"},
    {"question": "CSS відповідає за?", "options": ["Логіку програми", "Стиль сторінки", "Базу даних"], "answer": "Стиль сторінки"},
    {"question": "Який метод HTTP використовується для відправки форми?", "options": ["GET", "POST", "PUT"], "answer": "POST"},
    {"question": "Що таке SQLAlchemy?", "options": ["Мова програмування", "ORM для роботи з БД", "Операційна система"], "answer": "ORM для роботи з БД"},
    {"question": "Яка функція використовується для рендерингу HTML у Flask?", "options": ["print()", "render_template()", "open()"], "answer": "render_template()"},
    {"question": "Що таке база даних?", "options": ["Набір стилів", "Сховище даних", "Мова програмування"], "answer": "Сховище даних"},
    {"question": "Що таке Python?", "options": ["Мова програмування", "Операційна система", "Браузер"], "answer": "Мова програмування"}
]
#тимчасова частина для перевірки підключення PostgreSQL
from sqlalchemy import text

@app.route("/test-db")
def test_db():
    try:
        result = db.session.execute(text("SELECT 1"))
        return f"✅ DB connected! Result: {result.scalar()}"
    except Exception as e:
        return f"❌ DB connection failed: {e}"
#тимчасова частина для перевірки підключення PostgreSQL

# Реєстрація
@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get("email")
        fullname = request.form.get("fullname")

        if not email.endswith("@nubip.edu.ua"):
            return render_template("register.html", error="Введіть університетську пошту (домен має бути @nubip.edu.ua)", email=email, fullname=fullname)

        session['email'] = email
        session['fullname'] = fullname
        session.pop('questions', None)
        return redirect(url_for('rules'))

    return render_template("register.html")


# Admin login
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        if email == ADMIN_EMAIL and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin'] = True
            return redirect('/admin/dashboard')
        else:
            return render_template("admin_login.html", error="Невірні дані")
    return render_template("admin_login.html")


# Admin dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin/login')

    results = Result.query.all()
    for r in results:
        minutes = r.time_spent // 60
        seconds = r.time_spent % 60
        r.time_display = f"{minutes}хв {seconds}с"

    return render_template("admin_dashboard.html", results=results)

#ADMIN СПИСОК ПИТАНЬ
@app.route('/admin/questions')
def admin_questions():
    if 'admin' not in session:
        return redirect('/admin/login')

    questions = Question.query.all()
    return render_template("admin_questions.html", questions=questions)

#ДОДАЄМО МАРШРУТ 
@app.route('/admin/questions/delete/<int:id>')
def delete_question(id):
    if 'admin' not in session:
        return redirect('/admin/login')

    question = Question.query.get(id)

    if question:
        db.session.delete(question)
        db.session.commit()

    return redirect('/admin/questions')


# add_question
@app.route('/admin/questions/add', methods=['GET', 'POST'])
def add_question():
    if 'admin' not in session:
        return redirect('/admin/login')

    # GET (відкрити сторінку)
    if request.method == 'GET':
        return render_template("add_question.html")

    # POST (збереження)
    text = request.form.get("question")
    q_type = request.form.get("type")

    if not text or not q_type:
        return "Помилка: заповніть всі поля"

    question = Question(text=text, type=q_type)
    db.session.add(question)
    db.session.flush()

    # SINGLE ПИТАННЯ
    if q_type == "single":
        options = request.form.getlist("options")
        correct_index = request.form.get("correct")

        for i, opt in enumerate(options):
            if opt.strip() == "":
                continue

            db.session.add(Option(
                text=opt,
                is_correct=(str(i) == correct_index),
                question_id=question.id
            ))

    # MULTIPLE ПИТАННЯ
    elif q_type == "multiple":
        options = request.form.getlist("options")
        correct_indexes = request.form.getlist("correct")

        for i, opt in enumerate(options):
            if opt.strip() == "":
                continue

            db.session.add(Option(
                text=opt,
                is_correct=(str(i) in correct_indexes),
                question_id=question.id
            ))

    # OPEN ПИТАННЯ
    elif q_type == "open":
        keywords = request.form.get("keywords")

        if keywords:
            for word in keywords.split(","):
                db.session.add(Option(
                    text=word.strip().lower(),
                    is_correct=True,
                    question_id=question.id
                ))

    
    db.session.commit()
    return redirect('/admin/questions')


#edit_questions
@app.route('/admin/questions/edit/<int:id>', methods=['GET', 'POST'])
def edit_question(id):
    if 'admin' not in session:
        return redirect('/admin/login')

    question = Question.query.get(id)

    if not question:
        return "Питання не знайдено"

    if request.method == 'POST':
        text = request.form.get("question")
        options = request.form.getlist("options")
        correct_index = request.form.get("correct")

        if not text or len(options) < 2 or correct_index is None:
            return "Помилка: заповніть всі поля"

        # оновлюємо текст питання
        question.text = text

        # видаляємо старі варіанти
        Option.query.filter_by(question_id=question.id).delete()

        # додаємо нові
        for i, opt in enumerate(options):
            if opt.strip() == "":
                continue

            new_option = Option(
                text=opt,
                is_correct=(str(i) == correct_index),
                question_id=question.id
            )
            db.session.add(new_option)

        db.session.commit()

        return redirect('/admin/questions')

    return render_template("edit_question.html", question=question)


#ВИДАЛЕННЯ У DASHBOARD
@app.route('/admin/delete/<int:id>')
def admin_delete(id):
    if 'admin' not in session:
        return redirect('/admin/login')

    result = Result.query.get(id)

    if result:
        db.session.delete(result)
        db.session.commit()

    return redirect('/admin/dashboard')


# ПРАВИЛА
@app.route('/rules')
def rules():
    return render_template("rules.html")


# Test
@app.route('/test', methods=['GET', 'POST'])
def test():
    if 'email' not in session:
        return redirect('/')

    existing = Result.query.filter_by(email=session['email']).first()
    if existing:
        return render_template("already_passed.html", result=existing)

    # ОДоразово генеруємо питання
    if 'questions' not in session:
        db_questions = Question.query.all()
        shuffled_questions = []

        for q in db_questions:
            question_data = {
                "id": q.id,
                "question": q.text,
                "type": q.type
            }

            # SINGLE питаня
            if q.type == "single":
                options = [opt.text for opt in q.options]
                random.shuffle(options)

                question_data["options"] = options
                question_data["answer"] = next(
                    opt.text for opt in q.options if opt.is_correct
                )

            # MULTIPLE питання
            elif q.type == "multiple":
                options = [opt.text for opt in q.options]
                random.shuffle(options)

                question_data["options"] = options
                question_data["answers"] = [
                    opt.text for opt in q.options if opt.is_correct
                ]

            # OPEN питання
            elif q.type == "open":
                question_data["keywords"] = [
                    opt.text.lower() for opt in q.options if opt.is_correct
                ]

            # MATCHING питання (не реалізовано)
            elif q.type == "matching":
                pairs = [(opt.text, opt.is_correct) for opt in q.options]
                question_data["pairs"] = pairs

            shuffled_questions.append(question_data)

        # перемішуємо 1 раз
        random.shuffle(shuffled_questions)

        # зберігаємо в session
        session['questions'] = shuffled_questions

    # POST (обробка результатів)
    if request.method == 'POST':
        try:
            time_spent = int(request.form.get("time_spent", 0))
        except ValueError:
            time_spent = 0

        violations = int(request.form.get("violations", 0) or 0)
        session['violations'] = violations

        score = 0
        user_answers = []

        for i, q in enumerate(session['questions']):
            q_type = q.get("type")

            # SINGLE питання
            if q_type == "single":
                user_answer = request.form.get(f"q{i}")
                user_answers.append(user_answer)

                if user_answer == q.get("answer"):
                    score += 1

            # MULTIPLE питання
            elif q_type == "multiple":
                user_answer = request.form.getlist(f"q{i}")
                user_answers.append(user_answer)

                correct_answers = q.get("answers", [])

                if set(user_answer) == set(correct_answers):
                    score += 1

            # OPEN питання
            elif q_type == "open":
                user_answer = request.form.get(f"q{i}", "").lower()
                user_answers.append(user_answer)

                keywords = q.get("keywords", [])

                matches = sum(1 for word in keywords if word in user_answer)

                if keywords and matches / len(keywords) >= 0.5:
                    score += 1

            # MATCHING питання (не реалізовно )
            elif q_type == "matching":
                user_answers.append("matching_not_checked")

        result = Result(
            email=session['email'],
            fullname=session['fullname'],
            score=score,
            total=len(session['questions']),
            time_spent=time_spent,
            violations=session.get('violations', 0)
        )

        db.session.add(result)
        db.session.commit()

        total_questions = len(session['questions']) if session.get('questions') else 0
        percentage = round((score / total_questions) * 100) if total_questions > 0 else 0

        session['last_score'] = score
        session['last_percentage'] = percentage
        session['last_time'] = time_spent
        session['answers'] = user_answers

        return redirect(url_for('result'))

    return render_template("test.html", questions=session['questions'])


# РЕЗУЛЬТАТ
@app.route('/result')
def result():
    if 'last_score' not in session:
        return redirect('/')

    return render_template(
        "result.html",
        fullname=session['fullname'],
        score=session['last_score'],
        total=len(session['questions']),
        percentage=session['last_percentage'],
        time_spent=session['last_time']
    )


# ПЕРЕГЛЯД ВІДПОВІДЕЙ
@app.route('/review')
def review():
    if 'answers' not in session:
        return redirect('/')

    return render_template(
        "review.html",
        questions=session['questions'],
        answers=session['answers']
    )

# REVIEW PDF
@app.route('/download_review_pdf')
def download_review_pdf():
    if 'answers' not in session:
        return redirect('/')

    questions = session['questions']
    user_answers = session['answers']
    fullname = session.get('fullname', 'Користувач')

    font_path = os.path.join(BASE_DIR, "DejaVuSans.ttf")
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))

    file_path = os.path.join(
        BASE_DIR,
        f"review_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

    pdf = SimpleDocTemplate(
        file_path,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    # СТИЛІ
    title_style = ParagraphStyle(
        name='Title',
        parent=styles['Title'],
        fontName='DejaVu',
        alignment=1,
        spaceAfter=15
    )

    header_style = ParagraphStyle(
        name='Header',
        parent=styles['Normal'],
        fontName='DejaVu',
        fontSize=12,
        spaceAfter=10
    )

    question_style = ParagraphStyle(
        name='Question',
        parent=styles['Normal'],
        fontName='DejaVu',
        fontSize=11,
        spaceAfter=6
    )

    option_style = ParagraphStyle(
        name='Option',
        parent=styles['Normal'],
        fontName='DejaVu',
        fontSize=10,
        leftIndent=10
    )

    elements = []

    # ПІДРАХУНОК РЕЗУЛЬТАТУ
    score = 0
    for i, q in enumerate(questions):
        q_type = q.get("type")
        user = user_answers[i]

        if q_type == "single":
            if user == q.get("answer"):
                score += 1
        elif q_type == "multiple":
            correct = set(q.get("answers", []))
            if set(user) == correct:
                score += 1
        elif q_type == "open":
            keywords = q.get("keywords", [])
            if keywords and user.lower() == keywords[0].lower():
                score += 1
        # matching поки не враховуємо (не реалізовано)

    total = len(questions)
    percent = round(score / total * 100) if total > 0 else 0

    # ЗАГОЛОВОК
    elements.append(Paragraph("Звіт тестування", title_style))
    elements.append(Paragraph(f"<b>ПІБ:</b> {fullname}", header_style))
    elements.append(Paragraph(f"<b>Результат:</b> {score}/{total} ({percent}%)", header_style))
    elements.append(Spacer(1, 10))

    # ПИТАННЯ
    for i, q in enumerate(questions):
        q_type = q.get("type")
        user = user_answers[i]

        # визначаємо правильну відповідь для відображення
        if q_type == "single":
            correct = q.get("answer")
            is_correct = user == correct
            options = q.get("options", [])
        elif q_type == "multiple":
            correct = set(q.get("answers", []))
            is_correct = set(user) == correct
            options = q.get("options", [])
        elif q_type == "open":
            correct = q.get("keywords", [])
            is_correct = correct and user.lower() == correct[0].lower()
            options = [user]  # для open просто показуємо відповідь користувача
        else:  # matching або інші (matching не реалізовано)
            correct = None
            is_correct = False
            options = q.get("options", [])

        # колір блоку
        bg_color = colors.whitesmoke
        border_color = colors.green if is_correct else colors.red

        # текст питання
        question_text = Paragraph(f"<b>{i+1}. {q['question']}</b>", question_style)

        # варіанти
        option_paragraphs = []
        for option in options:
            if q_type == "single" and option == correct:
                prefix = "✔ "
            elif q_type == "multiple" and option in correct:
                prefix = "✔ "
            elif q_type == "open":
                prefix = "✔ " if is_correct else "✖ "
            elif option == user:
                prefix = "✖ "
            else:
                prefix = "• "

            option_paragraphs.append(Paragraph(prefix + str(option), option_style))

        block_data = [[question_text]] + [[opt] for opt in option_paragraphs]

        table = Table(block_data, colWidths=[480])
        table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'DejaVu'),
            ('BACKGROUND', (0,0), (-1,-1), bg_color),
            ('BOX', (0,0), (-1,-1), 2, border_color),
            ('INNERPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 12))

    pdf.build(elements)
    return send_file(file_path, as_attachment=True)

# РЕЗУЛЬТАТИ
@app.route('/results')
def results():
    all_results = Result.query.all()
    return render_template("results.html", results=all_results)


# Download PDF для results
@app.route('/download_pdf')
def download_pdf():
    results = Result.query.all()
    font_path = os.path.join(BASE_DIR, "DejaVuSans.ttf")
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))
    file_path = os.path.join(BASE_DIR, f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf = SimpleDocTemplate(file_path, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(name='Title', parent=styles['Title'], fontName='DejaVu', alignment=1, spaceAfter=15)
    header_style = ParagraphStyle(name='Header', parent=styles['Normal'], fontName='DejaVu', fontSize=11, spaceAfter=10)
    cell_style = ParagraphStyle(name='Cell', fontName='DejaVu', fontSize=9, leading=11)

    elements = []
    elements.append(Paragraph("Звіт результатів тестування", title_style))
    elements.append(Paragraph(f"Дата: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", header_style))

    data = [["ID", "Email", "ПІБ", "Бали", "Всього", "%", "Час", "Порушення", "Статус"]]
    percent_list = []

    for r in results:
        percent = round((r.score / r.total) * 100)
        minutes = r.time_spent // 60
        seconds = r.time_spent % 60
        time_display = f"{minutes}хв {seconds}с"
        percent_list.append(percent)
        status = "✔ Складено" if percent >= 50 else "✖ Не складено"
        data.append([
            Paragraph(str(r.id), cell_style),
            Paragraph(r.email, cell_style),
            Paragraph(r.fullname, cell_style),
            Paragraph(str(r.score), cell_style),
            Paragraph(str(r.total), cell_style),
            Paragraph(f"{percent}%", cell_style),
            Paragraph(time_display, cell_style),
            Paragraph(str(r.violations), cell_style),
            Paragraph(status, cell_style)
        ])

    table = Table(data, colWidths=[30, 120, 140, 35, 35, 40, 60, 60, 80])
    style = TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'DejaVu'),
        ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ])
    for i in range(1, len(data)):
        percent = percent_list[i - 1]
        if percent >= 50:
            style.add('BACKGROUND', (0, i), (-1, i), colors.lightgreen)
        else:
            style.add('BACKGROUND', (0, i), (-1, i), colors.pink)
    table.setStyle(style)
    elements.append(table)
    pdf.build(elements)
    return send_file(file_path, as_attachment=True)

#тимчасовий шмат коду
def seed_questions():
    if Question.query.first():
        return  # щоб не дублювати

    questions_data = [
        {"question": "Столиця України?", "options": ["Київ", "Львів", "Одеса"], "answer": "Київ"},
        {"question": "2 + 2 = ?", "options": ["3", "4", "5"], "answer": "4"},
        {"question": "Яка мова програмування використовується у Flask?", "options": ["Java", "Python", "C++"], "answer": "Python"},
        {"question": "HTML використовується для?", "options": ["Створення структури веб-сторінки", "Роботи з базами даних", "Обчислень"], "answer": "Створення структури веб-сторінки"},
        {"question": "CSS відповідає за?", "options": ["Логіку програми", "Стиль сторінки", "Базу даних"], "answer": "Стиль сторінки"},
        {"question": "Який метод HTTP використовується для відправки форми?", "options": ["GET", "POST", "PUT"], "answer": "POST"},
        {"question": "Що таке SQLAlchemy?", "options": ["Мова програмування", "ORM для роботи з БД", "Операційна система"], "answer": "ORM для роботи з БД"},
        {"question": "Яка функція використовується для рендерингу HTML у Flask?", "options": ["print()", "render_template()", "open()"], "answer": "render_template()"},
        {"question": "Що таке база даних?", "options": ["Набір стилів", "Сховище даних", "Мова програмування"], "answer": "Сховище даних"},
        {"question": "Що таке Python?", "options": ["Мова програмування", "Операційна система", "Браузер"], "answer": "Мова програмування"}
    ]

    for q in questions_data:
        question = Question(text=q["question"])
        db.session.add(question)
        db.session.flush()  # отримуємо id

        for opt in q["options"]:
            option = Option(
                text=opt,
                is_correct=(opt == q["answer"]),
                question_id=question.id
            )
            db.session.add(option)

    db.session.commit()
#кінець тимчасового коду 

with app.app_context():
    import time
    from sqlalchemy.exc import OperationalError

    for i in range(10):
        try:
            db.create_all()
            print("✅ DB connected")
            break
        except OperationalError:
            print("⏳ Waiting for DB...")
            time.sleep(2)
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
