import os
import asyncio
import pandas as pd
import re
from datetime import datetime, timedelta
from aiogram import Bot

API_TOKEN = os.getenv('API_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
FILE_NAME = '4 курс 8 фак весна 25-26.xlsx'

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

DAYS_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда",
    3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}

def clean_subj(s):
    return re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', str(s)).lower()

def parse_metadata(meta_str):
    s = str(meta_str).strip().lower()
    if s == 'nan' or not s: return ""
    match = re.search(r'(\d+)\s+(\d+)\s+([а-яa-z/]+)', s)
    if match: return f"({match.group(1)} т {match.group(2)} {match.group(3)})"
    return f"({s})"

def get_schedule_for_date(df, target_date):
    weekday = target_date.weekday()
    if weekday > 5: return [] 
    
    start_col = 1 + (weekday * 3)
    cols = [start_col, start_col + 1, start_col + 2]
    target_day = str(target_date.day)
    
    date_row = -1
    for r in range(df.shape[0]):
        for c in cols:
            if c < df.shape[1]:
                val = str(df.iloc[r, c]).strip().split('.')[0]
                if val == target_day:
                    date_row = r
                    break
        if date_row != -1: break
    
    if date_row == -1: return []

    base_row_721 = -1
    for r in range(date_row, min(date_row + 25, df.shape[0])):
        if "7-21" in str(df.iloc[r, 0]):
            base_row_721 = r
            break
            
    if base_row_721 == -1: return []

    raw_lessons = []
    for i, c in enumerate(cols):
        if c >= df.shape[1]: continue
        
        meta = str(df.iloc[base_row_721 - 1, c]).strip()
        if meta.lower() == 'nan': meta = ""

        check_val = str(df.iloc[base_row_721 + 2, c]).strip().lower()
        is_joint = True if check_val == 'nan' or not check_val else False

        final_subj, final_room = "", ""

        if not is_joint:
            final_subj = str(df.iloc[base_row_721, c]).strip()
            room_val = str(df.iloc[base_row_721 + 1, c]).strip()
            final_room = room_val if room_val.lower() != 'nan' else ""
        else:
            subj_top = str(df.iloc[base_row_721, c]).strip()
            subj_bot = str(df.iloc[base_row_721 + 1, c]).strip()
            final_subj = subj_top if subj_top.lower() != 'nan' and len(subj_top) > 1 else subj_bot
            room_val = str(df.iloc[base_row_721 + 4, c]).strip()
            final_room = room_val if room_val.lower() != 'nan' else ""

        if (not final_subj or final_subj.lower() == 'nan') and i > 0 and raw_lessons:
            final_subj = raw_lessons[-1]['subj']
            meta = raw_lessons[-1]['meta']
            final_room = raw_lessons[-1]['room']

        if final_subj and final_subj.lower() != 'nan' and len(final_subj) > 1:
            raw_lessons.append({'idx': i + 1, 'subj': final_subj, 'meta': meta, 'room': final_room})
            
    return raw_lessons

def format_lessons(lessons):
    if not lessons: return ""
    merged = []
    for l in lessons:
        s_key = clean_subj(l['subj'])
        if merged and merged[-1]['subj_key'] == s_key:
            merged[-1]['indices'].append(l['idx'])
            if len(str(l['meta'])) > len(str(merged[-1]['meta'])): merged[-1]['meta'] = l['meta']
            if len(str(l['room'])) > len(str(merged[-1]['room'])): merged[-1]['room'] = l['room']
        else:
            merged.append({'indices':[l['idx']], 'subj':l['subj'], 'subj_key':s_key, 'meta':l['meta'], 'room':l['room']})
    
    res = ""
    for m in merged:
        idx_str = f"{m['indices'][0]}-{m['indices'][-1]}" if len(m['indices']) > 1 else f"{m['indices'][0]}"
        meta_part = f" {parse_metadata(m['meta'])}" if m['meta'] else ""
        room_part = f" {m['room']}" if m['room'] else ""
        res += f"• {idx_str} пара: {m['subj']}{meta_part}{room_part}\n"
    return res

async def main():
    bot = Bot(token=API_TOKEN)
    if not os.path.exists(FILE_NAME): return
    try:
        df = pd.read_excel(FILE_NAME, header=None, sheet_name=2)
    except:
        df = pd.read_excel(FILE_NAME, header=None)

    # Целевая дата: завтра (с учетом МСК +3)
    target = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    if target.weekday() == 6: target += timedelta(days=1)

    today_lessons = get_schedule_for_date(df, target)
    day_name = DAYS_RU[target.weekday()]
    
    final_text = f"📅 **Расписание на завтра ({target.day} {MONTHS_RU[target.month]}, {day_name}):**\n\n"
    final_text += format_lessons(today_lessons) if today_lessons else "Пар не найдено. 🎉\n"

    # Блок ВАЖНОЕ (на 2 дня вперед от завтра)
    important_content = ""
    found_days, offset = 0, 1
    while found_days < 2 and offset < 10:
        check_date = target + timedelta(days=offset)
        offset += 1
        if check_date.weekday() == 6: continue
        
        f_lessons = get_schedule_for_date(df, check_date)
        # Фильтр: убираем лекции (л) и ГЗ
        vazhno = [l for l in f_lessons if not any(x in str(l['meta']).lower() for x in [' л', 'л ', 'гз']) and str(l['meta']).lower().strip() != 'л']

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
