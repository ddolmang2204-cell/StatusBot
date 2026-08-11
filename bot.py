import os
import discord
from discord.ext import tasks
from flask import Flask
from threading import Thread
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 로컬 테스트 시 .env 파일 로드 (Render 등 서버에서는 자동으로 환경 변수 읽음)
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

# 2. 디스코드 봇 설정 (명령어/접두사 없음)
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# 환경 변수에서 토큰과 채널 ID 불러오기
TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

# ==========================================
# [링크 설정 칸] 각 실행기별 바로가기 주소를 입력하세요!
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

# 웹사이트에서 상태를 크롤링해오는 함수
async def fetch_statuses():
    url = "https://robloxexecutorstatus.com/"
    statuses = {}
    
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    for name in EXECUTOR_LINKS.keys():
                        element = soup.find(string=lambda text: text and name.lower() in text.lower())
                        if element:
                            parent_text = element.find_parent().get_text().upper()
                            if "WORKING" in parent_text:
                                statuses[name] = "🟢"
                            elif "PATCHED" in parent_text:
                                statuses[name] = "🔴"
                            else:
                                statuses[name] = "🔴"
                        else:
                            statuses[name] = "🔴"
        except Exception as e:
            print(f"상태 크롤링 중 오류 발생: {e}")
            for name in EXECUTOR_LINKS.keys():
                statuses[name] = "🔴"
                
    return statuses

# 6시간마다 실행되는 루프 작업
@tasks.loop(hours=6)
async def update_status():
    if not TARGET_CHANNEL_ID:
        return
    
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        return

    # 이전 메시지 삭제 (최근 5개 중 봇이 보낸 것 삭제)
    async for message in channel.history(limit=5):
        if message.author == bot.user:
            await message.delete()
            break

    # 사이트에서 최신 상태 가져오기
    statuses = await fetch_statuses()

    # 메시지 디자인 포맷 구성
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

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")
    if not update_status.is_running():
        update_status.start()

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)