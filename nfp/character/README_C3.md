# موتور انیمیشن شخصیت NFP — مرحله C3 (C3a تا C3d)

C3 شخصیتِ قفل‌شده C1 را به Rig مرحله C2 وصل می‌کند، حرکت و حالت چهره را به‌صورت قطعی برنامه‌ریزی می‌کند، دهان را با زمان‌بندی کلمات هماهنگ می‌کند و همه را در مرورگر اجرا می‌کند. هیچ فایل C1، C2، Studio، Docu یا Camera Motion تغییر نکرده است. به هیچ API، TTS یا شبکه‌ای وابسته نیست.

```
cast.json + cast.lock.json ──(C3a Adapter)──► complete rig spec (18 fields) + fingerprint + DOM id
action script (actions.json) + word timings ──(C3b Planner + C3c LipSync, Python)──► KeyList (JSON)
KeyList ──(C3d Runtime core, JS)──► SVG character on any page: seek / state / the page's GSAP timeline
        └─(optional Player, JS)──► live preview: play / pause / resume / stop
```

## C3a — Adapter (`adapter/`)
- تنها ورودی مجاز `load_checked(<project>)` است که همان `load_and_check` در C1 را اجرا می‌کند و قفل هویت را بررسی می‌کند. `adapt()` دیکشنری خام را نمی‌پذیرد.
- خروجی همیشه هر **۱۸ فیلد** `K.chars.actor(spec)` را دارد، پس Rig هیچ‌وقت به پیش‌فرض‌های خودش (که ۵ مورد آن هویت Kim است) نمی‌رسد.
- فیلدهای اختیاری لباس که cast خالی گذاشته از `neutral_defaults.json` پر می‌شوند و `lip` از رنگ پوست خود شخصیت مشتق می‌شود. هیچ‌کدام از این مقادیر با پیش‌فرض‌های Rig برابر نیست و این موضوع تست شده است.
- اگر cast **خودش صراحتاً** رنگی برابر با یکی از رنگ‌های Kim انتخاب کرده باشد (مثلاً پوست `#d99a73`)، مجاز است اما در `warnings` گزارش می‌شود.
- **محافظ هویت بصری (`adapter/visual_guard.py` + `adapter/protected_looks.json`):** `load_checked` هر ترکیب stage × wardrobe همه شخصیت‌ها را بررسی می‌کند و cast شبیه به هویت محافظت‌شده را رد می‌کند، حتی اگر هیچ رنگی دقیقاً برابر نباشد:
  - **R1، کپی لباس:** همان نوع لباس با رنگ top و (pants یا shoe) نزدیک به لباس‌های شاخص (KIM07، KIM25، KIMT)؛
  - **R2، کپی پالت:** پوست، مو و چشم همگی در فاصله ۲۰ واحد RGB؛
  - **R3، شبیه‌سازی کلی:** سیلوئت شاخص (`woman` + `long_straight`، یا `teen` + `teen_long` با aliasها) همراه با پالت نزدیک (میانگین نزدیکی ≥ ۰٫۴۵).
  - مو تیره و چشم قهوه‌ای به‌تنهایی رد نمی‌شود. تغییر مدل مو یا دور کردن پالت همیشه کافی است.
  - `protected_looks.json` فقط داده حفاظتی است و برای کشیدن هیچ شخصیتی استفاده نمی‌شود. تست‌ها در `tests/test_visual_guard.py` هستند (موارد مثبت و منفی).
- هویت (پوست، رنگ مو، رنگ چشم)، `outfit` و `top` هرگز ساخته نمی‌شوند. اگر نباشند، خطای روشن داده می‌شود.
- fingerprint روی DOM با `data-nfp-fp` می‌نشیند و شناسه DOM از `isolation.dom_id` در C1 گرفته می‌شود.

## C3b — Planner (`animation/keys.py`, `presets.py`, `script.py`)
- ورودی آن action script است (`schema/action_script.v1.json`) و خروجی KeyList (`schema/keylist.v1.json`): `{part, prop, t, val, dur, ease}` به‌علاوه `actor`، `f/df` (شماره فریم دقیق)، `from` و `src`.
- شبکه فریم ثابت و **فقط 30fps** است. هر fps دیگری (۲۴، ۲۵، ۶۰ و...) با خطای روشن رد می‌شود، چون زمان‌های فریم‌محور مثل پلک، flap دهان و settle روی شبکه ۳۰ تعریف و تست شده‌اند. PRNG فقط seedدار است (همان mulberry32 در Rig). خروجی با ورودی یکسان، بایت‌به‌بایت یکسان است و `digest` آن ثبت می‌شود.
- **دو حرکت هم‌زمان روی یک ویژگی پذیرفته نمی‌شود.** هیچ کلیدی بی‌صدا جابه‌جا یا حذف نمی‌شود و خطا اعلام می‌شود.
- Idle (تنفس و پلک‌زدن seedدار) در آخر و فقط در کانال‌های آزاد پر می‌شود.
- حرکت‌ها: `enter` (pop / fade / walk)، `exit`، `walk`، `run`، `move`، `blink`، `breathe`، `look`، `turn`، `nod`، `arm`، `arms_rest`، `wave`، `point`، `lean`، `hop`، `shiver`، `expr`، `sit`، `stand`، `talk`.
- `walk` و `run` دقیقاً به‌اندازه `dx` جابه‌جا می‌کنند (بدون drift). پاها و لگن به حالت استراحت برمی‌گردند. خم شدن بدن، کج بودن سر و حالت بازو به همان وضعیت پیش از راه رفتن برمی‌گردند.
- ورود دوباره با `walk` شخصیت را به جایی می‌رساند که پیش از خروج ایستاده بود. اگر جابه‌جایی نسبت به طول قدم زیاد باشد، `foot_slide_risk` گزارش می‌شود.
- `animation/profile_flat_cartoon_v2.json` آینه داده‌ای Rig است. تست مرورگر ثابت می‌کند با `K.chars` واقعی برابر است.

## C3c — Lip Sync (`animation/timing_normalize.py`, `lipsync.py`)
- ورودی‌های پشتیبانی‌شده: `timing.json` در Studio، داده `DATA` در Docu، خروجی segments در Whisper، و فهرست کلمه‌ها. همه به ساختار `t0, t1, text, quality` تبدیل می‌شوند.
- **Docu:** کلمه‌های `hl:false` زمان ساختگی دارند و استفاده نمی‌شوند. چون `DATA` متن کلمه ندارد، شناسه عنصر (`w-…`) **هرگز** به‌جای متن استفاده نمی‌شود. در نبود متن، دهان با flapهای خنثی (`open`/`small`) و بر پایه مدت کلمه حرکت می‌کند.
- همه کلمه‌های همه جمله‌ها **اول بر حسب زمان مرتب** می‌شوند، بعد هم‌پوشانی بررسی می‌شود. ترتیب جمله‌ها و کلمه‌ها در فایل روی نتیجه اثری ندارد.
- کلمه‌های `estimated` به‌طور پیش‌فرض دهان را حرکت می‌دهند و برچسب می‌خورند. با `"estimated": false` در `talk` ساکت می‌مانند و در گزارش (`estimated_skipped`) فهرست می‌شوند.
- کلمه بدون زمان معتبر هیچ زمان ساختگی‌ای نمی‌گیرد. `unresolved` می‌شود و نامش با دلیل در گزارش می‌آید. کلمه‌های تخمینی برچسب `estimated` دارند.
- دهان روی فریم `round(t0·fps)` باز می‌شود (حداکثر نیم فریم فاصله). در سکوت بیشتر از 0.15 ثانیه دهان بسته می‌شود و در مکث کوتاه‌تر نیمه‌باز (`small`) می‌ماند. پایان گفتار به دهانِ حالت چهره فعلی (بسته) برمی‌گردد.
- نگاشت اولیه فارسی و انگلیسی روی همان ۱۲ دهان Rig انجام می‌شود. متن به ترتیب منطقی (گفتاری) خوانده می‌شود. راست‌به‌چپ بودن فقط به نمایش مربوط است. ZWNJ و علامت‌های bidi نادیده گرفته می‌شوند و ي/ك عربی به ی/ک تبدیل می‌شوند. این **phoneme recognition نیست**.

## C3d — Runtime: هسته قطعی + Player جدا
Runtime دو فایل جدا دارد:

| فایل | نقش | ساعت دیواری و زمان‌بندی فریم |
|---|---|---|
| `runtime/character_runtime.js` | **هسته قطعی:** اعتبارسنجی، ساخت شخصیت، `seek`، `state`، `toTimeline`، `dispose` | **ندارد** (این را تست E15 بررسی می‌کند) |
| `runtime/character_player.js` | **Player:** پخش زنده برای پیش‌نمایش در مرورگر (`play`، `pause`، `resume`، `stop`، `playing`) | دارد، به‌عمد |

هسته‌ای که در صفحه‌های رندر (HyperFrames و Studio) جاسازی می‌شود، **فقط** `character_runtime.js` است. بنابراین رندر قطعی است و lint در HyperFrames خطایی نمی‌دهد. Player هرگز در صفحه رندر قرار نمی‌گیرد.

**ترتیب بارگذاری** (همه محلی، بدون شبکه):
```
renderers/flat_cartoon_v2/rig.css, rig/00_core.js, rig/10_chars.js,
runtime/character_runtime.js
runtime/character_player.js        ← فقط برای پیش‌نمایش زنده، بعد از هسته
```

**رندر یا timeline صفحه (بدون Player):**
```js
const rt = NFPCharacterRuntime.create({ svg, keylist });   // اعتبارسنجی + ساخت شخصیت
rt.seek(t); rt.state(t); rt.time();                        // قطعی: هر ترتیب seek، همان تصویر
rt.toTimeline(gsap, window.__timelines.main);              // timeline صریح الزامی است
```
- `toTimeline(gsap, tl)` کلیدها را روی **همان** timeline داده‌شده می‌گذارد و هیچ‌وقت timeline تازه نمی‌سازد. اگر `tl` داده نشود یا timeline معتبر GSAP نباشد، با این خطای روشن متوقف می‌شود: `toTimeline: pass the GSAP timeline to extend (e.g. window.__timelines.main); the runtime never creates its own timeline`.
- اگر timeline کوتاه‌تر از KeyList باشد، تا طول KeyList ادامه داده می‌شود. هم‌ارزی آن با `seek` تست شده است (E12).

**پیش‌نمایش زنده (با Player):**
```js
const rt = NFPCharacterRuntime.create({ svg, keylist });
NFPCharacterPlayer.attach(rt);          // play/pause/resume/stop/playing فقط به همین rt اضافه می‌شود
rt.play({ from: 0, to: rt.duration, rate: 1, onFrame: (t) => {}, onEnd: (t) => {} });
rt.pause(); rt.resume(); rt.stop();     // stop به from برمی‌گردد؛ rt.time() و rt.playing() وضعیت را می‌دهند
```
- `play`، `pause`، `resume`، `stop` و `playing` **فقط بعد از** `NFPCharacterPlayer.attach(rt)` وجود دارند. Runtime دیگری که Player به آن وصل نشده، هیچ‌کدام از این متدها را ندارد، و هیچ prototype یا شیء سراسری تغییر نمی‌کند.
- اتصال دوباره به همان نمونه رد می‌شود. `play` فقط `rate` در بازه (0, 16] و `0 ≤ from < to ≤ duration` را می‌پذیرد.
- بعد از اتصال، `rt.dispose()` اول پخش را متوقف می‌کند و بعد شخصیت را حذف می‌کند.
- برای تست می‌شود ساعت را تزریق کرد: `NFPCharacterPlayer.attach(rt, { clock, requestAnimationFrame, cancelAnimationFrame })`.
- صفحه دمو (`cli.py demo`) هر دو فایل را بار می‌کند و Player را به Runtime خودش وصل می‌کند.

### امنیت ورودی (KeyList داده نامطمئن فرض می‌شود)
- هر ۱۸ فیلد spec از نظر **نوع و مقدار** بررسی می‌شود: رنگ `#rrggbb` با حروف کوچک، پرچم 0/1، و واژگان Rig. مقدار خالی، `null` یا نامعتبر رد می‌شود، پس Rig هیچ‌وقت به پیش‌فرض‌های Kim نمی‌رسد.
- `x`، `y` و `scale` باید عدد متناهی در محدوده مجاز باشند. شناسه‌ها با الگو بررسی می‌شوند و باید با حرف شروع شوند (پس `__proto__` رد می‌شود).
- عنصرهای بیرونی با `createElementNS` و `setAttribute` ساخته می‌شوند. خروجی Rig در یک `<template>` بی‌اثر (inert) parse می‌شود و با یک allow-list از عنصرها و attributeها سنجیده می‌شود (بدون event handler، بدون `foreignObject`/`script`/`image`، فقط `url(#local)`). تنها پس از این بررسی وارد صفحه می‌شود.
- **fingerprint** از spec دوباره محاسبه می‌شود (SHA-256، دقیقاً مانند `fingerprint()` در C1) و باید برابر باشد.
- **digest** (SHA-256 روی JSON کانونی) اجباری است و در هر دو اعتبارسنج بررسی می‌شود.
- **محدودیت‌های صادقانه:**
  - بررسی fingerprint فقط ثابت می‌کند fingerprint با رنگ‌ها و عینک همان spec می‌خواند. ثابت **نمی‌کند** که هویت در `cast.lock.json` ثبت است. Runtime به cast دسترسی ندارد؛ قفل را Adapter در Python اجرا می‌کند.
  - digest امضا نیست: هر کسی KeyList را ویرایش کند می‌تواند آن را دوباره بسازد.
  - محاسبه fingerprint از spec فقط تا وقتی دقیق است که کاتالوگ سبک `face` را فقط `default` و `glasses` را تنها mark بداند (امروز چنین است). اگر کاتالوگ گسترش یابد، این بررسی باید همراه آن به‌روز شود.
- به Director، فایل `base.html`، Studio، HyperFrames و شبکه وابسته نیست.

## اجرا
```
python3 nfp/character/animation/cli.py plan  nfp/character/examples/demo-anim/actions.json --out keylist.json
python3 nfp/character/animation/cli.py check keylist.json
python3 nfp/character/animation/cli.py demo  nfp/character/examples/demo-anim/actions.json --html demo.html
python3 nfp/character/tests/test_adapter.py
python3 nfp/character/tests/test_visual_guard.py
python3 nfp/character/tests/test_animation.py
python3 nfp/character/tests/test_lipsync.py
node    nfp/character/tests/anim_render_check.mjs [--gsap <local gsap.min.js>] [--shots <dir>]
```
`examples/demo-anim/timing.json` **ساختگی** است و دستی نوشته شده است: هیچ صدا، TTS یا Whisperی در کار نیست. `examples/demo-anim/keylist.json` خروجی مرجع (golden) است و تست‌ها تکرار آن را بایت‌به‌بایت بررسی می‌کنند.

## محدودیت‌های صادقانه (برای مراحل بعد)
- **ژست دست:** دست فقط یک دایره است. `wave` و `point` حرکت کل بازو هستند، نه انگشت.
- **viseme واقعی:** فقط ۱۲ دهان swap وجود دارد. نگاشت بر اساس حروف تقریبی است.
- **نشستن:** تقریبی است. لگن pivot ندارد و Rig فقط نمای روبه‌رو دارد. صندلی را صحنه باید بکشد (`seat_top_stage_y` در `notes`).
- **چرخش سر:** فقط تمایل و جابه‌جایی دوبعدی است، نمای نیم‌رخ ندارد.
- **`under` (رنگ داخلی بلیزر):** در schema نسخه C1 نیست، پس همیشه مقدار خنثی `#ece6dc` دارد و cast نمی‌تواند آن را انتخاب کند. افزودنش تغییری افزایشی در C1 است و تأیید جدا لازم دارد.
- **fps:** فقط 30. پشتیبانی fps دیگر یعنی تعریف همه ثابت‌های فریمی بر حسب ثانیه، به‌همراه تست جدا.
- **Lip Sync:** فقط با زمان‌بندی مصنوعی تست شده است، نه با صدای واقعی.
- اتصال به Studio 9:16 و Docu 16:9 در این مرحله انجام **نشده** است.
