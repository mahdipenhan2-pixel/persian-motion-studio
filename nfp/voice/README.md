# NFP Voice Engine (V1 + V2 + V3)

موتور مستقل صدا: فهرست صداها، انتخاب صدا برای هر شخصیت (Voice Casting)، برنامهٔ صدای هر جمله، منابع صوتی آفلاین و گزارش خروجی (Manifest).

**V1 به هیچ موتور دیگری وصل نیست.** چیزی از Film، Studio، هستهٔ Stage 2 یا شبکه import نمی‌کند و C1 را فقط می‌خواند. فقط از کتابخانهٔ استاندارد Python استفاده می‌کند.

## مرز مسئولیت
| Voice Engine انجام می‌دهد | انجام نمی‌دهد (مسئولیت دیگران) |
|---|---|
| صداها، Casting، گویندهٔ هر جمله، منبع صوت، مکث‌ها، ساخت فایل صوتی هر جمله، Manifest، کنترل سازگاری صدا با شخصیت | زمان کلمه‌ها: Whisper و align در هستهٔ Stage 2، و `words.json` در Film. لب‌خوانی: C3. شات و زمان: Director |

## فایل‌ها
| فایل | مسئولیت |
|---|---|
| `voices.json` + `registry.py` | فهرست صداها (`nfp.voice.registry/1`): سرویس، `presentation`، `age`، `languages` (کد ISO 639؛ `*` یعنی هر زبانی)، `verified`، منبع |
| `casting.py` | Voice Casting (`nfp.voice.casting/1`)، بررسی تناسب صدا با شخصیت، و هشدار، Override یا مسدودسازی |
| `plan.py` | برنامهٔ صدا (`nfp.voice.plan/1`): گوینده، صدا، منبع، مکث‌ها و `cache_key` هر جمله |
| `providers/synthetic.py` | تُن آزمایشی برای تست آفلاین (**گفتار نیست**) |
| `providers/prepared.py` | فایل صوتی آماده برای هر جمله |
| `manifest.py` | ساخت فایل صوتی هر جمله و `voice_manifest.json` (`nfp.voice.manifest/1`)، و اعتبارسنجی آن |
| `audiotools.py` | ابزار ffprobe و ffmpeg (نصب‌شده در محیط) و اندازه‌گیری‌های PCM |
| `normalize.py` | V2: تبدیل هر WAV معتبر به قالب موتور، و تطبیق بلندی صدا با یک gain ثابت |
| `qc.py` | V2: کنترل کیفیت با آستانه‌های قابل تنظیم و جدایی Warning از Error |
| `cache.py` | V2: کش فایل‌های ساخته‌شده |
| `providers/gemini.py` | V3: آداپتور صدای AI (Gemini TTS)، **خاموش به‌طور پیش‌فرض**؛ تنها فایلی که کد شبکه دارد |
| `cli.py` | فرمان‌های `check`، `plan`، `produce`، `validate`، `cache-stats` و `cache-clear` |
| `tests/test_voice_v1.py`، `tests/test_voice_v2.py` | تست‌های آفلاین |

## ورودی ۱: Casting (`voices.cast.json`)
```json
{"schema": "nfp.voice.casting/1", "project": "my-docu", "cast_dir": "my-cast",
 "rules": {"block_mismatch": false},
 "voices": {"prepared:ali": {"provider": "prepared", "presentation": "male", "age": "adult", "languages": ["fa"], "verified": true}},
 "narrator": {"voice": "gemini:Charon", "style": "documentary"},
 "roles": {"lina": {"voice": "gemini:Kore", "fingerprint": "<اثرانگشت C1>",
                    "stages": {"child": "synthetic:child"}, "expect": {"presentation": "female", "age": "adult"},
                    "override": {"reason": "..."}}}}
```
**ویژگی‌های مورد انتظار شخصیت:**
- از `expect` گرفته می‌شود.
- اگر `expect` نباشد، از build هر مرحلهٔ سنی در C1 استنباط می‌شود:
  - `woman`: زن بزرگسال؛
  - `man`: مرد بزرگسال؛
  - `teen`: نوجوان؛
  - `child` و `baby`: کودک.

**قواعد تناسب:**
| وضعیت | نتیجه |
|---|---|
| ناسازگاری جنسیت، سن یا زبان، در حالت پیش‌فرض | **Warning** |
| همان ناسازگاری در حالت پیش‌فرض + `override` با `reason` | **Override** ثبت می‌شود و دلیلش نگه داشته می‌شود |
| ناسازگاری + `rules.block_mismatch: true` | **Block مطلق**: Override هم آن را باز نمی‌کند |
| صدای `verified: false` | Warning |
| صدای نامعلوم، شخصیت نامعلوم، مرحلهٔ سنی نامعتبر، Override بدون دلیل، اثرانگشت متفاوت با قفل C1 | **Error**، صرف‌نظر از قواعد |

- `block_mismatch` قاعدهٔ پروژه است و بر تصمیم موردی مقدم است.
- برای استفاده از صدای ناسازگار در چنین پروژه‌ای، دو راه هست: صدای سازگار انتخاب شود، یا قاعده برای کل پروژه خاموش شود.
- Override در این حالت هم اعتبارسنجی می‌شود و دلیلش الزامی است.
- با صداهای سازگار، این قاعده چیزی را مسدود نمی‌کند.

## ورودی ۲: متن جمله‌ها (Script)
```json
{"language": "en", "sentences": [
  {"id": "s1", "text": "...", "speaker": "narrator"},
  {"id": "s2", "text": "...", "speaker": "lina", "stage": "adult", "language": "fa",
   "pause_before_ms": 300, "pause_after_ms": 0, "style": "warm", "audio": "rec/s2.wav"}]}
```
- **`speaker`:** `narrator` (پیش‌فرض) یا یکی از نقش‌های Casting.
- **`audio`:** فایل صوتی آماده برای همان جمله؛ منبع `prepared` می‌شود.
- **`pause_*`:** سکوت داخل فایل همان جمله، بین 0 و 5000 میلی‌ثانیه. آزمون L0 نشان داد هستهٔ بدون تغییر این سکوت را نگه می‌دارد و زمان کلمه‌ها دقیق می‌ماند.

## خروجی: `voice_manifest.json` + `audio/<id>.wav`
- همهٔ فایل‌ها mono، 16-bit و با **یک نرخ نمونه‌برداری** هستند (پیش‌فرض 24000). این همان قالبی است که هستهٔ Stage 2 می‌پذیرد.
- برای هر جمله ثبت می‌شود: `speaker`، `voice`، `provider`، `source` (و هش آن)، مکث‌ها، `frames`، `duration`، `sha256` و `cache_key`.
- Manifest **زمان کلمه‌ها را ندارد.** زمان کلمه‌ها مثل قبل از align گرفته می‌شود. Manifest فقط می‌گوید هر جمله را چه کسی گفته است.
- `validate_manifest` بررسی می‌کند: اسکیما، فیلدها، شناسه‌ها، یکسانی نرخ، وجود و قالب فایل‌ها، `frames` و `sha256`.

## V2: Normalization، QC و Cache
هر سه اختیاری و مستقل‌اند. `produce()` بدون این گزینه‌ها دقیقاً همان خروجی V1 را می‌دهد.

### Normalization: `produce(..., normalize={...})` یا `--normalize`
- **ورودی:** فقط WAV معتبر، با هر نرخ نمونه‌برداری، تعداد کانال یا عمق بیت (شامل float). فایلی که WAV نیست، یا خراب است، با پیامی رد می‌شود که شناسهٔ جمله و مسیر فایل را دارد.
- **خروجی:** mono (میانگین کانال‌ها در FFmpeg)، 16-bit، با نرخ اجرا. مدت فایل در حد دو نمونهٔ صوتی ثابت می‌ماند و این بررسی می‌شود.
- **بلندی صدا:** بلندی یکپارچهٔ EBU R128 با **یک gain ثابت** به `target_lufs` (پیش‌فرض −20) می‌رسد. compressor یا limiter در کار نیست. gain با دو حد محدود می‌شود:
  - `true_peak_max` (پیش‌فرض −1.5 dBTP)؛
  - `max_gain_db` (پیش‌فرض 20).

  حدی که gain را محدود کرده ثبت می‌شود. ورودی زیر −70 LUFS قابل اندازه‌گیری نیست و gain نمی‌گیرد.
- **مکث‌ها** پس از Normalization اضافه می‌شوند، پس دقیق می‌مانند.
- **مشخصات ورودی و خروجی و بلندی صدا پیش و پس** در `normalize` هر جمله در Manifest ثبت می‌شوند.

### QC: `produce(..., qc={...})` یا `--qc`، خروجی `qc_report.json` (`nfp.voice.qc/1`)
| سطح | بررسی‌ها |
|---|---|
| **Error** | فایل خراب یا غیرقابل‌خواندن؛ قالب اشتباه (نرخ، کانال، بیت)؛ فایل خالی، کوتاه‌تر از 0.3 یا بلندتر از 60 ثانیه؛ فایل ساکت (peak زیر −60 dBFS)؛ Clipping سنگین (بیش از 0.1٪ نمونه‌ها)؛ طول متفاوت با «گفتار + مکث‌های برنامه» |
| **Warning** | چند نمونهٔ Clip؛ peak بدون headroom؛ True Peak بالای −1 dBTP؛ صدای بسیار ضعیف (زیر −40 LUFS)؛ فاصله از target بیش از ±2 LU؛ سکوت غیرعادی ابتدا یا انتها (بیش از 1 ثانیه فراتر از مکث برنامه)؛ سکوت داخلی بیش از 2 ثانیه |

- همهٔ آستانه‌ها در `qc.DEFAULTS` هستند و قابل تنظیم‌اند.
- هر بررسی با مقدار، حد و سطح ثبت می‌شود.
- هر Error اجرا را متوقف می‌کند، ولی گزارش و Manifest پیش از توقف نوشته می‌شوند.

### Cache: `produce(..., cache=Cache(dir))` یا `--cache [DIR]`
- **محل پیش‌فرض:** `$NFP_VOICE_CACHE` یا `~/.cache/nfp-voice`. **هرگز داخل مخزن نیست.**
- **کلید:** sha256 از `cache_key` برنامه (منبع، صدا، سبک، زبان، متن، مکث‌ها، هش فایل آماده)، به‌علاوهٔ قالب خروجی، تنظیمات Normalization، پارامترهای صدا و نسخهٔ موتور.
- **هر ورودی کش:** `<key>.wav` + `<key>.json`. فایل JSON آخر نوشته می‌شود و نشانهٔ کامل بودن ورودی است.
- **هنگام Hit بررسی می‌شود:** JSON، کلید، sha256، قالب و تعداد frame. ورودی خراب یا ناقص حذف و دوباره ساخته می‌شود (در `discarded` شمرده می‌شود).
- **نوشتن اتمی:** فایل موقت یکتا در همان پوشه، سپس `os.replace`. اجرای هم‌زمان چند فرایند تست شده است.
- **ثبت در Manifest:** `cache {key, hit}` برای هر جمله، و `cache {dir, hits, misses, discarded}` برای کل اجرا.
- **پاک‌سازی:** `cache-clear` فقط ورودی‌های کش را از پوشه‌ای که نشانهٔ `NFP_VOICE_CACHE` دارد حذف می‌کند. پوشه‌ای که این نشانه را ندارد و خالی نیست اصلاً استفاده نمی‌شود.

## V3: صدای AI (`providers={"gemini": {...}}` یا `--allow-tts gemini`)
- **درخواست:** دقیقاً همان درخواست هستهٔ قفل‌شدهٔ Stage 2 است (Interactions API؛ نام صدا از فهرست، مثلاً `gemini:Kore` یعنی `Kore`؛ سبک به‌صورت speech metadata). تست، برابری بایت‌به‌بایت آن را با `synth_once` هسته ثابت می‌کند. هسته import نمی‌شود.
- **دروازه‌ها:** همه پیش از **اولین** درخواست بررسی می‌شوند و اگر یکی بسته باشد، هیچ درخواستی فرستاده نمی‌شود:
  1. فعال‌سازی صریح Provider در همان اجرا؛
  2. مدل از فهرست رایگان (`gemini-3.8-flash-tts`، `gemini-3.8-flash-lite-tts`، `gemini-3.1-flash-tts-preview`؛ همان فهرست هسته)؛
  3. `GEMINI_FREE_TIER_CONFIRMED=YES` در محیط؛
  4. `GEMINI_API_KEY` در محیط؛
  5. بودجه: اگر جمله‌هایی که باید ساخته شوند از `max_requests` (پیش‌فرض 8، حداکثر 40) بیشتر باشند، کل اجرا پیش از هر درخواست رد می‌شود.
- **فاصلهٔ بین درخواست‌ها:** `spacing_s` (پیش‌فرض 25 ثانیه).
- **HTTP 429:** کل اجرا فوراً متوقف می‌شود؛ هیچ تکراری و هیچ مدل جایگزینی در کار نیست. جمله‌های ساخته‌شده در کش می‌مانند و اجرای بعد فقط بقیه را درخواست می‌کند.
- **کلید API:** فقط در هدر `x-goog-api-key` فرستاده می‌شود. هرگز در URL، پیام خطا، Manifest، گزارش QC یا کش نوشته نمی‌شود، و تست این را بررسی می‌کند.
- **خروجی:**
  - PCM بدون هدر (24 kHz) یا WAV پذیرفته می‌شود؛ مکث‌ها پس از آن افزوده می‌شوند.
  - با `normalize`، نرخ و کانال تبدیل و بلندی صدا تطبیق داده می‌شود. بدون `normalize`، قالب ناسازگار رد می‌شود.
  - در Manifest ثبت می‌شود: `generation {model, requested, source_rate}` برای هر جملهٔ AI، و `providers.gemini {model, max_requests, requests_used}` برای کل اجرا.
- **کش:** مدل جزو کلید کش است. کلید جمله‌های Synthetic و Prepared همان کلید V2 است، پس کش‌های قبلی معتبر می‌مانند. با کش گرم، هیچ درخواستی فرستاده نمی‌شود.
- **`estimate`:** بدون هیچ درخواست یا نوشتن فایلی می‌گوید هر Provider چند جمله باید بسازد، و با `--allow-tts gemini` چند درخواست لازم است.
- **وضعیت فعلی:** هیچ درخواست واقعی فرستاده نشده است. همهٔ تست‌ها با یک transport ساختگی و بدون شبکه اجرا می‌شوند. اولین درخواست واقعی فقط با تأیید جدای صاحب پروژه انجام می‌شود.

## زبان‌ها
فارسی و انگلیسی پشتیبانی می‌شوند. زبان فقط یک کد ISO 639 است، پس افزودن زبان دیگر به تغییر کد نیاز ندارد: کافی است در `languages` صدای مربوط فهرست شود. صدایی که زبان جمله را ندارد Warning می‌دهد. در حالت پیش‌فرض، Override با دلیل آن را به Override ثبت‌شده تبدیل می‌کند؛ با `block_mismatch` به‌طور مطلق مسدود می‌شود.

## اجرا
```
python3 nfp/voice/cli.py check    <voices.cast.json>
python3 nfp/voice/cli.py plan     <voices.cast.json> <script.json> [--out plan.json]
python3 nfp/voice/cli.py produce  <voices.cast.json> <script.json> --out <dir> [--rate 24000]
python3 nfp/voice/cli.py validate <dir>/voice_manifest.json
python3 nfp/voice/cli.py produce  <voices.cast.json> <script.json> --out <dir> --normalize --qc --cache
python3 nfp/voice/cli.py cache-stats [--cache DIR]
python3 nfp/voice/cli.py cache-clear [--cache DIR]
python3 nfp/voice/tests/test_voice_v1.py
python3 nfp/voice/tests/test_voice_v2.py
python3 nfp/voice/tests/test_voice_v3.py
python3 nfp/voice/cli.py estimate <voices.cast.json> <script.json> --allow-tts gemini [--cache]
```

## محدودیت‌ها
- **بدون `normalize`** (رفتار V1)، فایل آماده تبدیل نمی‌شود و قالب نادرست رد می‌شود. با `normalize` تبدیل انجام می‌شود.
- **Normalization و اندازه‌گیری بلندی صدا به FFmpeg نیاز دارند.** اگر نصب نباشد، خطای روشن داده می‌شود و جایگزینی در کار نیست. در آن صورت QC بررسی بلندی صدا را با Warning کنار می‌گذارد.
- **صدای Gemini:** آداپتور آماده است، ولی هیچ صدای AI واقعی ساخته نشده است. اجرای واقعی به کلید، دسترسی شبکه به `generativelanguage.googleapis.com` و تأیید جدا نیاز دارد. یکسانی جنسیت ادراکی صداها هنوز تأیید نشده است (`verified: false`).
- **آزمون گفتار واقعی انسانی (V2.5):** شرط ورود به V3 نیست و به‌صورت **آزمون اختیاری و معوق** ثبت شده است. صدای نهایی پروژه‌ها می‌تواند AI باشد. دانلود از Common Voice ممکن نشد (دسترسی مسدود)، و از Wikimedia هم ممکن نشد (خطای 429).
- **صدای Synthetic** گفتار نیست و فقط برای تست سازوکار است. تست Whisper و align به گفتار واقعی نیاز دارد (گروه Alignment).
- **اتصال به Film** (`run.py` و `cast_plan.py`) مرحلهٔ بعد است. مسیر فعلی Film بدون Voice Engine دست‌نخورده می‌ماند.

## V5: صدای واقعی محلی با Piper
- **Provider جدید `piper`** (`providers/piper.py`) کنار Providerهای قبلی است و چیزی از آن‌ها تغییر نکرده. گفتار واقعی، رایگان و آفلاین است و هیچ درخواست شبکه یا کلیدی ندارد.
- **صداهای ثبت‌شده در `voices.json`:**
  - `piper:fa-amir`: فارسی، مرد، مجموعه‌داده CC0
  - `piper:fa-gyro`: فارسی، مرد، مجوز در MODEL_CARD ذکر نشده
  - `piper:en-lessac`: انگلیسی، زن، مجوز Blizzard 2013
  - `piper:en-ryan`: انگلیسی، مرد، CC BY-NC-SA، فقط غیرتجاری

  پیش از انتشار تجاری، مجوز هر صدا را بررسی کنید. صدای Piper فارسیِ زنانه‌ای به‌صورت رایگان منتشر نشده است.
- **مدل‌ها** فقط از یک پوشهٔ ثابت خوانده می‌شوند: `$NFP_PIPER_DIR`، یا در نبود آن `ROOT/assets/voices/piper`. این پوشه را `python3 nfp/setup/fetch_assets.py --only piper` پر می‌کند. هنگام رندر هیچ دانلودی انجام نمی‌شود؛ اگر مدلی نباشد، اجرا با پیام روشن و دستور دانلود رد می‌شود.
- **Cache:** sha256 فایل مدل در cache key طرح (plan) است، پس با عوض شدن مدل، صدای قبلی دوباره استفاده نمی‌شود.
- **تست:** `python3 nfp/voice/tests/test_voice_v5.py --work <dir>`، با تشخیص گفتار واقعی faster-whisper برای فارسی و انگلیسی.
