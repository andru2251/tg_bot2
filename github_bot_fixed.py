import os
import asyncio
import pandas as pd
import re
from datetime import datetime, timedelta
from aiogram import Bot

API_TOKEN = os.getenv('API_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FILE_NAME = '5 курс 8 фак осень 26-27.xlsx'

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

MONTHS_RU_REV = {
    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
    'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
    'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
}

DAYS_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда",
    3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}

# Column positions for each weekday (0=Mon..5=Sat):
# Lesson columns: start_col = 1 + weekday*3, so Mon=[1,2,3], Tue=[4,5,6], etc.
# Date (day number) is always in the LAST lesson col of each day group
# Month name is always in the FIRST lesson col of each day group
DAY_DATE_COL  = [3, 6, 9, 12, 15, 18]   # column holding the day number
DAY_MONTH_COL = [1, 4, 7, 10, 13, 16]   # column holding the month name


def clean_subj(s):
    return re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', str(s)).lower()


def parse_metadata(meta_str):
    s = str(meta_str).strip().lower()
    if s == 'nan' or not s:
        return ""
    match = re.search(r'(\d+)\s+(\d+)\s+([а-яa-z/]+)', s)
    if match:
        return f"({match.group(1)} т {match.group(2)} {match.group(3)})"
    return f"({s})"


def find_date_row(df, target_date):
    """
    Locate the header row that contains target_date and return
    (row_index, weekday_index 0-5) or (-1, -1) if not found.

    Layout per date-row:
        col 0  = week number
        col 1  = month for Mon,  col 3  = day for Mon
        col 4  = month for Tue,  col 6  = day for Tue
        col 7  = month for Wed,  col 9  = day for Wed
        col 10 = month for Thu,  col 12 = day for Thu
        col 13 = month for Fri,  col 15 = day for Fri
        col 16 = month for Sat,  col 18 = day for Sat
    """
    target_day = str(target_date.day)
    target_month = target_date.month

    for r in range(df.shape[0]):
        for wd in range(6):
            date_col  = DAY_DATE_COL[wd]
            month_col = DAY_MONTH_COL[wd]
            if date_col >= df.shape[1]:
                continue
            day_val   = str(df.iloc[r, date_col]).strip()
            month_str = str(df.iloc[r, month_col]).strip().lower()
            if day_val == target_day and MONTHS_RU_REV.get(month_str) == target_month:
                return r, wd
    return -1, -1


def get_schedule_for_date(df, target_date):
    """Return list of lesson dicts for group 7-21 on target_date."""
    if target_date.weekday() > 5:   # Sunday — no lessons
        return []

    date_row, wd = find_date_row(df, target_date)
    if date_row == -1:
        return []

    start_col = 1 + (wd * 3)
    cols = [start_col, start_col + 1, start_col + 2]

    # Find the row for group 7-21 within 25 rows after the date header
    base_row = -1
    for r in range(date_row, min(date_row + 25, df.shape[0])):
        if '7-21' in str(df.iloc[r, 0]):
            base_row = r
            break

    if base_row == -1:
        return []

    lessons = []
    for i, c in enumerate(cols):
        if c >= df.shape[1]:
            continue

        subj = str(df.iloc[base_row, c]).strip()
        if not subj or subj.lower() == 'nan' or len(subj) <= 1:
            continue

        # Row above group row holds meta-info (type, audience, count)
        meta_val = str(df.iloc[base_row - 1, c]).strip()
        meta = "" if meta_val.lower() == 'nan' else meta_val

        # Row below group row holds the room
        room_val = str(df.iloc[base_row + 1, c]).strip()
        room = "" if room_val.lower() == 'nan' else room_val

        lessons.append({'idx': i + 1, 'subj': subj, 'meta': meta, 'room': room})

    return lessons


def format_lessons(lessons):
    if not lessons:
        return ""
    merged = []
    for l in lessons:
        s_key = clean_subj(l['subj'])
        if merged and merged[-1]['subj_key'] == s_key:
            merged[-1]['indices'].append(l['idx'])
            if len(str(l['meta'])) > len(str(merged[-1]['meta'])):
                merged[-1]['meta'] = l['meta']
            if len(str(l['room'])) > len(str(merged[-1]['room'])):
                merged[-1]['room'] = l['room']
        else:
            merged.append({
                'indices': [l['idx']],
                'subj': l['subj'],
                'subj_key': s_key,
                'meta': l['meta'],
                'room': l['room']
            })

    res = ""
    for m in merged:
        idx_str  = f"{m['indices'][0]}-{m['indices'][-1]}" if len(m['indices']) > 1 else f"{m['indices'][0]}"
        meta_part = f" {parse_metadata(m['meta'])}" if m['meta'] else ""
        room_part = f" {m['room']}" if m['room'] else ""
        res += f"• {idx_str} пара: {m['subj']}{meta_part}{room_part}\n"
    return res


async def main():
    bot = Bot(token=API_TOKEN)

    if not os.path.exists(FILE_NAME):
        return

    # FIX 1: 7-21 is on sheet index 0 ('7,8,7и спец'), not sheet index 2
    try:
        df = pd.read_excel(FILE_NAME, header=None, sheet_name=0)
    except Exception:
        df = pd.read_excel(FILE_NAME, header=None)

    # Target date: tomorrow (Moscow time UTC+3)
    target = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    if target.weekday() == 6:       # skip Sunday
        target += timedelta(days=1)

    today_lessons = get_schedule_for_date(df, target)
    day_name = DAYS_RU[target.weekday()]

    final_text = (
        f"📅 **Расписание на завтра "
        f"({target.day} {MONTHS_RU[target.month]}, {day_name}):**\n\n"
    )
    final_text += format_lessons(today_lessons) if today_lessons else "Пар не найдено. 🎉\n"

    # ВАЖНОЕ: ближайшие 2 учебных дня после завтра (без лекций и ГЗ)
    important_content = ""
    found_days, offset = 0, 1
    while found_days < 2 and offset < 10:
        check_date = target + timedelta(days=offset)
        offset += 1
        if check_date.weekday() == 6:
            continue

        f_lessons = get_schedule_for_date(df, check_date)
        vazhno = [
            l for l in f_lessons
            if not any(
                x in str(l['meta']).lower()
                for x in [' л', 'л ', 'гз']
            )
            and str(l['meta']).lower().strip() != 'л'
        ]

        if vazhno:
            v_day_name = DAYS_RU[check_date.weekday()]
            important_content += f"\n📍 {v_day_name}, {check_date.day} {MONTHS_RU[check_date.month]}:\n"
            important_content += format_lessons(vazhno)
        found_days += 1

    if important_content:
        final_text += f"\n⚠️ **ВАЖНО:**\n{important_content}"

    await bot.send_message(CHAT_ID, final_text, parse_mode="Markdown")
    session = await bot.get_session()
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
