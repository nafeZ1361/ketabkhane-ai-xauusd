# مدل هزینهٔ بروکر

## قاعده
مشخصات بروکر «داده» است، نه حدس. هر فیلد باید از منبع مستند (Specification نماد در MT5 و برنامهٔ کمیسیون حساب) بیاید.
اگر فیلدی خالی یا صفر-ناشناخته باشد، بارگذار پروفایل را **رد می‌کند** (`UnknownSpecError`) تا هزینهٔ نامعلوم به‌عنوان هزینهٔ واقعی وارد نتیجه نشود.

## پروفایل
فایل نمونه: `config/broker_profile.example.json` — همهٔ مقادیر `null` و `verified: false` هستند و تا پر نشدن رد می‌شوند.

فیلدهای الزامی:
`contract_size`, `point_size`, `tick_size`, `tick_value`, `spread_points`,
`slippage_points`, `commission_per_lot_round_turn`, `lots`, `min_lot`, `lot_step`,
به‌همراه `profile_id`, `symbol`, `source`, `verified`.

## فرمول
```
cost_per_trade = (spread_points + slippage_points) * point_size * contract_size * lots
               + commission_per_lot_round_turn * lots

gross = (exit_price - entry_price) * contract_size * lots
net   = gross - cost_per_trade
```

## برچسب‌ها
| برچسب | معنا |
|---|---|
| `NO_TRADING_COSTS` | بدون مدل هزینه؛ سود/زیان در واحد قیمت |
| `PROVISIONAL_COST_SCENARIO` | پروفایل ناتأییدشده؛ نتیجه فقط سناریوی فرضی است |
| `VERIFIED_COSTS` | پروفایل با منبع مستند و `verified: true` |

`pnl_unit` در `summary.json` مشخص می‌کند عدد در «واحد قیمت» است یا «ارز حساب».

## نمونهٔ اجرا (مقادیر فرضی، نه داده واقعی بروکر)
پروفایل فرضی: قرارداد ۱۰۰، نقطه ۰٫۰۱، اسپرد ۲۵، اسلیپیج ۲، کمیسیون ۷، حجم ۰٫۱ لات
→ `cost_per_trade = 3.4`

- روی ۳۰۰٬۰۰۰ ردیف، ۹٬۸۹۰ معامله
- بدون هزینه: `-36.37` واحد قیمت
- با هزینهٔ فرضی: `-33,996.8` ارز حساب (برچسب `PROVISIONAL_COST_SCENARIO`)

این دو عدد هم‌واحد نیستند و نباید مستقیم مقایسه شوند؛ `pnl_unit` همین را نشان می‌دهد.

> این پروفایل فقط برای اثبات کارکرد موتور بوده و در مخزن ثبت نشده است.