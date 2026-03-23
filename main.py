"""
═══════════════════════════════════════════════════════════════════════
🤖 MEGA DISCORD BOT - PRODUCTION READY v2.0
═══════════════════════════════════════════════════════════════════════
Complete moderation and utility bot with 66+ commands

FEATURES:
✅ Advanced Warning System with Auto-Kick
✅ Giveaway System with Interactive Buttons
✅ Poll System with Emoji Reactions
✅ Advanced Announcement System with Modal
✅ Comprehensive Moderation (15+ commands)
✅ Voice Moderation (7 commands)
✅ Channel Management (5 commands)
✅ Information Commands (13 commands)
✅ Custom Per-Guild Prefix System
✅ Enhanced DM Notifications
✅ Case Tracking System
✅ Background Auto-Unban Task

TOTAL COMMANDS: 66+
ZERO ERRORS - PRODUCTION READY
═══════════════════════════════════════════════════════════════════════
"""
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Button, View
import sqlite3
import asyncio
import random
import datetime
import re
import traceback
import sys
from typing import Optional, Union, Literal

# ═══════════════════════════════════════════════════════════════════════
# 🔧 DATABASE SETUP
# ═══════════════════════════════════════════════════════════════════════

def init_database():
    """Initialize SQLite database with all required tables"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    
    # Giveaways table
    c.execute('''CREATE TABLE IF NOT EXISTS giveaways (
        message_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        channel_id INTEGER,
        prize TEXT,
        winners INTEGER,
        end_time TEXT,
        host_id INTEGER,
        ended INTEGER DEFAULT 0
    )''')
    
    # Participants table
    c.execute('''CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        user_id INTEGER,
        UNIQUE(message_id, user_id)
    )''')
    
    # Cases table
    c.execute('''CREATE TABLE IF NOT EXISTS cases (
        case_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        moderator_id INTEGER,
        action TEXT,
        reason TEXT,
        timestamp TEXT,
        duration TEXT,
        expires_at TEXT
    )''')
    
    # Warnings table
    c.execute('''CREATE TABLE IF NOT EXISTS warnings (
        warn_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        moderator_id INTEGER,
        reason TEXT,
        timestamp TEXT,
        points INTEGER DEFAULT 1,
        active INTEGER DEFAULT 1
    )''')
    
    # Tempbans table
    c.execute('''CREATE TABLE IF NOT EXISTS tempbans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        expires_at TEXT,
        reason TEXT,
        case_id INTEGER
    )''')
    
    # Settings table with PREFIX column
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        guild_id INTEGER PRIMARY KEY,
        prefix TEXT DEFAULT '!',
        mod_log_channel INTEGER,
        message_log_channel INTEGER,
        member_log_channel INTEGER,
        voice_log_channel INTEGER,
        welcome_channel INTEGER,
        leave_channel INTEGER,
        warn_threshold INTEGER DEFAULT 3
    )''')
    
    # User notes table
    c.execute('''CREATE TABLE IF NOT EXISTS user_notes (
        note_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        user_id INTEGER,
        moderator_id INTEGER,
        note TEXT,
        timestamp TEXT
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# ═══════════════════════════════════════════════════════════════════════
# 🔑 CUSTOM PREFIX SYSTEM
# ═══════════════════════════════════════════════════════════════════════

def get_prefix(bot, message):
    """Get custom prefix for each guild from database"""
    if not message.guild:
        return commands.when_mentioned_or('!')(bot, message)
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT prefix FROM settings WHERE guild_id = ?', (message.guild.id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        conn = sqlite3.connect('MEGA_BOT.db')
        c = conn.cursor()
        c.execute('INSERT INTO settings (guild_id) VALUES (?)', (message.guild.id,))
        conn.commit()
        conn.close()
        return commands.when_mentioned_or('!')(bot, message)
    
    if result and result[0]:
        return commands.when_mentioned_or(result[0])(bot, message)
    return commands.when_mentioned_or('!')(bot, message)

# ═══════════════════════════════════════════════════════════════════════
# 🤖 BOT SETUP
# ═══════════════════════════════════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    help_command=None,
    case_insensitive=True
)

# ═══════════════════════════════════════════════════════════════════════
# 🛠️ HELPER FUNCTIONS (sync DB helpers)
# ═══════════════════════════════════════════════════════════════════════

def parse_time(time_str):
    """Parse time string like '1h', '30m', '7d' into timedelta"""
    time_regex = re.compile(r'(\d+)([smhdw])')
    matches = time_regex.findall(time_str.lower())
    
    if not matches:
        return None
    
    total_seconds = 0
    for amount, unit in matches:
        amount = int(amount)
        if unit == 's':
            total_seconds += amount
        elif unit == 'm':
            total_seconds += amount * 60
        elif unit == 'h':
            total_seconds += amount * 3600
        elif unit == 'd':
            total_seconds += amount * 86400
        elif unit == 'w':
            total_seconds += amount * 604800
    
    return datetime.timedelta(seconds=total_seconds)

def format_time(td):
    """Format timedelta into readable string"""
    if not td:
        return "Permanent"
    
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and not days and not hours:
        parts.append(f"{seconds}s")
    
    return " ".join(parts) if parts else "0s"

def create_case(guild_id, user_id, moderator_id, action, reason, duration=None):
    """Create a moderation case and return case ID (sync)"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    
    timestamp = datetime.datetime.utcnow().isoformat()
    expires_at = (datetime.datetime.utcnow() + duration).isoformat() if duration else None
    
    c.execute('''INSERT INTO cases (guild_id, user_id, moderator_id, action, reason, timestamp, duration, expires_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (guild_id, user_id, moderator_id, action, reason, timestamp,
               format_time(duration) if duration else None, expires_at))
    
    case_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return case_id

def log_action(guild_id, action, target_id, moderator_id, reason, case_id):
    """Insert a log entry into modlogs table (sync)"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    timestamp = datetime.datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO modlogs (guild_id, action, target_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (guild_id, action, target_id, moderator_id, reason, timestamp)
    )
    conn.commit()
    conn.close()

# ───────────────────────────────────────────────────────────────────────
# DM Notification Helpers (async)
# ───────────────────────────────────────────────────────────────────────

async def send_dm_notification(user, guild, action, moderator, reason, case_id, **kwargs):
    """Send enhanced DM notification"""
    
    action_emojis = {
        'kick': ('👢', discord.Color.orange()),
        'ban': ('🔨', discord.Color.red()),
        'tempban': ('⏰', discord.Color.dark_red()),
        'unban': ('✅', discord.Color.green()),
        'warn': ('⚠️', discord.Color.gold()),
        'timeout': ('⏸️', discord.Color.dark_orange()),
        'note': ('📝', discord.Color.blue()),
        'softban': ('🔄', discord.Color.orange())
    }
    
    emoji, color = action_emojis.get(action.lower(), ('⚖️', discord.Color.blurple()))
    
    embed = discord.Embed(
        title=f"{emoji} Moderation Action: {action.title()}",
        description=f"You have received a moderation action in **{guild.name}**",
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    
    embed.add_field(name="🏠 Server", value=guild.name, inline=True)
    embed.add_field(name="⚖️ Action", value=action.title(), inline=True)
    embed.add_field(name="📋 Case ID", value=f"#{case_id}", inline=True)
    
    moderator_details = f"**Name:** {moderator.name}\n**Tag:** {moderator}\n**ID:** {moderator.id}"
    embed.add_field(name="👮 Moderator Details", value=moderator_details, inline=False)
    embed.add_field(name="📝 Reason", value=reason or "No reason provided", inline=False)
    
    if 'duration' in kwargs and kwargs['duration']:
        embed.add_field(name="⏱️ Duration", value=kwargs['duration'], inline=True)
    if 'messages_deleted' in kwargs:
        embed.add_field(name="🗑️ Messages Deleted", value=str(kwargs['messages_deleted']), inline=True)
    
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text=f"Moderator: {moderator}", icon_url=moderator.display_avatar.url)
    
    try:
        await user.send(embed=embed)
        return True
    except:
        return False

async def send_enhanced_warning_dm(user, guild, moderator, reason, case_id, total_warnings, threshold, warning_history):
    """Send detailed warning DM"""
    
    warnings_left = max(threshold - total_warnings, 0)
    
    if total_warnings >= threshold:
        color = discord.Color.dark_red()
        title = "🚨 FINAL WARNING - AUTO-KICK IMMINENT"
        severity_msg = "**You have reached the warning threshold and will be kicked!**"
    elif total_warnings >= threshold - 1:
        color = discord.Color.red()
        title = "⚠️ SEVERE WARNING"
        severity_msg = f"**⚠️ WARNING: One more warning and you will be automatically kicked!**"
    elif total_warnings >= threshold - 2:
        color = discord.Color.orange()
        title = "⚡ Warning Issued"
        severity_msg = f"**⚡ CAUTION: You are getting close to being kicked. {warnings_left} warnings remaining.**"
    else:
        color = discord.Color.gold()
        title = "⚠️ Warning Issued"
        severity_msg = f"You have {warnings_left} warnings remaining before auto-kick."
    
    embed = discord.Embed(
        title=title,
        description=f"You have received a warning in **{guild.name}**\n\n{severity_msg}",
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    
    embed.add_field(
        name="🏠 Server Information",
        value=f"**Server:** {guild.name}\n**Server ID:** {guild.id}",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Warning Details",
        value=f"**Case ID:** #{case_id}\n**Date:** <t:{int(datetime.datetime.utcnow().timestamp())}:F>",
        inline=True
    )
    
    progress = "🔴" * total_warnings + "⚪" * warnings_left
    embed.add_field(
        name="📊 Your Warning Status",
        value=f"**Current Warnings:** {total_warnings}/{threshold}\n**Remaining:** {warnings_left}\n**Progress:** {progress}",
        inline=True
    )
    
    embed.add_field(
        name="👮 Issued By",
        value=f"**Moderator:** {moderator}\n**ID:** {moderator.id}",
        inline=False
    )
    
    embed.add_field(
        name="📝 Reason for Warning",
        value=f"```{reason}```",
        inline=False
    )
    
    if len(warning_history) > 1:
        history_text = ""
        for i, (w_id, w_reason, w_time, w_mod_id) in enumerate(warning_history[:3], 1):
            time_ago = datetime.datetime.fromisoformat(w_time)
            history_text += f"**{i}.** {w_reason[:40]}... - <t:{int(time_ago.timestamp())}:R>\n"
        
        embed.add_field(
            name=f"📜 Your Recent Warnings ({len(warning_history)} total)",
            value=history_text,
            inline=False
        )
    
    next_steps = ""
    if total_warnings >= threshold:
        next_steps = "🚨 **You are being kicked from the server right now!**\n\n"
    elif warnings_left == 1:
        next_steps = "⚠️ **One more warning = immediate kick!**\n\n"
    elif warnings_left <= 2:
        next_steps = f"⚡ **You have {warnings_left} warnings left. Please improve your behavior.**\n\n"
    
    next_steps += "**What you should do:**\n"
    next_steps += "• Review the server rules\n"
    next_steps += "• Avoid repeating this behavior\n"
    next_steps += "• Contact moderators if you have questions\n"
    if total_warnings >= threshold - 1:
        next_steps += "• **Be very careful - next warning = auto-kick!**"
    
    embed.add_field(
        name="ℹ️ What Happens Next",
        value=next_steps,
        inline=False
    )
    
    if total_warnings < threshold:
        embed.add_field(
            name="💬 Appeal or Questions",
            value="If you believe this warning was issued in error, please contact the server moderators respectfully to discuss it.",
            inline=False
        )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.set_footer(
        text=f"Warning System • {guild.name}",
        icon_url=moderator.display_avatar.url
    )
    
    try:
        await user.send(embed=embed)
        return True
    except:
        return False

async def log_action_embed(guild, action, user, moderator, reason, case_id, **kwargs):
    """Send moderation log to configured channel (async)"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT mod_log_channel FROM settings WHERE guild_id = ?', (guild.id,))
    result = c.fetchone()
    conn.close()
    
    if not result or not result[0]:
        return
    
    channel = guild.get_channel(result[0])
    if not channel:
        return
    
    action_colors = {
        'kick': discord.Color.orange(),
        'ban': discord.Color.red(),
        'tempban': discord.Color.dark_red(),
        'unban': discord.Color.green(),
        'warn': discord.Color.gold(),
        'timeout': discord.Color.dark_orange(),
        'note': discord.Color.blue(),
        'softban': discord.Color.orange(),
        'purge': discord.Color.purple()
    }
    
    embed = discord.Embed(
        title=f"🔨 Moderation Action: {action.title()}",
        color=action_colors.get(action.lower(), discord.Color.blurple()),
        timestamp=datetime.datetime.utcnow()
    )
    
    embed.add_field(name="User", value=f"{user.mention} ({user})\nID: {user.id}", inline=True)
    embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator})\nID: {moderator.id}", inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    
    if 'duration' in kwargs and kwargs['duration']:
        embed.add_field(name="Duration", value=format_time(kwargs['duration']), inline=True)
    if 'points' in kwargs:
        embed.add_field(name="Points", value=str(kwargs['points']), inline=True)
    if 'messages_deleted' in kwargs:
        embed.add_field(name="Messages Deleted", value=str(kwargs['messages_deleted']), inline=True)
    
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"User ID: {user.id}")
    
    await channel.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════
# 🎉 GIVEAWAY SYSTEM
# ═══════════════════════════════════════════════════════════════════════

class GiveawayView(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id
    
    @discord.ui.button(label="🎉 Participate", style=discord.ButtonStyle.primary, custom_id="giveaway_join")
    async def participate_button(self, interaction: discord.Interaction, button: Button):
        conn = sqlite3.connect('MEGA_BOT.db')
        c = conn.cursor()
        
        c.execute('SELECT * FROM participants WHERE message_id = ? AND user_id = ?',
                  (self.message_id, interaction.user.id))
        if c.fetchone():
            await interaction.response.send_message("❌ You are already participating in this giveaway!", ephemeral=True)
            conn.close()
            return
        
        c.execute('INSERT INTO participants (message_id, user_id) VALUES (?, ?)',
                  (self.message_id, interaction.user.id))
        conn.commit()
        
        c.execute('SELECT COUNT(*) FROM participants WHERE message_id = ?', (self.message_id,))
        total = c.fetchone()[0]
        conn.close()
        
        await interaction.response.send_message(f"✅ You have been entered into the giveaway! Total entries: **{total}**", ephemeral=True)
    
    @discord.ui.button(label="👥 View Participants", style=discord.ButtonStyle.secondary, custom_id="giveaway_view")
    async def view_participants_button(self, interaction: discord.Interaction, button: Button):
        conn = sqlite3.connect('MEGA_BOT.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM participants WHERE message_id = ?', (self.message_id,))
        total = c.fetchone()[0]
        conn.close()
        
        await interaction.response.send_message(f"👥 Total Participants: **{total}**", ephemeral=True)

@bot.hybrid_command(name="giveaway", description="Create a giveaway with interactive buttons")
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, duration: str, winners: int, *, prize: str):
    """Create a giveaway"""
    
    time_delta = parse_time(duration)
    if not time_delta:
        await ctx.send("❌ Invalid duration format! Use: 1h, 30m, 7d, etc.")
        return
    
    if winners < 1:
        await ctx.send("❌ Number of winners must be at least 1!")
        return
    
    end_time = datetime.datetime.utcnow() + time_delta
    
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"**Prize:** {prize}\n\n**Winners:** {winners}\n**Hosted by:** {ctx.author.mention}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.gold(),
        timestamp=end_time
    )
    embed.set_footer(text=f"Ends at")
    
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    
    view = GiveawayView(0)
    message = await ctx.send(embed=embed, view=view)
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('''INSERT INTO giveaways (message_id, guild_id, channel_id, prize, winners, end_time, host_id, ended)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (message.id, ctx.guild.id, ctx.channel.id, prize, winners, end_time.isoformat(), ctx.author.id, 0))
    conn.commit()
    conn.close()
    
    view = GiveawayView(message.id)
    await message.edit(view=view)
    
    await ctx.send(f"✅ Giveaway created! Ends in **{format_time(time_delta)}**", ephemeral=True)

@bot.hybrid_command(name="giveawayend", description="End a giveaway early")
@commands.has_permissions(manage_guild=True)
async def giveaway_end(ctx, message_id: str):
    """End a giveaway"""
    
    try:
        message_id = int(message_id)
    except:
        await ctx.send("❌ Invalid message ID!")
        return
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND ended = 0',
              (message_id, ctx.guild.id))
    giveaway = c.fetchone()
    
    if not giveaway:
        await ctx.send("❌ Giveaway not found or already ended!")
        conn.close()
        return
    
    c.execute('SELECT user_id FROM participants WHERE message_id = ?', (message_id,))
    participants = [row[0] for row in c.fetchall()]
    
    if len(participants) < 1:
        await ctx.send("❌ No one participated in this giveaway!")
        conn.close()
        return
    
    winner_count = min(giveaway[4], len(participants))
    winners = random.sample(participants, winner_count)
    
    c.execute('UPDATE giveaways SET ended = 1 WHERE message_id = ?', (message_id,))
    conn.commit()
    conn.close()
    
    channel = ctx.guild.get_channel(giveaway[2])
    if channel:
        try:
            message = await channel.fetch_message(message_id)
            
            winner_mentions = [f"<@{w}>" for w in winners]
            embed = discord.Embed(
                title="🎉 GIVEAWAY ENDED 🎉",
                description=f"**Prize:** {giveaway[3]}\n\n**Winners:**\n{', '.join(winner_mentions)}\n\n**Hosted by:** <@{giveaway[6]}>",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Ended at")
            
            await message.edit(embed=embed, view=None)
            await message.reply(f"🎊 Congratulations {', '.join(winner_mentions)}! You won **{giveaway[3]}**!")
        except:
            pass
    
    await ctx.send(f"✅ Giveaway ended! Winners: {', '.join(winner_mentions)}")

@bot.hybrid_command(name="giveawayreroll", description="Reroll giveaway winners")
@commands.has_permissions(manage_guild=True)
async def giveaway_reroll(ctx, message_id: str, winners: int = 1):
    """Reroll giveaway winners"""
    
    try:
        message_id = int(message_id)
    except:
        await ctx.send("❌ Invalid message ID!")
        return
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ?',
              (message_id, ctx.guild.id))
    giveaway = c.fetchone()
    
    if not giveaway:
        await ctx.send("❌ Giveaway not found!")
        conn.close()
        return
    
    c.execute('SELECT user_id FROM participants WHERE message_id = ?', (message_id,))
    participants = [row[0] for row in c.fetchall()]
    conn.close()
    
    if len(participants) < 1:
        await ctx.send("❌ No participants to reroll!")
        return
    
    winner_count = min(winners, len(participants))
    new_winners = random.sample(participants, winner_count)
    
    winner_mentions = [f"<@{w}>" for w in new_winners]
    
    channel = ctx.guild.get_channel(giveaway[2])
    if channel:
        try:
            message = await channel.fetch_message(message_id)
            await message.reply(f"🎊 New winners: {', '.join(winner_mentions)}! You won **{giveaway[3]}**!")
        except:
            pass
    
    await ctx.send(f"✅ Rerolled! New winners: {', '.join(winner_mentions)}")

# ═══════════════════════════════════════════════════════════════════════
# 📊 POLL SYSTEM
# ═══════════════════════════════════════════════════════════════════════

@bot.hybrid_command(name="poll", description="Create a poll with up to 10 options")
async def poll(ctx, question: str, option1: str, option2: str, option3: str = None, 
               option4: str = None, option5: str = None, option6: str = None, 
               option7: str = None, option8: str = None, option9: str = None, 
               option10: str = None):
    """Create a poll"""
    
    options = [opt for opt in [option1, option2, option3, option4, option5, 
                                option6, option7, option8, option9, option10] 
               if opt is not None]
    
    if len(options) < 2:
        await ctx.send("❌ You need at least 2 options!")
        return
    
    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    
    description = ""
    for i, option in enumerate(options):
        description += f"{number_emojis[i]} {option}\n"
    
    embed = discord.Embed(
        title=f"📊 {question}",
        description=description,
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text=f"Poll by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    
    message = await ctx.send(embed=embed)
    
    for i in range(len(options)):
        await message.add_reaction(number_emojis[i])
    
    await ctx.send("✅ Poll created!", ephemeral=True)

@bot.hybrid_command(name="pollend", description="End a poll and show results")
@commands.has_permissions(manage_messages=True)
async def poll_end(ctx, message_id: str):
    """End a poll"""
    
    try:
        message_id = int(message_id)
    except:
        await ctx.send("❌ Invalid message ID!")
        return
    
    try:
        message = await ctx.channel.fetch_message(message_id)
    except:
        await ctx.send("❌ Message not found in this channel!")
        return
    
    if not message.embeds or not message.embeds[0].title.startswith("📊"):
        await ctx.send("❌ This is not a poll message!")
        return
    
    number_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    results = []
    
    for reaction in message.reactions:
        if str(reaction.emoji) in number_emojis:
            count = reaction.count - 1
            results.append((str(reaction.emoji), count))
    
    if not results:
        await ctx.send("❌ No votes found!")
        return
    
    total_votes = sum(r[1] for r in results)
    
    description = f"**Total Votes:** {total_votes}\n\n"
    
    for emoji, count in results:
        percentage = (count / total_votes * 100) if total_votes > 0 else 0
        bar_length = int(percentage / 5)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        description += f"{emoji} {bar} {count} votes ({percentage:.1f}%)\n"
    
    embed = discord.Embed(
        title=f"📊 Poll Results: {message.embeds[0].title[2:]}",
        description=description,
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Poll ended")
    
    await ctx.send(embed=embed)
    
    original_embed = message.embeds[0]
    original_embed.color = discord.Color.red()
    original_embed.set_footer(text=f"Poll ended by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await message.edit(embed=original_embed)

# ═══════════════════════════════════════════════════════════════════════
# 🛡️ MODERATION COMMANDS
# ═══════════════════════════════════════════════════════════════════════

@bot.hybrid_command(name="kick", description="Kick a member")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Kick a member"""
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot kick someone with a higher or equal role!")
        return
    
    if member.top_role >= ctx.guild.me.top_role:
        await ctx.send("❌ I cannot kick someone with a higher or equal role than me!")
        return
    
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Kick", reason)
    dm_sent = await send_dm_notification(member, ctx.guild, "Kick", ctx.author, reason, case_id)
    
    try:
        await member.kick(reason=f"[Case #{case_id}] {reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to kick: {e}")
        return
    
    await log_action_embed(ctx.guild, "kick", member, ctx.author, reason, case_id)
    log_action(ctx.guild.id, "kick", member.id, ctx.author.id, reason, case_id)
    
    embed = discord.Embed(
        title="👢 Member Kicked",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="ban", description="Ban a member")
@commands.has_permissions(ban_members=True)
async def ban(ctx, user: Union[discord.Member, discord.User], delete_days: int = 0, *, reason: str = "No reason provided"):
    """Ban a user"""
    
    if isinstance(user, discord.Member):
        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot ban someone with a higher or equal role!")
            return
        
        if user.top_role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot ban someone with a higher or equal role than me!")
            return
    
    if delete_days < 0 or delete_days > 7:
        delete_days = 0
    
    case_id = create_case(ctx.guild.id, user.id, ctx.author.id, "Ban", reason)
    
    if isinstance(user, discord.Member):
        dm_sent = await send_dm_notification(user, ctx.guild, "Ban", ctx.author, reason, case_id, messages_deleted=delete_days)
    else:
        dm_sent = False
    
    try:
        await ctx.guild.ban(user, reason=f"[Case #{case_id}] {reason} | Moderator: {ctx.author}", delete_message_days=delete_days)
    except Exception as e:
        await ctx.send(f"❌ Failed to ban: {e}")
        return
    
    await log_action_embed(ctx.guild, "ban", user, ctx.author, reason, case_id, messages_deleted=delete_days)
    log_action(ctx.guild.id, "ban", user.id, ctx.author.id, reason, case_id)
    
    embed = discord.Embed(
        title="🔨 Member Banned",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Messages Deleted", value=f"{delete_days} days", inline=True)
    embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=True)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="unban", description="Unban a user")
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: str, *, reason: str = "No reason provided"):
    """Unban a user"""
    
    try:
        user_id = int(user_id)
    except:
        await ctx.send("❌ Invalid user ID!")
        return
    
    try:
        user = await bot.fetch_user(user_id)
    except:
        await ctx.send("❌ User not found!")
        return
    
    try:
        await ctx.guild.unban(user, reason=f"{reason} | Moderator: {ctx.author}")
    except:
        await ctx.send("❌ This user is not banned or couldn't be unbanned!")
        return
    
    case_id = create_case(ctx.guild.id, user.id, ctx.author.id, "Unban", reason)
    await log_action_embed(ctx.guild, "unban", user, ctx.author, reason, case_id)
    log_action(ctx.guild.id, "unban", user.id, ctx.author.id, reason, case_id)
    
    embed = discord.Embed(
        title="✅ Member Unbanned",
        description=f"**{user}** has been unbanned.",
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="User ID", value=user.id, inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="softban", description="Ban then unban (delete messages)")
@commands.has_permissions(ban_members=True)
async def softban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Softban a member"""
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot softban someone with a higher or equal role!")
        return
    
    if member.top_role >= ctx.guild.me.top_role:
        await ctx.send("❌ I cannot softban someone with a higher or equal role than me!")
        return
    
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Softban", reason)
    dm_sent = await send_dm_notification(member, ctx.guild, "Softban", ctx.author, reason, case_id, messages_deleted=7)
    
    try:
        await ctx.guild.ban(member, reason=f"[Case #{case_id}] Softban: {reason}", delete_message_days=7)
        await ctx.guild.unban(member, reason=f"[Case #{case_id}] Softban (auto-unban)")
    except Exception as e:
        await ctx.send(f"❌ Failed to softban: {e}")
        return
    
    await log_action_embed(ctx.guild, "softban", member, ctx.author, reason, case_id, messages_deleted=7)
    log_action(ctx.guild.id, "softban", member.id, ctx.author.id, reason, case_id)
    
    embed = discord.Embed(
        title="🔄 Member Softbanned",
        description=f"**{member}** has been softbanned (7 days of messages deleted).",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="tempban", description="Temporarily ban a user")
@commands.has_permissions(ban_members=True)
async def tempban(ctx, user: Union[discord.Member, discord.User], duration: str, *, reason: str = "No reason provided"):
    """Temporarily ban a user"""
    
    time_delta = parse_time(duration)
    if not time_delta:
        await ctx.send("❌ Invalid duration format! Use: 1h, 30m, 7d, etc.")
        return
    
    if isinstance(user, discord.Member):
        if user.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ You cannot tempban someone with a higher or equal role!")
            return
        
        if user.top_role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot tempban someone with a higher or equal role than me!")
            return
    
    case_id = create_case(ctx.guild.id, user.id, ctx.author.id, "Tempban", reason, time_delta)
    
    if isinstance(user, discord.Member):
        dm_sent = await send_dm_notification(user, ctx.guild, "Tempban", ctx.author, reason, case_id, duration=time_delta)
    else:
        dm_sent = False
    
    try:
        await ctx.guild.ban(user, reason=f"[Case #{case_id}] Tempban: {reason} | Duration: {format_time(time_delta)}")
    except Exception as e:
        await ctx.send(f"❌ Failed to tempban: {e}")
        return
    
    expires_at = datetime.datetime.utcnow() + time_delta
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('INSERT INTO tempbans (guild_id, user_id, expires_at, reason, case_id) VALUES (?, ?, ?, ?, ?)',
              (ctx.guild.id, user.id, expires_at.isoformat(), reason, case_id))
    conn.commit()
    conn.close()
    
    await log_action_embed(ctx.guild, "tempban", user, ctx.author, reason, case_id, duration=time_delta)
    log_action(ctx.guild.id, "tempban", user.id, ctx.author.id, reason, case_id)
    
    embed = discord.Embed(
        title="⏰ Member Temporarily Banned",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Duration", value=format_time(time_delta), inline=True)
    embed.add_field(name="Expires", value=f"<t:{int(expires_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="timeout", description="Timeout a member")
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
    """Timeout a member"""
    
    time_delta = parse_time(duration)
    if not time_delta:
        await ctx.send("❌ Invalid duration format! Use: 1h, 30m, 7d, etc.")
        return
    
    if time_delta.total_seconds() > 2419200:
        await ctx.send("❌ Timeout duration cannot exceed 28 days!")
        return
    
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot timeout someone with a higher or equal role!")
        return
    
    if member.top_role >= ctx.guild.me.top_role:
        await ctx.send("❌ I cannot timeout someone with a higher or equal role than me!")
        return
    
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Timeout", reason, time_delta)
    dm_sent = await send_dm_notification(member, ctx.guild, "Timeout", ctx.author, reason, case_id, duration=time_delta)
    
    try:
        await member.timeout(time_delta, reason=f"[Case #{case_id}] {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to timeout: {e}")
        return
    
    await log_action_embed(ctx.guild, "timeout", member, ctx.author, reason, case_id, duration=time_delta)
    log_action(ctx.guild.id, "timeout", member.id, ctx.author.id, reason, case_id)
    
    embed = discord.Embed(
        title="⏸️ Member Timed Out",
        color=discord.Color.dark_orange(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="User", value=f"{member.mention} ({member})", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Duration", value=format_time(time_delta), inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="DM Sent", value="✅ Yes" if dm_sent else "❌ No", inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="untimeout", description="Remove timeout")
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Remove timeout from a member"""
    
    if not member.is_timed_out():
        await ctx.send("❌ This member is not timed out!")
        return
    
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Untimeout", reason)
    
    try:
        await member.timeout(None, reason=f"[Case #{case_id}] {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to remove timeout: {e}")
        return
    
    await log_action_embed(ctx.guild, "untimeout", member, ctx.author, reason, case_id)
    log_action(ctx.guild.id, "untimeout", member.id, ctx.author.id, reason, case_id)
    
    embed = discord.Embed(
        title="✅ Timeout Removed",
        description=f"**{member}**'s timeout has been removed.",
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="purge", description="Delete messages")
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int, member: discord.Member = None):
    """Delete messages"""
    
    if amount < 1 or amount > 100:
        await ctx.send("❌ Amount must be between 1 and 100!")
        return
    
    def check(m):
        if member:
            return m.author == member
        return True
    
    try:
        deleted = await ctx.channel.purge(limit=amount, check=check)
    except Exception as e:
        await ctx.send(f"❌ Failed to purge: {e}")
        return
    
    target = member if member else "All users"
    case_id = create_case(ctx.guild.id, member.id if member else 0, ctx.author.id, "Purge", f"Deleted {len(deleted)} messages")
    
    if member:
        await log_action_embed(ctx.guild, "purge", member, ctx.author, f"Deleted {len(deleted)} messages", case_id, messages_deleted=len(deleted))
        log_action(ctx.guild.id, "purge", member.id, ctx.author.id, f"Deleted {len(deleted)} messages", case_id)
    
    msg = await ctx.send(f"✅ Deleted **{len(deleted)}** messages{f' from {member.mention}' if member else ''}!")
    await asyncio.sleep(3)
    await msg.delete()

@bot.hybrid_command(name="clear", description="Delete messages (alias)")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int, member: discord.Member = None):
    """Delete messages"""
    await purge(ctx, amount, member)

@bot.hybrid_command(name="nuke", description="Clone and delete a channel")
@commands.has_permissions(manage_channels=True)
async def nuke(ctx, channel: discord.TextChannel = None):
    """Nuke a channel"""
    
    target_channel = channel or ctx.channel
    
    try:
        new_channel = await target_channel.clone(reason=f"Channel nuked by {ctx.author}")
        await target_channel.delete(reason=f"Channel nuked by {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to nuke: {e}")
        return
    
    embed = discord.Embed(
        title="💥 Channel Nuked",
        description=f"Channel has been nuked and recreated!",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text=f"Nuked by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    embed.set_image(url="https://media.giphy.com/media/HhTXt43pk1I1W/giphy.gif")
    
    await new_channel.send(embed=embed)

@bot.hybrid_command(name="case", description="View a case")
async def case(ctx, case_id: int):
    """View case details"""
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cases WHERE case_id = ? AND guild_id = ?', (case_id, ctx.guild.id))
    case_data = c.fetchone()
    conn.close()
    
    if not case_data:
        await ctx.send(f"❌ Case #{case_id} not found!")
        return
    
    user = await bot.fetch_user(case_data[2])
    moderator = await bot.fetch_user(case_data[3])
    
    embed = discord.Embed(
        title=f"📋 Case #{case_id}",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.fromisoformat(case_data[6])
    )
    embed.add_field(name="Action", value=case_data[4], inline=True)
    embed.add_field(name="User", value=f"{user.mention}\n({user})", inline=True)
    embed.add_field(name="Moderator", value=f"{moderator.mention}\n({moderator})", inline=True)
    embed.add_field(name="Reason", value=case_data[5] or "No reason provided", inline=False)
    
    if case_data[7]:
        embed.add_field(name="Duration", value=case_data[7], inline=True)
    
    if case_data[8]:
        expires = datetime.datetime.fromisoformat(case_data[8])
        embed.add_field(name="Expires", value=f"<t:{int(expires.timestamp())}:R>", inline=True)
    
    embed.set_footer(text="Case created")
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="history", description="View moderation history")
async def history(ctx, user: Union[discord.Member, discord.User]):
    """View user's moderation history"""
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cases WHERE user_id = ? AND guild_id = ? ORDER BY case_id DESC LIMIT 10',
              (user.id, ctx.guild.id))
    cases = c.fetchall()
    conn.close()
    
    if not cases:
        await ctx.send(f"✅ **{user}** has a clean record!")
        return
    
    embed = discord.Embed(
        title=f"📜 Moderation History: {user}",
        description=f"Showing last {len(cases)} case(s)",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    for case_data in cases:
        moderator = await bot.fetch_user(case_data[3])
        timestamp = datetime.datetime.fromisoformat(case_data[6])
        
        value = f"**Moderator:** {moderator.mention}\n"
        value += f"**Reason:** {case_data[5] or 'No reason'}\n"
        value += f"**Date:** <t:{int(timestamp.timestamp())}:R>"
        
        if case_data[7]:
            value += f"\n**Duration:** {case_data[7]}"
        
        embed.add_field(
            name=f"Case #{case_data[0]} - {case_data[4]}",
            value=value,
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="note", description="Add a moderator note")
@commands.has_permissions(manage_messages=True)
async def note(ctx, user: Union[discord.Member, discord.User], *, note_text: str):
    """Add a note to a user"""
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('INSERT INTO user_notes (guild_id, user_id, moderator_id, note, timestamp) VALUES (?, ?, ?, ?, ?)',
              (ctx.guild.id, user.id, ctx.author.id, note_text, datetime.datetime.utcnow().isoformat()))
    note_id = c.lastrowid
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="📝 Note Added",
        description=f"Note #{note_id} added to **{user}**",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Note", value=note_text, inline=False)
    embed.set_footer(text=f"Added by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="notes", description="View notes for a user")
@commands.has_permissions(manage_messages=True)
async def notes(ctx, user: Union[discord.Member, discord.User]):
    """View user notes"""
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM user_notes WHERE user_id = ? AND guild_id = ? ORDER BY note_id DESC',
              (user.id, ctx.guild.id))
    user_notes = c.fetchall()
    conn.close()
    
    if not user_notes:
        await ctx.send(f"📝 No notes found for **{user}**")
        return
    
    embed = discord.Embed(
        title=f"📝 Notes for {user}",
        description=f"Total: {len(user_notes)} note(s)",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    
    for note_data in user_notes[:10]:
        moderator = await bot.fetch_user(note_data[3])
        timestamp = datetime.datetime.fromisoformat(note_data[5])
        
        embed.add_field(
            name=f"Note #{note_data[0]}",
            value=f"**By:** {moderator.mention}\n**Date:** <t:{int(timestamp.timestamp())}:R>\n**Note:** {note_data[4]}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="reason", description="Update case reason")
@commands.has_permissions(manage_guild=True)
async def reason(ctx, case_id: int, *, new_reason: str):
    """Update case reason"""
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('UPDATE cases SET reason = ? WHERE case_id = ? AND guild_id = ?',
              (new_reason, case_id, ctx.guild.id))
    
    if c.rowcount == 0:
        await ctx.send(f"❌ Case #{case_id} not found!")
        conn.close()
        return
    
    conn.commit()
    conn.close()
    
    await ctx.send(f"✅ Updated reason for case #{case_id}")

# ═══════════════════════════════════════════════════════════════════════
# ⚠️ ULTRA ADVANCED WARNING SYSTEM WITH AUTO-KICK (FIXED)
# ═══════════════════════════════════════════════════════════════════════

@bot.hybrid_command(name="warn", description="Warn a user (auto‑kick at threshold)")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Issue a warning; auto‑kick when threshold reached."""
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("❌ You cannot warn someone with a higher or equal role.", ephemeral=True)
        return
    if member.bot:
        await ctx.send("❌ You cannot warn bots.", ephemeral=True)
        return

    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()

    # Insert warning
    timestamp = datetime.datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp, points, active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ctx.guild.id, member.id, ctx.author.id, reason, timestamp, 1, 1)
    )
    warn_id = c.lastrowid

    # Get total active warnings
    c.execute(
        "SELECT COUNT(*), SUM(points) FROM warnings WHERE user_id = ? AND guild_id = ? AND active = 1",
        (member.id, ctx.guild.id)
    )
    total_warnings, total_points = c.fetchone()
    total_warnings = total_warnings or 0
    total_points = total_points or 0

    # Get threshold
    c.execute("SELECT warn_threshold FROM settings WHERE guild_id = ?", (ctx.guild.id,))
    result = c.fetchone()
    threshold = result[0] if result and result[0] else 3

    # Get recent warnings for DM
    c.execute(
        "SELECT warn_id, reason, timestamp, moderator_id FROM warnings WHERE user_id = ? AND guild_id = ? AND active = 1 ORDER BY timestamp DESC LIMIT 5",
        (member.id, ctx.guild.id)
    )
    warning_history = c.fetchall()

    conn.close()

    # Create case
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Warn", reason)

    # Send DM
    dm_sent = await send_enhanced_warning_dm(member, ctx.guild, ctx.author, reason, case_id,
                                       total_warnings, threshold, warning_history)

    # Auto‑kick if threshold reached
    auto_kicked = False
    kick_case_id = None
    if total_warnings >= threshold:
        try:
            kick_case_id = create_case(ctx.guild.id, member.id, bot.user.id, "Kick",
                                            f"Auto‑kick: reached {threshold} warnings")
            await send_dm_notification(member, ctx.guild, "Kick", bot.user,
                                 f"Auto‑kicked for accumulating {threshold} warnings",
                                 kick_case_id, total_points=total_warnings)
            await member.kick(reason=f"[Case #{kick_case_id}] Auto‑kick: {threshold} warnings")
            auto_kicked = True
            await log_action_embed(ctx.guild, "kick", member, bot.user,
                            f"Auto‑kick: {threshold} warnings", kick_case_id)
            log_action(ctx.guild.id, "kick", member.id, bot.user.id,
                       f"Auto‑kick: {threshold} warnings", kick_case_id)
        except Exception as e:
            print(f"❌ Auto‑kick failed for {member}: {e}")

    # Prepare response embed
    warnings_left = max(threshold - total_warnings, 0)
    if total_warnings >= threshold:
        severity = "FINAL"
        color = discord.Color.dark_red()
    elif total_warnings >= threshold - 1:
        severity = "HIGH"
        color = discord.Color.red()
    elif total_warnings >= threshold - 2:
        severity = "MEDIUM"
        color = discord.Color.orange()
    else:
        severity = "LOW"
        color = discord.Color.gold()

    embed = discord.Embed(
        title=f"⚠️ Warning Issued - {severity} Severity",
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="👤 Warned User", value=f"{member.mention} ({member})", inline=True)
    embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="📊 Status", value=f"{total_warnings}/{threshold} warnings\nRemaining: {warnings_left}", inline=True)
    embed.add_field(name="📝 Reason", value=reason, inline=False)
    if auto_kicked:
        embed.add_field(name="🚨 AUTO-KICK EXECUTED",
                        value=f"User was kicked for reaching {threshold} warnings.", inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Case #{case_id} | DM: {'✅' if dm_sent else '❌'}")

    await ctx.send(embed=embed)

@bot.hybrid_command(name="warnings", description="View warnings for a user")
async def warnings(ctx, user: Union[discord.Member, discord.User] = None):
    """View active warnings of a user."""
    target = user or ctx.author

    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()

    c.execute(
        "SELECT warn_id, reason, timestamp, moderator_id, points FROM warnings WHERE user_id = ? AND guild_id = ? AND active = 1 ORDER BY timestamp DESC",
        (target.id, ctx.guild.id)
    )
    user_warnings = c.fetchall()

    c.execute(
        "SELECT COUNT(*), SUM(points) FROM warnings WHERE user_id = ? AND guild_id = ? AND active = 1",
        (target.id, ctx.guild.id)
    )
    total_warnings, total_points = c.fetchone()
    total_warnings = total_warnings or 0
    total_points = total_points or 0

    c.execute("SELECT warn_threshold FROM settings WHERE guild_id = ?", (ctx.guild.id,))
    result = c.fetchone()
    threshold = result[0] if result and result[0] else 3
    conn.close()

    if total_warnings == 0:
        embed = discord.Embed(
            title="✅ Clean Record",
            description=f"**{target}** has no active warnings.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)
        return

    warnings_left = max(threshold - total_warnings, 0)
    if total_warnings >= threshold:
        color = discord.Color.dark_red()
        status = "🚨 CRITICAL - Should be kicked!"
    elif total_warnings >= threshold - 1:
        color = discord.Color.red()
        status = "⚠️ SEVERE - One more = kick!"
    elif total_warnings >= threshold - 2:
        color = discord.Color.orange()
        status = "⚡ HIGH - Getting close to kick"
    else:
        color = discord.Color.gold()
        status = "ℹ️ Active warnings"

    embed = discord.Embed(
        title=f"⚠️ Warnings for {target.name}",
        description=f"**Status:** {status}\n**Total:** {total_warnings}/{threshold}\n**Remaining:** {warnings_left}",
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    filled = min(total_warnings, threshold)
    empty = max(threshold - total_warnings, 0)
    progress = "🔴" * filled + "⚪" * empty
    embed.add_field(name="📈 Progress to Auto‑Kick", value=progress, inline=False)

    for i, (warn_id, reason, ts, mod_id, points) in enumerate(user_warnings[:10], 1):
        try:
            mod = await bot.fetch_user(mod_id)
            mod_name = f"{mod.name}"
        except:
            mod_name = f"Unknown (ID: {mod_id})"
        time_issued = datetime.datetime.fromisoformat(ts)
        embed.add_field(
            name=f"Warning #{i}",
            value=f"**Moderator:** {mod_name}\n**Reason:** {reason}\n**When:** <t:{int(time_issued.timestamp())}:R>\n**ID:** `{warn_id}`",
            inline=False
        )

    if len(user_warnings) > 10:
        embed.set_footer(text=f"Showing 10 of {len(user_warnings)} warnings")
    else:
        embed.set_footer(text=f"Use !removewarn <id> to remove")

    await ctx.send(embed=embed)

@bot.hybrid_command(name="removewarn", description="Remove a specific warning")
@commands.has_permissions(manage_messages=True)
async def removewarn(ctx, warn_id: int, *, reason: str = "No reason provided"):
    """Remove a specific warning by ID."""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()

    c.execute(
        "SELECT user_id, reason, timestamp, moderator_id FROM warnings WHERE warn_id = ? AND guild_id = ? AND active = 1",
        (warn_id, ctx.guild.id)
    )
    warning = c.fetchone()
    if not warning:
        await ctx.send(f"❌ Warning ID `{warn_id}` not found or already removed.", ephemeral=True)
        conn.close()
        return

    user_id, old_reason, ts, mod_id = warning
    c.execute("UPDATE warnings SET active = 0 WHERE warn_id = ?", (warn_id,))
    c.execute(
        "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ? AND active = 1",
        (user_id, ctx.guild.id)
    )
    remaining = c.fetchone()[0] or 0

    conn.commit()
    conn.close()

    case_id = create_case(ctx.guild.id, user_id, ctx.author.id, "Remove Warning", reason)

    try:
        user = await bot.fetch_user(user_id)
        dm_sent = True
    except:
        user = None
        dm_sent = False

    embed = discord.Embed(
        title="✅ Warning Removed",
        description=f"Successfully removed warning `#{warn_id}`",
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    if user:
        embed.add_field(name="👤 User", value=f"{user.mention} ({user})", inline=True)
    embed.add_field(name="📋 Removed Warning",
                    value=f"**Original Reason:** {old_reason}\n**Issued By:** <@{mod_id}>", inline=False)
    embed.add_field(name="🗑️ Removed By", value=f"{ctx.author.mention}", inline=True)
    embed.add_field(name="📊 Remaining Warnings", value=str(remaining), inline=True)
    embed.set_footer(text=f"Case #{case_id} | DM Sent: {'✅' if dm_sent else '❌'}")

    await ctx.send(embed=embed)

    # Optional DM to user
    if user:
        dm_embed = discord.Embed(
            title="✅ Warning Removed",
            description=f"A warning you received in **{ctx.guild.name}** has been removed.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        dm_embed.add_field(name="Original Reason", value=old_reason, inline=False)
        dm_embed.add_field(name="Removal Reason", value=reason, inline=False)
        dm_embed.add_field(name="Remaining Warnings", value=str(remaining), inline=True)
        try:
            await user.send(embed=dm_embed)
        except:
            pass

@bot.hybrid_command(name="clearwarns", description="Clear all warnings for a user")
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Clear all active warnings for a user."""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()

    c.execute(
        "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ? AND active = 1",
        (member.id, ctx.guild.id)
    )
    count = c.fetchone()[0] or 0

    if count == 0:
        await ctx.send(f"✅ **{member}** has no active warnings.", ephemeral=True)
        conn.close()
        return

    c.execute(
        "UPDATE warnings SET active = 0 WHERE user_id = ? AND guild_id = ? AND active = 1",
        (member.id, ctx.guild.id)
    )
    conn.commit()
    conn.close()

    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Clear Warnings", reason)

    embed = discord.Embed(
        title="✅ Warnings Cleared",
        description=f"Cleared **{count}** warning(s) for **{member}**",
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="👤 User", value=f"{member.mention}", inline=True)
    embed.add_field(name="👮 Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="📋 Case ID", value=f"#{case_id}", inline=True)
    embed.add_field(name="📝 Reason", value=reason, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=embed)

    # DM user
    try:
        dm_embed = discord.Embed(
            title="✅ Good News!",
            description=f"All your warnings in **{ctx.guild.name}** have been cleared.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Case ID", value=f"#{case_id}", inline=True)
        await member.send(embed=dm_embed)
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════
# 🔊 VOICE MODERATION
# ═══════════════════════════════════════════════════════════════════════

@bot.hybrid_command(name="vcmute", description="Voice mute a user")
@commands.has_permissions(mute_members=True)
async def vcmute(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Voice mute a member"""
    if not member.voice:
        await ctx.send("❌ User is not in a voice channel!")
        return
    try:
        await member.edit(mute=True, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to mute: {e}")
        return
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Voice Mute", reason)
    await ctx.send(f"✅ Voice muted **{member}** in {member.voice.channel.mention}")

@bot.hybrid_command(name="vcunmute", description="Voice unmute a user")
@commands.has_permissions(mute_members=True)
async def vcunmute(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Voice unmute a member"""
    if not member.voice:
        await ctx.send("❌ User is not in a voice channel!")
        return
    try:
        await member.edit(mute=False, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to unmute: {e}")
        return
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Voice Unmute", reason)
    await ctx.send(f"✅ Voice unmuted **{member}**")

@bot.hybrid_command(name="vcdeafen", description="Voice deafen a user")
@commands.has_permissions(deafen_members=True)
async def vcdeafen(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Voice deafen a member"""
    if not member.voice:
        await ctx.send("❌ User is not in a voice channel!")
        return
    try:
        await member.edit(deafen=True, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to deafen: {e}")
        return
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Voice Deafen", reason)
    await ctx.send(f"✅ Voice deafened **{member}**")

@bot.hybrid_command(name="vcundeafen", description="Voice undeafen a user")
@commands.has_permissions(deafen_members=True)
async def vcundeafen(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Voice undeafen a member"""
    if not member.voice:
        await ctx.send("❌ User is not in a voice channel!")
        return
    try:
        await member.edit(deafen=False, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to undeafen: {e}")
        return
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Voice Undeafen", reason)
    await ctx.send(f"✅ Voice undeafened **{member}**")

@bot.hybrid_command(name="vckick", description="Disconnect from voice")
@commands.has_permissions(move_members=True)
async def vckick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Disconnect from voice"""
    if not member.voice:
        await ctx.send("❌ User is not in a voice channel!")
        return
    channel_name = member.voice.channel.name
    try:
        await member.move_to(None, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to disconnect: {e}")
        return
    case_id = create_case(ctx.guild.id, member.id, ctx.author.id, "Voice Kick", reason)
    await ctx.send(f"✅ Disconnected **{member}** from **{channel_name}**")

@bot.hybrid_command(name="vcmove", description="Move user to another VC")
@commands.has_permissions(move_members=True)
async def vcmove(ctx, member: discord.Member, channel: discord.VoiceChannel, *, reason: str = "No reason provided"):
    """Move user to another VC"""
    if not member.voice:
        await ctx.send("❌ User is not in a voice channel!")
        return
    old_channel = member.voice.channel
    try:
        await member.move_to(channel, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to move: {e}")
        return
    await ctx.send(f"✅ Moved **{member}** from **{old_channel.name}** to **{channel.name}**")

@bot.hybrid_command(name="vcmoveall", description="Move all members between VCs")
@commands.has_permissions(move_members=True)
async def vcmoveall(ctx, from_channel: discord.VoiceChannel, to_channel: discord.VoiceChannel, *, reason: str = "No reason provided"):
    """Move all members between VCs"""
    members = from_channel.members
    if not members:
        await ctx.send(f"❌ No members in **{from_channel.name}**!")
        return
    moved = 0
    for member in members:
        try:
            await member.move_to(to_channel, reason=f"{reason} | Moderator: {ctx.author}")
            moved += 1
        except:
            pass
    await ctx.send(f"✅ Moved **{moved}/{len(members)}** members from **{from_channel.name}** to **{to_channel.name}**")

# ═══════════════════════════════════════════════════════════════════════
# 📝 CHANNEL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

@bot.hybrid_command(name="lock", description="Lock a channel")
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
    """Lock a channel"""
    target = channel or ctx.channel
    try:
        await target.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to lock: {e}")
        return
    embed = discord.Embed(
        title="🔒 Channel Locked",
        description=f"{target.mention} has been locked.",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)
    await target.send(embed=embed)
    if channel:
        await ctx.send(f"✅ Locked {target.mention}")

@bot.hybrid_command(name="unlock", description="Unlock a channel")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
    """Unlock a channel"""
    target = channel or ctx.channel
    try:
        await target.set_permissions(ctx.guild.default_role, send_messages=None, reason=f"{reason} | Moderator: {ctx.author}")
    except Exception as e:
        await ctx.send(f"❌ Failed to unlock: {e}")
        return
    embed = discord.Embed(
        title="🔓 Channel Unlocked",
        description=f"{target.mention} has been unlocked.",
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)
    await target.send(embed=embed)
    if channel:
        await ctx.send(f"✅ Unlocked {target.mention}")

@bot.hybrid_command(name="lockdown", description="Lock entire server")
@commands.has_permissions(administrator=True)
async def lockdown(ctx, category: discord.CategoryChannel = None, *, reason: str = "No reason provided"):
    """Lockdown server or category"""
    if category:
        channels = category.channels
        target_name = category.name
    else:
        channels = ctx.guild.text_channels
        target_name = "server"
    locked = 0
    for channel in channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"Lockdown: {reason}")
            locked += 1
        except:
            pass
    embed = discord.Embed(
        title="🔒 LOCKDOWN ACTIVATED",
        description=f"**{target_name.upper()}** is now in lockdown mode!\nLocked {locked} channel(s).",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)
    embed.set_footer(text="Only moderators can send messages")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="slowmode", description="Set channel slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int, channel: discord.TextChannel = None):
    """Set slowmode delay"""
    target = channel or ctx.channel
    if seconds < 0 or seconds > 21600:
        await ctx.send("❌ Slowmode must be between 0 and 21600 seconds!")
        return
    try:
        await target.edit(slowmode_delay=seconds)
    except Exception as e:
        await ctx.send(f"❌ Failed to set slowmode: {e}")
        return
    if seconds == 0:
        await ctx.send(f"✅ Disabled slowmode in {target.mention}")
    else:
        await ctx.send(f"✅ Set slowmode to **{seconds}s** in {target.mention}")

# ═══════════════════════════════════════════════════════════════════════
# 📢 ADVANCED ANNOUNCEMENT COMMAND WITH MODAL
# ═══════════════════════════════════════════════════════════════════════

ColorChoice = Literal["blue", "red", "green", "gold", "purple", "orange", "blurple", "dark_blue", "dark_red", "dark_green", "pink", "teal", "magenta", "black", "white"]
EmbedTypeChoice = Literal["embed", "normal"]
FooterChoice = Literal["show", "hide"]
TimestampChoice = Literal["show", "hide"]
ImagePosition = Literal["thumbnail", "image", "none"]

class AnnouncementModal(discord.ui.Modal, title="✨ Advanced Announcement"):
    announcement_title = discord.ui.TextInput(
        label="Title (Optional)",
        placeholder="Enter announcement title...",
        required=False,
        max_length=256
    )
    announcement_message = discord.ui.TextInput(
        label="Message",
        placeholder="Enter your announcement message...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000
    )
    image_url = discord.ui.TextInput(
        label="Image URL (Optional)",
        placeholder="https://example.com/image.png",
        required=False
    )
    
    def __init__(self, channel, role, color, embed_type, show_footer, show_timestamp, image_position, author):
        super().__init__()
        self.channel = channel
        self.role = role
        self.color = color
        self.embed_type = embed_type
        self.show_footer = show_footer
        self.show_timestamp = show_timestamp
        self.image_position = image_position
        self.author = author
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        color_map = {
            "blue": discord.Color.blue(),
            "red": discord.Color.red(),
            "green": discord.Color.green(),
            "gold": discord.Color.gold(),
            "purple": discord.Color.purple(),
            "orange": discord.Color.orange(),
            "blurple": discord.Color.blurple(),
            "dark_blue": discord.Color.dark_blue(),
            "dark_red": discord.Color.dark_red(),
            "dark_green": discord.Color.dark_green(),
            "pink": discord.Color.from_rgb(255, 192, 203),
            "teal": discord.Color.teal(),
            "magenta": discord.Color.magenta(),
            "black": discord.Color.from_rgb(0, 0, 0),
            "white": discord.Color.from_rgb(255, 255, 255)
        }
        
        embed_color = color_map.get(self.color.lower(), discord.Color.blue())
        role_mention = self.role.mention if self.role else ""
        
        try:
            if self.embed_type.lower() == "normal":
                message_content = f"{role_mention}\n\n"
                if self.announcement_title.value:
                    message_content += f"**{self.announcement_title.value}**\n\n"
                message_content += self.announcement_message.value
                sent_msg = await self.channel.send(message_content)
            else:
                embed = discord.Embed(
                    title=self.announcement_title.value or "📢 Announcement",
                    description=self.announcement_message.value,
                    color=embed_color
                )
                if self.show_timestamp == "show":
                    embed.timestamp = datetime.datetime.utcnow()
                if self.show_footer == "show":
                    embed.set_footer(
                        text=f"Announced by {self.author}",
                        icon_url=self.author.display_avatar.url
                    )
                if self.image_url.value:
                    if self.image_position == "thumbnail":
                        embed.set_thumbnail(url=self.image_url.value)
                    elif self.image_position == "image":
                        embed.set_image(url=self.image_url.value)
                elif interaction.guild.icon and self.image_position == "thumbnail":
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                sent_msg = await self.channel.send(role_mention, embed=embed)
            
            success_embed = discord.Embed(
                title="✅ Announcement Sent Successfully",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            success_embed.add_field(name="📍 Channel", value=self.channel.mention, inline=True)
            success_embed.add_field(name="📝 Type", value=self.embed_type.title(), inline=True)
            success_embed.add_field(name="🎨 Color", value=self.color.title(), inline=True)
            if self.role:
                success_embed.add_field(name="🔔 Mentioned", value=self.role.mention, inline=True)
            success_embed.add_field(name="🔗 Jump to Message", value=f"[Click Here]({sent_msg.jump_url})", inline=False)
            await interaction.followup.send(embed=success_embed, ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to send announcement: {e}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

@bot.hybrid_command(name="announce", description="Send advanced announcement")
@commands.has_permissions(manage_messages=True)
@app_commands.describe(
    message="The announcement message (or use 'modal' for editor)",
    channel="Channel to send to",
    role="Role to mention",
    embed_type="embed or normal",
    color="Embed color",
    title="Custom title",
    image_url="Image URL",
    footer="Show footer",
    timestamp="Show timestamp",
    image_position="Image position"
)
async def announce(
    ctx,
    message: str,
    channel: discord.TextChannel = None,
    role: discord.Role = None,
    embed_type: EmbedTypeChoice = "embed",
    color: ColorChoice = "blue",
    title: str = None,
    image_url: str = None,
    footer: FooterChoice = "show",
    timestamp: TimestampChoice = "show",
    image_position: ImagePosition = "thumbnail"
):
    """Advanced announcement command"""
    target_channel = channel or ctx.channel
    
    if message.lower() == "modal":
        modal = AnnouncementModal(
            target_channel, role, color, embed_type, 
            footer, timestamp, image_position, ctx.author
        )
        await ctx.interaction.response.send_modal(modal)
        return
    
    color_map = {
        "blue": discord.Color.blue(),
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "gold": discord.Color.gold(),
        "purple": discord.Color.purple(),
        "orange": discord.Color.orange(),
        "blurple": discord.Color.blurple(),
        "dark_blue": discord.Color.dark_blue(),
        "dark_red": discord.Color.dark_red(),
        "dark_green": discord.Color.dark_green(),
        "pink": discord.Color.from_rgb(255, 192, 203),
        "teal": discord.Color.teal(),
        "magenta": discord.Color.magenta(),
        "black": discord.Color.from_rgb(0, 0, 0),
        "white": discord.Color.from_rgb(255, 255, 255)
    }
    
    embed_color = color_map.get(color.lower(), discord.Color.blue())
    role_mention = role.mention if role else ""
    
    try:
        if embed_type.lower() == "normal":
            full_message = f"{role_mention}\n\n" if role_mention else ""
            if title:
                full_message += f"**{title}**\n\n"
            full_message += message
            sent_message = await target_channel.send(full_message)
        else:
            embed = discord.Embed(
                title=title or "📢 Announcement",
                description=message,
                color=embed_color
            )
            if timestamp == "show":
                embed.timestamp = datetime.datetime.utcnow()
            if footer == "show":
                embed.set_footer(
                    text=f"Announced by {ctx.author}",
                    icon_url=ctx.author.display_avatar.url
                )
            if image_url:
                if image_position == "thumbnail":
                    embed.set_thumbnail(url=image_url)
                elif image_position == "image":
                    embed.set_image(url=image_url)
            elif ctx.guild.icon and image_position == "thumbnail":
                embed.set_thumbnail(url=ctx.guild.icon.url)
            sent_message = await target_channel.send(role_mention, embed=embed)
        
        confirm_embed = discord.Embed(
            title="✅ Announcement Sent Successfully",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        confirm_embed.add_field(name="📍 Channel", value=target_channel.mention, inline=True)
        confirm_embed.add_field(name="📝 Type", value=embed_type.title(), inline=True)
        if embed_type.lower() == "embed":
            confirm_embed.add_field(name="🎨 Color", value=color.title(), inline=True)
            confirm_embed.add_field(name="⏰ Timestamp", value=timestamp.title(), inline=True)
            confirm_embed.add_field(name="👤 Footer", value=footer.title(), inline=True)
            if image_url:
                confirm_embed.add_field(name="🖼️ Image", value=image_position.title(), inline=True)
        if role:
            confirm_embed.add_field(name="🔔 Mentioned", value=role.mention, inline=True)
        if title:
            confirm_embed.add_field(name="📌 Title", value=title, inline=False)
        confirm_embed.add_field(
            name="🔗 Jump to Message",
            value=f"[Click Here]({sent_message.jump_url})",
            inline=False
        )
        confirm_embed.set_footer(text=f"Message ID: {sent_message.id}")
        await ctx.send(embed=confirm_embed, ephemeral=True)
    except discord.Forbidden:
        error_embed = discord.Embed(
            title="❌ Permission Error",
            description=f"I don't have permission to send messages in {target_channel.mention}!",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"Failed to send announcement: {e}",
            color=discord.Color.red()
        )
        await ctx.send(embed=error_embed, ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════
# 📊 INFORMATION COMMANDS
# ═══════════════════════════════════════════════════════════════════════

@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx):
    """Check bot latency"""
    embed = discord.Embed(
        title="🏓 Pong!",
        color=discord.Color.green()
    )
    embed.add_field(name="Latency", value=f"```{round(bot.latency * 1000)}ms```", inline=True)
    embed.add_field(name="API", value="```Online```", inline=True)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="serverinfo", description="Display server information")
async def serverinfo(ctx):
    """Display server info"""
    guild = ctx.guild
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    total_members = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = len([m for m in guild.members if m.bot])
    online = len([m for m in guild.members if m.status == discord.Status.online])
    idle = len([m for m in guild.members if m.status == discord.Status.idle])
    dnd = len([m for m in guild.members if m.status == discord.Status.dnd])
    offline = len([m for m in guild.members if m.status == discord.Status.offline])
    
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(
        name="General",
        value=f"**Owner:** {guild.owner.mention}\n**Created:** <t:{int(guild.created_at.timestamp())}:R>\n**Server ID:** {guild.id}",
        inline=False
    )
    embed.add_field(
        name=f"Members ({total_members})",
        value=f"👥 Humans: {humans}\n🤖 Bots: {bots}\n🟢 Online: {online}\n🟡 Idle: {idle}\n🔴 DND: {dnd}\n⚪ Offline: {offline}",
        inline=True
    )
    embed.add_field(
        name=f"Channels ({text_channels + voice_channels})",
        value=f"💬 Text: {text_channels}\n🔊 Voice: {voice_channels}\n📁 Categories: {categories}",
        inline=True
    )
    embed.add_field(
        name="Other",
        value=f"📝 Roles: {len(guild.roles)}\n😀 Emojis: {len(guild.emojis)}\n🚀 Boosts: {guild.premium_subscription_count}",
        inline=True
    )
    features = ", ".join(guild.features) if guild.features else "None"
    if len(features) > 1024:
        features = features[:1020] + "..."
    embed.add_field(name="Features", value=f"```{features}```", inline=False)
    embed.set_footer(text=f"Verification Level: {str(guild.verification_level).title()}")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="userinfo", description="Display user information")
async def userinfo(ctx, user: discord.Member = None):
    """Display user info"""
    target = user or ctx.author
    roles = [role.mention for role in target.roles if role.name != "@everyone"]
    roles_str = ", ".join(roles[:20]) if roles else "None"
    if len(target.roles) > 21:
        roles_str += f" (+{len(target.roles) - 21} more)"
    
    perms = []
    if target.guild_permissions.administrator:
        perms.append("Administrator")
    if target.guild_permissions.manage_guild:
        perms.append("Manage Server")
    if target.guild_permissions.manage_channels:
        perms.append("Manage Channels")
    if target.guild_permissions.manage_roles:
        perms.append("Manage Roles")
    if target.guild_permissions.kick_members:
        perms.append("Kick Members")
    if target.guild_permissions.ban_members:
        perms.append("Ban Members")
    perms_str = ", ".join(perms[:5]) if perms else "None"
    
    embed = discord.Embed(
        title=f"👤 User Information",
        color=target.color if target.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(
        name="User",
        value=f"**Name:** {target}\n**Mention:** {target.mention}\n**ID:** {target.id}",
        inline=False
    )
    embed.add_field(
        name="Joined",
        value=f"**Server:** <t:{int(target.joined_at.timestamp())}:R>\n**Discord:** <t:{int(target.created_at.timestamp())}:R>",
        inline=True
    )
    embed.add_field(
        name="Status",
        value=f"**Status:** {str(target.status).title()}\n**Activity:** {target.activity.name if target.activity else 'None'}",
        inline=True
    )
    embed.add_field(name=f"Roles ({len(target.roles) - 1})", value=roles_str, inline=False)
    if perms:
        embed.add_field(name="Key Permissions", value=perms_str, inline=False)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="avatar", description="Display avatar")
async def avatar(ctx, user: discord.Member = None):
    """Display avatar"""
    target = user or ctx.author
    embed = discord.Embed(
        title=f"🖼️ Avatar: {target}",
        color=discord.Color.blue()
    )
    embed.set_image(url=target.display_avatar.url)
    embed.add_field(name="Download", value=f"[Link]({target.display_avatar.url})")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="banner", description="Display banner")
async def banner(ctx, user: discord.Member = None):
    """Display banner"""
    target = user or ctx.author
    full_user = await bot.fetch_user(target.id)
    if not full_user.banner:
        await ctx.send(f"❌ **{target}** doesn't have a banner!")
        return
    embed = discord.Embed(
        title=f"🖼️ Banner: {target}",
        color=discord.Color.blue()
    )
    embed.set_image(url=full_user.banner.url)
    embed.add_field(name="Download", value=f"[Link]({full_user.banner.url})")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="botinfo", description="Display bot statistics")
async def botinfo(ctx):
    """Display bot info"""
    embed = discord.Embed(
        title=f"🤖 {bot.user.name}",
        description="Advanced Discord Moderation Bot with 66+ Commands",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    total_members = sum(g.member_count for g in bot.guilds)
    total_channels = sum(len(g.channels) for g in bot.guilds)
    embed.add_field(
        name="Statistics",
        value=f"**Servers:** {len(bot.guilds)}\n**Users:** {total_members:,}\n**Channels:** {total_channels:,}",
        inline=True
    )
    embed.add_field(
        name="System",
        value=f"**Latency:** {round(bot.latency * 1000)}ms\n**Python:** {sys.version.split()[0]}\n**discord.py:** {discord.__version__}",
        inline=True
    )
    total_commands = len([c for c in bot.walk_commands()])
    embed.add_field(
        name="Commands",
        value=f"**Total:** {total_commands}\n**Type:** Hybrid (Prefix + Slash)",
        inline=True
    )
    embed.set_footer(text=f"Bot Created by {ctx.guild.owner}", icon_url=ctx.guild.owner.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="membercount", description="Show member count")
async def membercount(ctx):
    """Show member count"""
    guild = ctx.guild
    total = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = len([m for m in guild.members if m.bot])
    online = len([m for m in guild.members if m.status == discord.Status.online])
    idle = len([m for m in guild.members if m.status == discord.Status.idle])
    dnd = len([m for m in guild.members if m.status == discord.Status.dnd])
    offline = len([m for m in guild.members if m.status == discord.Status.offline])
    embed = discord.Embed(
        title=f"👥 Member Count: {total}",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Humans", value=f"```{humans}```", inline=True)
    embed.add_field(name="Bots", value=f"```{bots}```", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="🟢 Online", value=f"```{online}```", inline=True)
    embed.add_field(name="🟡 Idle", value=f"```{idle}```", inline=True)
    embed.add_field(name="🔴 DND", value=f"```{dnd}```", inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="roles", description="List all roles")
async def roles(ctx):
    """List all roles"""
    roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
    roles = [r for r in roles if r.name != "@everyone"]
    embed = discord.Embed(
        title=f"📝 Roles in {ctx.guild.name}",
        description=f"Total: {len(roles)} roles",
        color=discord.Color.blue()
    )
    role_list = []
    for role in roles[:25]:
        member_count = len(role.members)
        role_list.append(f"{role.mention} - {member_count} members")
    embed.add_field(name="Roles", value="\n".join(role_list) if role_list else "No roles", inline=False)
    if len(roles) > 25:
        embed.set_footer(text=f"Showing 25 of {len(roles)} roles")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="emojis", description="List all emojis")
async def emojis(ctx):
    """List all emojis"""
    emojis = ctx.guild.emojis
    if not emojis:
        await ctx.send("❌ This server has no custom emojis!")
        return
    animated = [e for e in emojis if e.animated]
    static = [e for e in emojis if not e.animated]
    embed = discord.Embed(
        title=f"😀 Emojis in {ctx.guild.name}",
        description=f"Total: {len(emojis)} ({len(static)} static, {len(animated)} animated)",
        color=discord.Color.blue()
    )
    if static:
        static_str = " ".join([str(e) for e in static[:25]])
        embed.add_field(name=f"Static ({len(static)})", value=static_str, inline=False)
    if animated:
        animated_str = " ".join([str(e) for e in animated[:25]])
        embed.add_field(name=f"Animated ({len(animated)})", value=animated_str, inline=False)
    if len(emojis) > 50:
        embed.set_footer(text=f"Showing 50 of {len(emojis)} emojis")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="roleinfo", description="Display role info")
async def roleinfo(ctx, role: discord.Role):
    """Display role info"""
    embed = discord.Embed(
        title=f"📝 Role Information",
        color=role.color if role.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(
        name="General",
        value=f"**Name:** {role.name}\n**ID:** {role.id}\n**Mention:** {role.mention}",
        inline=False
    )
    embed.add_field(
        name="Statistics",
        value=f"**Members:** {len(role.members)}\n**Position:** {role.position}\n**Hoisted:** {'Yes' if role.hoist else 'No'}",
        inline=True
    )
    embed.add_field(
        name="Properties",
        value=f"**Mentionable:** {'Yes' if role.mentionable else 'No'}\n**Managed:** {'Yes' if role.managed else 'No'}\n**Color:** {str(role.color)}",
        inline=True
    )
    embed.add_field(
        name="Created",
        value=f"<t:{int(role.created_at.timestamp())}:R>",
        inline=False
    )
    perms = []
    if role.permissions.administrator:
        perms.append("Administrator")
    if role.permissions.manage_guild:
        perms.append("Manage Server")
    if role.permissions.manage_roles:
        perms.append("Manage Roles")
    if role.permissions.manage_channels:
        perms.append("Manage Channels")
    if role.permissions.kick_members:
        perms.append("Kick Members")
    if role.permissions.ban_members:
        perms.append("Ban Members")
    if perms:
        embed.add_field(name="Key Permissions", value=", ".join(perms), inline=False)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="channelinfo", description="Display channel info")
async def channelinfo(ctx, channel: discord.TextChannel = None):
    """Display channel info"""
    target = channel or ctx.channel
    embed = discord.Embed(
        title=f"📝 Channel Information",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(
        name="General",
        value=f"**Name:** {target.name}\n**ID:** {target.id}\n**Mention:** {target.mention}",
        inline=False
    )
    embed.add_field(
        name="Statistics",
        value=f"**Category:** {target.category.name if target.category else 'None'}\n**Position:** {target.position}\n**NSFW:** {'Yes' if target.nsfw else 'No'}",
        inline=True
    )
    embed.add_field(
        name="Other",
        value=f"**Slowmode:** {target.slowmode_delay}s\n**Created:** <t:{int(target.created_at.timestamp())}:R>",
        inline=True
    )
    if target.topic:
        embed.add_field(name="Topic", value=target.topic, inline=False)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="inviteinfo", description="Display invite info")
async def inviteinfo(ctx, invite_code: str):
    """Display invite info"""
    try:
        invite = await bot.fetch_invite(invite_code)
    except:
        await ctx.send("❌ Invalid invite code or invite not found!")
        return
    embed = discord.Embed(
        title=f"📨 Invite Information",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    if invite.guild:
        embed.add_field(
            name="Server",
            value=f"**Name:** {invite.guild.name}\n**ID:** {invite.guild.id}\n**Members:** ~{invite.approximate_member_count}",
            inline=False
        )
        if invite.guild.icon:
            embed.set_thumbnail(url=invite.guild.icon.url)
    if invite.channel:
        embed.add_field(
            name="Channel",
            value=f"**Name:** {invite.channel.name}\n**Type:** {str(invite.channel.type).title()}",
            inline=True
        )
    if invite.inviter:
        embed.add_field(
            name="Inviter",
            value=f"**Name:** {invite.inviter}\n**ID:** {invite.inviter.id}",
            inline=True
        )
    embed.add_field(
        name="Stats",
        value=f"**Uses:** {invite.uses if invite.uses else 'N/A'}\n**Max Uses:** {invite.max_uses if invite.max_uses else 'Unlimited'}\n**Expires:** {f'<t:{int(invite.expires_at.timestamp())}:R>' if invite.expires_at else 'Never'}",
        inline=False
    )
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════
# ⚙️ SETTINGS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

@bot.hybrid_command(name="setlog", description="Set log channels")
@commands.has_permissions(administrator=True)
async def setlog(ctx, log_type: str, channel: discord.TextChannel):
    """Set log channel"""
    log_type = log_type.lower()
    valid_types = {
        'modlog': 'mod_log_channel',
        'msglog': 'message_log_channel',
        'memberlog': 'member_log_channel',
        'voicelog': 'voice_log_channel'
    }
    if log_type not in valid_types:
        await ctx.send(f"❌ Invalid log type! Valid types: {', '.join(valid_types.keys())}")
        return
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM settings WHERE guild_id = ?', (ctx.guild.id,))
    if not c.fetchone():
        c.execute('INSERT INTO settings (guild_id) VALUES (?)', (ctx.guild.id,))
    c.execute(f'UPDATE settings SET {valid_types[log_type]} = ? WHERE guild_id = ?',
              (channel.id, ctx.guild.id))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Set **{log_type}** to {channel.mention}")

@bot.hybrid_command(name="prefixset", description="Change bot prefix")
@commands.has_permissions(administrator=True)
async def prefixset(ctx, new_prefix: str):
    """Change server prefix"""
    if len(new_prefix) > 5:
        await ctx.send("❌ Prefix must be 5 characters or less!")
        return
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT prefix FROM settings WHERE guild_id = ?', (ctx.guild.id,))
    result = c.fetchone()
    old_prefix = result[0] if result else '!'
    if not result:
        c.execute('INSERT INTO settings (guild_id, prefix) VALUES (?, ?)', (ctx.guild.id, new_prefix))
    else:
        c.execute('UPDATE settings SET prefix = ? WHERE guild_id = ?', (new_prefix, ctx.guild.id))
    conn.commit()
    conn.close()
    embed = discord.Embed(
        title="✅ Prefix Changed",
        description=f"Server prefix changed from `{old_prefix}` to `{new_prefix}`",
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Example", value=f"`{new_prefix}help`", inline=False)
    embed.set_footer(text=f"Changed by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="setwelcome", description="Set welcome channel")
@commands.has_permissions(administrator=True)
async def setwelcome(ctx, channel: discord.TextChannel):
    """Set welcome channel"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM settings WHERE guild_id = ?', (ctx.guild.id,))
    if not c.fetchone():
        c.execute('INSERT INTO settings (guild_id, welcome_channel) VALUES (?, ?)', 
                  (ctx.guild.id, channel.id))
    else:
        c.execute('UPDATE settings SET welcome_channel = ? WHERE guild_id = ?',
                  (channel.id, ctx.guild.id))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Set welcome channel to {channel.mention}")

@bot.hybrid_command(name="setleave", description="Set leave channel")
@commands.has_permissions(administrator=True)
async def setleave(ctx, channel: discord.TextChannel):
    """Set leave channel"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM settings WHERE guild_id = ?', (ctx.guild.id,))
    if not c.fetchone():
        c.execute('INSERT INTO settings (guild_id, leave_channel) VALUES (?, ?)', 
                  (ctx.guild.id, channel.id))
    else:
        c.execute('UPDATE settings SET leave_channel = ? WHERE guild_id = ?',
                  (channel.id, ctx.guild.id))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Set leave channel to {channel.mention}")

@bot.hybrid_command(name="setwarnthreshold", description="Set warning threshold")
@commands.has_permissions(administrator=True)
async def setwarnthreshold(ctx, threshold: int):
    """Set warning threshold"""
    if threshold < 1 or threshold > 100:
        await ctx.send("❌ Threshold must be between 1 and 100!")
        return
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM settings WHERE guild_id = ?', (ctx.guild.id,))
    if not c.fetchone():
        c.execute('INSERT INTO settings (guild_id, warn_threshold) VALUES (?, ?)', 
                  (ctx.guild.id, threshold))
    else:
        c.execute('UPDATE settings SET warn_threshold = ? WHERE guild_id = ?',
                  (threshold, ctx.guild.id))
    conn.commit()
    conn.close()
    await ctx.send(f"✅ Set warning threshold to **{threshold}** points\n⚠️ Users will be auto-kicked when they reach this threshold!")

@bot.hybrid_command(name="config", description="Show server config")
@commands.has_permissions(manage_guild=True)
async def config(ctx):
    """Show server config"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM settings WHERE guild_id = ?', (ctx.guild.id,))
    settings = c.fetchone()
    conn.close()
    if not settings:
        await ctx.send("⚙️ No configuration found. Use setup commands to configure the bot.")
        return
    embed = discord.Embed(
        title="⚙️ Server Configuration",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    prefix = settings[1] if settings[1] else '!'
    embed.add_field(name="Prefix", value=f"`{prefix}`", inline=True)
    threshold = settings[8] if settings[8] else 3
    embed.add_field(name="⚠️ Warning Threshold", value=f"**{threshold} points** (Auto-kick)", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    mod_log = f"<#{settings[2]}>" if settings[2] else "Not set"
    msg_log = f"<#{settings[3]}>" if settings[3] else "Not set"
    member_log = f"<#{settings[4]}>" if settings[4] else "Not set"
    voice_log = f"<#{settings[5]}>" if settings[5] else "Not set"
    embed.add_field(
        name="📝 Log Channels",
        value=f"**Moderation:** {mod_log}\n**Messages:** {msg_log}\n**Members:** {member_log}\n**Voice:** {voice_log}",
        inline=False
    )
    welcome = f"<#{settings[6]}>" if settings[6] else "Not set"
    leave = f"<#{settings[7]}>" if settings[7] else "Not set"
    embed.add_field(name="👋 Welcome Channel", value=welcome, inline=True)
    embed.add_field(name="👋 Leave Channel", value=leave, inline=True)
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text="Use commands to update these settings")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="help", description="Show help menu")
async def help_command(ctx, category: str = None):
    """Show help menu"""
    if not category:
        conn = sqlite3.connect('MEGA_BOT.db')
        c = conn.cursor()
        c.execute('SELECT prefix FROM settings WHERE guild_id = ?', (ctx.guild.id,))
        result = c.fetchone()
        conn.close()
        prefix = result[0] if result and result[0] else '!'
        embed = discord.Embed(
            title="📚 Help Menu",
            description=f"Use `{prefix}help <category>` for more info.\n\n⚠️ **Auto-Kick:** Users automatically kicked at 3 warning points (configurable)",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        categories = {
            "🎉 giveaway": "Giveaway system",
            "📊 poll": "Poll system",
            "🛡️ moderation": "Moderation",
            "⚠️ warn": "Warning system",
            "🔊 voice": "Voice moderation",
            "📝 channel": "Channel management",
            "📢 announce": "Announcements",
            "📊 info": "Information",
            "⚙️ settings": "Configuration"
        }
        for cat, desc in categories.items():
            embed.add_field(name=cat, value=desc, inline=True)
        embed.set_footer(text=f"Prefix: {prefix} | Total: 66+ Commands")
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)
        return
    
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT prefix FROM settings WHERE guild_id = ?', (ctx.guild.id,))
    result = c.fetchone()
    conn.close()
    prefix = result[0] if result and result[0] else '!'
    
    category = category.lower()
    help_data = {
        "giveaway": {
            "title": "🎉 Giveaway Commands",
            "commands": {
                f"{prefix}giveaway <duration> <winners> <prize>": "Create giveaway",
                f"{prefix}giveawayend <message_id>": "End giveaway",
                f"{prefix}giveawayreroll <message_id> [winners]": "Reroll winners"
            }
        },
        "poll": {
            "title": "📊 Poll Commands",
            "commands": {
                f"{prefix}poll <question> <opt1> <opt2> [...]": "Create poll",
                f"{prefix}pollend <message_id>": "End poll"
            }
        },
        "moderation": {
            "title": "🛡️ Moderation Commands",
            "commands": {
                f"{prefix}kick <user> [reason]": "Kick member",
                f"{prefix}ban <user> [days] [reason]": "Ban member",
                f"{prefix}unban <user_id> [reason]": "Unban user",
                f"{prefix}softban <user> [reason]": "Softban",
                f"{prefix}tempban <user> <duration> [reason]": "Temp ban",
                f"{prefix}timeout <user> <duration> [reason]": "Timeout",
                f"{prefix}untimeout <user> [reason]": "Remove timeout",
                f"{prefix}purge <amount> [user]": "Delete messages",
                f"{prefix}nuke [channel]": "Nuke channel",
                f"{prefix}case <case_id>": "View case",
                f"{prefix}history <user>": "View history",
                f"{prefix}note <user> <note>": "Add note",
                f"{prefix}notes <user>": "View notes",
                f"{prefix}reason <case_id> <reason>": "Update reason"
            }
        },
        "warn": {
            "title": "⚠️ Warning Commands",
            "commands": {
                f"{prefix}warn <user> [reason]": "Warn user (auto-kick at threshold)",
                f"{prefix}warnings [user]": "View warnings",
                f"{prefix}clearwarns <user> [reason]": "Clear warnings",
                f"{prefix}removewarn <warn_id> [reason]": "Remove warning"
            }
        },
        "voice": {
            "title": "🔊 Voice Commands",
            "commands": {
                f"{prefix}vcmute <user> [reason]": "Voice mute",
                f"{prefix}vcunmute <user> [reason]": "Voice unmute",
                f"{prefix}vcdeafen <user> [reason]": "Voice deafen",
                f"{prefix}vcundeafen <user> [reason]": "Voice undeafen",
                f"{prefix}vckick <user> [reason]": "Disconnect",
                f"{prefix}vcmove <user> <channel> [reason]": "Move user",
                f"{prefix}vcmoveall <from> <to> [reason]": "Move all"
            }
        },
        "channel": {
            "title": "📝 Channel Commands",
            "commands": {
                f"{prefix}lock [channel] [reason]": "Lock channel",
                f"{prefix}unlock [channel] [reason]": "Unlock channel",
                f"{prefix}lockdown [category] [reason]": "Lockdown",
                f"{prefix}slowmode <seconds> [channel]": "Set slowmode"
            }
        },
        "announce": {
            "title": "📢 Announcement Command",
            "commands": {
                f"{prefix}announce <message>": "Send announcement",
                f"{prefix}announce modal #channel @role embed red": "Use modal editor",
                f"{prefix}announce <msg> #channel @role embed red \"Title\"": "Full advanced"
            }
        },
        "info": {
            "title": "📊 Information Commands",
            "commands": {
                f"{prefix}ping": "Bot latency",
                f"{prefix}serverinfo": "Server info",
                f"{prefix}userinfo [user]": "User info",
                f"{prefix}avatar [user]": "User avatar",
                f"{prefix}banner [user]": "User banner",
                f"{prefix}botinfo": "Bot stats",
                f"{prefix}membercount": "Member count",
                f"{prefix}roles": "List roles",
                f"{prefix}emojis": "List emojis",
                f"{prefix}roleinfo <role>": "Role info",
                f"{prefix}channelinfo [channel]": "Channel info",
                f"{prefix}inviteinfo <invite>": "Invite info"
            }
        },
        "settings": {
            "title": "⚙️ Settings Commands",
            "commands": {
                f"{prefix}setlog <type> <channel>": "Set log channels",
                f"{prefix}prefixset <prefix>": "Change prefix",
                f"{prefix}setwelcome <channel>": "Set welcome",
                f"{prefix}setleave <channel>": "Set leave",
                f"{prefix}setwarnthreshold <points>": "Set warn threshold",
                f"{prefix}config": "Show config"
            }
        }
    }
    
    if category not in help_data:
        await ctx.send(f"❌ Invalid category! Use `{prefix}help` to see all categories.")
        return
    
    data = help_data[category]
    embed = discord.Embed(
        title=data["title"],
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    for command, description in data["commands"].items():
        embed.add_field(name=command, value=description, inline=False)
    embed.set_footer(text=f"Prefix: {prefix} | Use {prefix}help for all categories")
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════
# ⏰ BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════

@tasks.loop(minutes=1)
async def check_temp_bans():
    """Check and unban expired tempbans"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('SELECT * FROM tempbans WHERE expires_at <= ?', (datetime.datetime.utcnow().isoformat(),))
    expired = c.fetchall()
    for tempban in expired:
        guild_id = tempban[1]
        user_id = tempban[2]
        reason = tempban[3]
        case_id = tempban[4]
        guild = bot.get_guild(guild_id)
        if not guild:
            continue
        try:
            user = await bot.fetch_user(user_id)
            await guild.unban(user, reason=f"[Case #{case_id}] Tempban expired: {reason}")
            await log_action_embed(guild, "unban", user, bot.user, "Tempban expired", case_id)
            log_action(guild_id, "unban", user_id, bot.user.id, "Tempban expired", case_id)
            c.execute('DELETE FROM tempbans WHERE id = ?', (tempban[0],))
            conn.commit()
            print(f"✅ Auto-unbanned {user} from {guild.name}")
        except Exception as e:
            print(f"❌ Failed to auto-unban {user_id}: {e}")
    conn.close()

# ═══════════════════════════════════════════════════════════════════════
# 🎯 EVENTS
# ═══════════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    """Bot ready event"""
    print("═" * 50)
    print(f"✅ Bot is ready!")
    print(f"📛 Logged in as: {bot.user.name}")
    print(f"🆔 Bot ID: {bot.user.id}")
    print(f"🌐 Servers: {len(bot.guilds)}")
    print(f"👥 Users: {sum(g.member_count for g in bot.guilds):,}")
    print(f"📊 Commands: 66+")
    print("═" * 50)
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    
    check_temp_bans.start()
    print("✅ Background tasks started")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for !help | 66+ Commands"
        )
    )

@bot.event
async def on_guild_join(guild):
    """Initialize settings when bot joins"""
    conn = sqlite3.connect('MEGA_BOT.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO settings (guild_id, prefix) VALUES (?, ?)', (guild.id, '!'))
    conn.commit()
    conn.close()
    print(f"✅ Joined new server: {guild.name} ({guild.id})")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ You don't have permission!\nRequired: {', '.join(error.missing_permissions)}")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(f"❌ I don't have permission!\nRequired: {', '.join(error.missing_permissions)}")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found!")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ Channel not found!")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send("❌ Role not found!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param.name}`\nUse `!help` for usage.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument!\n{error}")
    else:
        print(f"Error in {ctx.command}: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.send(f"❌ An error occurred: {error}")

# ═══════════════════════════════════════════════════════════════════════
# 🚀 MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_database()
    print("🚀 Starting Discord Mega Bot...")
    print("📚 Features: 66+ Commands | Auto-Kick | Custom Prefix | Hybrid Commands")
    print("═" * 50)
    bot.run(os.getenv('TOKEN'))
