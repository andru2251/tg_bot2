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

    # Находим базовую строку группы 7-21 для этого блока даты
    # Обычно это строки 10, 23, 36 и т.д. в зависимости от блока
    base_group_row = -1
    for r in range(date_row, date_row + 20):
        if r < df.shape[0] and "7-21" in str(df.iloc[r, 0]):
            base_group_row = r
            break
            
    if base_group_row == -1: return []

    raw_lessons = []
    # Смещения для трех пар (каждая пара в своем столбце)
    # 1 пара - 1-й столбец дня, 2 пара - 2-й, 3 пара - 3-й
    for i, c in enumerate(cols):
        if c >= df.shape[1]: continue
        
        # 1. Метаданные: Строка выше 7-21
        meta = str(df.iloc[base_group_row - 1, c]).strip()
        if meta.lower() == 'nan': meta = ""

        # 2. Предмет: Строка 7-21
        subj = str(df.iloc[base_group_row, c]).strip()
        
        # 3. Аудитория: 
        # Проверяем строку ниже 7-21 (обычная пара)
        room = str(df.iloc[base_group_row + 1, c]).strip()
        
        # Если в строке 7-21 пусто, но в 8-21 (ниже) есть текст — значит ячейка объединена
        # или название предмета "упало" ниже. Проверим строку ниже.
        if subj.lower() == 'nan' or not subj:
            subj = str(df.iloc[base_group_row + 1, c]).strip() # Пробуем взять из строки 8-21
            room = str(df.iloc[base_group_row + 2, c]).strip() # Кабинет тогда еще ниже

        if subj.lower() != 'nan' and len(subj) > 1:
            # Очистка кабинета от 'nan'
            final_room = room if room.lower() != 'nan' else ""
            raw_lessons.append({'idx': i + 1, 'subj': subj, 'meta': meta, 'room': final_room})
            
    return raw_lessons

def format_lessons(lessons):
    if not lessons: return ""
    merged = []
    for l in lessons:
        s_key = clean_subj(l['subj'])
        if merged and merged[-1]['subj_key'] == s_key:
            merged[-1]['indices'].append(l['idx'])
        else:
            merged.append({'indices':[l['idx']], 'subj':l['subj'], 'subj_key':s_key, 'meta':l['meta'], 'room':l['room']})
    
    res = ""
    for m in merged:
        idx_str = f"{m['indices'][0]}-{m['indices'][-1]}" if len(m['indices']) > 1 else f"{m['indices'][0]}"
        room_str = f" [каб. {m['room']}]" if m['room'] else ""
        res += f"• {idx_str} пара: {m['subj']}{room_str} {parse_metadata(m['meta'])}\n"
    return res

async def main():
    bot = Bot(token=API_TOKEN)
    if not os.path.exists(FILE_NAME): return
    try:
        # Читаем лист с расписанием (индекс 2)
        df = pd.read_excel(FILE_NAME, header=None, sheet_name=2)
    except:
        df = pd.read_excel(FILE_NAME, header=None)

        target = datetime.now() + timedelta(hours=3) + timedelta(days=7)
        today_lessons = get_schedule_for_date(df, target)
        day_name = DAYS_RU[target.weekday()]
    
    final_text = f"📅 **Расписание на завтра ({target.day} {MONTHS_RU[target.month]}, {day_name}):**\n\n"
    final_text += format_lessons(today_lessons) if today_lessons else "Пар не найдено. 🎉\n"

    # Важное
    important_content = ""
    found_days, offset = 0, 1
    while found_days < 2 and offset < 10:
        check_date = target + timedelta(days=offset)
        offset += 1
        if check_date.weekday() == 6: continue
        f_lessons = get_schedule_for_date(df, check_date)
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
