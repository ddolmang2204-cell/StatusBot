import os
from datetime import datetime, timezone
import discord
from discord.ext import tasks, commands
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from curl_cffi.requests import AsyncSession

load_dotenv()

# ==================== Flask 서버 (Render Keep-Alive) ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ==================== Discord 봇 설정 ====================
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

# ==================== 상태 크롤링 (Cloudflare 우회) ====================
async def fetch_statuses():
    is_working = {name: False for name in EXECUTOR_LINKS.keys()}

    async with AsyncSession() as session:
        # 1. whatexpsare.online 체크
        try:
            res = await session.get("https://whatexpsare.online/", impersonate="chrome120", timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for name in EXECUTOR_LINKS.keys():
                    search_names = [name.lower(), name.lower().replace(" ", "")]
                    for element in soup.find_all(string=lambda t: t and any(sn in t.lower() for sn in search_names)):
                        container = element.find_parent(['div', 'tr', 'li', 'section', 'td', 'p'])
                        if container:
                            text = container.get_text(separator=" ", strip=True).lower()
                            if "updated" in text and "not updated" not in text:
                                is_working[name] = True
                                break
            else:
                print(f"[경고] whatexpsare.online 접속 실패: HTTP {res.status_code}")
        except Exception as e:
            print(f"whatexpsare.online 크롤링 오류: {e}")

        # 2. executors.online 체크
        try:
            res = await session.get("https://www.executors.online/executors", impersonate="chrome120", timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for name in EXECUTOR_LINKS.keys():
                    if is_working[name]:
                        continue
                        
                    search_names = [name.lower(), name.lower().replace(" ", "")]
                    for element in soup.find_all(string=lambda t: t and any(sn in t.lower() for sn in search_names)):
                        container = element.find_parent(['div', 'tr', 'li', 'section', 'td', 'p'])
                        if container:
                            text = container.get_text(separator=" ", strip=True).lower()
                            if ("working" in text or "online" in text) and not any(bad in text for bad in ["offline", "patched", "not working", "detected"]):
                                is_working[name] = True
                                break
            else:
                print(f"[경고] executors.online 접속 실패: HTTP {res.status_code}")
        except Exception as e:
            print(f"executors.online 크롤링 오류: {e}")

    return {name: "🟢" if is_working[name] else "🔴" for name in EXECUTOR_LINKS.keys()}

# ==================== 상태 메시지 전송 및 관리 ====================
async def send_status_message(channel, force=False):
    last_msg = None
    try:
        # 가장 최근에 봇이 올렸던 상태 메시지 딱 1개 찾기
        async for message in channel.history(limit=50):
            if message.author == bot.user:
                last_msg = message
                break
    except Exception as e:
        print(f"메시지 조회 오류: {e}")

    # 강제 실행(!상태)이 아닌 자동 루프일 때, 마지막 메시지 발송 후 6시간이 안 지났으면 스킵
    if not force and last_msg:
        now = datetime.now(timezone.utc)
        elapsed_seconds = (now - last_msg.created_at).total_seconds()
        
        # 6시간 = 21,600초 (오차 감안 5시간 50분 = 21,000초 기준)
        if elapsed_seconds < 21000:
            print(f"[알림] 아직 6시간이 지나지 않아 메시지를 생성하지 않습니다. (최근 작성: {int(elapsed_seconds // 60)}분 전)")
            return

    # 기존 봇 메시지가 존재하면 단 1개만 삭제 (Rate Limit 방지)
    if last_msg:
        try:
            await last_msg.delete()
            print("이전 상태 메시지를 성공적으로 삭제했습니다.")
        except Exception as e:
            print(f"메시지 삭제 오류: {e}")

    # 최신 상태 데이터 불러오기
    statuses = await fetch_statuses()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    description = (
        f"📅 **마지막 갱신:** `{date_str}`\n\n"
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

# ==================== 태스크 및 명령어 ====================
@tasks.loop(hours=6)
async def auto_update_status():
    if not TARGET_CHANNEL_ID:
        return
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel:
        await send_status_message(channel, force=False)

@bot.command(name='상태')
async def show_status(ctx):
    if ctx.author.id not in ADMIN_IDS:
        return 
    # !상태 명령어는 6시간 제한을 무시하고 즉시 삭제 후 갱신
    await send_status_message(ctx.channel, force=True)
    try:
        await ctx.message.delete()
    except Exception:
        pass

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")
    
    # 봇 재부팅 시에도 6시간 지났는지 판단 후 필요할 때만 갱신
    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    if target_channel:
        await send_status_message(target_channel, force=False)

    if not auto_update_status.is_running():
        auto_update_status.start()

if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)