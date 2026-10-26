# شواهد ادغام کاتالوگ TradingView و حلقه بازخورد یادگیری ماشین (DEC-2026-029)

- تاریخ: 2026-10-26
- ماژول‌ها: `src/xauusd_research/indicators/`, `src/xauusd_research/ml_engine/`
- آزمون‌ها: `tests/test_tv_indicators.py`, `tests/test_ml_feedback.py`

## ۱. نتایج آزمون‌های یکپارچگی (scripts/quality.py)
- کل آزمون‌ها: ۱۰۹ آزمون (۱۴ آزمون جدید اضافه شد).
- شکست‌ها / خطاها: صفر (100% Green).
- پوشش کد (Coverage): ۹۴٫۹۲٪ (آستانه مجاز ۸۰٪).
- بررسی کاراکترها و کدگذاری (check_encoding.py): صفر مورد mojibake.

## ۲. کاتالوگ و پیاده‌سازی‌های TradingView
کاتالوگ سیستم شامل بیش از ۳۵ توسعه‌دهنده سرشناس جامعه تریدینگ‌ویو و تیم‌های کمی است:
- **پیاده‌سازی‌های متن‌باز تاییدشده (VERIFIED_IMPLEMENTED):**
  1. `calculate_supertrend`: الگوریتم trailing ATR بدون بازنگاری (everget / KivancOzbilgic).
  2. `calculate_squeeze_momentum`: فشرده‌سازی باندهای بولینگر درون کانال کلتنر با رگرسیون خطی مومنتوم (LazyBear).
  3. `calculate_halftrend`: کانال پویا بر پایه انحراف ATR و پایدار در برابر بازنگاری (everget).
  4. `calculate_smc_structure`: ساختار نقدینگی و تشخیص BOS و CHoCH با تایید کندل بسته (LuxAlgo / Hashem).
  5. `calculate_wavetrend`: نوسانگر واگرایی میانگین متحرک دوگانه هموار (LazyBear / پایه متن‌باز VuManChu و Cipher B).
  6. `calculate_donchian_channel`: کانال شکست سقف و کف دوره‌ای بدون سوگیری نگاه به آینده.
- **موارد نیازمند ممیزی کد یا الگوریتم‌های اختصاصی (UNVERIFIED_PENDING_AUDIT):**
  - کدهای تجاری و جعبه‌سیاه (مانند MarketCipher، TradeDots، ChartPrime، TrendSpider) به صورت شفاف ثبت و معادل‌های باز و ریاضیاتی آن‌ها مستند شده‌اند تا از هرگونه کد جعلی جلوگیری شود.

## ۳. حلقه بازخورد پیوسته یادگیری ماشین (Machine Learning Feedback Loop)
- **موتور رژیم بازار (`RegimeDecisionEngine`):** دسته‌بندی پویای بازار به چهار حالت:
  - `BULL_TREND`: روند صعودی با ضریب ریسک کامل
  - `BEAR_TREND`: روند نزولی با ضریب ریسک کامل
  - `CHOPPY_RANGE`: نوسانات بی‌روند با کاهش ۵۰ درصدی حجم
  - `VOLATILITY_SHOCK`: انبساط ناگهانی نوسان با قفل نقدینگی کامل (Cash Lockout)
- **حلقه بازخورد تطبیقی (`AdaptiveFeedbackLoop`):**
  - ثبت خطاهای معاملات در دفتر رویداد ساختاریافته JSONL (`feedback_ledger.jsonl`).
  - تشخیص ریشه‌ای خطاها: شلاق در رِنج (`CHOP_WHIPSAW`)، اصطکاک اسپرد (`SPREAD_OVERRUN`)، استاپ‌اوت در نویز (`PREMATURE_EXIT`)، و شوک نوسان (`VOL_SHOCK_LOSS`).
  - تنظیم خودکار پارامترها (افزایش آستانه اطمینان ورود در شرایط رِنج، تطبیق ضریب مولتی‌پلایر ATR استاپ).
