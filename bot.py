import random
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

TOKEN = "8764097317:AAH33c23-SIkuvLjyhVgbaopC2XQQuavTQQ"

# ================= DATABASE =================
conn = sqlite3.connect("game.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    points INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    games INTEGER DEFAULT 0
)
""")
conn.commit()

# ================= GAME MEMORY =================
game_data = {}

# ================= RANK SYSTEM =================
def get_rank(points):
    if points >= 100:
        return "👑 ملك البات"
    elif points >= 50:
        return "🥇 أسطورة"
    elif points >= 20:
        return "🥈 محترف"
    else:
        return "🥉 مبتدئ"

# ================= START GAME =================
async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    member = await context.bot.get_chat_member(chat.id, user.id)
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ فقط الأدمن يكدر يبدأ اللعبة.")
        return

    keyboard = [
        [InlineKeyboardButton("🎮 انضمام", callback_data="join_game")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        "🎮 بدأت لعبة البات!\n⏳ الوقت المتبقي: 30 ثانية\n👥 اللاعبين: 0",
        reply_markup=reply_markup
    )

    game_data[chat.id] = {
        "players": [],
        "message_id": msg.message_id,
        "countdown": 30
    }

    asyncio.create_task(countdown_timer(context, chat.id))

# ================= JOIN BUTTON =================
async def join_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id

    await query.answer()

    if chat_id not in game_data:
        return

    if user.id not in game_data[chat_id]["players"]:
        game_data[chat_id]["players"].append(user.id)

        cursor.execute("INSERT OR IGNORE INTO players (user_id, username) VALUES (?, ?)",
                       (user.id, user.first_name))
        conn.commit()

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game_data[chat_id]["message_id"],
            text=f"🎮 بدأت لعبة البات!\n⏳ الوقت المتبقي: {game_data[chat_id]['countdown']} ثانية\n👥 اللاعبين: {len(game_data[chat_id]['players'])}",
            reply_markup=query.message.reply_markup
        )

# ================= COUNTDOWN =================
async def countdown_timer(context, chat_id):
    while chat_id in game_data and game_data[chat_id]["countdown"] > 0:
        await asyncio.sleep(1)
        game_data[chat_id]["countdown"] -= 1

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
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
