import discord
from discord import app_commands
import logging
from dotenv import load_dotenv
import os
from discord.ext import tasks, commands
import asyncio
from typing import Dict, List
import uuid
import aiohttp
import webserver

# Load environment variables
load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Logging
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot setup
bot = commands.Bot(command_prefix='!', intents=intents)

# Guild (for fast sync while developing)
TEST_GUILD_ID = 1093560345794199562
guild = discord.Object(id=TEST_GUILD_ID)

# In-memory reminder storage
user_reminders: Dict[int, List[Dict]] = {}


# View for canceling a single reminder (used when reminder triggers)
class ReminderView(discord.ui.View):
    def __init__(self, user_id: int, reminder_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.reminder_id = reminder_id

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        reminders = user_reminders.get(self.user_id, [])
        new_list = [r for r in reminders if r["id"] != self.reminder_id]
        if len(new_list) != len(reminders):
            user_reminders[self.user_id] = new_list
            await interaction.response.send_message("❌ Reminder canceled.", ephemeral=True)
        else:
            await interaction.response.send_message("Reminder not found.", ephemeral=True)

# View for listing all reminders with cancel buttons
class CancelButton(discord.ui.Button):
    def __init__(self, user_id: int, reminder_id: str, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.danger)
        self.user_id = user_id
        self.reminder_id = reminder_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only cancel your own reminders!", ephemeral=True)
            return

        reminders = user_reminders.get(self.user_id, [])
        new_list = [r for r in reminders if r["id"] != self.reminder_id]
        if len(new_list) != len(reminders):
            user_reminders[self.user_id] = new_list
            await interaction.response.send_message("❌ Reminder canceled.", ephemeral=True)
        else:
            await interaction.response.send_message("Reminder not found.", ephemeral=True)

class RemindersListView(discord.ui.View):
    def __init__(self, user_id: int, reminders: List[Dict]):
        super().__init__(timeout=None)
        for reminder in reminders:
            self.add_item(CancelButton(user_id, reminder["id"], f"Cancel: {reminder['task']}"))


@bot.tree.command(name="remind", description="Set a reminder with a task and time (in minutes).")
@app_commands.describe(task="What should I remind you about?", minutes="When to remind you (in minutes)")
async def remind(interaction: discord.Interaction, task: str, minutes: int):
    if minutes <= 0:
        await interaction.response.send_message("Minutes must be greater than 0.", ephemeral=True)
        return

    reminder_id = str(uuid.uuid4())
    user_id = interaction.user.id

    reminder = {
        "id": reminder_id,
        "task": task,
        "minutes": minutes,
        "user": interaction.user,
        "channel": interaction.channel,
    }

    user_reminders.setdefault(user_id, []).append(reminder)

    await interaction.response.send_message(
        f"✅ Reminder set for **{task}** in {minutes} minute(s).",
        ephemeral=True
    )

    async def send_reminder():
        await asyncio.sleep(minutes * 60)
        for r in user_reminders.get(user_id, []):
            if r["id"] == reminder_id:
                await reminder["channel"].send(
                    f"⏰ {interaction.user.mention} Reminder: **{task}**",
                    view=ReminderView(user_id, reminder_id)
                )
                break

    asyncio.create_task(send_reminder())

#slash command for checking active reminders
@bot.tree.command(name="reminders", description="List your active reminders.")
async def reminders(interaction: discord.Interaction):
    reminders = user_reminders.get(interaction.user.id, [])

    if not reminders:
        await interaction.response.send_message("You have no active reminders.", ephemeral=True)
        return

    embed = discord.Embed(title="⏳ Your Reminders", color=discord.Color.blue())
    for r in reminders:
        embed.add_field(
            name=f"• {r['task']}",
            value=f"In {r['minutes']} minute(s)",
            inline=False
        )

    view = RemindersListView(interaction.user.id, reminders)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



# dictionary slash command
@bot.tree.command(name="define", description="Look up a word in the dictionary.")
@app_commands.describe(word="The word you want to look up")
async def define(interaction: discord.Interaction, word: str):
    await interaction.response.defer(ephemeral=True)  # Show loading

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                await interaction.followup.send(f"❌ Could not find the word **{word}**.", ephemeral=True)
                return

            data = await response.json()

    try:
        entry = data[0]
        word_text = entry["word"]
        phonetics = entry.get("phonetic", "")
        meaning = entry["meanings"][0]
        part_of_speech = meaning["partOfSpeech"]
        definition = meaning["definitions"][0]["definition"]
        example = meaning["definitions"][0].get("example", "*No example provided.*")

        embed = discord.Embed(
            title=f"📖 {word_text} ({part_of_speech})",
            description=f"**Definition:** {definition}\n\n**Usage:** _{example}_",
            color=discord.Color.dark_green()
        )
        if phonetics:
            embed.set_footer(text=f"Phonetic: {phonetics}")

        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        print(f"Error parsing dictionary API response: {e}")
        await interaction.followup.send("⚠️ Something went wrong while parsing the definition.", ephemeral=True)

# Water reminder loop every 60 minutes
@tasks.loop(minutes=60)
async def water_reminder():
    channel_id = 1365983627049173053  # Replace with your real channel ID
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send("💧 dink water  :3")

# Sync commands and start loop
@bot.event
async def on_ready():
    await bot.wait_until_ready()
    print(f'Bot is ready: {bot.user}')
    try:
        bot.tree.clear_commands(guild=guild)
        synced = await bot.tree.sync(guild=guild)  # Use global sync by removing guild= if needed
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    water_reminder.start()

# Run the bot
webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
