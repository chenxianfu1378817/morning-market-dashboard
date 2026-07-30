# Morning Market Dashboard

一个适合手机查看的每日晨报页面：广西、广东天气，以及国际原油期货行情。

## 数据与运行

- 天气：Open-Meteo，默认展示南宁、桂林、广州、深圳，可在 `scripts/fetch_data.py` 调整城市。
- 原油：Yahoo Finance 公开行情接口，展示 WTI（CL=F）和 Brent（BZ=F）的最新价与前收价；页面显示抓取时间。
- GitHub Actions：每天北京时间 07:00 自动抓取并提交 `data/latest.json`。
- 页面：GitHub Pages 发布 `index.html`，手机浏览器可直接打开。

行情数据可能有延迟，仅供信息参考，不构成交易建议。
