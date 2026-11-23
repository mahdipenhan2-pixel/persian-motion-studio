# NFP Character Engine — مرحله C1 (لایه داده)

این مرحله فقط لایه داده است: مستقل از Rig، مرورگر، شبکه و API. هیچ فایل موجودی را تغییر نمی‌دهد.

## اصل‌ها
- **شخصیت = داده پروژه، نه کد.** هر پروژه فایل `cast.json` خودش را دارد. هیچ شخصیت ثابت و مشترکی برای همه ویدیوها وجود ندارد. فقط «قطعه‌ها» (بدن، مو، لباس، حالت چهره) در کاتالوگ سبک مشترک‌اند.
- **هویت قفل است.** `identity` (پوست، رنگ مو، رنگ چشم، چهره، نشانه‌ها) به‌علاوه سبک، fingerprint (SHA-256) دارد و در `cast.lock.json` ثبت می‌شود. تغییر هویت بدون به‌روزرسانی عمدی قفل خطا می‌دهد. تغییر لباس، مرحله سنی یا مدل مو قفل جدید نمی‌خواهد.
- **صحنه هویت را عوض نمی‌کند.** صحنه فقط می‌تواند `character`، `stage`، `wardrobe` و `expr` را انتخاب کند. فیلدهایی مثل `skin` یا `hairColor` رد می‌شوند.
- **ایزوله‌سازی پروژه‌ها.** `id`ها محلی‌اند و شناسه DOM با پروژه پیشوند می‌گیرد (`nfp-c-<project>-<id>-<n>`). هویت یکسان در دو پروژه بدون `derived_from` به‌عنوان «کپی ناخواسته» گزارش می‌شود.
- **Renderer افزونه است.** واژگان هر سبک در `parts/<style>.json` است (فعلاً `flat_cartoon_v2`، یعنی Rig فعلی). سبک‌های بعدی (مثلاً نیمه‌واقع‌گرا) کاتالوگ خودشان را می‌آورند.
- **سیاست افراد واقعی.** `provenance.real_person: true` فقط با `depiction: "symbolic"` و حداقل یک منبع مستند مجاز است. هیچ URL یا ارجاع بیرونی در شخصیت مجاز نیست.

## فایل‌ها
| فایل | مسئولیت |
|---|---|
| `schema/cast.v1.json` | قرارداد رسمی (JSON Schema 2020-12) برای فایل cast و ارجاع صحنه |
| `parts/flat_cartoon_v2.json` | واژگان مجاز سبک فعلی (بدن، مو، لباس، حالت چهره و غیره) |
| `registry.py` | بارگذاری، اعتبارسنجی، resolve، fingerprint، قفل، بررسی ارجاع صحنه |
| `isolation.py` | شناسه DOM پروژه‌محور، تشخیص کپی ناخواسته، بررسی `derived_from` |
| `policy.py` | قواعد افراد واقعی، منع URL، منع کاراکتر کنترلی |
| `cli.py` | `check` / `lock [--write]` / `resolve` / `scan` |
| `examples/demo-cast/` | نمونه دو شخصیت فارسی با قفل |
| `tests/test_character.py` | تست‌های آفلاین T1 (schema و policy) و T2 (قفل، resolve، ایزوله‌سازی، CLI) |

## اجرا
```
python3 nfp/character/cli.py check   nfp/character/examples/demo-cast
python3 nfp/character/cli.py lock    <project> --write       # فقط وقتی تغییر هویت عمدی است
python3 nfp/character/cli.py resolve <project> zahra --stage child --expr happy
python3 nfp/character/cli.py scan    <root>                  # همه <root>/*/cast.json با هم
python3 nfp/character/tests/test_character.py
```

## مراحل بعدی (هرکدام با تأیید جداگانه)
C2 انتقال Rig عمومی به main، C3 runtime و adapter و قرارداد قطعات، C4 لایه Studio 9:16 زیر Camera Motion، C5 اتصال به Director 16:9، C6 سبک نیمه‌واقع‌گرا.
