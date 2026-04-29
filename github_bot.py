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
    pair_offsets = [(1, 2), (3, 4), (5, 6)] 
    
    for pair_idx, (off1, off2) in enumerate(pair_offsets):
        subj, room, meta = "", "", ""
        for c in cols:
            if c >= df.shape[1]: continue
            for r_off in [off1, off2]:
                curr_r = date_row + r_off
                if curr_r >= df.shape[0]: continue
                
                val = str(df.iloc[curr_r, c]).strip()
                if not val or val.lower() == 'nan': continue
                
                if any(x in val.lower() for x in ['пз', ' л', ' т', 'вси', 'гз', ' с ', 'па', 'уп', 'з/о']):
                    meta = val
                elif re.search(r'\d+[а-яa-z]?$', val.lower()) and len(val) < 6:
                    room = val
                elif len(val) > 2 and not val.replace('.','').isdigit():
                    subj = val

        if subj:
            raw_lessons.append({'idx': pair_idx + 1, 'subj': subj, 'meta': meta, 'room': room})
        elif pair_idx > 0 and raw_lessons: # ИСПРАВЛЕНО: pair_idx вместо i
            prev = raw_lessons[-1]
            if prev['idx'] == pair_idx: # Склеиваем только если это продолжение той же временной ячейки
                 raw_lessons.append({'idx': pair_idx + 1, 'subj': prev['subj'], 'meta': prev['meta'], 'room': prev['room']})
            
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
        # Пробуем загрузить лист с группой 7-21 (индекс 2)
        df = pd.read_excel('schedule.xlsx', header=None, sheet_name=2)
    except Exception as e:
        print(f"DEBUG: Не удалось загрузить лист по индексу 2: {e}")
        df = pd.read_excel('schedule.xlsx', header=None)

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
