import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import os

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# ------------------------------------------------------------------------------
# Events
# ------------------------------------------------------------------------------
@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game(name="spamming in dms")
    )
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"✅ Connected to {len(bot.guilds)} guild(s)")
    await bot.tree.sync()
    print("✅ Slash commands synced.")

# ------------------------------------------------------------------------------
# Slash Command: dmspam
# ------------------------------------------------------------------------------
@bot.tree.command(name="dmspam", description="Spam a user's DMs (moderator only)")
@app_commands.describe(
    user="The user to spam",
    message="Message to send",
    count="Number of messages to send (default: 10)",
    delay="Delay between messages in seconds (default: 0.5)"
)
async def dmspam(
    interaction: discord.Interaction,
    user: discord.User,
    message: str,
    count: int = 10,
    delay: float = 0.5
):
    # Only allow users with manage_messages permission
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need `Manage Messages` permission to use this command.", ephemeral=True)
        return

    await interaction.response.send_message(f"🔄 Spamming **{user}** with **{count}** messages...", ephemeral=True)

    try:
        # Create DM channel
        dm = await user.create_dm()
        sent = 0
        for i in range(count):
            try:
                await dm.send(message)
                sent += 1
                if i < count - 1:
                    await asyncio.sleep(delay)
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Cannot send messages to {user}. They may have DMs disabled or blocked the bot.", ephemeral=True)
                break
            except discord.HTTPException as e:
                await interaction.followup.send(f"⚠️ Error sending message {i+1}: {e}", ephemeral=True)
                break
        await interaction.followup.send(f"✅ Sent {sent}/{count} messages to {user}.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to start DM: {e}", ephemeral=True)

# ------------------------------------------------------------------------------
# Slash Command: ping (optional)
# ------------------------------------------------------------------------------
@bot.tree.command(name="ping", description="Check the bot's latency")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 Latency: {latency}ms")

# ------------------------------------------------------------------------------
# Prefix Command: ping (optional)
# ------------------------------------------------------------------------------
@bot.command(name="ping", aliases=["pong"])
async def prefix_ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 🏓 Latency: {latency}ms")

# ------------------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Replace with your actual token
    bot.run(os.getenv("TOKEN"))
