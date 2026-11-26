# AI-Kline - A-share Technical Analysis and AI Prediction Tool



## Project Structure

```
AI-Kline/
├── main.py                 # CLI entry point
├── web_app.py              # Web app entry point
├── mcp_server.py           # MCP server entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── modules/                # Core modules
│   ├── __init__.py
│   ├── data_fetcher.py     # Data acquisition (Tushare + AKShare fallback)
│   ├── technical_analyzer.py # Technical indicators
│   ├── visualizer.py       # Chart generation (matplotlib + pyecharts)
│   └── ai_analyzer.py      # AI analysis (OpenAI-compatible multimodal API)
├── templates/
│   └── index.html          # Web UI template
├── static/
│   ├── css/style.css
│   └── js/main.js
├── assets/
│   └── echarts.min.js      # Bundled ECharts for offline interactive charts
└── output/                 # Generated at runtime (git-ignored)
    ├── charts/
    └── *_analysis_result.txt
```



