# Camera Motion Engine (NFP Studio)

ماژول افزونه‌ای برای حرکت سینمایی دوربین. هیچ فایل موجودی (هسته Stage 2، `compose.py`، `base.html`، `run.py`،
`project.py`، `index.html`، `render.yml`، `studio-build.yml`) تغییر نمی‌کند.

## اجرا
```
python3 studio/engine/run_motion.py camera-check --project <name>   # فقط اعتبارسنجی، بدون نوشتن فایل
python3 studio/engine/run_motion.py <plan|check|tts|prepare|whisper|align|compose|verify> --project <name>
```
همه دستورها جز `compose` همان توابع `run.py` (هسته قفل‌شده) هستند. `compose` اول `compose.py` اصلی را اجرا می‌کند و فقط
اگر پروژه فیلد دوربین داشته باشد، حرکت را اضافه می‌کند. پروژه بدون فیلد دوربین = خروجی بایت‌به‌بایت یکسان با `run.py`.

## فیلدهای project.json (همه اختیاری)
```json
"meta":  { "camera_default": { "move": "push-in", "intensity": 0.5, "transition": "fade" } },
"scenes": [{
  "media":  { "src": "assets/x.png", "frame": "top", "fit": "cover", "focus": [0.5, 0.5] },
  "camera": { "move": "ken-burns", "target": "media", "intensity": 0.6, "speed": 1.0,
              "ease": "sine.inOut", "duration": 4, "delay": 0,
              "transition_in": { "type": "slide", "duration": 0.35 } }
}]
```

| فیلد | مقادیر |
|---|---|
| `move` | `none`، `zoom-in`، `zoom-out`، `push-in`، `pull-out`، `pan-left`، `pan-right`، `pan-up`، `pan-down`، `pan-start`، `pan-end`، `ken-burns` |
| `target` | `media` (تصویر داخل قاب؛ پیش‌فرض وقتی media هست) یا `scene` (گرافیک‌های قالب؛ حرکت ملایم) |
| `intensity` | ۰ تا ۱ (مقدار جابه‌جایی) |
| `speed` | ۰٫۲۵ تا ۴ (سرعت: بیشتر از ۱ = زودتر تمام می‌شود و می‌ایستد؛ کمتر از ۱ = جابه‌جایی کمتر در کل صحنه) |
| `duration` / `delay` | ثانیه؛ پیش‌فرض کل مدت دیده‌شدن صحنه |
| `ease` | `none`، `sine.inOut`، `power1.inOut`، `power2.inOut`، `power1.out`، `power2.out` |
| `transition_in` | `fade` (پیش‌فرض فعلی)، `slide`، `zoom-through`، `wipe`؛ مدت ۰٫۱۵ تا ۰٫۶ ثانیه؛ برای صحنه اول مجاز نیست |
| `media.frame` | `top` (y 96-548) یا `bottom` (y 1372-1640) |
| `media.src` | فقط فایل داخل `assets/` همان پروژه: jpg، png، webp، svg ساده؛ حداکثر ۸ MB؛ URL و مسیر بیرونی ممنوع |

`pan-start` و `pan-end` جهت خواندن را دنبال می‌کنند (در فارسی، شروع = راست). `slide` و `wipe` هم برای RTL قرینه‌اند.
جهت Ken Burns از شناسه صحنه محاسبه می‌شود (قطعی، نه تصادفی).

## قواعد ایمنی (در کد اجرا می‌شوند)
- نوار زیرنویس y 560-1360 (همان ناحیه‌ای که Verify هسته می‌سنجد) فقط مال زیرنویس است. قاب‌های media بیرون آن‌اند و
  حرکت گرافیک‌ها ریاضی کنترل می‌شود (لبه ناحیه بالا ≤ 552، لبه ناحیه پایین ≥ 1368)، حتی در ترکیب با transition.
- نوار پیشرفت (y 64-72) و خط handle (از y 1660) هرگز پوشانده نمی‌شوند.
- زیرنویس (`#stage`) هرگز حرکت نمی‌کند؛ `camera.js` اگر به آن دست بزند خطا می‌دهد.
- مدت Timeline تغییر نمی‌کند؛ `camera.js` اگر تغییر کند خطا می‌دهد.
- اگر `base.html` یا `compose.py` تغییر کنند، `run_motion.py` متوقف می‌شود تا نقطه‌های اتصال دوباره بررسی شوند
  (`camera/ANCHORS.json`).

## تست‌ها
```
python3 studio/tests/test_camera.py                 # T1 + T2 (آفلاین)
python3 studio/tests/camera_local_check.py --project motion-demo-fa --timing <timing.json> \
        --fonts <dir> --gsap <gsap.min.js> --work <dir خارج از مخزن> [--render]   # T3 (+ T4 رندر و Verify)
python3 studio/tests/make_motion_demo_assets.py     # ساخت دوباره تصاویر نمایشی (قطعی)
```

## پروژه نمایشی
`studio/projects/motion-demo-fa`: همان ۶ جمله Stage 2 (صدای آن‌ها در Cache هست؛ بدون Gemini)، تصاویر ساخته‌شده محلی.
