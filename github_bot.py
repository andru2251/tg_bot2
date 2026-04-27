import os
import asyncio
import pandas as pd
import re
from datetime import datetime, timedelta
from aiogram import Bot

API_TOKEN = os.getenv('API_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
TARGET_GROUP = "7-21"

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

MONTHS_ROOTS = {
    1: "январ", 2: "феврал", 3: "март", 4: "апрел",
    5: "май", 6: "июн", 7: "июл", 8: "август",
    9: "сентябр", 10: "октябр", 11: "ноябр", 12: "декабр"
}

DAYS_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда",
    3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}

def clean_subj(s):
    return re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', str(s)).lower()

def parse_metadata(meta_str):
    s = str(meta_str).strip().lower()
    if s == 'nan' or not s or s.isdigit(): return ""
    match = re.search(r'(\d+)\s+(\d+)\s+([а-яa-z/]+)', s)
    if match: return f"({match.group(1)} т {match.group(2)} {match.group(3)})"
    return f"({s.rstrip('.')})"

import os
import asyncio
import pandas as pd
import re
from datetime import datetime, timedelta
from aiogram import Bot

API_TOKEN = os.getenv('API_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
TARGET_GROUP = "7-21"

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

MONTHS_ROOTS = {
    1: "январ", 2: "феврал", 3: "март", 4: "апрел",
    5: "май", 6: "июн", 7: "июл", 8: "август",
    9: "сентябр", 10: "октябр", 11: "ноябр", 12: "декабр"
}

DAYS_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда",
    3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
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
    if target_date.weekday() > 5: return []
    target_month_root = MONTHS_ROOTS[target_date.month].lower()
    target_day = str(target_date.day)
    col_start = 1 + (target_date.weekday() * 3)
    day_cols = [col_start, col_start + 1, col_start + 2]
    
    date_row = -1
    for r in range(df.shape[0]):
        row_str = " ".join(df.iloc[r].astype(str).str.lower().values)
        if target_month_root in row_str:
            row_vals = [str(v).strip().split('.')[0] for v in df.iloc[r].values]
            if target_day in row_vals:
                date_row = r
                break
    if date_row == -1: return []

    group_row = -1
    for r in range(date_row, min(date_row + 60, df.shape[0])):
        if TARGET_GROUP.lower() in str(df.iloc[r, 0]).lower():
            group_row = r
            break
    if group_row == -1: return []

    raw_lessons = []
    for i, c in enumerate(day_cols):
        if c >= df.shape[1]: continue
        
        # 1. Вид занятия (строка выше)
        meta = str(df.iloc[group_row - 1, c]).strip()
        if meta.lower() == 'nan' or (meta.isdigit() and len(meta) < 2): meta = ""

        # 2. Предмет и Кабинет
        subj = ""
        room = ""
        
        # Проверяем основную строку группы
        val_main = str(df.iloc[group_row, c]).strip()
        if val_main and val_main.lower() != 'nan' and not val_main.replace(' ','').isdigit():
            subj = val_main
            # Кабинет строго под названием
            room_val = str(df.iloc[group_row + 1, c]).strip()
            if room_val and room_val.lower() != 'nan': room = room_val
        else:
            # Если в основной пусто, смотрим строку ниже
            val_sub = str(df.iloc[group_row + 1, c]).strip()
            if val_sub and val_sub.lower() != 'nan' and not val_sub.replace(' ','').isdigit():
                subj = val_sub
                # Кабинет строго под названием
                room_val = str(df.iloc[group_row + 2, c]).strip()
                if room_val and room_val.lower() != 'nan': room = room_val
        
        if subj:
            raw_lessons.append({'idx': i+1, 'subj': subj, 'meta': meta, 'room': room})
        elif i > 0 and raw_lessons:
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
            if len(str(l['meta'])) > len(str(merged[-1]['meta'])):
                merged[-1]['meta'] = l['meta']
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
        start_idx, end_idx = m['indices'][0], m['indices'][-1]
        idx_str = f"{start_idx}-{end_idx}" if start_idx != end_idx else f"{start_idx}"
        
        # Добавляем кабинет к названию, если он найден
        room_str = f" [каб. {m['room']}]" if m['room'] else ""
        res += f"• {idx_str} пара: {m['subj']}{room_str} {parse_metadata(m['meta'])}\n"
    return res

async def main():
    bot = Bot(token=API_TOKEN)
    try:
        try: df = pd.read_excel('schedule.xlsx', header=None)
        except: df = pd.read_csv('schedule.csv', header=None)
    except Exception as e:
        print(f"Ошибка файла: {e}"); return

    target = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    if target.weekday() == 6: target += timedelta(days=1)

    today_lessons = get_schedule_for_date(df, target)
    day_name = DAYS_RU[target.weekday()]
    
    final_text = f"📅 **Расписание на завтра ({target.day} {MONTHS_RU[target.month]}, {day_name}):**\n\n"
    final_text += format_lessons(today_lessons) if today_lessons else "Пар не найдено. 🎉\n"

    important_content = ""
    found_days, offset = 0, 1
    while found_days < 2 and offset < 10:
        check_date = target + timedelta(days=offset)
        offset += 1
        if check_date.weekday() == 6: continue
        
        f_lessons = get_schedule_for_date(df, check_date)
        vazhno = [l for l in f_lessons if not any(x in l['meta'].lower() for x in [' л', 'л ', 'гз']) and l['meta'].lower().strip() != 'л']

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


def format_lessons(lessons):
    if not lessons: return ""
    merged = []
    for l in lessons:
        s_key = clean_subj(l['subj'])
        if merged and merged[-1]['subj_key'] == s_key:
            merged[-1]['indices'].append(l['idx'])
            if len(str(l['meta'])) > len(str(merged[-1]['meta'])):
                merged[-1]['meta'] = l['meta']
        else:
            merged.append({'indices': [l['idx']], 'subj': l['subj'], 'subj_key': s_key, 'meta': l['meta']})
    
    res = ""
    for m in merged:
        start_idx, end_idx = m['indices'][0], m['indices'][-1]
        idx_str = f"{start_idx}-{end_idx}" if start_idx != end_idx else f"{start_idx}"
        res += f"• {idx_str} пара: {m['subj']} {parse_metadata(m['meta'])}\n"
    return res

async def main():
    bot = Bot(token=API_TOKEN)
    try:
        try: df = pd.read_excel('4 курс 8 фак весна 25-26.xlsx', header=None)
        except: df = pd.read_csv('4 курс 8 фак весна 25-26.cvs', header=None)
    except Exception as e:
        print(f"Ошибка файла: {e}"); return

    # Завтра (относительно запуска в 19:00 МСК)
    target = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    if target.weekday() == 6: target += timedelta(days=1)

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
        vazhno = [l for l in f_lessons if not any(x in l['meta'].lower() for x in [' л', 'л ', 'гз']) and l['meta'].lower().strip() != 'л']

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
