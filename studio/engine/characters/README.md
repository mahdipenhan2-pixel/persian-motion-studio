# لایه شخصیت NFP Studio (مرحله C4)

این لایه شخصیت‌های Character Engine (C1 تا C3 در `nfp/character/`) را به‌صورت **افزایشی** به صفحه‌های Studio 9:16 اضافه می‌کند؛ با همان الگوی Camera Motion. هیچ فایل موجودی تغییر نمی‌کند: نه Studio، نه Camera، نه هسته قفل‌شده Stage 2، نه C1 تا C3.

```
python3 studio/engine/run_cast.py cast-check --project <name>     # اعتبارسنجی آفلاین (چیزی نمی‌نویسد)
python3 studio/engine/run_cast.py compose    --project <name>     # = run_motion compose + شخصیت‌ها
```
پروژه‌ای که فیلد شخصیت ندارد، از `run_cast.py` دقیقاً **بایت‌به‌بایت** همان خروجی `run_motion.py` را می‌گیرد. این را `studio/tests/test_characters.py` بررسی می‌کند.

## فیلدهای اختیاری `project.json`
```json
"meta": { "cast": { "dir": "cast/<cast-project>",
          "actors": { "host": { "character": "maryam", "stage": "adult", "wardrobe": "studio", "x": 0.3, "framing": "bust" } } } },
"scenes": [{ "id": "s1", "...": "...",
  "characters": { "actors": [ "host", { "actor": "guest", "expr": "happy" } ],
                  "speaker": "host", "sentence_speakers": { "2": "narrator" },
                  "actions": [ { "actor": "host", "do": "wave", "at": 0.4 } ] } }]
```
- **`meta.cast.dir`:** پوشه‌ای داخل پروژه که `cast.json` و `cast.lock.json` (C1) را دارد. هویت شخصیت با قفل C1 کنترل می‌شود.
- **`x`:** محل شخصیت در عرض شکاف، عددی بین ۰ و ۱. **`framing`:** `bust` (پیش‌فرض) یا `full`.
- **گوینده پیش‌فرض `narrator` است**، یعنی گوینده بیرون از کادر است و دهان هیچ شخصیتی حرکت نمی‌کند. `speaker` و `sentence_speakers` فقط می‌توانند بازیگری را نام ببرند که در همان صحنه حاضر است.
- **`actions`:** زمان `at` بر حسب ثانیه از شروع صحنه است. فقط این حرکت‌ها مجازند: `look`، `nod`، `turn`، `lean`، `wave`، `point`، `expr`، `blink`، `arm`، `arms_rest`، و `hop` (فقط در قاب‌بندی `full`). راه رفتن در شکاف مجاز نیست.

## ناحیه امن و تداخل‌ها (`zones.json`)
- **تنها ناحیه شخصیت در C4، شکاف پایین است:** x بین ۷۰ و ۱۰۱۰ و y بین ۱۳۷۲ و ۱۶۵۰. این شکاف یک ظرف `overflow:hidden` است، پس هیچ پیکسلی از شخصیت وارد نوار زیرنویس (y بین ۵۶۰ و ۱۳۶۰، که verify در Stage 2 آن را می‌سنجد) یا ناحیه handle (از y=1660 به پایین) نمی‌شود.
- **شکاف `top` رزرو است:** همه قالب‌ها، از جمله `cta`، ناحیه بالا را پر می‌کنند.
- **این حالت‌ها رد می‌شوند:**
  - قالب `cta` که note یا handle دارد؛
  - قاب media پایینِ Camera؛
  - فرمت 16:9.
- `.deco` (آیکون تزئینی با شفافیت ۷٪ در y بین ۱۴۴۰ و ۱۸۰۰) **فقط در صحنه‌هایی که شخصیت دارند** با CSS مخفی می‌شود.
- **قاب‌بندی:**
  - `bust`: لگن روی لبه پایین شکاف می‌نشیند و پاها توسط شکاف بریده می‌شوند.
  - `full`: فقط وقتی پذیرفته می‌شود که کل بدن (به‌علاوه دست بالا رفته در `wave` یا دست کشیده در `point`) جا شود **و** ارتفاع چهره حداقل ۵۶ پیکسل باشد.
  - اندازه‌ها از Rig واقعی اندازه‌گیری شده‌اند (`rig_metrics`) و تست مرورگر برابری آن‌ها را بررسی می‌کند.

## نحوه اتصال
1. `compose.py` (بدون تغییر) و Camera (بدون تغییر) صفحه را می‌سازند.
2. `build.py` از کل ویدیو **یک** action script و **یک** KeyList می‌سازد، با Planner در C3.
   - هر بازیگر در کل ویدیو یک عنصر DOM دارد، پس شناسه‌ها هرگز تکراری نمی‌شوند.
   - در صحنه‌های پشت‌سرهم روی صحنه می‌ماند؛ در غیر این صورت با fade وارد و خارج می‌شود.
   - مدت KeyList برابر `floor(مدت صفحه × 30) / 30` است، پس timeline هرگز بلندتر نمی‌شود.
3. `inject.py` در anchorهای ثابت این‌ها را اضافه می‌کند: CSS (`rig.css` + `cast.css`)، لایه‌ای درست پیش از `#stage`، و اسکریپت‌ها (Rig از C2، Runtime از C3، و `cast.js`).
4. `cast.js` اول بررسی می‌کند که `rig.css` واقعاً فعال باشد. بعد با `toTimeline` کلیدها را روی همان `__timelines.main` اضافه می‌کند و بررسی می‌کند که مدت timeline تغییر نکرده باشد.

`ANCHORS.json` هش فایل‌های `base.html`، `compose.py`، `camera/inject.py` و `camera/camera.js` را قفل می‌کند. اگر هرکدام تغییر کند، `run_cast.py` متوقف می‌شود.

## تست‌ها
```
python3 studio/tests/test_characters.py --timing <timing.json> --fonts <fonts dir> --work <dir outside repo>
python3 studio/tests/characters_render_check.py --timing <timing.json> --fonts <fonts> --gsap <local gsap.min.js> --work <dir> [--render]
```
- **T1 و T2:** schema، جدول تداخل‌ها، قاب‌بندی، KeyList، inject، و برابری بایت‌به‌بایت.
- **T3:** تست مرورگر.
- **T4 (`--render`):** HyperFrames، MP4 و verify قفل‌شده در Stage 2.

صدای MP4 در T4 **مصنوعی** است: یک تُن روی زمان واقعی کلمه‌ها. زمان‌بندی کلمه‌ها واقعی است (Whisper روی صدای واقعی `motion-demo-fa`).

## محدودیت‌ها
- فقط 9:16 و فقط شکاف پایین. 16:9 و شکاف بالا برای مراحل بعد رزرو است.
- شخصیت‌ها حرکت Camera روی صحنه را دنبال نمی‌کنند، چون نقش «مجری ثابت» دارند.
- برای چند گوینده فقط یک صدای TTS وجود دارد.
- پنهان کردن `.deco` در صحنه‌ای که Camera آن را بزرگ‌نمایی می‌کند، رسترسازی صحنه را کمی تغییر می‌دهد. اندازه‌گیری‌شده: حداکثر ۱۲۳ پیکسل با اختلاف ۳۳/۲۵۵ روی لبه یک آیکون ناحیه بالا، و نه در نوار زیرنویس.
