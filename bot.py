import os
import discord
from discord.ext import tasks, commands
from flask import Flask
from threading import Thread
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 로컬 테스트 시 .env 파일 로드
load_dotenv()

# 1. Flask 웹 서버 (UptimeRobot 유지용)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# 2. 디스코드 봇 설정 (명령어 접두사 '!' 사용)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 환경 변수에서 토큰과 채널 ID 불러오기
TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

# ==========================================
# [링크 설정 칸]
# ==========================================
EXECUTOR_LINKS = {
    # Windows
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
    # Mac
    "MacSploit": "https://www.raptor.fun/",
    "Opiumware": "https://use.opiumware.today/",
}

# 웹사이트에서 상태를 크롤링해오는 함수 (개선됨)
async def fetch_statuses():
    url = "https://robloxexecutorstatus.com/"
    statuses = {}
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    for name in EXECUTOR_LINKS.keys():
                        # 이름이 포함된 태그를 찾음
                        element = soup.find(string=lambda text: text and name.lower() in text.lower())
                        if element:
                            # 부모 태그 혹은 형제 태그까지 전체 텍스트를 가져와서 확인
                            container = element.find_parent(['tr', 'div', 'article', 'section'])
                            container_text = container.get_text().upper() if container else element.find_parent().get_text().upper()
                            
                            # 'WORKING' 단어가 들어가 있으면 초록색, 아니면 빨간색
                            if "WORKING" in container_text:
                                statuses[name] = "🟢"
                            else:
                                statuses[name] = "🔴"
                        else:
                            statuses[name] = "🔴"
        except Exception as e:
            print(f"상태 크롤링 중 오류 발생: {e}")
            for name in EXECUTOR_LINKS.keys():
                statuses[name] = "🔴"
                
    return statuses

# 메시지 생성 및 전송 공통 함수
async def send_status_message(channel):
    async for message in channel.history(limit=5):
        if message.author == bot.user:
            await message.delete()
            break

    statuses = await fetch_statuses()

    description = (
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

    embed = discord.Embed(color=0x2b2d31)
    embed.description = description
    await channel.send(embed=embed)

@tasks.loop(hours=6)
async def auto_update_status():
    if not TARGET_CHANNEL_ID:
        return
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel:
        await send_status_message(channel)

@bot.command(name='상태')
async def show_status(ctx):
    await send_status_message(ctx.channel)
    try:
        await ctx.message.delete()
    except:
        pass

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")
    if not auto_update_status.is_running():
        auto_update_status.start()

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)