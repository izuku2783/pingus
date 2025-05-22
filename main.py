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
import json

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

# In-memory reminder storage
user_reminders: Dict[int, List[Dict]] = {}

# In-memory snipe cache
sniped_messages: Dict[int, Dict] = {}

# Server-specific hydration channel storage (guild_id: channel_id)
hydration_channels: Dict[int, int] = {}
SAVE_PATH = "hydration_channels.json"

# Load hydration channels from file
def load_channels():
    global hydration_channels
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, "r") as f:
            hydration_channels = json.load(f)

# Save hydration channels to file
def save_channels():
    with open(SAVE_PATH, "w") as f:
        json.dump(hydration_channels, f)

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
            await interaction.response.send_message("❌ Reminder canceled.")
        else:
            await interaction.response.send_message("Reminder not found.")

# View for listing all reminders with cancel buttons
class CancelButton(discord.ui.Button):
    def __init__(self, user_id: int, reminder_id: str, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.danger)
        self.user_id = user_id
        self.reminder_id = reminder_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only cancel your own reminders!")
            return

        reminders = user_reminders.get(self.user_id, [])
        new_list = [r for r in reminders if r["id"] != self.reminder_id]
        if len(new_list) != len(reminders):
            user_reminders[self.user_id] = new_list
            await interaction.response.send_message("❌ Reminder canceled.")
        else:
            await interaction.response.send_message("Reminder not found.")

class RemindersListView(discord.ui.View):
    def __init__(self, user_id: int, reminders: List[Dict]):
        super().__init__(timeout=None)
        for reminder in reminders:
            self.add_item(CancelButton(user_id, reminder["id"], f"Cancel: {reminder['task']}"))


@bot.tree.command(name="remind", description="Set a reminder with a task and time (in minutes).")
@app_commands.describe(task="What should I remind you about?", minutes="When to remind you (in minutes)")
async def remind(interaction: discord.Interaction, task: str, minutes: int):
    if minutes <= 0:
        await interaction.response.send_message("Minutes must be greater than 0.")
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
@bot.tree.command(name="reminders", description="List of your active reminders.")
async def reminders(interaction: discord.Interaction):
    reminders = user_reminders.get(interaction.user.id, [])

    if not reminders:
        await interaction.response.send_message("You have no active reminders.")
        return

    embed = discord.Embed(title="⏳ Your Reminders", color=discord.Color.pink())
    for r in reminders:
        embed.add_field(
            name=f"• {r['task']}",
            value=f"In {r['minutes']} minute(s)",
            inline=False
        )

    view = RemindersListView(interaction.user.id, reminders)
    await interaction.response.send_message(embed=embed, view=view)



# dictionary slash command
@bot.tree.command(name="define", description="Look up a word in the dictionary.")
@app_commands.describe(word="The word you want to look up")
async def define(interaction: discord.Interaction, word: str):
    await interaction.response.defer()  # Show loading

    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                await interaction.followup.send(f"❌ Could not find the word **{word}**.")
                return

            data = await response.json()

    try:
        entry = data[0]
        word_text = entry["word"]
        phonetics = entry.get("phonetic", "")
        meanings = entry["meanings"]

        embed = discord.Embed(
            title=f"📖 Definition of {word_text}",
            color=discord.Color.pink()
        )

        if phonetics:
            embed.set_footer(text=f"Phonetic: {phonetics}")

        count = 0
        for meaning in meanings:
            part_of_speech = meaning["partOfSpeech"]
            for definition_data in meaning["definitions"]:
                definition = definition_data["definition"]
                example = definition_data["example"]
                synonym = definition_data.get("synonyms")

                embed.add_field(
                    name=f"({part_of_speech}) {definition}",
                    value=f"_Synonym:_ {synonym} \n_Example:_ {example}",
                    inline=False
                )
                count += 1
                if count >= 10:
                    break
            if count >= 10:
                break

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error parsing dictionary API response: {e}")
        await interaction.followup.send("⚠️ Something went wrong while parsing the definition.")



#snipe command
@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return
    sniped_messages[message.channel.id] = {
        "content": message.content,
        "author": message.author,
        "time": message.created_at,
        "attachments": [att.url for att in message.attachments] if message.attachments else []
    }


@bot.tree.command(name="snipe", description="Snipe the last deleted message in this channel.")
async def snipe(interaction: discord.Interaction):
    data = sniped_messages.get(interaction.channel.id)

    if not data:
        await interaction.response.send_message("There's nothing to snipe!")
        return

    embed = discord.Embed(
        title="💬 Sniped Message",
        description=data["content"] or "*No content*",
        color=discord.Color.pink(),
        timestamp=data["time"]
    )
    embed.set_author(name=str(data["author"]), icon_url=data["author"].display_avatar.url)

    if data["attachments"]:
        embed.set_image(url=data["attachments"][0])

    await interaction.response.send_message(embed=embed)


# Water reminder loop every 60 minutes
@bot.tree.command(name="sethydrationchannel", description="Set the channel to receive water reminders.")
@app_commands.describe(channel="The channel where water reminders should be sent.")
async def sethydrationchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can set the hydration channel.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    hydration_channels[guild_id] = channel.id
    await interaction.response.send_message(f"✅ Water reminders will now be sent to {channel.mention} every 60 minutes.")

@tasks.loop(minutes=60)
async def water_reminder():
    for guild_id, channel_id in hydration_channels.items():
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await channel.send("💧 dink water @ladies :3")
            except Exception as e:
                print(f"Failed to send reminder to {channel.name} in {guild_id}: {e}")


# Sync commands and start loop
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="AT THE YACHTED CLUB"))
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    if not water_reminder.is_running():
        water_reminder.start()
        print("✅ Water reminder loop started.")



# Run the bot
webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
