import telebot
import random
import sqlite3
from telebot import types

# --- الإعدادات ---
API_TOKEN = '8764097317:AAH33c23-SIkuvLjyhVgbaopC2XQQuavTQQ'
DEVELOPER_ID = '8417816240'  # ضع الآيدي الخاص بك هنا
bot = telebot.TeleBot(API_TOKEN)

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('muhaibis.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            points INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            rounds INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def update_user_stats(user_id, name, won=False, lost=False):
    conn = sqlite3.connect('muhaibis.db')
    cursor = conn.cursor()
    # التأكد من وجود المستخدم
    cursor.execute('INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)', (user_id, name))
    
    if won:
        cursor.execute('UPDATE users SET points = points + 10, wins = wins + 1, rounds = rounds + 1, name = ? WHERE user_id = ?', (name, user_id))
    elif lost:
        cursor.execute('UPDATE users SET losses = losses + 1, rounds = rounds + 1, name = ? WHERE user_id = ?', (name, user_id))
    
    conn.commit()
    conn.close()

def get_rank(points):
    if points >= 500: return "👑 ملك البات"
    if points >= 150: return "🥇 أسطورة"
    if points >= 50:  return "🥈 محترف"
    return "🥉 مبتدئ"

# --- متغيرات اللعبة المؤقتة ---
games = {} 
user_to_group = {} 

init_db()

# --- الأوامر ---

@bot.message_handler(commands=['ha'])
def my_stats(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('muhaibis.db')
    cursor = conn.cursor()
    cursor.execute('SELECT points, wins, losses, rounds FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        points, wins, losses, rounds = row
        rank = get_rank(points)
        text = (f"📊 إحصائياتك يا بطل:\n\n"
                f"👤 الاسم: {message.from_user.first_name}\n"
                f"🏅 الرتبة: {rank}\n"
                f"✨ النقاط: {points}\n"
                f"🏆 عدد الفوز: {wins}\n"
                f"❌ عدد الخسارة: {losses}\n"
                f"🔄 جولات لعبتها: {rounds}")
    else:
        text = "ما عندك سجل حالياً، العب أول جولة حتى تطلع بياناتك!"
    bot.reply_to(message, text)

@bot.message_handler(commands=['tob'])
def top_players(message):
    conn = sqlite3.connect('muhaibis.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, points FROM users ORDER BY points DESC LIMIT 10')
    rows = cursor.fetchall()
    conn.close()

    text = "🏆 قائمة أفضل 10 لاعبين (TOP 10):\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i} - {row[0]} » {row[1]} نقطة\n"
    bot.reply_to(message, text)

# --- منطق اللعبة (معدل لإضافة النقاط) ---

def is_authorized(message):
    if message.from_user.id == DEVELOPER_ID: return True
    member = bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ['administrator', 'creator']

@bot.message_handler(commands=['start_game'])
def start_cmd(message):
    if message.chat.type == "private" or not is_authorized(message): return
    chat_id = message.chat.id
    games[chat_id] = {'players': [], 'team1': [], 'team2': [], 'phase': 'joining', 'ring_holder': None, 'eliminated': []}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("انضمام للعبة ✋", callback_data=f"join_{chat_id}"))
    bot.send_message(chat_id, "🎮 بدأت جولة محيبس جديدة!\nسجل اسمك بالضغط على انضمام.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('join_'))
def join_player(call):
    chat_id = int(call.data.split('_')[1])
    user = call.from_user
    if chat_id in games and user.id not in [p['id'] for p in games[chat_id]['players']]:
        games[chat_id]['players'].append({'id': user.id, 'name': user.first_name})
        bot.answer_callback_query(call.id, "تم الانضمام!")

@bot.message_handler(commands=['split'])
def split_teams(message):
    chat_id = message.chat.id
    if chat_id not in games or not is_authorized(message): return
    if len(games[chat_id]['players']) < 2:
        return bot.reply_to(message, "لازم لاعبين اثنين على الأقل!")

    players = games[chat_id]['players']
    random.shuffle(players)
    mid = len(players) // 2
    games[chat_id]['team1'], games[chat_id]['team2'] = players[:mid], players[mid:]
    
    leader1, leader2 = games[chat_id]['team1'][0], games[chat_id]['team2'][0]
    bot.send_message(chat_id, f"🔵 فريق 1: {leader1['name']} (قائد)\n🔴 فريق 2: {leader2['name']} (قائد)\n\nيا {leader1['name']}، بيت المحبس بالخاص!")
    
    user_to_group[leader1['id']] = chat_id
    markup = types.InlineKeyboardMarkup()
    for p in games[chat_id]['team1']:
        markup.add(types.InlineKeyboardButton(p['name'], callback_data=f"hide_{p['id']}"))
    bot.send_message(leader1['id'], "اختار حامل المحبس:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('hide_'))
def finalize_hiding(call):
    holder_id = int(call.data.split('_')[1])
    group_id = user_to_group.get(call.from_user.id)
    if not group_id: return
    games[group_id]['ring_holder'] = holder_id
    leader2 = games[group_id]['team2'][0]
    user_to_group[leader2['id']] = group_id
    bot.send_message(group_id, f"💍 المحبس تبيت! يا {leader2['name']} ابدأ التفتيش بالخاص.")
    send_guess_menu(leader2['id'], group_id)

def send_guess_menu(leader_id, group_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for p in games[group_id]['team1']:
        if p['id'] not in games[group_id]['eliminated']:
            markup.add(types.InlineKeyboardButton(f"تفتيش {p['name']}", callback_data=f"guess_{p['id']}"))
    bot.send_message(leader_id, "منو عنده المحبس؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('guess_'))
def handle_guessing(call):
    guess_id = int(call.data.split('_')[1])
    group_id = user_to_group.get(call.from_user.id)
    if not group_id: return

    game = games[group_id]
    target = next(p for p in game['team1'] if p['id'] == guess_id)
    
    if guess_id == game['ring_holder']:
        # فوز الفريق الثاني
        bot.send_message(group_id, f"🔊 {call.from_user.first_name} صاح: {target['name']} افتحهههه! 🔥💍")
        bot.send_message(group_id, "🎉 الفريق الثاني فاز! كل واحد حصل +10 نقاط.")
        
        for p in game['team2']: update_user_stats(p['id'], p['name'], won=True)
        for p in game['team1']: update_user_stats(p['id'], p['name'], lost=True)
        
        del games[group_id]
        bot.edit_message_text("مبروك الفوز!", call.from_user.id, call.message.message_id)
    else:
        game['eliminated'].append(guess_id)
        bot.send_message(group_id, f"🔊 {call.from_user.first_name} كَال لـ {target['name']}: طاااااااااالع! ✋")
        bot.edit_message_text("طلع فارغ، كمل:", call.from_user.id, call.message.message_id)
        send_guess_menu(call.from_user.id, group_id)

bot.infinity_polling()
                message_id=game_data[chat_id]["message_id"],
                text=f"🎮 بدأت لعبة البات!\n⏳ الوقت المتبقي: {game_data[chat_id]['countdown']} ثانية\n👥 اللاعبين: {len(game_data[chat_id]['players'])}",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🎮 انضمام", callback_data="join_game")]]
                )
            )
        except:
            pass

    if chat_id in game_data:
        await finish_game(context, chat_id)

# ================= FINISH GAME =================
async def finish_game(context, chat_id):
    players = game_data[chat_id]["players"]

    if len(players) < 2:
        await context.bot.send_message(chat_id, "❌ ماكو لاعبين كافيين.")
        del game_data[chat_id]
        return

    winner_id = random.choice(players)

    for user_id in players:
        cursor.execute("UPDATE players SET games = games + 1 WHERE user_id=?", (user_id,))

        if user_id == winner_id:
            cursor.execute("UPDATE players SET wins = wins + 1, points = points + 10 WHERE user_id=?", (user_id,))
        else:
            cursor.execute("UPDATE players SET losses = losses + 1 WHERE user_id=?", (user_id,))

    conn.commit()

    cursor.execute("SELECT username, points FROM players WHERE user_id=?", (winner_id,))
    winner = cursor.fetchone()

    rank = get_rank(winner[1])

    await context.bot.send_message(
        chat_id,
        f"🏆 انتهت الجولة!\n"
        f"🎉 الفائز: {winner[0]}\n"
        f"⭐ نقاطه: {winner[1]}\n"
        f"🎖 رتبته: {rank}"
    )

    del game_data[chat_id]

# ================= STATS =================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("SELECT points, wins, losses, games FROM players WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if not data:
        await update.message.reply_text("❌ ما عندك سجل بعد.")
        return

    points, wins, losses, games_played = data
    rank = get_rank(points)

    await update.message.reply_text(
        f"📊 إحصائياتك:\n\n"
        f"🎮 لعبت: {games_played}\n"
        f"🏆 فوز: {wins}\n"
        f"❌ خسارة: {losses}\n"
        f"⭐ نقاط: {points}\n"
        f"🎖 رتبتك: {rank}"
    )

# ================= LEADERBOARD =================
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT username, points FROM players ORDER BY points DESC LIMIT 10")
    top = cursor.fetchall()

    if not top:
        await update.message.reply_text("❌ ماكو بيانات بعد.")
        return

    text = "🏆 أفضل 10 لاعبين:\n\n"
    for i, player in enumerate(top, start=1):
        text += f"{i}. {player[0]} - {player[1]} نقطة\n"

    await update.message.reply_text(text)

# ================= RUN BOT =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("startgame", startgame))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CallbackQueryHandler(join_button, pattern="join_game"))

print("Bot is running...")
app.run_polling()
