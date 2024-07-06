from flask import Flask, render_template, request
import mysql.connector
import requests
from bs4 import BeautifulSoup
import database_config

app = Flask(__name__)

url = "https://career.habr.com/vacancies"

number_of_pages = 1

def create_database():
    conn = None
    try:
        conn = mysql.connector.connect(
            user=database_config.DB_CONFIG['user'],
            password=database_config.DB_CONFIG['password'],
            host=database_config.DB_CONFIG['host'],
            port=database_config.DB_CONFIG['port']
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_config.DB_CONFIG['database']}")
        print(f"Database '{database_config.DB_CONFIG['database']}' created or already exists.")
    except mysql.connector.Error as err:
        print(f"Error creating database: {err}")
    finally:
        if conn:
            cursor.close()
            conn.close()
def create_table():
    conn = None
    try:
        conn = mysql.connector.connect(**database_config.DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Vacancies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                Company_Name VARCHAR(255),
                Vacancy_Title VARCHAR(255),
                Information VARCHAR(255),
                Link VARCHAR(255),
                Requirements TEXT
            )
        """)
        print("Table 'Vacancies' created or already exists in the database.")
    except mysql.connector.Error as err:
        print(f"Error creating table: {err}")
    finally:
        if conn:
            cursor.close()
            conn.close()
def vacancy_habr(vacancy_card):
    name_company = vacancy_card.find("div", class_="vacancy-card__company").text.strip()
    title = vacancy_card.find("div", class_="vacancy-card__title").text.strip()
    location = vacancy_card.find("div", class_="vacancy-card__meta").text.strip()
    requirements = vacancy_card.find("div", class_="vacancy-card__skills").text.strip()
    link = "https://career.habr.com" + vacancy_card.find("div", class_="vacancy-card__title").a['href']
    city = location.split(',')[0].strip() if ',' in location else "City no"

    return {
        'title': title,
        'location': location,
        'requirements': requirements,
        'link': link,
        'city': city,
        'name_company': name_company
    }
def install_vacancy_in_mysql(vacancy_data):
    conn = None
    try:
        conn = mysql.connector.connect(**database_config.DB_CONFIG)
        cursor = conn.cursor()
        sql = "INSERT INTO Vacancies (Company_Name, Vacancy_Title, Information, Link, Requirements) VALUES (%s, %s, %s, %s, %s)"
        values = (
            vacancy_data['name_company'],
            vacancy_data['title'],
            vacancy_data['location'],
            vacancy_data['link'],
            vacancy_data['requirements']
        )
        cursor.execute(sql, values)
        conn.commit()
        print("Vacancy data added to the database.")
    except mysql.connector.Error as err:
        print(f"Error adding data to the database: {err}")
    finally:
        if conn:
            cursor.close()
            conn.close()
def erase_vacancies_in_mysql():
    conn = None
    try:
        conn = mysql.connector.connect(**database_config.DB_CONFIG)
        cursor = conn.cursor()
        sql = "DELETE FROM Vacancies"
        cursor.execute(sql)
        conn.commit()
        sql = "ALTER TABLE Vacancies AUTO_INCREMENT = 1"
        cursor.execute(sql)
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Ошибка при удалении данных из базы данных: {err}")
    finally:
        if conn:
            cursor.close()
            conn.close()
def get_vacancy_analytics():
    conn = None
    try:
        conn = mysql.connector.connect(**database_config.DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM Vacancies")
        total_vacancies = cursor.fetchone()[0]

        cursor.execute("SELECT Information, COUNT(*) FROM Vacancies GROUP BY Information")
        vacancies_by_city = cursor.fetchall()

        return {
            'total_vacancies': total_vacancies,
            'vacancies_by_city': vacancies_by_city,
        }
    except mysql.connector.Error as err:
        print(f"Ошибка при получении аналитики: {err}")
    finally:
        if conn:
            cursor.close()
            conn.close()
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':

        company = request.form.get('company')
        position = request.form.get('position')
        city = request.form.get('city')
        work_type = request.form.get('work_type')
        experience_level = request.form.get('experience_level')
        skills = request.form.get('skills')

        vacancies_found = search_in_database(company, position, city, work_type, experience_level, skills)
        analytics = get_vacancy_analytics()

        return render_template('index.html', vacancies=vacancies_found, analytics=analytics)
    else:
        company = None
        position = None
        city = None
        work_type = None
        experience_level = None
        skills = None

    return render_template('index.html', company=company, position=position, city=city, work_type=work_type, experience_level=experience_level, skills=skills)
def search_in_database(company, position, city, work_type, experience_level, skills):
    create_database()
    create_table()
    conn = None
    try:
        conn = mysql.connector.connect(**database_config.DB_CONFIG)
        cursor = conn.cursor()

        sql = "SELECT * FROM Vacancies WHERE 1=1"

        if company:
            sql += f" AND Company_Name LIKE '%{company}%'"
        if position:
            sql += f" AND Vacancy_Title LIKE '%{position}%'"
        if city:
            sql += f" AND Information LIKE '%{city}%'"
        if work_type:
            sql += f" AND Information LIKE '%{work_type}%'"
        if experience_level:
            sql += f" AND Requirements LIKE '%{experience_level}%'"
        if skills:
            sql += f" AND Requirements LIKE '%{skills}%'"

        cursor.execute(sql)
        vacancies = cursor.fetchall()

        vacancies_list = []
        for vacancy in vacancies:
            vacancies_list.append({
                'title': vacancy[2],
                'name_company': vacancy[1],
                'location': vacancy[3],
                'link': vacancy[4],
                'requirements': vacancy[5]
            })

        return vacancies_list
    except mysql.connector.Error as err:
        print(f"Error while searching the database: {err}")
    finally:
        if conn:
            cursor.close()
            conn.close()

@app.route('/load_database', methods=['POST'])
def load_database():
    create_database()
    create_table()

    erase_vacancies_in_mysql()

    number_of_pages = 1
    while True:
        page_url = f"{url}?page={number_of_pages}"
        r = requests.get(page_url)
        soup = BeautifulSoup(r.text, "html.parser")
        vacancies = soup.find_all("div", class_="vacancy-card")
        if not vacancies:
            break
        for vacancy in vacancies:
            vacancy_data = vacancy_habr(vacancy)
            install_vacancy_in_mysql(vacancy_data)

        number_of_pages += 1

    return redirect(url_for('index'))

if __name__ == '__main__':
    create_database()
    create_table()
    app.run(debug=True)