import os
import asyncio
import pandas as pd
import re
from datetime import datetime, timedelta
from aiogram import Bot

API_TOKEN = os.getenv('API_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

DAYS_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда",
    3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}

# Столбцы: Пн(2,3,4), Вт(6,7,8), Ср(10,11,12) и т.д.
DAY_COLUMNS = {
    0: [1, 2, 3], 1: [5, 6, 7], 2: [9, 10, 11],
    3: [13, 14, 15], 4: [17, 18, 19], 5: [21, 22, 23]
}

def clean_subj(s):
    return re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', str(s)).lower()

def parse_metadata(meta_str):
    s = str(meta_str).strip().lower()
    if s == 'nan' or not s or s.isdigit(): return ""
    match = re.search(r'(\d+)\s+(\d+)\s+([а-яa-z/]+)', s)
    if match: return f"({match.group(1)} т {match.group(2)} {match.group(3)})"
    return f"({s.rstrip('.')})"

def get_schedule_for_date(df, target_date):
    weekday = target_date.weekday()
    if weekday not in DAY_COLUMNS: return []
    
    cols = DAY_COLUMNS[weekday]
    target_day = str(target_date.day)
    
    # 1. Находим строку с датой в нужных столбцах
    date_row = -1
    for r in range(df.shape[0]):
        # Проверяем ячейки дня на наличие только числа (даты)
        for c in cols:
            if c < df.shape[1]:
                cell_val = str(df.iloc[r, c]).strip().split('.')[0]
                if cell_val == target_day:
                    date_row = r
                    break
        if date_row != -1: break
    
    if date_row == -1: return []

    # 2. Анализируем блок из 6 строк ПОД датой
    raw_lessons = []
    search_range = range(date_row + 1, min(date_row + 7, df.shape[0]))

    for i, c in enumerate(cols):
        subj, room, meta = "", "", ""
        
        for r in search_range:
            val = str(df.iloc[r, c]).strip()
            if val.lower() == 'nan' or not val: continue

            # Метаданные (вид занятия)
            if any(x in val.lower() for x in ['пз', ' л', ' т', 'вси', 'гз', ' с ', 'па', 'уп', 'з/о']):
                if not meta: meta = val
            # Кабинет (цифры или цифры+буква в конце)
            elif re.search(r'\d+[а-яa-z]?$', val.lower()) and len(val) < 6:
                if not room: room = val
            # Предмет (текст)
            elif len(val) > 2 and not val.replace('.','').isdigit():
                if not subj: subj = val

        if subj:
            raw_lessons.append({'idx': i+1, 'subj': subj, 'meta': meta, 'room': room})
        elif i > 0 and raw_lessons:
            # Склейка по горизонтали (объединенные ячейки)
            prev = raw_lessons[-1]
            raw_lessons.append({'idx': i+1, 'subj': prev['subj'], 'meta': prev['meta'], 'room': prev['room']})
            
    return raw_lessons

def format_lessons(lessons):
    if not lessons: return ""
    merged = []
    for l in lessons:
        s_key = clean_subj(l['subj'])
        if merged and merged[-1]['subj_key'] == s_key:
            merged[-1]['indices'].append(l['idx'])
            if len(str(l['meta'])) > len(str(merged[-1]['meta'])): merged[-1]['meta'] = l['meta']
            if not merged[-1]['room'] and l['room']: merged[-1]['room'] = l['room']
        else:
            merged.append({'indices': [l['idx']], 'subj': l['subj'], 'subj_key': s_key, 'meta': l['meta'], 'room': l['room']})
    
    res = ""
    for m in merged:
        start_idx, end_idx = m['indices'][0], m['indices'][-1]
        idx_str = f"{start_idx}-{end_idx}" if start_idx != end_idx else f"{start_idx}"
        room_str = f" [каб. {m['room']}]" if m['room'] else ""
        res += f"• {idx_str} пара: {m['subj']}{room_str} {parse_metadata(m['meta'])}\n"
    return res

async def main():
    bot = Bot(token=API_TOKEN)
    try:
        try: df = pd.read_excel('schedule.xlsx', header=None)
        except: df = pd.read_csv('schedule.csv', header=None)
    except Exception as e:
        print(f"Ошибка: {e}"); return

    # Целевая дата: завтра (с учетом МСК +3)
    target = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    if target.weekday() == 6: target += timedelta(days=1)

    today_lessons = get_schedule_for_date(df, target)
    day_name = DAYS_RU[target.weekday()]
    
    final_text = f"📅 **Расписание на завтра ({target.day} {MONTHS_RU[target.month]}, {day_name}):**\n\n"
    final_text += format_lessons(today_lessons) if today_lessons else "Пар не найдено. 🎉\n"

    # Блок ВАЖНОЕ
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
