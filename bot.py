import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import json
import os
import subprocess
import urllib3
import shutil
import sys
import sqlite3
import functools
from http.server import SimpleHTTPRequestHandler, HTTPServer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- HUGGING FACE BYPASS ---
def custom_sender(method, url, **kwargs):
    url = url.replace("api.telegram.org", "149.154.167.220")
    kwargs['verify'] = False 
    headers = kwargs.get('headers', {})
    headers['Host'] = 'api.telegram.org'
    kwargs['headers'] = headers
    return requests.request(method, url, **kwargs)

telebot.apihelper.CUSTOM_REQUEST_SENDER = custom_sender
# ---------------------------

# BOT TOKEN YAHAN DALO
TOKEN = "8857508546:AAE1BBVDC-fMm50pNIvocnHeTYzurIZ1eOE" 
bot = telebot.TeleBot(TOKEN)

# Data Storage & Folders
DB_FILE = "host_data.db"
PROJECTS_DIR = "hosted_projects"

user_states = {}
upload_sessions = {}
running_processes = {}
active_admins = set() 

if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

# --- SQLITE DATABASE SYSTEM ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS store (id INTEGER PRIMARY KEY, data TEXT)")
    conn.commit()
    conn.close()

def load_data():
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT data FROM store WHERE id=1")
    row = c.fetchone()
    conn.close()
    if row:
        data = json.loads(row[0])
        if "admin_pass" not in data:
            data["admin_pass"] = "BOTPY123"
        return data
    else:
        return {"users": {}, "admin_upi": "", "base_url": "URL_NOT_SET", "pending_requests": {}, "admin_pass": "BOTPY123"}

def save_data(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM store WHERE id=1")
    c.execute("INSERT INTO store (id, data) VALUES (1, ?)", (json.dumps(data),))
    conn.commit()
    conn.close()

db = load_data()

def get_user(user_id):
    user_id_str = str(user_id)
    if user_id_str not in db["users"]:
        db["users"][user_id_str] = {"balance": 0.0, "history": [], "projects": {}}
        save_data(db)
    return db["users"][user_id_str]

# --- KEYBOARDS ---
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("HOST PYTHON"), KeyboardButton("MY LIST"))
    markup.row(KeyboardButton("MY BALANCE"), KeyboardButton("ADD BALANCE"))
    markup.row(KeyboardButton("HISTORY"), KeyboardButton("RUN BOTS"))
    return markup

def back_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("BACK"))
    return markup

def host_type_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("FREE"), KeyboardButton("PAID"))
    markup.add(KeyboardButton("BACK"))
    return markup

def admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("USER INFO"), KeyboardButton("TOTAL PROJECT INFO"))
    markup.row(KeyboardButton("SET LINK"), KeyboardButton("REQUESTS INFO"))
    markup.row(KeyboardButton("SET UPI ID"), KeyboardButton("CHANGE PASSWORD"))
    markup.row(KeyboardButton("LOGOUT"), KeyboardButton("BACK"))
    return markup

# --- USER COMMANDS ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    get_user(message.from_user.id)
    user_states.pop(message.from_user.id, None)
    text = f"HI WOLKOWM TO PYTHON HOSTING BOT FOR DEV @Darkaura9999\nOK ENJOY BOT"
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "BACK")
def back_btn(message):
    user_states.pop(message.from_user.id, None)
    upload_sessions.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "Back to Main Menu", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "MY BALANCE")
def my_bal(message):
    user = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"💰 My Balance: ₹{user['balance']}", reply_markup=main_menu())

# --- ADD BALANCE & PAYMENT ---
@bot.message_handler(func=lambda message: message.text == "ADD BALANCE")
def add_bal(message):
    if not db["admin_upi"]:
        bot.send_message(message.chat.id, "Admin ne abhi UPI set nahi kiya hai.", reply_markup=main_menu())
        return
    user_states[message.from_user.id] = "waiting_for_amount"
    bot.send_message(message.chat.id, "Apne amunt dalo (Numbers me):", reply_markup=back_menu())

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_amount")
def handle_amount_state(message):
    user_id = message.from_user.id
    try:
        amount = float(message.text)
        if amount <= 0: raise ValueError
        admin_upi = db["admin_upi"]
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={admin_upi}&pn=Admin&am={amount}"
        user_states[user_id] = f"waiting_for_utr_{amount}"
        bot.send_photo(message.chat.id, qr_url, caption=f"Scan this QR to pay ₹{amount}.\nPay ke bad 12 anko ka UTR dale:")
    except:
        bot.send_message(message.chat.id, "Invalid amount.", reply_markup=main_menu())
        user_states.pop(user_id, None)

@bot.message_handler(func=lambda message: message.from_user.id in user_states and str(user_states[message.from_user.id]).startswith("waiting_for_utr_"))
def handle_utr_state(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    amount = float(state.split("_")[3])
    utr = message.text.strip()
    req_id = str(int(time.time()))
    db["pending_requests"][req_id] = {"user_id": user_id, "amount": amount, "utr": utr}
    save_data(db)
    bot.send_message(message.chat.id, "Request sent to Admin. Wait for approval.", reply_markup=main_menu())
    user_states.pop(user_id, None)

@bot.message_handler(func=lambda message: message.text == "HISTORY")
def show_history(message):
    user = get_user(message.from_user.id)
    history = user["history"]
    if not history:
        bot.send_message(message.chat.id, "No history found.")
        return
    text = "🧾 PAYMENT HISTORY:\n\n"
    for h in history[-10:]:
        text += f"Amount: ₹{h['amount']} | UTR: {h['utr']} | Status: {h['status']}\n"
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

# --- HOST PYTHON LOGIC ---
@bot.message_handler(func=lambda message: message.text == "HOST PYTHON")
def host_py(message):
    user_states[message.from_user.id] = "waiting_for_host_type"
    bot.send_message(message.chat.id, "Select Hosting Type:", reply_markup=host_type_menu())

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_host_type")
def select_host_type(message):
    choice = message.text
    if choice not in ["FREE", "PAID"]: return
    user_id = message.from_user.id
    user = get_user(user_id)
    if choice == "PAID" and user["balance"] < 5:
        bot.send_message(message.chat.id, "Aapka balance kam hai PAID ke liye (Minimum ₹5 chahiye). ADD BALANCE karein.", reply_markup=main_menu())
        user_states.pop(user_id, None)
        return
    upload_sessions[user_id] = {"type": choice, "files": [], "project_name": ""}
    user_states[user_id] = "waiting_for_project_name"
    bot.send_message(message.chat.id, "Project Name do (No spaces):", reply_markup=back_menu())

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_project_name")
def get_proj_name(message):
    user_id = message.from_user.id
    proj_name = message.text.strip().replace(" ", "_")
    upload_sessions[user_id]["project_name"] = proj_name
    user_states[user_id] = "uploading_files"
    bot.send_message(message.chat.id, "UPLOAD YOUR FILES (.py, .txt). Upload hone ke baad /done bhejein.", reply_markup=back_menu())

@bot.message_handler(content_types=['document'], func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "uploading_files")
def handle_docs(message):
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.document.file_id)
        file_url = f"https://149.154.167.220/file/bot{TOKEN}/{file_info.file_path}"
        response = requests.get(file_url, headers={'Host': 'api.telegram.org'}, verify=False)
        downloaded_file = response.content
        file_name = message.document.file_name
        proj_name = upload_sessions[user_id]["project_name"]
        
        save_dir = os.path.join(PROJECTS_DIR, str(user_id), proj_name)
        if not os.path.exists(save_dir): os.makedirs(save_dir)
            
        with open(os.path.join(save_dir, file_name), 'wb') as new_file:
            new_file.write(downloaded_file)
            
        upload_sessions[user_id]["files"].append(file_name)
        bot.send_message(message.chat.id, f"File saved: {file_name}\nAur upload karein ya /done bhejein.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error saving file: {str(e)}")

# COMMON DONE HANDLER (FOR HOST AND FILE MANAGER)
@bot.message_handler(commands=['done'])
def handle_done_all(message):
    user_id = message.from_user.id
    state = str(user_states.get(user_id, ""))
    
    if state == "uploading_files":
        session = upload_sessions.get(user_id)
        if not session or not session["files"]:
            bot.send_message(message.chat.id, "Koi file upload nahi hui. Cancelled.", reply_markup=main_menu())
            user_states.pop(user_id, None)
            return
            
        proj_name = session["project_name"]
        host_type = session["type"]
        
        db["users"][str(user_id)]["projects"][proj_name] = {"type": host_type, "files": session["files"], "status": "STOPPED"}
        if host_type == "PAID": db["users"][str(user_id)]["balance"] -= 5.0
        save_data(db)
        
        file_list = "\n".join(session["files"])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("RUN", callback_data=f"run_{user_id}_{proj_name}"))
        
        bot.send_message(message.chat.id, f"Files Uploaded for {proj_name}:\n{file_list}\n\nProject Type: {host_type}", reply_markup=markup)
        bot.send_message(message.chat.id, "Main Menu", reply_markup=main_menu())
        user_states.pop(user_id, None)
        upload_sessions.pop(user_id, None)
        
    elif state.startswith("fm_uploading_"):
        proj_name = state.split("_")[2]
        bot.send_message(message.chat.id, f"Checking karega... ✅ Sab files project '{proj_name}' me add ho gayi hain!", reply_markup=main_menu())
        user_states.pop(user_id, None)

# --- RUN BOTS LOGIC W/ REAL LOGS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("run_"))
def run_project_callback(call):
    data = call.data.split("_")
    user_id = data[1]
    proj_name = data[2]
    
    msg_id = call.message.message_id
    bot.edit_message_text("Checking requirements...", call.message.chat.id, msg_id)
    time.sleep(1)
    
    proj_path = os.path.join(PROJECTS_DIR, user_id, proj_name)
    req_file = os.path.join(proj_path, "requirements.txt")
    
    if os.path.exists(req_file):
        bot.edit_message_text("Installing Requirements...\nLogs: pip install processing...", call.message.chat.id, msg_id)
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=proj_path)
        time.sleep(2)
        bot.edit_message_text("Installing Requirements... ✅ OK HARA", call.message.chat.id, msg_id)
    
    py_files = [f for f in os.listdir(proj_path) if f.endswith('.py')]
    if not py_files:
        bot.edit_message_text("❌ No .py file found to run.", call.message.chat.id, msg_id)
        return
        
    main_file = py_files[0] 
    process_key = f"{user_id}_{proj_name}"
    
    if process_key in running_processes:
        running_processes[process_key].terminate()
        
    # REAL LOGS SYSTEM
    log_path = os.path.join(proj_path, "logs.txt")
    log_file = open(log_path, "w")
    proc = subprocess.Popen([sys.executable, main_file], cwd=proj_path, stdout=log_file, stderr=subprocess.STDOUT)
    running_processes[process_key] = proc
    
    db["users"][str(user_id)]["projects"][proj_name]["status"] = "LIVE"
    save_data(db)
    
    proj_type = db["users"][str(user_id)]["projects"][proj_name]["type"]
    base_url = db.get("base_url", "URL_NOT_SET")
    url = f"{base_url}/{user_id}/{proj_name}/"
    
    success_text = f"✅ Project {proj_name} is LIVE!\nType: {proj_type}\nURL: {url}\nLogs: 100% REAL LIVE 🟢 (Visit URL to see files & logs.txt)"
    bot.edit_message_text(success_text, call.message.chat.id, msg_id)
    
    if proj_type == "FREE":
        bot.send_message(call.message.chat.id, f"⚠️ Note: {proj_name} is FREE. Sleep mode will activate in 2 minutes.")
        threading.Timer(120.0, sleep_bot, args=[user_id, proj_name]).start()

def sleep_bot(user_id, proj_name):
    process_key = f"{user_id}_{proj_name}"
    if process_key in running_processes:
        running_processes[process_key].terminate()
        del running_processes[process_key]
    user_id_str = str(user_id)
    if user_id_str in db["users"] and proj_name in db["users"][user_id_str]["projects"]:
        db["users"][user_id_str]["projects"][proj_name]["status"] = "SLEEP"
        save_data(db)
        try: bot.send_message(user_id, f"💤 Aapka FREE project '{proj_name}' 2 min baad SLEEP MOD me chala gaya hai.")
        except: pass

@bot.message_handler(func=lambda message: message.text == "RUN BOTS")
def run_bots_menu(message):
    user_id = str(message.from_user.id)
    projects = db["users"].get(user_id, {}).get("projects", {})
    if not projects:
        bot.send_message(message.chat.id, "No projects hosted.", reply_markup=main_menu())
        return
    text = "Your Hosted Projects:\n"
    markup = InlineKeyboardMarkup()
    for p_name, p_data in projects.items():
        text += f"- {p_name} ({p_data['status']})\n"
        markup.add(InlineKeyboardButton(f"RUN {p_name}", callback_data=f"run_{user_id}_{p_name}"))
    bot.send_message(message.chat.id, text, reply_markup=markup)

# --- MY LIST & FILE MANAGER (WITH ADD/CREATE) ---
@bot.message_handler(func=lambda message: message.text == "MY LIST")
def my_list_cmd(message):
    user_id = str(message.from_user.id)
    projects = db["users"].get(user_id, {}).get("projects", {})
    if not projects:
        bot.send_message(message.chat.id, "No projects found.")
        return
        
    base_url = db.get("base_url", "URL_NOT_SET")
    text = "📂 ALL LIST\n\n"
    for p_name, p_data in projects.items():
        file_count = len(p_data.get("files", []))
        text += f"Project: {p_name}\nStatus: {p_data['status']}\nFiles: {file_count}\nURL: {base_url}/{user_id}/{p_name}/\n\n"
        
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("FILE MANAGER", callback_data="open_file_manager"))
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "open_file_manager")
def file_manager_open(call):
    user_states[call.from_user.id] = "fm_waiting_for_project"
    bot.send_message(call.message.chat.id, "Konsa project manage karna hai? Name likho:", reply_markup=back_menu())

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "fm_waiting_for_project")
def fm_select_project(message):
    user_id = str(message.from_user.id)
    proj_name = message.text.strip()
    projects = db["users"].get(user_id, {}).get("projects", {})
    
    if proj_name not in projects:
        bot.send_message(message.chat.id, "Project nahi mila. Sahi name dalo.")
        return
        
    user_states[int(user_id)] = f"fm_manage_{proj_name}"
    files = projects[proj_name]["files"]
    text = f"Files in {proj_name}:\n" + "\n".join(files) + "\n\nKonsi file me kam karna hai? Name dalo:"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📤 UPLOAD / ADD FILE", callback_data=f"fm_add_{proj_name}"))
    markup.row(InlineKeyboardButton("📄 CREATE NEW FILE", callback_data=f"fm_create_{proj_name}"))
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

# FILE MANAGER: UPLOAD FILES
@bot.callback_query_handler(func=lambda call: call.data.startswith("fm_add_"))
def fm_add_start(call):
    proj_name = call.data.split("_")[2]
    user_states[call.from_user.id] = f"fm_uploading_{proj_name}"
    bot.edit_message_text("Agar aapko apni file upload karni hai ya add karni hai toh apni file upload karke send kar do.", call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['document'], func=lambda message: str(user_states.get(message.from_user.id, "")).startswith("fm_uploading_"))
def fm_handle_extra_docs(message):
    user_id = message.from_user.id
    proj_name = user_states[user_id].split("_")[2]
    try:
        file_info = bot.get_file(message.document.file_id)
        file_url = f"https://149.154.167.220/file/bot{TOKEN}/{file_info.file_path}"
        response = requests.get(file_url, headers={'Host': 'api.telegram.org'}, verify=False)
        file_name = message.document.file_name
        
        save_path = os.path.join(PROJECTS_DIR, str(user_id), proj_name, file_name)
        with open(save_path, 'wb') as new_file:
            new_file.write(response.content)
            
        if file_name not in db["users"][str(user_id)]["projects"][proj_name]["files"]:
            db["users"][str(user_id)]["projects"][proj_name]["files"].append(file_name)
            save_data(db)
            
        bot.send_message(message.chat.id, f"Received file: {file_name}\nAgar jo aapko bas itni hi upload karni hai to /done bhejo. Hum ise aapke project me add kar denge. Agar aur karni hai to upload kar sakte hain.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {str(e)}")

# FILE MANAGER: CREATE NEW FILE
@bot.callback_query_handler(func=lambda call: call.data.startswith("fm_create_"))
def fm_create_start(call):
    proj_name = call.data.split("_")[2]
    user_states[call.from_user.id] = f"fm_create_name_{proj_name}"
    bot.edit_message_text("Apni nai file ka name dalo (e.g. main.py):", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: str(user_states.get(message.from_user.id, "")).startswith("fm_create_name_"))
def fm_create_name(message):
    user_id = message.from_user.id
    proj_name = user_states[user_id].split("_")[3]
    file_name = message.text.strip()
    user_states[user_id] = f"fm_create_code_{proj_name}_{file_name}"
    bot.send_message(message.chat.id, f"Ab {file_name} ka code yahan paste karo:")

@bot.message_handler(func=lambda message: str(user_states.get(message.from_user.id, "")).startswith("fm_create_code_"))
def fm_create_code(message):
    user_id = message.from_user.id
    data = user_states[user_id].split("_")
    proj_name = data[3]
    file_name = data[4]
    
    save_path = os.path.join(PROJECTS_DIR, str(user_id), proj_name, file_name)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(message.text)
        
    if file_name not in db["users"][str(user_id)]["projects"][proj_name]["files"]:
        db["users"][str(user_id)]["projects"][proj_name]["files"].append(file_name)
        save_data(db)
        
    bot.send_message(message.chat.id, f"✅ {file_name} successfully create aur save ho gayi!", reply_markup=main_menu())
    user_states.pop(user_id, None)

# FILE MANAGER: EDIT/DELETE EXISTING
@bot.message_handler(func=lambda message: message.from_user.id in user_states and str(user_states[message.from_user.id]).startswith("fm_manage_"))
def fm_select_file(message):
    user_id = message.from_user.id
    proj_name = user_states[user_id].split("_")[2]
    file_name = message.text.strip()
    
    projects = db["users"][str(user_id)]["projects"]
    if file_name not in projects[proj_name]["files"]:
        bot.send_message(message.chat.id, "File nahi mili. Sahi name type karein ya buttons use karein.")
        return
        
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("EDIT", callback_data=f"fmedit_{user_id}_{proj_name}_{file_name}"),
        InlineKeyboardButton("DELETE", callback_data=f"fmdel_{user_id}_{proj_name}_{file_name}")
    )
    bot.send_message(message.chat.id, f"File: {file_name}\nKya karna hai?", reply_markup=markup)
    user_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith("fmdel_"))
def fm_delete_file(call):
    data = call.data.split("_")
    user_id, proj_name, file_name = data[1], data[2], data[3]
    proj_path = os.path.join(PROJECTS_DIR, user_id, proj_name)
    file_path = os.path.join(proj_path, file_name)
    
    if os.path.exists(file_path): os.remove(file_path)
    if file_name in db["users"][user_id]["projects"][proj_name]["files"]:
        db["users"][user_id]["projects"][proj_name]["files"].remove(file_name)
        save_data(db)
    
    bot.edit_message_text("✅ File Deleted", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("fmedit_"))
def fm_edit_file(call):
    data = call.data.split("_")
    user_id, proj_name, file_name = int(data[1]), data[2], data[3]
    user_states[user_id] = f"fm_upload_new_{proj_name}_{file_name}"
    bot.edit_message_text("OK AB AAP APNE NEW CODE DO. (Text message ya new file bhejo)", call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['text', 'document'], func=lambda message: message.from_user.id in user_states and str(user_states[message.from_user.id]).startswith("fm_upload_new_"))
def fm_save_new_code(message):
    user_id = message.from_user.id
    state_data = user_states[user_id].split("_")
    proj_name = state_data[3]
    file_name = state_data[4]
    
    save_path = os.path.join(PROJECTS_DIR, str(user_id), proj_name, file_name)
    try:
        if message.content_type == 'text':
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(message.text)
        elif message.content_type == 'document':
            file_info = bot.get_file(message.document.file_id)
            file_url = f"https://149.154.167.220/file/bot{TOKEN}/{file_info.file_path}"
            response = requests.get(file_url, headers={'Host': 'api.telegram.org'}, verify=False)
            with open(save_path, 'wb') as f:
                f.write(response.content)
        bot.send_message(message.chat.id, f"✅ Code updated in {file_name}!", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {str(e)}")
    user_states.pop(user_id, None)

# --- ADMIN PANEL ---
@bot.message_handler(commands=['admin'])
def admin_start(message):
    user_states[message.from_user.id] = "waiting_for_admin_pass"
    bot.send_message(message.chat.id, "Apne password admin ka do:")

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_admin_pass")
def admin_login(message):
    if message.text == db["admin_pass"]:
        user_states.pop(message.from_user.id, None)
        active_admins.add(message.from_user.id)
        bot.send_message(message.chat.id, "Admin Logged In!", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Wrong Password!", reply_markup=main_menu())
        user_states.pop(message.from_user.id, None)

@bot.message_handler(func=lambda message: message.text == "LOGOUT" and message.from_user.id in active_admins)
def admin_logout(message):
    active_admins.discard(message.from_user.id)
    bot.send_message(message.chat.id, "Admin Logged Out!", reply_markup=main_menu())

@bot.message_handler(func=lambda message: message.text == "CHANGE PASSWORD" and message.from_user.id in active_admins)
def change_pass_cmd(message):
    user_states[message.from_user.id] = "waiting_for_old_pass"
    bot.send_message(message.chat.id, "Apna old password dalo:", reply_markup=back_menu())

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_old_pass")
def check_old_pass(message):
    if message.text == db["admin_pass"]:
        user_states[message.from_user.id] = "waiting_for_new_pass"
        bot.send_message(message.chat.id, "New password dalo:")
    else:
        bot.send_message(message.chat.id, "Wrong old password!", reply_markup=admin_menu())
        user_states.pop(message.from_user.id, None)

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_new_pass")
def save_new_pass(message):
    db["admin_pass"] = message.text.strip()
    save_data(db)
    bot.send_message(message.chat.id, "Password successfully changed!", reply_markup=admin_menu())
    user_states.pop(message.from_user.id, None)

@bot.message_handler(func=lambda message: message.text == "SET UPI ID" and message.from_user.id in active_admins)
def admin_set_upi(message):
    user_states[message.from_user.id] = "waiting_for_admin_upi"
    bot.send_message(message.chat.id, "Enter UPI ID:", reply_markup=back_menu())

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_admin_upi" and message.from_user.id in active_admins)
def admin_save_upi(message):
    db["admin_upi"] = message.text.strip()
    save_data(db)
    bot.send_message(message.chat.id, f"UPI ID Set to: {db['admin_upi']}", reply_markup=admin_menu())
    user_states.pop(message.from_user.id, None)

@bot.message_handler(func=lambda message: message.text == "SET LINK" and message.from_user.id in active_admins)
def admin_set_link(message):
    user_states[message.from_user.id] = "waiting_for_admin_link"
    bot.send_message(message.chat.id, "Hugging Face ka Base URL do (e.g. https://your-space.hf.space):", reply_markup=back_menu())

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_admin_link" and message.from_user.id in active_admins)
def admin_save_link(message):
    url = message.text.strip()
    if url.endswith("/"): url = url[:-1]
    db["base_url"] = url
    save_data(db)
    bot.send_message(message.chat.id, f"Link Set to: {db['base_url']}", reply_markup=admin_menu())
    user_states.pop(message.from_user.id, None)

@bot.message_handler(func=lambda message: message.text == "USER INFO" and message.from_user.id in active_admins)
def admin_user_info(message):
    text = "Users & Projects:\n"
    for uid, udata in db["users"].items():
        text += f"\nUser: {uid}\n"
        for pname, pdata in udata["projects"].items():
            text += f"  - {pname} ({pdata['type']}) [{pdata['status']}]\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == "TOTAL PROJECT INFO" and message.from_user.id in active_admins)
def admin_total_info(message):
    total = sum(len(u["projects"]) for u in db["users"].values())
    live = sum(1 for u in db["users"].values() for p in u["projects"].values() if p["status"] == "LIVE")
    sleep = sum(1 for u in db["users"].values() for p in u["projects"].values() if p["status"] == "SLEEP")
    bot.send_message(message.chat.id, f"Total Projects: {total}\nLIVE: {live}\nSLEEP: {sleep}")

@bot.message_handler(func=lambda message: message.text == "REQUESTS INFO" and message.from_user.id in active_admins)
def admin_req_info(message):
    if not db["pending_requests"]:
        bot.send_message(message.chat.id, "No pending requests.")
        return
    for req_id, rdata in db["pending_requests"].items():
        text = f"Req ID: {req_id}\nUser: {rdata['user_id']}\nAmount: ₹{rdata['amount']}\nUTR: {rdata['utr']}"
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("SUCCESS", callback_data=f"payacc_{req_id}"), InlineKeyboardButton("REJECT", callback_data=f"payrej_{req_id}"))
        bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("payacc_") or call.data.startswith("payrej_"))
def admin_payment_action(call):
    if call.from_user.id not in active_admins:
        bot.answer_callback_query(call.id, "You are not an admin!", show_alert=True)
        return
    action, req_id = call.data.split("_")
    if req_id not in db["pending_requests"]:
        bot.answer_callback_query(call.id, "Req not found.", show_alert=True)
        return
    rdata = db["pending_requests"].pop(req_id)
    user_id = str(rdata["user_id"])
    amount = rdata["amount"]
    utr = rdata["utr"]
    user = get_user(user_id)
    
    if action == "payacc":
        user["balance"] += amount
        user["history"].append({"amount": amount, "utr": utr, "status": "SUCCESS"})
        bot.edit_message_text(f"{call.message.text}\n\n✅ SUCCESS", call.message.chat.id, call.message.message_id)
        try: bot.send_message(user_id, f"✅ ₹{amount} added to wallet! UTR: {utr}")
        except: pass
    else:
        user["history"].append({"amount": amount, "utr": utr, "status": "REJECT"})
        bot.edit_message_text(f"{call.message.text}\n\n❌ REJECTED", call.message.chat.id, call.message.message_id)
        try: bot.send_message(user_id, f"❌ Payment Rejected! UTR: {utr}")
        except: pass
    save_data(db)

# --- 100% REAL URL HOSTING SERVER ---
def run_real_server():
    # Ye handler seedha projects ka folder show karega URL par!
    Handler = functools.partial(SimpleHTTPRequestHandler, directory=PROJECTS_DIR)
    server = HTTPServer(('0.0.0.0', 7860), Handler)
    server.serve_forever()

if __name__ == "__main__":
    print("PYTHON HOSTING BOT STARTED WITH SQL & REAL SERVER...")
    threading.Thread(target=run_real_server, daemon=True).start()
    while True:
        try: bot.infinity_polling(skip_pending=True)
        except Exception as e: time.sleep(3)
