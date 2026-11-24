# NFP Film — موتور مستند ۱۶:۹ (مرحلهٔ اول)

موتور تولید مستند انیمیشنی افقی با کیفیت ۱۹۲۰×۱۰۸۰ و ۳۰fps. پایهٔ آن موتور مستند شاخهٔ `docu-16x9-test30` (Commit `fa94f06`) است. شخصیت‌ها با C1 تا C3 ساخته می‌شوند.

## ساختار
| مسیر | محتوا |
|---|---|
| `kit/20_backgrounds.js`، `40_fx.js`، `41_cine.js`، `50_director.js` | کیت سبک (پس‌زمینهٔ لایه‌ای، نور، درجه‌بندی رنگ، مه، افکت، Director). **کپی بایت‌به‌بایت؛ ویرایش نشود.** |
| `kit/55_cast_bridge.js` | پل اتصال Director به Runtime در C3 (جدید) |
| `engine/project.py`، `run.py`، `compose.py`، `base.html` | برگرفته از موتور مستند؛ تغییرات در `PROVENANCE.json` ثبت شده‌اند |
| `engine/verify.py`، `untimed.py`، `assemble.py`، `photoslots.py` | کپی بایت‌به‌بایت |
| `engine/cast_plan.py` | برنامه‌ریزی شخصیت‌ها با C3 برای هر شات (جدید) |
| `assets/noise.png` | بافت grain (کپی) |
| `PROVENANCE.json` | منبع، هش و فهرست تغییرات هر فایل |

Rig شخصیت (`00_core.js`، `10_chars.js`) کپی نشده است. همان فایل‌های C2 هستند (هش یکسان با کیت مستند) و مستقیم از `nfp/character/renderers/flat_cartoon_v2/rig/` خوانده می‌شوند.

**منتقل نشده:** پروژه‌ها و دارایی‌های Kim، شاخهٔ `docu-6min-data`، Workflowهای Kim، و صحنه‌های آماده (`21_scenes.js`، `42_scenes_cine.js`) که متن‌ها و پالت‌های اختصاصی Kim دارند. نسخهٔ پاک‌شدهٔ صحنه‌ها مرحلهٔ بعد است.

## پروژه
```json
{ "meta": {"title": "...", "lang": "en", "format": "16:9", "width": 1920, "height": 1080, "fps": 30, "target_duration": 60},
  "voice": {"voice": "Kore"}, "shots": "shots.js",
  "cast": {"dir": "my-cast"},
  "characters": [{"shot": "room", "actor": "ana-room", "character": "ana", "from": ["s2","w",0], "to": ["s3","w",0],
                  "x": 640, "y": 980, "scale": 0.95, "depth": 0.9, "expr": "happy",
                  "actions": [{"do": "nod", "at": ["s2","e",2]}]}],
  "chapters": [{"id": "c1", "sentences": [{"id": "s1", "text": "...", "speaker": "ana-room"}]}] }
```
- **زبان (`meta.lang`):**
  - `en` (پیش‌فرض): Inter و Caveat، چپ‌به‌راست.
  - `fa`: Vazirmatn (Inter برای واژه‌های لاتین)، راست‌به‌چپ.
  - متن‌های SVG صحنه با یک قاعدهٔ CSS به فونت زبان پروژه می‌روند و فایل‌های کیت تغییر نمی‌کنند.
  - زبان Whisper همان زبان پروژه است.
- **شخصیت‌ها به‌صورت داده تعریف می‌شوند، نه کد:**
  - هر ورودی `characters` یعنی یک شخصیت در یک شات.
  - در `shots.js`، داخل `build()` همان شات و در جای درست ترتیب لایه‌ها، `K.film.cast(S, "ana-room")` صدا زده می‌شود: روی صحنه و زیر لایه‌های grade و نور.
  - زمان‌ها همان لنگرهای Director هستند: عدد، `"end"`، `[sid,"w",i]`، `[sid,"e",i]` یا `[sid, کسر]`.
  - همهٔ حرکت‌های C3 در دسترس‌اند.
  - گفتار فقط از `speaker` جمله‌ها می‌آید. پیش‌فرض `narrator` است؛ یعنی دهان هیچ‌کس حرکت نمی‌کند.
  - قاعدهٔ صدا: تا آماده شدن ماژول چندصدا، فقط یک صدای TTS برای کل ویدیو وجود دارد. شخصیتی که حرف می‌زند باید با جنسیت آن صدا جور باشد.
- **هویت:**
  - قفل C1 و محافظ هویت بصری (فقط جلوی شبیه‌سازی ناخواستهٔ هویت Kim را می‌گیرد) پیش از هر برنامه‌ریزی اجرا می‌شوند.
  - شخصیت واقعی با نمایش نمادین و ذکر منبع مجاز است.

## خروجی‌ها
- `story/index.html`: صفحهٔ HyperFrames. رندر در 1920×1080 و 30fps، بدون هیچ مرحلهٔ ۷۲۰p.
- `words.json` (`nfp.film.words/1`): زمان دقیق هر کلمه، به‌صورت دادهٔ مستقل.
- `story.srt`: فقط خروجی جانبی؛ موتور هرگز آن را نمی‌خواند.
- `cast_report.json`: گزارش شخصیت‌ها.

## اجرا
```
python3 nfp/film/engine/run.py <plan|check|tts|fit|prepare|whisper|align|compose|verify> --project <dir> [--chapter c1] [--build <dir>]
```

## تست‌ها (آفلاین، بدون TTS)
```
python3 nfp/film/tests/test_provenance.py                                        # F1 منشأ و هش
python3 nfp/film/tests/film_equivalence_check.py --gsap G --fonts F --work W     # F2/F3 برابری تصویری لایه‌به‌لایه با موتور مرجع
python3 nfp/film/tests/film_cast_check.py        --gsap G --fonts F --work W     # F4/F5 پل C3، هویت، ردها
python3 nfp/film/tests/film_lang_check.py        --gsap G --fonts F --work W     # F6/F7 فارسی/انگلیسی، RTL، هایلایت، words.json
python3 nfp/film/tests/film_render_check.py      --gsap G --fonts F --work W     # F8 رندر واقعی ۱۰ ثانیه + verify
```
- `G`: نسخهٔ محلی `gsap.min.js` 3.12.5.
- `F`: پوشهٔ woff2 شامل Inter (400/700/800)، Caveat 700 و Vazirmatn (400/700).
- `W`: پوشه‌ای بیرون از مخزن.

## محدودیت‌ها (مرحلهٔ اول)
- هر ویدیو فقط یک صدای TTS دارد. ماژول چندصدا مرحلهٔ بعد است.
- صحنه‌های آمادهٔ عمومی و ماژول‌های Graphics، Timeline، Location و Map هنوز ساخته نشده‌اند.
- گفتار یک شخصیت باید کامل داخل یک شات باشد.
- واژه‌های تک‌حرفی (مثل «و») فقط کوتاه هایلایت می‌شوند. منطق هایلایت همان منطق موتور مرجع است.
- حجم MP4 با کیفیت `standard` در آزمون ۱۰ ثانیه‌ای حدود ۴۲ مگابایت بود.
