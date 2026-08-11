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
# [관리자 고유 ID 설정]
# 여기에 명령어를 사용할 수 있는 관리자들의 ID를 넣습니다.
# ==========================================
ADMIN_IDS = [1529055485964320839, 1429412320194592811]

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

# 웹사이트에서 상태를 크롤링해오는 함수
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
                        element = soup.find(string=lambda text: text and name.lower() in text.lower())
                        if element:
                            container = element.find_parent(['tr', 'div', 'article', 'section'])
                            container_text = container.get_text().upper() if container else element.find_parent().get_text().upper()
                            
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
    # 1. 봇의 이전 메시지 삭제 시도 (권한 없으면 무시)
    try:
        async for message in channel.history(limit=5):
            if message.author == bot.user:
                await message.delete()
                break
    except Exception as e:
        print(f"이전 메시지 삭제/조회 권한 없음 (무시됨): {e}")
        pass

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
    
    # 2. 메시지 전송 시도
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"메시지 전송 권한 없음: {e}")

@tasks.loop(hours=6)
async def auto_update_status():
    if not TARGET_CHANNEL_ID:
        return
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel:
        await send_status_message(channel)

@bot.command(name='상태')
async def show_status(ctx):
    # 관리자 확인: 요청한 사람의 ID가 ADMIN_IDS 목록에 없으면 무시
    if ctx.author.id not in ADMIN_IDS:
        return # 권한이 없는 경우 아무 반응 없이 조용히 종료합니다.
        
    await send_status_message(ctx.channel)
    
    # 명령어를 입력한 관리자의 '!상태' 메시지 삭제 시도 (권한 없으면 무시)
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")
    if not auto_update_status.is_running():
        auto_update_status.start()

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("에러: DISCORD_TOKEN이 설정되지 않았습니다. 환경변수 설정을 확인해주세요.")