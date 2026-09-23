# 环境验证脚本：只测数据链路（行情/财务/新闻 + 技术指标 + 画图），不调用 AI 模型
import os
from dotenv import load_dotenv

from modules.data_fetcher import StockDataFetcher
from modules.technical_analyzer import TechnicalAnalyzer
from modules.visualizer import Visualizer

load_dotenv()

STOCK = '000001'  # 平安银行
SAVE = './output'
os.makedirs(SAVE, exist_ok=True)

fetcher = StockDataFetcher()
analyzer = TechnicalAnalyzer()
viz = Visualizer()

print(f"[1/4] 获取 {STOCK} 历史行情...")
stock_data = fetcher.fetch_stock_data(STOCK, '3个月')
print(f"      OK - {len(stock_data)} 行, 最新日期: {stock_data.index[-1] if hasattr(stock_data.index[-1], 'strftime') else stock_data.index[-1]}")

print("[2/4] 获取财务与新闻数据...")
fin = fetcher.fetch_financial_data(STOCK)
news = fetcher.fetch_news_data(STOCK)
print(f"      OK - 财务字段 {len(fin) if fin is not None else 0}, 新闻 {len(news) if news is not None else 0} 条")

print("[3/4] 计算技术指标...")
ind = analyzer.calculate_indicators(stock_data)
print(f"      OK - {list(ind.keys()) if isinstance(ind, dict) else type(ind)}")

print("[4/4] 生成图表...")
chart = viz.create_charts(stock_data, ind, STOCK, SAVE)
print(f"      OK - {chart}")

print("\nVERIFY_PASS")
