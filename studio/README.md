# NFP Studio (Phase 1): scene-based reels and shorts

هر ویدیو یک پوشه زیر `studio/projects/` است با یک فایل `project.json`.

## ساخت ویدیوی جدید
1. پوشه‌ی `studio/projects/wrinkled-palms-fa` را کپی کن و اسمش را عوض کن (فقط حروف انگلیسی، عدد و `-`).
2. `project.json` را ویرایش کن:
   - `meta.lang`: `fa` یا `en`
   - هر صحنه: `id`، `template`، `narration` (یک یا چند جمله)، `on_screen`
3. در GitHub: Actions ← **Studio Build** ← Run workflow ← اسم پوشه را بنویس ← `confirm_free_tier` را فقط بعد از چک کردن free-tier روی YES بگذار.
4. خروجی (MP4، SRT، گزارش) در Artifacts همان اجرا است.

## قالب‌های صحنه
| template | فیلدهای on_screen |
|---|---|
| `title` | `title` (≤24)، `subtitle` (≤40)، `icon` |
| `compare` | `a` و `b`: `big` (≤14)، `small` (≤18)، `tone` (ok/warn)، `icon` |
| `info` | `heading` (≤30)، `lines` (۱ تا ۳ خط، هرکدام ≤36)، `icon` |
| `steps` | `heading`، `items` (۲ تا ۴ مورد: `icon`، `text` ≤22) |
| `cta` | `heading` (≤30)، `note` (≤60)، `handle` (≤30)، `icon` |

آیکون‌ها: alert, clipboard, clock, cross, drop, hand, info, jar, thermometer

## قواعد
- هر جمله حداکثر ۱۶۰ کاراکتر (با نقطه جمله‌ها را جدا کن). مجموع حداکثر ۴۰ جمله.
- فعلاً فقط `9:16`. فرمت ۱۶:۹ در فاز مستند می‌آید.
- هر جمله‌ی جدید = یک درخواست TTS. جمله‌های تکراری از کش می‌آیند.
- گرافیک‌ها فقط در بالای صفحه (y 110-540) و پایین (y 1400-1630) هستند. نوار وسط مخصوص کپشن است.

## تست آفلاین (اختیاری)
```
python3 studio/tests/test_studio.py
```
