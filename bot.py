"""
PaundsBot – ProBot tarzı özelliklere sahip tek dosyalık Discord botu
-------------------------------------------------------------------
Özellikler:
- Hoş geldin mesajı (embed) + otomatik rol verme
- Level/XP sistemi (SQLite ile kalıcı)
- !rank komutu (kullanıcının level ve XP’sini gösterir)
- Basit moderasyon: !kick, !ban, !timeout, !clear
- İşlem günlüğü (log kanalı)

Kurulum (Terminal):
1) Python 3.10+
2) pip install -U discord.py python-dotenv
3) .env dosyası oluştur ve içini doldur:
   DISCORD_TOKEN=bot_tokenin
   GUILD_ID=123456789012345678
   WELCOME_CHANNEL_ID=123456789012345678
   LOG_CHANNEL_ID=123456789012345678
   AUTOROLE_ID=123456789012345678
   COMMAND_PREFIX=!
4) python bot.py

Notlar:
- Discord Developer Portal > Bot > Privileged Gateway Intents: MESSAGE CONTENT ve SERVER MEMBERS açık olmalı.
- Roller/kanalların kimliklerini (ID) almak için Geliştirici Modu’nu aç ve sağ tıkla > Kimliği Kopyala.
"""

import os
import sqlite3
import random
import time
from datetime import timedelta
from typing import Optional

from dotenv import load_dotenv
import discord
from discord.ext import commands

# --------------------------------------------------
# Yüklemeler & Intents
# --------------------------------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
AUTOROLE_ID = int(os.getenv("AUTOROLE_ID", "0"))
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# --------------------------------------------------
# SQLite – Level Sistemi
# --------------------------------------------------
DB_PATH = "levels.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER,
        guild_id   INTEGER,
        xp         INTEGER DEFAULT 0,
        level      INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )
    """
)
conn.commit()

# mesaj başına XP cooldown (saniye)
XP_COOLDOWN = 60
last_xp_time = {}  # (guild_id, user_id) -> timestamp


def get_user(user_id: int, guild_id: int):
    cur.execute(
        "SELECT xp, level FROM users WHERE user_id=? AND guild_id=?",
        (user_id, guild_id),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT OR IGNORE INTO users(user_id, guild_id, xp, level) VALUES (?, ?, 0, 0)",
            (user_id, guild_id),
        )
        conn.commit()
        return 0, 0
    return row[0], row[1]


def set_user(user_id: int, guild_id: int, xp: int, level: int):
    cur.execute(
        "REPLACE INTO users(user_id, guild_id, xp, level) VALUES (?, ?, ?, ?)",
        (user_id, guild_id, xp, level),
    )
    conn.commit()


def xp_needed_for(level: int) -> int:
    # Basit formül: her seviye için 100 * (level + 1)
    return 100 * (level + 1)


async def add_xp(member: discord.Member, amount: int):
    xp, level = get_user(member.id, member.guild.id)
    xp += amount

    leveled_up = False
    while xp >= xp_needed_for(level):
        xp -= xp_needed_for(level)
        level += 1
        leveled_up = True

    set_user(member.id, member.guild.id, xp, level)

    if leveled_up:
        try:
            await member.send(f"🎉 Tebrikler {member.display_name}! Yeni seviyen: **{level}**")
        except discord.Forbidden:
            pass
        log_channel = member.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"🔼 {member.mention} seviye atladı: **{level}**")


# --------------------------------------------------
# Bot Eventleri
# --------------------------------------------------
@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı.")
    try:
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Paunds topluluğu"))
    except Exception:
        pass


@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != GUILD_ID and GUILD_ID != 0:
        return

    # Hoş geldin mesajı
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(title="Hoş Geldin!", description=f"{member.mention} sunucuya katıldı!", color=0x00FFAA)
        embed.add_field(name="Kurallar", value="Lütfen #kurallar kanalını okuyun.")
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    # Otomatik rol
    role = member.guild.get_role(AUTOROLE_ID)
    if role:
        try:
            await member.add_roles(role, reason="PaundsBot oto-rol")
        except discord.Forbidden:
            pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # XP verme – cooldown kontrolü
    key = (message.guild.id, message.author.id)
    now = time.time()
    if last_xp_time.get(key, 0) + XP_COOLDOWN <= now:
        last_xp_time[key] = now
        await add_xp(message.author, random.randint(10, 20))

    await bot.process_commands(message)


# --------------------------------------------------
# Komutlar
# --------------------------------------------------
@bot.command(name="rank")
async def rank(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    xp, level = get_user(member.id, member.guild.id)
    needed = xp_needed_for(level)
    embed = discord.Embed(title=f"{member.display_name} – Seviye Bilgisi", color=0x00FFAA)
    embed.add_field(name="Seviye", value=str(level))
    embed.add_field(name="XP", value=f"{xp} / {needed}")
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx: commands.Context, amount: int):
    if amount < 1:
        return await ctx.reply("1 veya daha büyük bir sayı gir.")
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 {len(deleted)-1} mesaj silindi.", delete_after=5)


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx: commands.Context, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} sunucudan atıldı. Sebep: {reason}")
        log = ctx.guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(f"👢 {member} kicklendi. Yetkili: {ctx.author} | Sebep: {reason}")
    except discord.Forbidden:
        await ctx.reply("Bu kullanıcıyı atmak için yetkim yetmiyor.")


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx: commands.Context, member: discord.Member, *, reason: str = "Sebep belirtilmedi"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.mention} banlandı. Sebep: {reason}")
        log = ctx.guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(f"🔨 {member} banlandı. Yetkili: {ctx.author} | Sebep: {reason}")
    except discord.Forbidden:
        await ctx.reply("Bu kullanıcıyı banlamak için yetkim yetmiyor.")


@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout(ctx: commands.Context, member: discord.Member, minutes: int, *, reason: str = "Sebep belirtilmedi"):
    try:
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(f"⏳ {member.mention} {minutes} dakika susturuldu. Sebep: {reason}")
        log = ctx.guild.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(f"⏳ {member} {minutes}dk timeout. Yetkili: {ctx.author} | Sebep: {reason}")
    except discord.Forbidden:
        await ctx.reply("Bu kullanıcıyı timeoutlamak için yetkim yetmiyor.")
    except Exception as e:
        await ctx.reply(f"Hata: {e}")


@bot.command(name="help_paunds")
async def help_paunds(ctx: commands.Context):
    embed = discord.Embed(title="PaundsBot Komutları", color=0x00FFAA, description=f"Önek (prefix): `{COMMAND_PREFIX}`")
    embed.add_field(name="Genel", value="rank – seviye bilgisini göster\nhelp_paunds – bu menü")
    embed.add_field(name="Moderasyon", value="clear <sayı>\nkick @üye [sebep]\nban @üye [sebep]\ntimeout @üye <dakika> [sebep]")
    embed.set_footer(text="Paunds tarafından")
    await ctx.reply(embed=embed, mention_author=False)


# --------------------------------------------------
# Çalıştır
# --------------------------------------------------
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN .env dosyasında bulunamadı.")
    bot.run(TOKEN)


// Sunucu oluşturma ve proje aktivitesi sağlama.
const express = require('express');
const app express();
const port 3000;
// Web sunucu
app.get('/', (req, res) => {
res.sendStatus(200);
});
app.listen(port, () => {
console.log('Sunucu $(port) numaralı bağlantı noktasında yürütülüyor.");
});
client.login(process.env.token)
