Absolutely! Here's a **professional and informative `README.md`** you can use for your Discord bot project:

---

# 💧 Hydration Reminder & Utility Bot

A multipurpose Discord bot built with `discord.py`, providing:

* ⏰ Custom Reminders
* 📚 Dictionary Lookup
* 💬 Snipe Deleted Messages
* 💧 Hourly Water Reminders (server-specific channel and role support)

Hosted on **Render** with uptime monitoring via **UptimeRobot**.

---

 🚀 Features

# 🧠 Reminders

Set personal reminders using slash commands.

```bash
/remind task:"Do homework" hours:2 minutes:30
```

# 📋 View and Cancel Reminders

```bash
/reminders
```

Lists all active reminders with cancel buttons.

# 📚 Dictionary Command

Look up definitions for English words using the Free Dictionary API.

```bash
/define word:"ephemeral"
```

# 💬 Snipe

Retrieve the last deleted message in a channel.

```bash
/snipe
```

# 💧 Water Reminder System

Send automatic hydration reminders every 60 minutes in a **server-specific channel**, tagging a specific **role**.

Commands:

* `/sethydrationchannel` – Set the hydration reminder channel and mention role
* `/pausehydration` – Pause hydration reminders temporarily

---

 🛠️ Installation (for local development)

# 1. Clone the Repository

```bash
git clone https://github.com/yourusername/your-bot.git
cd your-bot
```

# 2. Install Requirements

```bash
pip install -r requirements.txt
```

# 3. Set Environment Variables

Create a `.env` file:

```
DISCORD_TOKEN=your_discord_token_here
```

---

 🌐 Hosting on Render

1. Push your project to GitHub
2. Go to [Render.com](https://render.com/)
3. Create a new **Web Service**:

   * Select your GitHub repo
   * Environment = `Python`
   * Start command: `python main.py`
4. Add an environment variable:

   * `DISCORD_TOKEN`: Your bot's token

# Keep-Alive

Use a lightweight Flask server (`webserver.py`) to prevent timeouts.

python
# webserver.py
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()


This is pinged by UptimeRobot to prevent Render from sleeping.

---

 🟢 Keeping the Bot Alive

Use [UptimeRobot](https://uptimerobot.com/) to ping the Render URL every 5 minutes.

1. Go to UptimeRobot > Create Monitor
2. Monitor Type: `HTTP(s)`
3. URL: `https://your-render-app-name.onrender.com/`
4. Monitoring Interval: `5 minutes`

---

🔐 Permissions

This bot needs the following permissions:

* Send Messages
* Embed Links
* Manage Messages (for future features)
* Use Slash Commands

---

 📄 License

MIT License – feel free to use and modify.
