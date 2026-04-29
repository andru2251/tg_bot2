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

        subj_721 = str(df.iloc[base_row_721, c]).strip()
        subj_821 = str(df.iloc[base_row_721 + 1, c]).strip()
        
        final_subj = ""
        final_room = ""

        # СТРОГАЯ ЛОГИКА ПОИСКА ПРЕДМЕТА И КАБИНЕТА
        if subj_721.lower() != 'nan' and len(subj_721) > 1:
            # Пара только у 7-21
            final_subj = subj_721
            room_val = str(df.iloc[base_row_721 + 1, c]).strip() # 7-21 + 1
            final_room = room_val if room_val.lower() != 'nan' else ""
        
        elif subj_821.lower() != 'nan' and len(subj_821) > 1:
            # Совместная пара с 8-21
            final_subj = subj_821
            room_val = str(df.iloc[base_row_721 + 4, c]).strip() # 7-21 + 4
            final_room = room_val if room_val.lower() != 'nan' else ""

        # Склейка объединенных ячеек по горизонтали
        if (not final_subj or final_subj.lower() == 'nan') and i > 0 and raw_lessons:
            final_subj = raw_lessons[-1]['subj']
            meta = raw_lessons[-1]['meta']
            final_room = raw_lessons[-1]['room']

        if final_subj and final_subj.lower() != 'nan':
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

    # Вывод на неделю для проверки
    start_date = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    final_text = f"📅 **Проверка расписания на неделю (с {start_date.day} {MONTHS_RU[start_date.month]}):**\n\n"

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
