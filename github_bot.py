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
        
        # 1. Метаданные (всегда над 7-21)
        meta = str(df.iloc[base_row_721 - 1, c]).strip()
        if meta.lower() == 'nan': meta = ""

        # 2. Определяем тип пары через контрольную строку (7-21 + 2)
        check_val = str(df.iloc[base_row_721 + 2, c]).strip().lower()
        is_joint = True if check_val == 'nan' or not check_val else False # Если пусто - совместная

        final_subj = ""
        final_room = ""

        if not is_joint:
            # РАЗДЕЛЬНАЯ ПАРА
            final_subj = str(df.iloc[base_row_721, c]).strip()
            room_val = str(df.iloc[base_row_721 + 1, c]).strip()
            final_room = room_val if room_val.lower() != 'nan' else ""
        else:
            # СОВМЕСТНАЯ ПАРА
            # В совместной ячейке текст может быть в строке 7-21 или 8-21
            subj_top = str(df.iloc[base_row_721, c]).strip()
            subj_bot = str(df.iloc[base_row_721 + 1, c]).strip()
            final_subj = subj_top if subj_top.lower() != 'nan' and len(subj_top) > 1 else subj_bot
            
            # Аудитория строго в 7-21 + 4
            room_val = str(df.iloc[base_row_721 + 4, c]).strip()
            final_room = room_val if room_val.lower() != 'nan' else ""

        # Подхват для 1-2, 1-3 пар (горизонтальное объединение)
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

    start_date = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    final_text = f"📅 **Расписание на неделю (с {start_date.day} {MONTHS_RU[start_date.month]}):**\n\n"

    for i in range(7):
        curr = start_date + timedelta(days=i)
        if curr.weekday() == 6: continue 
        
        day_lessons = get_schedule_for_date(df, curr)
        d_name = DAYS_RU[curr.weekday()]
        final_text += f"📍 **{curr.day} {MONTHS_RU[curr.month]} ({d_name}):**\n"
        final_text += format_lessons(day_lessons) if day_lessons else "🎉 Пар не найдено\n"
        final_text += "\n"

    await bot.send_message(CHAT_ID, final_text, parse_mode="Markdown")
    session = await bot.get_session()
    await session.close()

if __name__ == "__main__":
    asyncio.run(main())
