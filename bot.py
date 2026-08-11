import os
from datetime import datetime
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

# 2. 디스코드 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 환경 변수에서 토큰과 채널 ID 불러오기
TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

# ==========================================
# [관리자 고유 ID 설정]
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

# 정확하게 상태를 대조해서 읽어오는 크롤링 함수
async def fetch_statuses():
    urls = [
        "https://www.executors.online/executors",
        "https://whatexpsare.online/"
    ]
    is_working = {name: False for name in EXECUTOR_LINKS.keys()}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        for name in EXECUTOR_LINKS.keys():
                            # 사이트 내에서 해당 이름이 포함된 모든 태그 혹은 문자열 검색
                            elements = soup.find_all(string=lambda text: text and name.lower() in text.lower())
                            for el in elements:
                                parent = el.find_parent()
                                if parent:
                                    # 부모 및 주변 형제 요소의 텍스트를 모두 합쳐서 검사
                                    context_text = parent.get_text() + " " + "".join([s.get_text() for s in parent.find_next_siblings()])
                                    context_text = context_text.lower()
                                    
                                    # 명확하게 작동 중을 뜻하는 단어가 있을 때만 True로 설정
                                    if "working" in context_text or "online" in context_text or "updated" in context_text:
                                        # 단, 'not working'이나 'offline'이 포함된 경우는 제외
                                        if "not working" not in context_text and "offline" not in context_text and "patched" not in context_text:
                                            is_working[name] = True
            except Exception as e:
                print(f"사이트 {url} 체크 중 오류 발생: {e}")
    
    return {name: "🟢" if is_working[name] else "🔴" for name in EXECUTOR_LINKS.keys()}

# 상태 메시지 전송 및 갱신 함수
async def send_status_message(channel):
    try:
        async for message in channel.history(limit=5):
            if message.author == bot.user:
                await message.delete()
                break
    except Exception as e:
        print(f"이전 메시지 삭제/조회 권한 없음 (무시됨): {e}")

    statuses = await fetch_statuses()
    date_str = datetime.now().strftime("%Y-%m-%d")

    description = (
        f"📅 **마지막 갱신 날짜:** `{date_str}`\n\n"
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
        print("에러: 'image_3.png' 파일을 찾을 수 없습니다. 텍스트만 전송합니다.")
        await channel.send(embed=embed)
    except Exception as e:
        print(f"메시지 전송 중 오류 발생: {e}")

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
        print("상태 메시지를 전송합니다...")
        await send_status_message(target_channel)
        print("상태 메시지 전송 완료.")
    else:
        print(f"에러: ID가 {TARGET_CHANNEL_ID}인 채널을 찾을 수 없습니다.")

    if not auto_update_status.is_running():
        auto_update_status.start()

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("에러: DISCORD_TOKEN이 설정되지 않았습니다.")