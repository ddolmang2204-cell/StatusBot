import os
from datetime import datetime
import discord
from discord.ext import tasks, commands
from flask import Flask
from threading import Thread
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

ADMIN_IDS = [1529055485964320839, 1429412320194592811]

EXECUTOR_LINKS = {
    "Potassium": "https://www.potassium.pro/",
    "SirHurt": "https://sirhurt.net/",
    "Volt": "https://voltbz.net/",
    "Wave": "https://getwave.gg/",
    "Synapse Z": "https://z.synapse.do/",
    "Cosmic": "https://cosmic.best/",
    "Xeno": "https://www.xeno.now/",
    "Velocity": "https://getvelocity.llc/",
    "Solara": "https://getsolara.dev/",
    "Madium": "https://getmadium.net/",
    "Real": "https://projectreal.gg/",
    "MacSploit": "https://www.raptor.fun/",
    "Opiumware": "https://use.opiumware.today/",
}

async def fetch_statuses():
    is_working = {name: False for name in EXECUTOR_LINKS.keys()}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        # 1. whatexpsare.online 체크 (Updated / Not Updated 기준)
        try:
            async with session.get("https://whatexpsare.online/", headers=headers, timeout=10) as response:
                if response.status == 200:
                    soup = BeautifulSoup(await response.text(), 'html.parser')
                    for name in EXECUTOR_LINKS.keys():
                        for element in soup.find_all(string=lambda t: t and name.lower() in t.lower()):
                            container = element.find_parent(['div', 'tr', 'article', 'li', 'section'])
                            if container:
                                text = container.get_text().lower()
                                if "updated" in text and "not updated" not in text:
                                    is_working[name] = True
                                    break
        except Exception as e:
            print(f"whatexpsare.online 정밀 체크 오류: {e}")

        # 2. executors.online 체크 (Working / Offline / Patched 기준)
        try:
            async with session.get("https://www.executors.online/executors", headers=headers, timeout=10) as response:
                if response.status == 200:
                    soup = BeautifulSoup(await response.text(), 'html.parser')
                    for name in EXECUTOR_LINKS.keys():
                        for element in soup.find_all(string=lambda t: t and name.lower() in t.lower()):
                            container = element.find_parent(['div', 'tr', 'article', 'li', 'section'])
                            if container:
                                text = container.get_text().lower()
                                if ("working" in text or "online" in text) and not any(bad in text for bad in ["offline", "patched", "not working", "detected"]):
                                    is_working[name] = True
                                    break
        except Exception as e:
            print(f"executors.online 정밀 체크 오류: {e}")
    
    return {name: "🟢" if is_working[name] else "🔴" for name in EXECUTOR_LINKS.keys()}

async def send_status_message(channel):
    try:
        async for message in channel.history(limit=5):
            if message.author == bot.user:
                await message.delete()
                break
    except Exception as e:
        print(f"메시지 삭제 오류: {e}")

    statuses = await fetch_statuses()
    date_str = datetime.now().strftime("%Y-%m-%d")

    description = (
        f" **마지막 갱신 날짜:** `{date_str}`\n\n"
        "**Windows [윈도우]**\n\n"
        f"• **Potassium** / {{유료}}: [바로가기]({EXECUTOR_LINKS['Potassium']}) {statuses.get('Potassium', '🔴')}\n"
        f"• **SirHurt** / {{유료}}: [바로가기]({EXECUTOR_LINKS['SirHurt']}) {statuses.get('SirHurt', '🔴')}\n"
        f"• **Volt** / {{유료}}: [바로가기]({EXECUTOR_LINKS['Volt']}) {statuses.get('Volt', '🔴')}\n"
        f"• **Wave** / {{유료}}: [바로가기]({EXECUTOR_LINKS['Wave']}) {statuses.get('Wave', '🔴')}\n"
        f"• **Synapse Z** / {{유료}}: [바로가기]({EXECUTOR_LINKS['Synapse Z']}) {statuses.get('Synapse Z', '🔴')}\n"
        f"• **Cosmic** / {{유료}}: [바로가기]({EXECUTOR_LINKS['Cosmic']}) {statuses.get('Cosmic', '🔴')}\n\n"
        f"• **Xeno** / 무료: [바로가기]({EXECUTOR_LINKS['Xeno']}) {statuses.get('Xeno', '🔴')}\n"
        f"• **Velocity** / 무료/키필요: [바로가기]({EXECUTOR_LINKS['Velocity']}) {statuses.get('Velocity', '🔴')}\n"
        f"• **Solara** / 무료: [바로가기]({EXECUTOR_LINKS['Solara']}) {statuses.get('Solara', '🔴')}\n"
        f"• **Madium** / 무료/키필요: [바로가기]({EXECUTOR_LINKS['Madium']}) {statuses.get('Madium', '🔴')}\n"
        f"• **Real** / 무료/키필요: [바로가기]({EXECUTOR_LINKS['Real']}) {statuses.get('Real', '🔴')}\n\n"
        "────────────────────────\n\n"
        "**Mac [맥]**\n\n"
        f"• **MacSploit** / {{유료}}: [바로가기]({EXECUTOR_LINKS['MacSploit']}) {statuses.get('MacSploit', '🔴')}\n\n"
        f"• **Opiumware** / 무료/키필요: [바로가기]({EXECUTOR_LINKS['Opiumware']}) {statuses.get('Opiumware', '🔴')}"
    )

    embed = discord.Embed(title="Scripter Si | Status", color=0x2b2d31)
    embed.description = description
    embed.set_image(url="attachment://scs_logo.png")
    
    try:
        with open('image_3.png', 'rb') as photo:
            file = discord.File(photo, filename='scs_logo.png')
            await channel.send(embed=embed, file=file)
    except FileNotFoundError:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"전송 오류: {e}")

@tasks.loop(hours=6)
async def auto_update_status():
    if not TARGET_CHANNEL_ID:
        return
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel:
        await send_status_message(channel)

@bot.command(name='상태')
async def show_status(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return 
    await send_status_message(ctx.channel)
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")
    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    if target_channel:
        await send_status_message(target_channel)

    if not auto_update_status.is_running():
        auto_update_status.start()

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)