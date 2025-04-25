import telebot
import datetime
import time
import os
import subprocess
import psutil
import sqlite3
import threading
import re

BOT_TOKEN = '7021915989:AAG3L7L5NXCsaTEhZJPhgbn-vTiO956vE3Q'
ADMIN_ID = [5594480622, 6238630618]
processes = []
banned_numbers = []
allowed_users = []
SERVER_ID = [-1002162807845]

def check():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT status FROM status WHERE id = 1')
    status_bot = cursor.fetchone()[0]
    connection.close()

    if status_bot == 'off':
        return 'off'
    return True

def is_bot_active():
    return check() == True

bot = telebot.TeleBot(BOT_TOKEN)

connection = sqlite3.connect('user_data.db', check_same_thread=False)
cursor = connection.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        expiration_time TEXT
    )
''')
connection.commit()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS banned_numbers (
        phone_number TEXT PRIMARY KEY
    )
''')
connection.commit()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS spam_attempts (
        user_id INTEGER PRIMARY KEY,
        last_attempt_time TEXT,
        command_type TEXT
    )
''')
connection.commit()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS status (
        id INTEGER PRIMARY KEY,
        status TEXT
    )
''')
connection.commit()

cursor.execute('SELECT COUNT(*) FROM status')

if cursor.fetchone()[0] == 0:
    cursor.execute('INSERT INTO status (id, status) VALUES (1, "on")')
    connection.commit()

db_lock = threading.Lock()

def cleanup_expired_attempts():
    with db_lock:
        connection = get_db_connection()
        cursor = connection.cursor()
        now = datetime.datetime.now()

        # Xóa các bản ghi /sms cũ hơn 60 giây
        sms_expiration = now - datetime.timedelta(seconds=60)
        cursor.execute('DELETE FROM spam_attempts WHERE command_type = "sms" AND last_attempt_time < ?', 
                       (sms_expiration.strftime('%Y-%m-%d %H:%M:%S'),))

        # Xóa các bản ghi /call cũ hơn 900 giây
        call_expiration = now - datetime.timedelta(seconds=700)
        cursor.execute('DELETE FROM spam_attempts WHERE command_type = "call" AND last_attempt_time < ?', 
                       (call_expiration.strftime('%Y-%m-%d %H:%M:%S'),))

        connection.commit()
        connection.close()

def get_db_connection():
    connection = sqlite3.connect('user_data.db')
    return connection

def load_banned_numbers():
    global banned_numbers
    banned_numbers = [] 
    with db_lock:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT phone_number FROM banned_numbers')
        rows = cursor.fetchall()
        banned_numbers = [row[0] for row in rows] 
        connection.close()

def hide_phone_number(phone_number: str) -> str:
    return phone_number[:3] + '****' + phone_number[-3:]

def add_banned_number(phone_number: str):
    with db_lock:
        connection = get_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM banned_numbers WHERE phone_number = ?', (phone_number,))
            result = cursor.fetchone()
            if result[0] > 0:
                return False

            cursor.execute('INSERT INTO banned_numbers (phone_number) VALUES (?)', (phone_number,))
            connection.commit()
            banned_numbers.append(phone_number)  # Update the in-memory list
            return True
        finally:
            connection.close()

def get_banned_numbers() -> str:
    if not banned_numbers:
        return 'Danh sách số điện thoại bị cấm hiện đang trống.'
    
    return 'Danh sách số điện thoại cấm\n' + '\n'.join(f'- {number}' for number in banned_numbers)

def add_user(user_id: int, expiration_time: datetime.datetime):
    with db_lock:
        connection = sqlite3.connect('user_data.db')
        cursor = connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, expiration_time)
            VALUES (?, ?)
        ''', (user_id, expiration_time.strftime('%Y-%m-%d %H:%M:%S')))
        connection.commit()
        connection.close()

def cleanup_expired_users():
    while True:
        with db_lock:
            connection = sqlite3.connect('user_data.db')
            cursor = connection.cursor()
            expiration_time = datetime.datetime.now()
            cursor.execute('DELETE FROM users WHERE expiration_time < ?', (expiration_time.strftime('%Y-%m-%d %H:%M:%S'),))
            connection.commit()
            connection.close()
        time.sleep(10)  # Wait for 10 seconds before checking again

WARNING_MESSAGE = (
    "<blockquote style='background-color: #f8d7da; padding: 10px; border-left: 5px solid #f5c6cb;'>"
    "<b>⚠️ LƯU Ý KHI DÙNG BOT:</b>\n"
    "- KHÔNG TẤN CÔNG MỘT SỐ QUÁ NHIỀU LẦN TRONG KHOẢNG THỜI GIAN NGẮN. HÃY CHỜ 5 PHÚT ĐẾN 48 GIỜ TRƯỚC KHI TẤN CÔNG LẠI ĐỂ GIẢM BỊ API CHẶN SỐ.\n\n"
    "- NẾU BẠN DÙNG VỚI MỤC ĐÍCH VI PHẠM PHÁP LUẬT, CHÚNG TÔI SẼ KHÔNG CHỊU TRÁCH NHIỆM. BẠN PHẢI CHỊU TOÀN BỘ HẬU QUẢ TRƯỚC PHÁP LUẬT.\n\n"
    "- ĐỪNG SO SÁNH BOT NÀY VỚI CÁC BOT KHÁC. MỖI BOT ĐƯỢC XÂY DỰNG KHÁC NHAU, NÊN HÃY TÔN TRỌNG. GIÁ RẺ HƠN ĐỒNG NGHĨA VỚI KHẢ NĂNG KHÔNG BẰNG CÁC BÊN KHÁC.\n\n"
    "- CHÚNG TÔI BẢO HÀNH VIP 1-1 NẾU LỖI DO CODE HOẶC API. CÁC TRƯỜNG HỢP KHÁC, CHÚNG TÔI SẼ KHÔNG CHỊU TRÁCH NHIỆM."
    "</blockquote>"
)

def send_periodic_message():
    for channel_id in SERVER_ID:
        try:
            bot.send_message(channel_id, WARNING_MESSAGE, parse_mode='HTML')
        except Exception as e:
            print(f"Error sending message to channel {channel_id}: {e}")

def start_periodic_messages():
    while True:
        send_periodic_message()
        time.sleep(1800)


periodic_thread = threading.Thread(target=start_periodic_messages, daemon=True)
periodic_thread.start()
cleanup_thread = threading.Thread(target=cleanup_expired_users, daemon=True)
cleanup_thread.start()


def load_users_from_database():
    cursor.execute('SELECT user_id, expiration_time FROM users')
    rows = cursor.fetchall()
    for row in rows:
        user_id = row[0]
        expiration_time = datetime.datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
        if expiration_time > datetime.datetime.now():
            allowed_users.append(user_id)

load_users_from_database()
load_banned_numbers()

@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.type == 'private':
        if message.from_user.id not in ADMIN_ID:
            if not check():
                bot.reply_to(message, 'Hiện tại bot đang off')
                return
        bot.reply_to(message, 'Chào mừng bạn đến với bot spam tin nhắn sms\nTham gia nhóm https://t.me/phlzx_network để sử dụng bot')

@bot.message_handler(commands=['add_phone'])
def handle_add_phone(message):
    if message.from_user.id not in ADMIN_ID:
        if not check():
            bot.reply_to(message, 'Hiện tại bot đang off gọi Admin để bật bot.')
            return
    admin_id = message.from_user.id
    if admin_id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh /add_phone.')
        return

    if len(message.text.split()) < 2:
        bot.reply_to(message, 'Vui lòng nhập số điện thoại cần cấm\nví dụ: /add_phone 0123456789')
        return

    phone_number = message.text.split()[1]

    # viettel = r"^0(3[2-9]|9[6-8]|8[6-9]|7[0-2|6-9])\d{7}$"
    # vinaphone = r"^0(9[1|4|8]|8[1|2|4|6])\d{7}$"
    # mobifone = r"^0(9[0|3|6|7|8]|7[6|7|8|9])\d{7}$"
    # vietnamobile = r"^0(92|58|56)\d{7}$"
    # gmobile = r"^099\d{7}$"

    # if not re.match(viettel, phone_number) and not re.match(vinaphone, phone_number) and not re.match(mobifone, phone_number) and not re.match(vietnamobile, phone_number) and not re.match(gmobile, phone_number):
    #     bot.reply_to(message, 'Số điện thoại không hợp lệ\nVui lòng nhập một số điện thoại đúng của Việt Nam.')
    #     return

    if add_banned_number(phone_number):
        bot.reply_to(message, f'Số điện thoại {phone_number} đã được thêm vào danh sách cấm.')
    else:
        bot.reply_to(message, f'Số điện thoại {phone_number} đã có trong danh sách cấm.')


@bot.message_handler(commands=['delete_phone'])
def handle_delete_phone(message):
    if message.from_user.id not in ADMIN_ID:
        if not check():
            bot.reply_to(message, 'Hiện tại bot đang off gọi Admin để bật bot.')
            return
    admin_id = message.from_user.id
    if admin_id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh /delete_phone.')
        return

    if len(message.text.split()) < 2:
        bot.reply_to(message, 'Vui lòng nhập số điện thoại cần xóa khỏi danh sách cấm\nví dụ: /delete_phone 0123456789')
        return

    phone_number = message.text.split()[1]
    if phone_number in banned_numbers:
        banned_numbers.remove(phone_number)  # Update the in-memory list
        with db_lock:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute('DELETE FROM banned_numbers WHERE phone_number = ?', (phone_number,))
            connection.commit()
            connection.close()
        bot.reply_to(message, f'Số điện thoại {phone_number} đã được xóa khỏi danh sách cấm.')
    else:
        bot.reply_to(message, f'Số điện thoại {phone_number} không có trong danh sách cấm.')

@bot.message_handler(commands=['list_phone'])
def handle_list_phone(message):
    if message.from_user.id not in ADMIN_ID:
        if not check():
            bot.reply_to(message, 'Hiện tại bot đang off gọi Admin để bật bot.')
            return
    admin_id = message.from_user.id
    if admin_id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh /list_phone.')
        return
    
    bot.reply_to(message, get_banned_numbers())


@bot.message_handler(commands=['add_user'])
def handle_add_user(message):
    if message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh /add_user.')
        return

    if len(message.text.split()) < 2:
        bot.reply_to(message, 'Vui lòng nhập ID người dùng cần thêm vào danh sách\nví dụ: /add_user 123456789')
        return

    try:
        user_id = int(message.text.split()[1])
    except ValueError:
        bot.reply_to(message, 'ID người dùng không hợp lệ.')
        return

    # Default expiration time is 30 days
    expiration_time = datetime.datetime.now() + datetime.timedelta(days=30)

    if len(message.text.split()) == 3:
        time_input = message.text.split()[2]
        if time_input[-1] == 'd':
            days = int(time_input[:-1])
            expiration_time = datetime.datetime.now() + datetime.timedelta(days=days)
        elif time_input[-1] == 'h':
            hours = int(time_input[:-1])
            expiration_time = datetime.datetime.now() + datetime.timedelta(hours=hours)
        elif time_input[-1] == 'w':
            weeks = int(time_input[:-1])
            expiration_time = datetime.datetime.now() + datetime.timedelta(weeks=weeks)
        elif time_input[-1] == 'm':
            months = int(time_input[:-1])
            expiration_time = datetime.datetime.now() + datetime.timedelta(days=30 * months)  # Approximate month as 30 days
        else:
            bot.reply_to(message, 'Thời gian không hợp lệ. Vui lòng sử dụng định dạng 1h, 1d, 1w, hoặc 1m.')
            return

    if user_id in allowed_users:
        bot.reply_to(message, f'Người dùng có ID {user_id} đã có trong danh sách.')
        return

    allowed_users.append(user_id)
    add_user(user_id, expiration_time)
    bot.reply_to(message, f'Người dùng có ID {user_id} đã được thêm vào danh sách với thời gian hết hạn {expiration_time}.')

@bot.message_handler(commands=['delete_user'])
def handle_delete_user(message):
    if message.from_user.id not in ADMIN_ID:
        if not check():
            bot.reply_to(message, 'Hiện tại bot đang off gọi Admin để bật bot.')
            return
    admin_id = message.from_user.id
    chat_id = message.chat.id
    msg = message.text.split()
    if admin_id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh /delete_user.')
        return

    if len(msg) < 2:
        bot.reply_to(message, 'Vui lòng nhập ID người dùng cần xóa khỏi danh sách\nví dụ: /delete_user 123456789')
        return

    try:
        user_id = int(msg[1])
    except ValueError:
        bot.reply_to(message, 'ID người dùng không hợp lệ.')
        return

    if user_id in allowed_users:
        allowed_users.remove(user_id)
        with db_lock:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            connection.commit()
            connection.close()
        bot.reply_to(message, f'Người dùng có ID {user_id} đã bị xóa khỏi danh sách.')
    else:
        bot.reply_to(message, f'Người dùng có ID {user_id} không có trong danh sách.')


@bot.message_handler(commands=['list_user'])
def handle_list_user(message):
    if message.from_user.id not in ADMIN_ID:
        if not check():
            bot.reply_to(message, 'Hiện tại bot đang off gọi Admin để bật bot.')
            return
    admin_id = message.from_user.id
    chat_id = message.chat.id
    if admin_id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh /list_user.')
        return

    if not allowed_users:
        bot.reply_to(message, 'Danh sách người dùng hiện đang trống.')
        return

    allowed_users_text = 'Danh sách người dùng VIP\n'
    for user_id in allowed_users:
        # Lấy thời gian hết hạn từ cơ sở dữ liệu
        with db_lock:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute('SELECT expiration_time FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            connection.close()

        if result:
            expiration_time = result[0]
            allowed_users_text += f'- **User  ID:** {user_id} | **Thời gian hết hạn:** {expiration_time}\n'
        else:
            allowed_users_text += f'- **User  ID:** {user_id} | **Thời gian hết hạn:** Không tìm thấy\n'

    bot.reply_to(message, allowed_users_text, parse_mode='Markdown')

@bot.message_handler(commands=['sms'])
def handle_send_sms(message):
    if not is_bot_active():
        bot.reply_to(message, 'Hiện tại bot đang bảo trì. Chỉ Admin mới có thể sử dụng lệnh này.')
        return
    global banned_numbers
    cleanup_expired_attempts()

    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_ID and user_id not in allowed_users:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh này. Vui lòng liên hệ admin để được thêm vào danh sách sử dụng. Hoặc /thanhtoan để mua VIP')
        return

    if message.chat.type == 'private' and message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, 'Chỉ có admin mới có thể nhắn tin riêng với bot\nTham gia nhóm https://t.me/phlzx_network để sử dụng bot')
        return

    bot_status = check()
    if bot_status == 'off':
        bot.reply_to(message, 'Hiện tại bot đang off gọi Admin để bật bot.')
        return

    with db_lock:
        connection = get_db_connection()
        cursor = connection.cursor()
        now = datetime.datetime.now()
        cursor.execute('SELECT last_attempt_time, command_type FROM spam_attempts WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

        if row:
            last_attempt_time = datetime.datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            command_type = row[1]

            if command_type == "sms":
                cooldown_period = datetime.timedelta(seconds=60)
            elif command_type == "call":
                cooldown_period = datetime.timedelta(seconds=700)
            else:
                cooldown_period = datetime.timedelta(seconds=0)

            if now - last_attempt_time < cooldown_period:
                time_left = cooldown_period - (now - last_attempt_time)
                seconds_left = int(time_left.total_seconds())
                user_mention = message.from_user.first_name
                bot.reply_to(message, f'{user_mention} phải chờ {seconds_left} giây nữa trước khi có thể dùng lệnh spam mới.')
                bot.delete_message(chat_id, message.message_id)
                connection.close()
                return

    if len(message.text.split()) < 2:
        bot.reply_to(message, 'Vui lòng nhập số điện thoại cần spam\nví dụ: /sms 0123456789')
        return

    phone_number = message.text.split()[1]

    if not re.match(r'^\d{10}$', phone_number):
        bot.reply_to(message, 'Số điện thoại không hợp lệ. Vui lòng nhập số điện thoại đúng (10 số).')
        return
    
    if phone_number in banned_numbers:
        user_mention = message.from_user.first_name
        bot.reply_to(message, f'{user_mention} không thể spam vì số này nằm trong danh sách cấm\nVui lòng nhập số khác.')
        return

    hidden_phone_number = hide_phone_number(phone_number)
    localtime = time.asctime(time.localtime(time.time()))
    user_mention = message.from_user.first_name

    hi = f'''🌟𝐒𝐏𝐀𝐌 𝐒𝐌𝐒 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋𝐋𝐘
⭐️𝚸𝐡𝝾𝖓𝐞: {hidden_phone_number}
⏰𝗧𝗶𝗺𝗲: {localtime}
👤𝗦𝗽𝗮𝗺 𝗯𝘆 <a href='tg://user?id={user_id}'>{user_mention}</a>
'''
    bot.send_message(chat_id, text=hi, parse_mode='HTML')

    with db_lock:
        now = datetime.datetime.now()
        cursor.execute('INSERT OR REPLACE INTO spam_attempts (user_id, last_attempt_time, command_type) VALUES (?, ?, ?)', 
               (user_id, now.strftime('%Y-%m-%d %H:%M:%S'), "sms"))
        connection.commit()

    try:
        bot.delete_message(chat_id, message.message_id)
    except telebot.apihelper.ApiTelegramException as e:
        print(f"Error deleting message: {e}") 

    file_path = os.path.join(os.getcwd(), "sms.py")
    process = subprocess.Popen(["python3", file_path, phone_number, "3"])
    processes.append(process) 

@bot.message_handler(commands=['call'])
def handle_send_call(message):
    if not is_bot_active():
        bot.reply_to(message, 'Hiện tại bot đang bảo trì. Chỉ Admin mới có thể sử dụng lệnh này.')
        return
    global banned_numbers 
    cleanup_expired_attempts()

    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in ADMIN_ID and user_id not in allowed_users:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh này. Vui lòng liên hệ admin để được thêm vào danh sách sử dụng. Hoặc /thanhtoan để mua VIP')
        return

    if message.chat.type == 'private' and message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, 'Chỉ có admin mới có thể nhắn tin riêng với bot\nTham gia nhóm https://t.me/phlzx_network để sử dụng bot')
        return

    bot_status = check()
    if bot_status == 'off':
        bot.reply_to(message, 'Hiện tại bot đang off gọi Admin để bật bot.')
        return

    with db_lock:
        connection = get_db_connection()
        cursor = connection.cursor()
        now = datetime.datetime.now()
        cursor.execute('SELECT last_attempt_time, command_type FROM spam_attempts WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()

        if row:
            last_attempt_time = datetime.datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            command_type = row[1]

            if command_type == "sms":
                cooldown_period = datetime.timedelta(seconds=60)
            elif command_type == "call":
                cooldown_period = datetime.timedelta(seconds=700)
            else:
                cooldown_period = datetime.timedelta(seconds=0)

            if now - last_attempt_time < cooldown_period:
                time_left = cooldown_period - (now - last_attempt_time)
                seconds_left = int(time_left.total_seconds())
                user_mention = message.from_user.first_name
                bot.reply_to(message, f'{user_mention} phải chờ {seconds_left} giây nữa trước khi có thể dùng lệnh spam mới.')
                bot.delete_message(chat_id, message.message_id)
                connection.close()
                return

    if len(message.text.split()) < 2:
        bot.reply_to(message, 'Vui lòng nhập số điện thoại cần spam\nví dụ: /call 0123456789')
        return

    phone_number = message.text.split()[1]

    if not re.match(r'^\d{10}$', phone_number):
        bot.reply_to(message, 'Số điện thoại không hợp lệ. Vui lòng nhập số điện thoại đúng (10 số).')
        return
    
    if phone_number in banned_numbers:
        user_mention = message.from_user.first_name
        bot.reply_to(message, f'{user_mention} không thể spam vì số này nằm trong danh sách cấm\nVui lòng nhập số khác.')
        return

    hidden_phone_number = hide_phone_number(phone_number)
    localtime = time.asctime(time.localtime(time.time()))
    user_mention = message.from_user.first_name

    hi = f'''🌟𝐒𝐏𝐀𝐌 CALL 𝐒𝐔𝐂𝐂𝐄𝐒𝐒𝐅𝐔𝐋𝐋𝐘
⭐️𝚸𝐡𝝾𝖓𝐞: {hidden_phone_number}
⏰𝗧𝗶𝗺𝗲: {localtime}
👤𝗦𝗽𝗮𝗺 𝗯𝘆 <a href='tg://user?id={user_id}'>{user_mention}</a>
'''
    bot.send_message(chat_id, text=hi, parse_mode='HTML')

    with db_lock:
        now = datetime.datetime.now()
        cursor.execute('INSERT OR REPLACE INTO spam_attempts (user_id, last_attempt_time, command_type) VALUES (?, ?, ?)', 
               (user_id, now.strftime('%Y-%m-%d %H:%M:%S'), "call"))
        connection.commit()

    # Chạy file call.py
    file_path = os.path.join(os.getcwd(), "call.py")
    process = subprocess.Popen(["python3", file_path, phone_number, "1"])
    processes.append(process)

    bot.delete_message(chat_id, message.message_id)

@bot.message_handler(commands=['token'])
def handle_add_token(message):
    # Check if the user is an Admin
    if message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh này.')
        return

    # Split the message text to get phone and token
    if len(message.text.split()) < 2:
        bot.reply_to(message, 'Vui lòng nhập phone|token.\nVí dụ: /token 0123456789|your_token')
        return

    token_input = message.text.split()[1]
    
    # Validate the input format
    if '|' not in token_input:
        bot.reply_to(message, 'Định dạng không hợp lệ. Vui lòng sử dụng định dạng phone|token.')
        return

    phone, token = token_input.split('|', 1)

    # Append the phone and token to live.txt
    with open('live.txt', 'a') as file:
        file.write(f'{phone}|{token}\n')

    bot.reply_to(message, f'Đã thêm thành công: {phone}|{token} vào live.txt.')

@bot.message_handler(commands=['status'])
def handle_status(message):
    if message.from_user.id not in ADMIN_ID:
        return

    # Lấy thông tin hệ thống
    num_processes = len(psutil.pids())
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    uptime_seconds = time.time() - psutil.boot_time()
    uptime = datetime.timedelta(seconds=int(uptime_seconds))

    # Đếm số dòng trong live.txt
    try:
        live_file_path = os.path.join(os.getcwd(), 'live.txt')
        if os.path.exists(live_file_path):
            with open(live_file_path, 'r') as f:
                line_count = sum(1 for _ in f)
        else:
            line_count = 0
    except Exception as e:
        line_count = f'Lỗi: {str(e)}'

    # Ghép thông tin
    status_message = (
        f'🖥️ **Server Status:**\n'
        f'**Number of Active Processes:** {num_processes}\n'
        f'**CPU Usage:** {cpu_percent}%\n'
        f'**Memory Usage:** {memory_info.percent}%\n'
        f'**Uptime:** {str(uptime).split(".")[0]}\n'
        f'**API CALL:** {line_count}'
    )

    bot.reply_to(message, status_message, parse_mode='Markdown')
    
@bot.message_handler(commands=['bot'])
def handle_status_bot(message):
    msg = message.text.split()
    
    if message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, 'Bạn không có quyền sử dụng lệnh /bot.')
        return
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute('SELECT status FROM status WHERE id = 1')
    current_status = cursor.fetchone()[0]
    
    if len(msg) < 2:
        bot.reply_to(message, f'Cách dùng -> /bot (on/off)\non: bật bot\noff: tắt bot\nTrạng thái hiện tại: {current_status}')
        connection.close()
        return
    
    status = msg[1].lower()
    
    if status in ['on', 'off']:
        cursor.execute('UPDATE status SET status = ? WHERE id = 1', (status,))
        connection.commit()
        bot.reply_to(message, f'Trạng thái bot đã được cập nhật thành {status}.')
    else:
        bot.reply_to(message, f'Cách dùng -> /bot (on/off)\non: bật bot\noff: tắt bot\nTrạng thái hiện tại: {current_status}')
    
    connection.close()

@bot.message_handler(commands=['plan'])
def handle_plan(message):
    user_id = message.from_user.id

    with db_lock:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute('SELECT expiration_time FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        connection.close()

    if result:
        expiration_time = result[0]
        response_message = f'**Thông tin của người dùng:**\n'
        response_message += f'- **User  ID:** {user_id}\n'
        response_message += f'- **Expiration Time:** {expiration_time}\n'
    else:
        response_message = f'Không tìm thấy thông tin cho người dùng ID {user_id}.'

    bot.reply_to(message, response_message, parse_mode='Markdown')

@bot.message_handler(commands=['thanhtoan'])
def handle_payment(message):
    user_id = message.from_user.id

    payment_info = (
        "🤑 **THÔNG TIN THANH TOÁN:**\n"
        f"**NGÂN HÀNG:** `MB BANK`\n"
        f"**SỐ TÀI KHOẢN:** `0373442125`\n"
        f"**CHỦ TÀI KHOẢN:** `NGUYEN THI THU NGUYET`\n"
        f"**SỐ TIỀN:** `40.000 VNĐ`\n"
        f"**NỘI DUNG:** `VIP{user_id}`\n\n"
        f"**Vui Lòng chụp bill và gửi cho ADMIN**\n"
        f"**QR Code thanh toán:** [Nhấn vào đây để xem QR](https://img.vietqr.io/image/MB-0373442125-qr_only.png?amount=40000&addInfo=VIP{user_id})"
    )
    bot.reply_to(message, payment_info, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def handle_admin(message):
    commands = [
            "Danh sách lệnh điều khiển bot ",
            "/sms - Gửi spam số điện thoại.",
            "/call - Gửi call số điện thoại.",
            "/plan - Xem thông tin của bạn.",
            "/thanhtoan - Thanh toán mua VIP.",
            "/add_phone - Cấm một số điện thoại.",
            "/delete_phone - Bỏ cấm một số điện thoại.",
            "/list_phone - Hiển thị danh sách số điện thoại bị cấm.",
            "/add_user - Thêm người dùng vào danh sách VIP.",
            "/delete_user - Xóa người dùng khỏi danh sách VIP.",
            "/list_user - Hiển thị danh sách người dùng VIP.",
            "/status - Hiển thị trạng thái server.",
            "/bot - Chỉnh trạng thái của bot.",
    ]

    help_message = "" + "\n".join(commands)
    bot.reply_to(message, help_message)

while True:
    bot.infinity_polling()
