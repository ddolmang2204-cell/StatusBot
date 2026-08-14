import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from curl_cffi.requests import AsyncSession

load_dotenv()

# ==================== 로깅 설정 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== 상수 정의 ====================
KST = timezone(timedelta(hours=9))

FETCH_TIMEOUT = 15
HISTORY_LIMIT = 100
UPDATE_INTERVAL_HOURS = 6
UPDATE_THRESHOLD_SECONDS = 21000
MAX_RETRIES = 2
RETRY_BACKOFF_BASE = 2
REQUEST_DELAY = 1

CACHE_TTL = 3600

# ==================== 상태 이모지 ====================
GREEN_STATUS = "<:639945verifiedbadge:1537724052666454126>"
RED_STATUS = "<:12870loading:1537724065970782258>"

LOGO_URL = os.environ.get("LOGO_URL", "")

# ==================== WEAO 설정 ====================
# executors.online은 사용하지 않습니다.
WEAO_API_URL = "https://whatexpsare.online/api/status/exploits"

# WEAO API는 지정된 User-Agent를 요구합니다.
WEAO_HEADERS = {
    "User-Agent": "WEAO-3PService",
    "Accept": "application/json",
}

# Discord에 표시할 항목과 WEAO의 title을 정확하게 연결합니다.
# WEAO API의 updateStatus=True -> GREEN_STATUS
# WEAO API의 updateStatus=False -> RED_STATUS
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

# WEAO에서 현재 제공하지 않거나 이름이 바뀐 항목이 있어도
# Discord 메시지의 기존 목록은 유지합니다.
EXECUTOR_ALIASES = {
    "Potassium": {"potassium"},
    "SirHurt": {"sirhurt"},
    "Volt": {"volt"},
    "Wave": {"wave"},
    "Synapse Z": {"synapse z", "synapsez"},
    "Cosmic": {"cosmic"},
    "Xeno": {"xeno"},
    "Velocity": {"velocity"},
    "Solara": {"solara"},
    "Madium": {"madium"},
    "Real": {"real"},
    "MacSploit": {"macsploit"},
    "Opiumware": {"opiumware"},
}


# ==================== Discord 봇 설정 ====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = list(map(int, ADMIN_IDS_STR.split(","))) if ADMIN_IDS_STR else []


# ==================== 상태 캐싱 ====================
class StatusCache:
    def __init__(self, ttl=CACHE_TTL):
        self.data = None
        self.timestamp = None
        self.ttl = ttl

    def get(self):
        """캐시된 데이터 조회"""
        if self.data is None or self.timestamp is None:
            return None

        elapsed = (
            datetime.now(timezone.utc) - self.timestamp
        ).total_seconds()

        if elapsed > self.ttl:
            logger.debug(
                f"캐시 만료 ({elapsed:.0f}초 > {self.ttl}초)"
            )
            self.data = None
            self.timestamp = None
            return None

        logger.debug(
            f"캐시 사용 (경과: {elapsed:.0f}초/{self.ttl}초)"
        )
        return self.data

    def set(self, data):
        """캐시 데이터 저장"""
        self.data = data
        self.timestamp = datetime.now(timezone.utc)
        logger.info(f"캐시 저장: {len(data)} 항목")

    def invalidate(self):
        """캐시 무효화"""
        self.data = None
        self.timestamp = None


status_cache = StatusCache(ttl=CACHE_TTL)


# ==================== WEAO API ====================
async def fetch_weao_with_retry(session, max_retries=MAX_RETRIES):
    """WEAO 상태 API를 재시도 포함으로 조회"""
    for attempt in range(max_retries):
        try:
            logger.info(
                f"[WEAO] API 요청 시도 "
                f"{attempt + 1}/{max_retries}"
            )

            response = await session.get(
                WEAO_API_URL,
                headers=WEAO_HEADERS,
                impersonate="chrome120",
                timeout=FETCH_TIMEOUT,
            )

            if response.status_code == 200:
                logger.info("[WEAO] API 응답 성공")
                return response

            if response.status_code == 429:
                logger.warning(
                    "[WEAO] 429 Too Many Requests - "
                    "요청 간격을 늘리는 것을 권장합니다."
                )
            else:
                logger.warning(
                    f"[WEAO] HTTP {response.status_code}"
                )

        except asyncio.TimeoutError:
            logger.warning(
                f"[WEAO] 타임아웃 (>{FETCH_TIMEOUT}초)"
            )

        except Exception as e:
            logger.error(
                f"[WEAO] {type(e).__name__}: {e}"
            )

        if attempt < max_retries - 1:
            wait_time = RETRY_BACKOFF_BASE ** attempt
            logger.info(
                f"[WEAO] {wait_time}초 후 재시도..."
            )
            await asyncio.sleep(wait_time)

    logger.error("[WEAO] 모든 재시도 실패")
    return None


def normalize_name(name):
    """executor 이름 비교용 정규화"""
    return (
        str(name)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def find_weao_executor(items, executor_name):
    """WEAO 응답에서 지정 executor를 찾습니다."""
    aliases = EXECUTOR_ALIASES.get(
        executor_name,
        {normalize_name(executor_name)}
    )

    normalized_aliases = {
        normalize_name(alias) for alias in aliases
    }

    # 1차: 정확한 title 매칭
    for item in items:
        if not isinstance(item, dict):
            continue

        title = normalize_name(item.get("title", ""))
        if title in normalized_aliases:
            return item

    # 2차: 공백 등을 무시한 보조 매칭
    compact_aliases = {
        alias.replace(" ", "")
        for alias in normalized_aliases
    }

    for item in items:
        if not isinstance(item, dict):
            continue

        title = normalize_name(item.get("title", ""))
        if title.replace(" ", "") in compact_aliases:
            return item

    return None


def parse_weao_status(items):
    """
    WEAO API의 updateStatus 값을 그대로 사용합니다.

    True  -> GREEN_STATUS
    False -> RED_STATUS
    항목 없음 -> RED_STATUS

    HTML 문구나 'online/working' 같은 추측성 문자열은
    사용하지 않습니다.
    """
    result = {}

    for executor_name in EXECUTOR_LINKS:
        item = find_weao_executor(items, executor_name)

        if item is None:
            logger.warning(
                f"[WEAO] {executor_name}: API에서 항목을 찾지 못함"
            )
            result[executor_name] = RED_STATUS
            continue

        update_status = item.get("updateStatus")

        if isinstance(update_status, bool):
            result[executor_name] = (
                GREEN_STATUS if update_status else RED_STATUS
            )
            logger.info(
                f"[WEAO] {executor_name}: "
                f"{'✅ Updated' if update_status else '❌ Not Updated'}"
            )
        else:
            logger.warning(
                f"[WEAO] {executor_name}: "
                f"updateStatus 값이 없음/비정상 "
                f"({update_status!r})"
            )
            result[executor_name] = RED_STATUS

    return result


async def fetch_statuses(force=False):
    """WEAO에서 모든 executor 상태 조회"""
    if not force:
        cached = status_cache.get()
        if cached is not None:
            return cached

    # WEAO API는 한 번만 요청합니다.
    # 불필요하게 사이트를 반복 크롤링하지 않습니다.
    await asyncio.sleep(REQUEST_DELAY)

    async with AsyncSession() as session:
        response = await fetch_weao_with_retry(session)

        if response is None:
            logger.error(
                "[WEAO] 상태 데이터를 가져오지 못했습니다."
            )
            return {
                name: RED_STATUS
                for name in EXECUTOR_LINKS
            }

        try:
            data = response.json()
        except Exception as e:
            logger.error(
                f"[WEAO] JSON 파싱 실패: {e}"
            )
            logger.debug(
                f"[WEAO] 응답 내용: {response.text[:1000]}"
            )
            return {
                name: RED_STATUS
                for name in EXECUTOR_LINKS
            }

        if not isinstance(data, list):
            logger.error(
                f"[WEAO] 예상하지 못한 API 응답 형식: "
                f"{type(data).__name__}"
            )
            return {
                name: RED_STATUS
                for name in EXECUTOR_LINKS
            }

        result = parse_weao_status(data)
        status_cache.set(result)

        logger.info(
            "[최종 결과]\n"
            + json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            )
        )

        return result


# ==================== 메시지 전송 ====================
async def send_status_message(channel, force=False):
    """상태 메시지 전송/갱신"""
    existing_msg = None

    try:
        async for message in channel.history(
            limit=HISTORY_LIMIT
        ):
            if message.author == bot.user:
                existing_msg = message
                break
    except Exception as e:
        logger.error(f"메시지 검색 오류: {e}")

    if not force and existing_msg:
        now = datetime.now(timezone.utc)
        elapsed_seconds = (
            now - existing_msg.created_at
        ).total_seconds()

        if elapsed_seconds < UPDATE_THRESHOLD_SECONDS:
            logger.info(
                f"갱신 스킵 "
                f"(경과: {elapsed_seconds:.0f}초 "
                f"< {UPDATE_THRESHOLD_SECONDS}초)"
            )
            return

    try:
        statuses = await fetch_statuses(force=force)
    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        return

    date_str = datetime.now(KST).strftime(
        "%Y-%m-%d %H:%M"
    )

    description = (
        f"📅 **마지막 갱신:** `{date_str}`\n\n"
        "**Windows [윈도우]**\n\n"
        f"• **Potassium** / {{유료}}: "
        f"[바로가기]({EXECUTOR_LINKS['Potassium']}) "
        f"{statuses.get('Potassium', RED_STATUS)}\n"
        f"• **SirHurt** / {{유료}}: "
        f"[바로가기]({EXECUTOR_LINKS['SirHurt']}) "
        f"{statuses.get('SirHurt', RED_STATUS)}\n"
        f"• **Volt** / {{유료}}: "
        f"[바로가기]({EXECUTOR_LINKS['Volt']}) "
        f"{statuses.get('Volt', RED_STATUS)}\n"
        f"• **Wave** / {{유료}}: "
        f"[바로가기]({EXECUTOR_LINKS['Wave']}) "
        f"{statuses.get('Wave', RED_STATUS)}\n"
        f"• **Synapse Z** / {{유료}}: "
        f"[바로가기]({EXECUTOR_LINKS['Synapse Z']}) "
        f"{statuses.get('Synapse Z', RED_STATUS)}\n"
        f"• **Cosmic** / {{유료}}: "
        f"[바로가기]({EXECUTOR_LINKS['Cosmic']}) "
        f"{statuses.get('Cosmic', RED_STATUS)}\n\n"
        f"• **Xeno** / 무료: "
        f"[바로가기]({EXECUTOR_LINKS['Xeno']}) "
        f"{statuses.get('Xeno', RED_STATUS)}\n"
        f"• **Velocity** / 무료/키필요: "
        f"[바로가기]({EXECUTOR_LINKS['Velocity']}) "
        f"{statuses.get('Velocity', RED_STATUS)}\n"
        f"• **Solara** / 무료: "
        f"[바로가기]({EXECUTOR_LINKS['Solara']}) "
        f"{statuses.get('Solara', RED_STATUS)}\n"
        f"• **Madium** / 무료/키필요: "
        f"[바로가기]({EXECUTOR_LINKS['Madium']}) "
        f"{statuses.get('Madium', RED_STATUS)}\n"
        f"• **Real** / 무료/키필요: "
        f"[바로가기]({EXECUTOR_LINKS['Real']}) "
        f"{statuses.get('Real', RED_STATUS)}\n\n"
        "────────────────────────\n\n"
        "**Mac [맥]**\n\n"
        f"• **MacSploit** / {{유료}}: "
        f"[바로가기]({EXECUTOR_LINKS['MacSploit']}) "
        f"{statuses.get('MacSploit', RED_STATUS)}\n\n"
        f"• **Opiumware** / 무료/키필요: "
        f"[바로가기]({EXECUTOR_LINKS['Opiumware']}) "
        f"{statuses.get('Opiumware', RED_STATUS)}"
    )

    embed = discord.Embed(
        title="Scripter Si | Status",
        color=0x2b2d31
    )
    embed.description = description

    if LOGO_URL:
        embed.set_image(url=LOGO_URL)

    if existing_msg:
        try:
            await existing_msg.edit(embed=embed)
            logger.info("메시지 수정 완료")
            return
        except Exception as e:
            logger.error(
                f"메시지 수정 실패: {e}, "
                "재전송 시도 중..."
            )

            try:
                await existing_msg.delete()
            except Exception as delete_err:
                logger.error(
                    f"메시지 삭제 실패: {delete_err}"
                )

    try:
        await channel.send(embed=embed)
        logger.info("새 메시지 전송 완료")
    except Exception as e:
        logger.error(f"메시지 전송 실패: {e}")


# ==================== 태스크 및 명령어 ====================
@tasks.loop(hours=UPDATE_INTERVAL_HOURS)
async def auto_update_status():
    """자동 상태 갱신"""
    if not TARGET_CHANNEL_ID:
        return

    channel = bot.get_channel(TARGET_CHANNEL_ID)

    if not channel:
        logger.error(
            f"채널 조회 실패: {TARGET_CHANNEL_ID}"
        )
        return

    logger.info(
        f"자동 갱신 시작 (채널: {channel.name})"
    )
    await send_status_message(
        channel,
        force=False
    )


@bot.command(name="상태")
@commands.has_permissions(administrator=True)
async def show_status(ctx):
    """수동 상태 갱신 명령어"""
    logger.info(
        f"상태 갱신 명령: "
        f"{ctx.author} ({ctx.author.id})"
    )

    await send_status_message(
        ctx.channel,
        force=True
    )

    try:
        await ctx.message.delete()
    except Exception as e:
        logger.debug(
            f"명령어 메시지 삭제 실패: {e}"
        )


@show_status.error
async def show_status_error(ctx, error):
    """명령어 오류 처리"""
    if isinstance(
        error,
        commands.MissingPermissions
    ):
        logger.warning(
            f"권한 없음 - "
            f"{ctx.author}가 !상태 명령어 시도"
        )
        await ctx.send(
            "⚠️ 이 명령어는 관리자만 사용할 수 있습니다.",
            delete_after=5
        )
    else:
        logger.error(
            f"명령어 오류: {error}"
        )
        await ctx.send(
            "❌ 명령어 실행 중 오류가 발생했습니다.",
            delete_after=5
        )


@bot.command(name="캐시초기화")
@commands.has_permissions(administrator=True)
async def clear_cache(ctx):
    """캐시 초기화"""
    logger.info(
        f"캐시 초기화 명령: {ctx.author}"
    )

    status_cache.invalidate()

    await ctx.send(
        "✅ 캐시가 초기화되었습니다. "
        "다음 갱신 시 WEAO에서 새로 조회합니다.",
        delete_after=5
    )

    try:
        await ctx.message.delete()
    except Exception:
        pass


@clear_cache.error
async def clear_cache_error(ctx, error):
    """캐시 초기화 명령 오류 처리"""
    if isinstance(
        error,
        commands.MissingPermissions
    ):
        await ctx.send(
            "⚠️ 이 명령어는 관리자만 사용할 수 있습니다.",
            delete_after=5
        )
    else:
        logger.error(
            f"캐시 초기화 오류: {error}"
        )


# ==================== 이벤트 ====================
@bot.event
async def on_ready():
    """봇 준비 완료"""
    logger.info(
        f"로그인 성공: "
        f"{bot.user.name} ({bot.user.id})"
    )

    if not auto_update_status.is_running():
        logger.info("자동 갱신 태스크 시작")
        auto_update_status.start()


@bot.event
async def on_error(event, *args, **kwargs):
    """전역 오류 핸들러"""
    logger.error(
        f"이벤트 오류 [{event}]:",
        exc_info=True
    )


# ==================== 메인 ====================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info(
        "Discord Executor Status Bot 시작 "
        "(WEAO API 버전 - UptimeRobot)"
    )
    logger.info("=" * 70)

    if not TOKEN:
        logger.error(
            "❌ DISCORD_TOKEN이 설정되지 않음"
        )
        raise SystemExit(1)

    if not TARGET_CHANNEL_ID:
        logger.warning(
            "⚠️ CHANNEL_ID가 설정되지 않음 "
            "(자동 갱신 비활성화)"
        )

    if not ADMIN_IDS:
        logger.warning(
            "⚠️ ADMIN_IDS가 설정되지 않음 "
            "(현재 명령어는 Discord 관리자 권한을 사용)"
        )

    if not LOGO_URL:
        logger.warning(
            "⚠️ LOGO_URL이 설정되지 않음 "
            "(이미지 없이 텍스트만 전송)"
        )

    logger.info("설정:")
    logger.info(
        f"  - 채널 ID: {TARGET_CHANNEL_ID}"
    )
    logger.info(
        f"  - 관리자 ID: "
        f"{ADMIN_IDS if ADMIN_IDS else '없음'}"
    )
    logger.info(
        f"  - 갱신 간격: {UPDATE_INTERVAL_HOURS}시간"
    )
    logger.info(
        f"  - 캐시 TTL: {CACHE_TTL}초"
    )
    logger.info(
        f"  - Keep-Alive: UptimeRobot 사용 중"
    )
    logger.info("=" * 70)

    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(
            f"❌ 봇 실행 실패: {e}",
            exc_info=True
        )