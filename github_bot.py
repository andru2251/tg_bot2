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

def is_meta(s):
    """Проверяет, является ли строка метаданными (тема, занятие, тип)"""
    s = str(s).lower()
    # Если есть комбинация цифр и ПЗ, Л, Т, С
    if re.search(r'\d+.*\d+.*(пз|л|т|с|вси|гз)', s): return True
    if len(s.split()) >= 2 and any(x in s for x in ['пз', 'л', 'т', 'вси']): return True
    return False

def parse_metadata(meta_str):
    s = str(meta_str).strip().lower()
    if s == 'nan' or not s: return ""
    # Ищем формат '10 97 пз'
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

    raw_lessons = []
    # Каждая пара — блок из строк под датой
    offsets = [(1, 2), (3, 4), (5, 6)] 
    
    for pair_idx, (r1_off, r2_off) in enumerate(offsets):
        subj, room, meta = "", "", ""
        for c in cols:
            if c >= df.shape[1]: continue
            
            # Смотрим ячейку НАД основной строкой пары для поиска метаданных
            potential_meta = str(df.iloc[date_row + r1_off - 1, c]).strip()
            if is_meta(potential_meta): meta = potential_meta

            for r_off in [r1_off, r2_off]:
                curr_r = date_row + r_off
                if curr_r >= df.shape[0]: continue
                val = str(df.iloc[curr_r, c]).strip()
                if not val or val.lower() == 'nan': continue
                
                # Если это метаданные, которые мы еще не нашли
                if is_meta(val):
                    if not meta: meta = val
                # Если это кабинет (цифры или короткий код типа '1 ауд')
                elif re.search(r'^\d+\s?[а-я]?$|^[а-я]{1,3}\d+$|ауд', val.lower()):
                    if not room: room = val
                # Иначе это название предмета (ИНО, ФП, ПР, ОХВБ...)
                else:
                    if not subj: subj = val

        if subj:
            raw_lessons.append({'idx': pair_idx + 1, 'subj': subj, 'meta': meta, 'room': room})
    return raw_lessons

def format_lessons(lessons):
    if not lessons: return ""
    merged = []
    for l in lessons:
        s_key = clean_subj(l['subj'])
        if merged and merged[-1]['subj_key'] == s_key:
            merged[-1]['indices'].append(l['idx'])
            if l['meta'] and not merged[-1]['meta']: merged[-1]['meta'] = l['meta']
            if l['room'] and not merged[-1]['room']: merged[-1]['room'] = l['room']
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
        df = pd.read_excel(FILE_NAME, header=None, sheet_name=2)
    except:
        df = pd.read_excel(FILE_NAME, header=None)

    target = datetime.now() + timedelta(hours=3) + timedelta(days=1)
    if target.weekday() == 6: target += timedelta(days=1)

    today_lessons = get_schedule_for_date(df, target)
    day_name = DAYS_RU[target.weekday()]
    
    final_text = f"📅 **Расписание на завтра ({target.day} {MONTHS_RU[target.month]}, {day_name}):**\n\n"
    final_text += format_lessons(today_lessons) if today_lessons else "Пар не найдено. 🎉\n"

    # Блок Важно
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
