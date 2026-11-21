# سیستم مستند ۱۶:۹ (NFP Docu)

این پوشه یک لایه‌ی جدا و مستقل است. هسته‌ی قفل‌شده (`scripts/story_stage2.py`)، Studio، `render.yml`، `index.html` و `main` دست نخورده‌اند.

## هدف
ساخت مستند انیمیشنی افقی (۱۹۲۰×۱۰۸۰، ۳۰ fps، روایت و زیرنویس انگلیسی) با هزینه‌ی صفر:
Gemini TTS (سطح رایگان، با کش) + faster-whisper + HyperFrames روی GitHub Actions + موتور هنری کدی.

## ساختار
- `engine/kit/` — موتور هنری: شخصیت مفصل‌دار (`10_chars.js`)، دکور لایه‌ای با پارالاکس (`20_backgrounds.js`)، نور/برچسب/یادداشت دست‌نویس/VHS/وسایل (`40_fx.js`)، کارگردان که شات‌ها را به زمان واقعی جمله‌ها وصل می‌کند (`50_director.js`).
- `engine/run.py` — مراحل: plan, check, tts, fit, prepare, whisper, align, compose, verify (هسته فقط برای صدا/Whisper/align استفاده می‌شود).
- `engine/compose.py`, `engine/verify.py` — ساخت و بررسی ۱۶:۹ (هسته‌ی قفل‌شده فقط ۹:۱۶ را می‌پذیرد، پس این دو فایل جدا هستند).
- `engine/assemble.py` — اتصال فصل‌ها برای ۱۳ دقیقه (هر فصل ≤ ۴۰ جمله و ≈ ۱۶۵ ثانیه؛ هر فصل به تعداد صحیح فریم پد می‌شود تا صدا و تصویر در محل اتصال هم‌طول بمانند).
- `projects/<نام>/project.json` + `shots.js` — متن/منابع و شات‌ها.
- `tests/test_docu.py` — تست آفلاین. `qa/` — ابزار بررسی محلی (Chrome).

## اجرای تست ۳۰ ثانیه‌ای از GitHub Actions
پیش‌نیاز (یک‌بار): Secret با نام `GEMINI_API_KEY` در Settings → Secrets and variables → Actions → Secrets (همان که قبلاً برای Studio گذاشتی).

**روش الف — بدون هیچ تغییری در main (پیشنهادی):**
1. Settings → Secrets and variables → Actions → تب **Variables** → New repository variable: نام `GEMINI_FREE_TIER_CONFIRMED` و مقدار `YES` (فقط بعد از اینکه مطمئن شدی Billing در Gemini API فعال نیست).
2. Actions → در لیست اجراها، اجرای «Docu Build» روی branch `docu-16x9-test30` → **Re-run all jobs** (با هر push به این branch هم خودکار اجرا می‌شود).

**روش ب — دکمه‌ی Run workflow:** GitHub فقط وقتی فایل workflow روی main باشد دکمه را نشان می‌دهد؛ پس این روش نیاز به اجازه‌ی تو برای قرار دادن فقط همین یک فایل روی main دارد.

## خروجی‌ها (Artifacts)
`story.mp4`، `story.srt`، `contact_sheet.png`، `verify.json`، `timing_report.md`، `narration.wav`.
اگر `verify.json` مشکلی گزارش کند، job قرمز می‌شود.

## قواعد
فقط ابزار رایگان؛ بدون هیچ هزینه. افراد واقعی فقط به شکل نمادین. هر ادعا منبع دارد (`sources` در project.json).

## یادداشت تست
تست ۳۰ ثانیه‌ای kim-test30 (فصل c1) با صدای واقعی؛ اجرا با push روی شاخهٔ docu-16x9-test30.

اجرای مجدد تست ۳۰ ثانیه‌ای پس از تنظیم متغیر تأیید رایگان بودن.
