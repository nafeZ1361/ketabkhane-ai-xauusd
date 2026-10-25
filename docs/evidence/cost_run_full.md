# اجرای کل دیتاست با مدل هزینهٔ بروکر

- تاریخ: 2026-10-25
- پروفایل: `config/broker_profile.json` (`XAUUSD-AronMarkets-2026-10`)
- حالت: `stream` | زمان مرجع: UTC | سیاست: `eu-dst`

## منابع اعداد (هیچ عددی حدس زده نشده)

| پارامتر | مقدار | منبع |
|---|---|---|
| Contract size | 100 | Specification در MT5 (اسکرین‌شات) |
| Digits / point | 2 / 0.01 | Specification؛ point = 10^-digits (تعریف MT5) |
| Min lot / step / max | 0.01 / 0.01 / 10 | Specification |
| Stops level | 10 | Specification |
| Commission | 0.00 | تاریخچهٔ معاملات حساب (کارمزد ورود و خروج صفر) |
| Swap | 0.00 | تاریخچهٔ معاملات |
| Spread | 30 point (میانه) | ستون SPREAD خودِ دیتاست (۳٬۴۸۹٬۳۵۹ ردیف) |
| Slippage | 0 | مدل نشده (محدودیت) |

تأیید متقابل: در تاریخچهٔ معاملات، حرکت ۶٫۰۵ دلاری قیمت روی ۰٫۰۱ لات دقیقاً ۶٫۰۵ دلار سود/زیان داده است؛ یعنی ارزش هر ۱ دلار حرکت قیمت برای ۰٫۰۱ لات = ۱ دلار (Contract size = ۱۰۰).

## هزینهٔ هر معامله

`
cost = 30 * 0.01 * 100 * 0.01 = 0.30 USD
`

## نتیجه

```json
{
  "strategy": "ma_5_20",
  "fast": 5,
  "slow": 20,
  "cost_label": "PROVISIONAL_COST_SCENARIO",
  "pnl_unit": "ACCOUNT_CURRENCY",
  "broker_profile": {
    "profile_id": "XAUUSD-AronMarkets-2026-10",
    "symbol": "XAUUSD",
    "source": "MT5 Specification screenshot (AronMarkets-Demo, XAUUSD Gold vs US Dollar/Spot): digits=2, contract_size=100, min_lot=0.01, lot_step=0.01, max_lot=10, stops_level=10, spread=floating. Trade history 2026-09-07: commission=0.00 and swap=0.00 for 0.01 lot; price move 6.05 USD on 0.01 lot = 6.05 USD P/L (confirms contract_size=100). point_size = 10^-digits = 0.01 (MT5 definition). tick_value derived = tick_size * contract_size = 1.0. spread_points = median 30 of the dataset SPREAD column (3,489,359 rows); slippage not modeled.",
    "verified": false,
    "contract_size": 100.0,
    "point_size": 0.01,
    "spread_points": 30.0,
    "slippage_points": 0.0,
    "commission_per_lot_round_turn": 0.0,
    "lots": 0.01,
    "cost_per_trade": 0.3
  },
  "server_tz": "eu-dst",
  "time_reference": "UTC",
  "rows": 3489359,
  "gaps": 6505,
  "issues": [],
  "metrics": {
    "trades": 114014,
    "net_pnl": -36572.71,
    "win_rate": 0.241821,
    "profit_factor": 0.6445876073762481,
    "max_drawdown": 36628.9
  },
  "input_sha256": "e539f77788859c25f6d8b53606f89e7e3531af1c46ff53207d9f0831dc2acb9e"
}
```

## مقایسه با اجرای بدون هزینه

| مورد | بدون هزینه | با هزینه |
|---|---|---|
| معاملات | 114,014 | 114,014 |
| سود خالص | ‎-2,368.51‎ واحد قیمت | ‎-36,572.71‎ دلار |
| هزینهٔ کل | 0 | ‎-34,204.20‎ دلار |

با حجم ۰٫۰۱ لات، هر واحد قیمت معادل یک دلار است؛ بنابراین مقیاس دو ستون یکسان است.

## نتیجه‌گیری صادقانه

هزینهٔ معاملات (۳۴٬۲۰۴ دلار) حدود ۱۴ برابر زیان خالص بدون هزینه است. یعنی استراتژی فعلی (تقاطع MA 5/20) با این تعداد معامله و این اسپرد، **از نظر اقتصادی ناپایدار** است. این یک نتیجهٔ منفی معتبر است، نه شکست ابزار.

## محدودیت‌ها

- اسپرد ثابت (میانه) فرض شده است؛ اسپرد واقعی در هر کندل متفاوت است و در اخبار تا ۲۰۰۵ point هم دیده شده.
- اسلیپیج و سواپ شبانه مدل نشده‌اند.
- برچسب نتیجه `PROVISIONAL_COST_SCENARIO` است.