import telebot
from telebot import types
import sqlite3
import random
import time

bot = telebot.TeleBot('7806589236:AAGk_GMl6VtpF8v87ElqyXsEi-J_cvL_4a4')

def init_db():
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    c.execute('DROP TABLE IF EXISTS tests')
    c.execute('DROP TABLE IF EXISTS ad_links')
    c.execute('DROP TABLE IF EXISTS ad_stats')
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS user_test_results')
    c.execute('DROP TABLE IF EXISTS ads')
    
    c.execute('''CREATE TABLE IF NOT EXISTS tests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  creator_id INTEGER,
                  title TEXT,
                  description TEXT,
                  questions TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active BOOLEAN DEFAULT 1,
                  total_attempts INTEGER DEFAULT 0,
                  avg_score REAL DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ad_links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  test_id INTEGER,
                  source TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS ad_stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ad_link_id INTEGER,
                  user_id INTEGER,
                  clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_test_results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  test_id INTEGER,
                  score INTEGER,
                  completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Добавляем таблицу для рекламных сообщений
    c.execute('''CREATE TABLE IF NOT EXISTS ads
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  message_type TEXT,
                  content TEXT,
                  media_id TEXT,
                  caption TEXT,
                  frequency INTEGER,
                  is_active BOOLEAN DEFAULT 1,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

user_states = {}

# Список админов (добавьте сюда ID администраторов)
ADMIN_IDS = []  # Замените на реальные ID администраторов

class Test:
    def __init__(self):
        self.title = None
        self.questions = []
        self.current_question = {}

@bot.message_handler(commands=['start'])
def start(message):
    update_user_activity(message.from_user)
    
    if message.text.startswith('/start ad_'):
        parts = message.text.split('_')
        if len(parts) >= 3:
            ad_link_id = parts[1]
            test_id = parts[2]
            
            conn = sqlite3.connect('tests.db')
            c = conn.cursor()
            
            c.execute("INSERT INTO ad_stats (ad_link_id, user_id) VALUES (?, ?)",
                     (ad_link_id, message.from_user.id))
            conn.commit()
            
            c.execute("SELECT title FROM tests WHERE id = ?", (test_id,))
            result = c.fetchone()
            conn.close()
            
            if result:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                start_test = types.KeyboardButton('✍️ Начать тест')
                markup.add(start_test)
                
                bot.reply_to(message, 
                            f"Добро пожаловать! Вы перешли к тесту: {result[0]}\n"
                            "Нажмите кнопку ниже, чтобы начать.",
                            reply_markup=markup)
                return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    take_test = types.KeyboardButton('✍️ Пройти тест')
    create_test = types.KeyboardButton('🎯 Создать тест')
    help_btn = types.KeyboardButton('❓ Помощь')
    about_btn = types.KeyboardButton('ℹ️ О боте')
    markup.add(take_test, create_test, help_btn, about_btn)
    
    if message.from_user.id in ADMIN_IDS:
        admin_btn = types.KeyboardButton('👑 Админ-панель')
        markup.add(admin_btn)
    
    bot.reply_to(message, 
                 "Привет! Я бот для создания и прохождения тестов.\n"
                 "Выберите действие:",
                 reply_markup=markup)

def start_specific_test(message, test_id):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    # Получаем информацию о тесте
    c.execute("SELECT title, questions FROM tests WHERE id = ?", (test_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        bot.reply_to(message, "Тест не найден!")
        return
    
    title, questions = result
    questions = eval(questions)  # Преобразуем строку обратно в список вопросов
    
    # Сохраняем состояние пользователя для прохождения теста
    user_states[user_id] = {
        'test_id': test_id,
        'questions': questions,
        'total_questions': len(questions),
        'correct_answers': 0
    }
    
    bot.send_message(message.chat.id, f"Начинаем тест: {title}")
    # Показываем первый вопрос
    show_question(message, user_id)

@bot.message_handler(func=lambda message: message.text == '🎯 Создать тест')
def create_test(message):
    user_id = message.from_user.id
    user_states[user_id] = Test()
    
    bot.reply_to(message, "Введите название теста:")
    bot.register_next_step_handler(message, process_test_title)

def process_test_title(message):
    user_id = message.from_user.id
    user_states[user_id].title = message.text
    user_states[user_id].current_question = {'options': []}
    
    bot.reply_to(message, "Введите вопрос:")
    bot.register_next_step_handler(message, process_question_text)

def process_question_text(message):
    user_id = message.from_user.id
    user_states[user_id].current_question['question'] = message.text
    
    bot.reply_to(message, "Введите правильный ответ:")
    bot.register_next_step_handler(message, process_correct_answer)

def process_correct_answer(message):
    user_id = message.from_user.id
    correct_answer = message.text
    user_states[user_id].current_question['correct_answer'] = correct_answer
    user_states[user_id].current_question['options'] = [correct_answer]
    
    bot.reply_to(message, f"Введите неправильный вариант ответа №1:")
    bot.register_next_step_handler(message, process_wrong_answer, 1)

def process_wrong_answer(message, answer_num):
    user_id = message.from_user.id
    user_states[user_id].current_question['options'].append(message.text)
    
    if answer_num < 3:
        bot.reply_to(message, f"Введите неправильный вариант ответа №{answer_num + 1}:")
        bot.register_next_step_handler(message, process_wrong_answer, answer_num + 1)
    else:
        question = user_states[user_id].current_question
        user_states[user_id].questions.append(question)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        add_question = types.KeyboardButton('Добавить еще вопрос')
        finish_test = types.KeyboardButton('Завершить создание теста')
        markup.add(add_question, finish_test)
        
        bot.reply_to(message, 
                    "Вопрос успешно добавлен! Хотите добавить еще вопрос или завершить создание теста?",
                    reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == 'Добавить еще вопрос')
def add_question(message):
    user_id = message.from_user.id
    user_states[user_id].current_question = {'options': []}
    
    bot.reply_to(message, "Введите следующий вопрос:")
    bot.register_next_step_handler(message, process_question_text)

@bot.message_handler(func=lambda message: message.text == 'Завершить создание теста')
def finish_test(message):
    user_id = message.from_user.id
    test = user_states[user_id]
    
    if len(test.questions) == 0:
        bot.reply_to(message, "Нельзя создать тест без вопросов! Добавьте хотя бы один вопрос.")
        return
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO tests (
                creator_id, 
                title, 
                description,
                questions, 
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            user_id, 
            test.title,
            test.description if hasattr(test, 'description') else None,
            str(test.questions)
        ))
        
        test_id = c.lastrowid
        
        conn.commit()
        
        bot_username = bot.get_me().username
        test_link = f"https://t.me/{bot_username}?start=test_{test_id}"
        
        del user_states[user_id]
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        create_test_btn = types.KeyboardButton('🎯 Создать тест')
        take_test_btn = types.KeyboardButton('✍️ Пройти тест')
        markup.add(create_test_btn, take_test_btn)
        
        success_message = (
            f"✅ *Тест успешно создан и сохранен\!*\n\n"
            f"📝 Название: `{test.title}`\n"
            f"❓ Количество вопросов: `{len(test.questions)}`\n\n"
            f"🔗 *Ссылка на ваш тест:*\n`{test_link}`\n\n"
            f"Отправьте эту ссылку друзьям, чтобы они могли пройти ваш тест\\."
        )
        
        bot.reply_to(
            message, 
            success_message,
            parse_mode='MarkdownV2',
            reply_markup=markup
        )
        
    except sqlite3.Error as e:
        bot.reply_to(
            message, 
            "❌ Произошла ошибка при сохранении теста. Пожалуйста, попробуйте еще раз."
        )
        print(f"Database error: {e}")
    
    finally:
        conn.close()

def update_test_statistics(test_id, score):
    """Обновляет статистику теста после его прохождения"""
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        # Обновляем количество попыток и среднюю оценку
        c.execute("""
            UPDATE tests 
            SET 
                total_attempts = total_attempts + 1,
                avg_score = ((avg_score * total_attempts) + ?) / (total_attempts + 1),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (score, test_id))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error updating test statistics: {e}")
    finally:
        conn.close()

@bot.message_handler(func=lambda message: message.text == '✍️ Пройти тест')
def select_test(message):
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    c.execute("SELECT id, title FROM tests WHERE is_active = 1")
    tests = c.fetchall()
    conn.close()
    
    if not tests:
        bot.reply_to(message, "Пока нет доступных тестов.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for test_id, title in tests:
        markup.add(types.InlineKeyboardButton(
            text=title,
            callback_data=f"test_{test_id}"
        ))
    
    bot.reply_to(message, "Выберите тест:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('test_'))
def start_test(call):
    test_id = call.data.split('_')[1]
    user_id = call.from_user.id
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    c.execute("SELECT questions FROM tests WHERE id = ?", (test_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        bot.answer_callback_query(call.id, "Тест не найден!")
        return
    
    questions = eval(result[0])
    user_states[user_id] = {
        'test_id': test_id,
        'questions': questions.copy(),
        'total_questions': len(questions),
        'correct_answers': 0
    }
    
    show_question(call.message, user_id)

def show_question(message, user_id):
    if random.random() < 0.2:
        show_random_ad(message)
    
    state = user_states[user_id]
    if not state['questions']:
        total_questions = state['total_questions']
        correct_answers = state['correct_answers']
        score = (correct_answers / total_questions) * 100
        
        update_test_statistics(state['test_id'], score)
        
        conn = sqlite3.connect('tests.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO user_test_results (user_id, test_id, score)
            VALUES (?, ?, ?)
        """, (user_id, state['test_id'], score))
        conn.commit()
        conn.close()
        
        result_text = (
            "🎉 *Тест завершен\\!*\n\n"
            f"📊 *Ваш результат:*\n"
            f"✅ Правильных ответов: {correct_answers} из {total_questions}\n"
            f"📈 Процент успеха: {score:.1f}%\n\n"
        )
        
        if score == 100:
            result_text += "🏆 Превосходно\\! Идеальный результат\\!"
        elif score >= 80:
            result_text += "🌟 Отличная работа\\! Почти идеально\\!"
        elif score >= 60:
            result_text += "👍 Хороший результат\\! Есть куда расти\\!"
        elif score >= 40:
            result_text += "💪 Неплохо, но нужно больше практики\\!"
        else:
            result_text += "📚 Рекомендуем повторить материал и попробовать снова\\!"
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        retry_btn = types.KeyboardButton('🔄 Пройти другой тест')
        menu_btn = types.KeyboardButton('🏠 Главное меню')
        markup.add(retry_btn, menu_btn)
        
        bot.send_message(
            message.chat.id,
            result_text,
            parse_mode='MarkdownV2',
            reply_markup=markup
        )
        del user_states[user_id]
        return
    
    question = state['questions'][0]
    options = question['options']
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    random.shuffle(options)
    for i, option in enumerate(options):
        button_text = f"{'ABCD'[i]}. {option}"
        markup.add(types.InlineKeyboardButton(
            text=button_text,
            callback_data=f"answer_{i}"
        ))
    
    question_text = (
        f"❓ *Вопрос {state['total_questions'] - len(state['questions']) + 1} "
        f"из {state['total_questions']}*\n\n"
        f"{question['question']}"
    )
    
    question_text = question_text.replace('.', '\\.').replace('-', '\\-').replace('!', '\\!')
    
    bot.send_message(
        message.chat.id,
        question_text,
        parse_mode='MarkdownV2',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def process_answer(call):
    user_id = call.from_user.id
    if user_id not in user_states:
        bot.answer_callback_query(call.id, "❌ Тест уже завершен или не начат!")
        return
    
    state = user_states[user_id]
    
    if not state['questions']:
        bot.answer_callback_query(call.id, "❌ Тест уже завершен!")
        return
        
    current_question = state['questions'][0]
    selected_option = int(call.data.split('_')[1])
    selected_answer = current_question['options'][selected_option]
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    if selected_answer == current_question['correct_answer']:
        state['correct_answers'] += 1
        bot.send_message(
            call.message.chat.id,
            "✅ *Правильно\\!*",
            parse_mode='MarkdownV2'
        )
    else:
        bot.send_message(
            call.message.chat.id,
            f"❌ *Неправильно\\!*\nПравильный ответ: *{current_question['correct_answer']}*",
            parse_mode='MarkdownV2'
        )
    
    state['questions'].pop(0)
    
    time.sleep(1)
    
    if not state['questions']:
        total_questions = state['total_questions']
        correct_answers = state['correct_answers']
        score = (correct_answers / total_questions) * 100
        
        update_test_statistics(state['test_id'], score)
        
        conn = sqlite3.connect('tests.db')
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO user_test_results (user_id, test_id, score)
                VALUES (?, ?, ?)
            """, (user_id, state['test_id'], score))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        finally:
            conn.close()
        
        result_text = (
            "🎉 *Тест завершен\\!*\n\n"
            f"📊 *Ваш результат:*\n"
            f"✅ Правильных ответов: `{correct_answers}` из `{total_questions}`\n"
            f"📈 Процент успеха: `{score:.1f}%`\n\n"
        )
        
        if score == 100:
            result_text += "🏆 Превосходно\\! Идеальный результат\\!"
        elif score >= 80:
            result_text += "🌟 Отличная работа\\! Почти идеально\\!"
        elif score >= 60:
            result_text += "👍 Хороший результат\\! Есть куда расти\\!"
        elif score >= 40:
            result_text += "💪 Неплохо, но нужно больше практики\\!"
        else:
            result_text += "📚 Рекомендуем повторить материал и попробовать снова\\!"
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        retry_btn = types.KeyboardButton('🔄 Пройти другой тест')
        menu_btn = types.KeyboardButton('🏠 Главное меню')
        markup.add(retry_btn, menu_btn)
        
        bot.send_message(
            call.message.chat.id,
            result_text,
            parse_mode='MarkdownV2',
            reply_markup=markup
        )
        
        del user_states[user_id]
    else:
        show_question(call.message, user_id)

@bot.message_handler(func=lambda message: message.text == '🔄 Пройти другой тест')
def restart_test_selection(message):
    select_test(message)

@bot.message_handler(func=lambda message: message.text == '🏠 Главное меню')
def return_to_menu(message):
    start(message)

@bot.message_handler(func=lambda message: message.text == '❓ Помощь')
def help_command(message):
    help_text = (
        "📚 *Инструкция по использованию бота:*\n\n"
        "*🎯 Создание теста:*\n"
        "1\\. Нажмите '🎯 Создать тест'\n"
        "2\\. Введите название теста\n"
        "3\\. Добавьте вопросы и варианты ответов\n"
        "4\\. Получите ссылку на готовый тест\n\n"
        "*✍️ Прохождение теста:*\n"
        "1\\. Нажмите '✍️ Пройти тест'\n"
        "2\\. Выберите тест из списка\n"
        "3\\. Отвечайте на вопросы\n"
        "4\\. Получите результат\n\n"
        "❗️ Если возникли вопросы, обратитесь к администратору"
    )
    
    bot.reply_to(message, help_text, parse_mode='MarkdownV2')

@bot.message_handler(func=lambda message: message.text == 'ℹ️ О боте')
def about_command(message):
    about_text = (
        "🤖 *Test Creator Bot*\n\n"
        "Версия: 1\\.0\n"
        "Создан для проведения тестирований и опросов\n\n"
        "*🌟 Возможности:*\n"
        "• Неограниченное количество тестов\n"
        "• Разные типы вопросов\n"
        "• Статистика прохождения\n"
        "• Удобный интерфейс\n\n"
        "*👨‍💻 Разработчик:*\n"
        "Telegram: "
    )
    
    bot.reply_to(message, about_text, parse_mode='MarkdownV2')

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "У вас нет доступа к панели администратора.")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    stats_btn = types.KeyboardButton('📊 Статистика пользователей')
    ads_btn = types.KeyboardButton('Управление рекламой')
    back_btn = types.KeyboardButton('🏠 Главное меню')
    markup.add(stats_btn, ads_btn, back_btn)
    
    bot.reply_to(message, 
                 "*👑 Админ\\-панель*\n\nВыберите действие:",
                 parse_mode='MarkdownV2',
                 reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📊 Статистика пользователей')
def show_statistics(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM user_test_results")
    total_tests_taken = c.fetchone()[0]
    
    c.execute("""
        SELECT COUNT(DISTINCT id) 
        FROM users 
        WHERE last_activity >= datetime('now', '-1 day')
    """)
    active_users_24h = c.fetchone()[0]
    
    c.execute("""
        SELECT 
            users.first_name,
            users.username,
            COUNT(user_test_results.id) as tests_completed,
            ROUND(AVG(user_test_results.score), 1) as avg_score
        FROM users
        LEFT JOIN user_test_results ON users.id = user_test_results.user_id
        GROUP BY users.id
        HAVING tests_completed > 0
        ORDER BY tests_completed DESC
        LIMIT 5
    """)
    top_users = c.fetchall()
    
    c.execute("""
        SELECT 
            tests.title,
            COUNT(user_test_results.id) as times_completed,
            ROUND(AVG(user_test_results.score), 1) as avg_score
        FROM tests
        LEFT JOIN user_test_results ON tests.id = user_test_results.test_id
        GROUP BY tests.id
        HAVING times_completed > 0
        ORDER BY times_completed DESC
        LIMIT 5
    """)
    top_tests = c.fetchall()
    
    conn.close()
    
    response = "*📊 Статистика пользователей*\n\n"
    response += f"👥 Всего пользователей: `{total_users}`\n"
    response += f"📝 Всего пройдено тестов: `{total_tests_taken}`\n"
    response += f"🔥 Активных за 24 часа: `{active_users_24h}`\n\n"
    
    response += "*🏆 Топ\\-5 активных пользователей:*\n"
    for user in top_users:
        name = user[0] or user[1] or "Неизвестный"
        name = name.replace(".", "\\.").replace("-", "\\-").replace("!", "\\!")
        avg_score = user[3] if user[3] is not None else 0
        response += f"• {name}: `{user[2]}` тестов \\(ср\\. балл: `{avg_score}%`\\)\n"
    
    response += "\n*📈 Топ\\-5 популярных тестов:*\n"
    for test in top_tests:
        title = test[0].replace(".", "\\.").replace("-", "\\-").replace("!", "\\!")
        avg_score = test[2] if test[2] is not None else 0
        response += f"• {title}: `{test[1]}` раз \\(ср\\. балл: `{avg_score}%`\\)\n"
    
    bot.reply_to(message, response, parse_mode='MarkdownV2')

@bot.message_handler(func=lambda message: message.text == '🏠 Главное меню')
def return_to_main_menu(message):
    start(message)

@bot.message_handler(func=lambda message: message.text == '📊 Статистика тестов')
def show_test_statistics(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT 
                title,
                total_attempts,
                avg_score,
                created_at,
                updated_at
            FROM tests
            WHERE is_active = 1
            ORDER BY total_attempts DESC
        """)
        
        tests = c.fetchall()
        
        if not tests:
            bot.reply_to(message, "📊 Пока нет статистики по тестам.")
            return
        
        response = "*📊 Статистика тестов:*\n\n"
        
        for test in tests:
            title, attempts, avg_score, created, updated = test
            response += (
                f"*{title}*\n"
                f"📝 Попыток: `{attempts}`\n"
                f"📈 Средний балл: `{avg_score:.1f}%`\n"
                f"📅 Создан: `{created}`\n"
                f"🔄 Последнее прохождение: `{updated}`\n"
                f"\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
            )
        
        bot.reply_to(message, response, parse_mode='MarkdownV2')
        
    except sqlite3.Error as e:
        bot.reply_to(message, "❌ Произошла ошибка при получении статистики.")
        print(f"Database error: {e}")
    
    finally:
        conn.close()

@bot.message_handler(func=lambda message: message.text == 'Управление рекламой')
def manage_ads(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    add_ad = types.KeyboardButton('➕ Добавить рекламу')
    view_ads = types.KeyboardButton('👀 Просмотр рекламы')
    delete_ad = types.KeyboardButton('🗑 Удалить рекламу')
    back = types.KeyboardButton('◀️ Назад')
    markup.add(add_ad, view_ads, delete_ad, back)
    
    bot.reply_to(message, 
                 "*🎯 Управление рекламой*\n\nВыберите действие:",
                 parse_mode='MarkdownV2',
                 reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '➕ Добавить рекламу')
def add_ad(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    text_ad = types.KeyboardButton('📝 Текстовая реклама')
    photo_ad = types.KeyboardButton('🖼 Реклама с фото')
    video_ad = types.KeyboardButton('🎥 Реклама с видео')
    back = types.KeyboardButton('◀️ Назад')
    markup.add(text_ad, photo_ad, video_ad, back)
    
    user_states[message.from_user.id] = {'state': 'adding_ad'}
    
    bot.reply_to(message, 
                 "Выберите тип рекламы:",
                 reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📝 Текстовая реклама')
def add_text_ad(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    user_states[message.from_user.id] = {'state': 'waiting_ad_text'}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel = types.KeyboardButton('❌ Отмена')
    markup.add(cancel)
    
    bot.reply_to(message, 
                 "Отправьте текст рекламного сообщения:",
                 reply_markup=markup)

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('state') == 'waiting_ad_text')
def process_ad_text(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.text == '❌ Отмена':
        del user_states[message.from_user.id]
        manage_ads(message)
        return
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO ads (message_type, content)
            VALUES (?, ?)
        """, ('text', message.text))
        conn.commit()
        
        bot.reply_to(message, "✅ Рекламное сообщение успешно добавлено!")
    except sqlite3.Error as e:
        bot.reply_to(message, "❌ Ошибка при сохранении рекламы.")
        print(f"Database error: {e}")
    finally:
        conn.close()
        del user_states[message.from_user.id]
        manage_ads(message)

@bot.message_handler(func=lambda message: message.text == '🖼 Реклама с фото')
def add_photo_ad(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    user_states[message.from_user.id] = {'state': 'waiting_ad_photo'}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel = types.KeyboardButton('❌ Отмена')
    markup.add(cancel)
    
    bot.reply_to(message, 
                 "Отправьте фото для рекламы (можно с подписью):",
                 reply_markup=markup)

@bot.message_handler(content_types=['photo'], func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('state') == 'waiting_ad_photo')
def process_ad_photo(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    photo = message.photo[-1]
    caption = message.caption or ''
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO ads (message_type, media_id, caption)
            VALUES (?, ?, ?)
        """, ('photo', photo.file_id, caption))
        conn.commit()
        
        bot.reply_to(message, "✅ Рекламное фото успешно добавлено!")
    except sqlite3.Error as e:
        bot.reply_to(message, "❌ Ошибка при сохранении рекламы.")
        print(f"Database error: {e}")
    finally:
        conn.close()
        del user_states[message.from_user.id]
        manage_ads(message)

@bot.message_handler(func=lambda message: message.text == '🎥 Реклама с видео')
def add_video_ad(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    user_states[message.from_user.id] = {'state': 'waiting_ad_video'}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel = types.KeyboardButton('❌ Отмена')
    markup.add(cancel)
    
    bot.reply_to(message, 
                 "Отправьте видео для рекламы (можно с подписью):",
                 reply_markup=markup)

@bot.message_handler(content_types=['video'], func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('state') == 'waiting_ad_video')
def process_ad_video(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    video = message.video
    caption = message.caption or ''
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO ads (message_type, media_id, caption)
            VALUES (?, ?, ?)
        """, ('video', video.file_id, caption))
        conn.commit()
        
        bot.reply_to(message, "✅ Рекламное видео успешно добавлено!")
    except sqlite3.Error as e:
        bot.reply_to(message, "❌ Ошибка при сохранении рекламы.")
        print(f"Database error: {e}")
    finally:
        conn.close()
        del user_states[message.from_user.id]
        manage_ads(message)

@bot.message_handler(func=lambda message: message.text == '👀 Просмотр рекламы')
def view_ads(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    c.execute("""
        SELECT id, message_type, content, media_id, caption, is_active 
        FROM ads 
        ORDER BY created_at DESC
    """)
    
    ads = c.fetchall()
    conn.close()
    
    if not ads:
        bot.reply_to(message, "Рекламных сообщений пока нет.")
        return
    
    for ad in ads:
        ad_id, msg_type, content, media_id, caption, is_active = ad
        status = "✅ Активно" if is_active else "❌ Неактивно"
        
        if msg_type == 'text':
            bot.send_message(message.chat.id, 
                           f"Реклама #{ad_id}\nСтатус: {status}\n\n{content}")
        elif msg_type == 'photo':
            bot.send_photo(message.chat.id, media_id,
                         caption=f"Реклама #{ad_id}\nСтатус: {status}\n\n{caption}")
        elif msg_type == 'video':
            bot.send_video(message.chat.id, media_id,
                         caption=f"Реклама #{ad_id}\nСтатус: {status}\n\n{caption}")

@bot.message_handler(func=lambda message: message.text == '🗑 Удалить рекламу')
def delete_ad_start(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    c.execute("SELECT id, message_type, content, caption FROM ads WHERE is_active = 1")
    ads = c.fetchall()
    conn.close()
    
    if not ads:
        bot.reply_to(message, "Нет активных рекламных сообщений.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ad in ads:
        ad_id, msg_type, content, caption = ad
        button_text = f"#{ad_id} - {content[:30] if msg_type == 'text' else caption[:30] or 'Без описания'}..."
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"del_ad_{ad_id}"))
    
    bot.reply_to(message, "Выберите рекламу для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_ad_'))
def delete_ad(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    
    ad_id = call.data.split('_')[2]
    
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        c.execute("UPDATE ads SET is_active = 0 WHERE id = ?", (ad_id,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ Реклама успешно удалена!")
        bot.edit_message_text("✅ Реклама успешно удалена!", 
                            call.message.chat.id, 
                            call.message.message_id)
    except sqlite3.Error as e:
        bot.answer_callback_query(call.id, "❌ Ошибка при удалении рекламы.")
        print(f"Database error: {e}")
    finally:
        conn.close()

@bot.message_handler(func=lambda message: message.text == '◀️ Назад')
def return_to_admin(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    admin_panel(message)

@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def cancel_operation(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    if message.from_user.id in user_states:
        del user_states[message.from_user.id]
    
    manage_ads(message)

def update_user_activity(user):
    """Обновляет информацию о пользователе и его активности"""
    conn = sqlite3.connect('tests.db')
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO users (id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                last_activity = CURRENT_TIMESTAMP
        """, (user.id, user.username, user.first_name, user.last_name))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error updating user activity: {e}")
    finally:
        conn.close()

init_db()

# Запуск бота
bot.polling(none_stop=True)
