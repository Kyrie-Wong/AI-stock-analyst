# -*- coding: utf-8 -*-
"""验证 prompt 升级后的数据准备：估值分位、MA120、近20日指标序列"""
import sys, json
sys.path.insert(0, '.')
from modules.data_fetcher import StockDataFetcher
from modules.technical_analyzer import TechnicalAnalyzer
from modules.ai_analyzer import AIAnalyzer

CODE = '601138'

fetcher = StockDataFetcher()

# 1. 估值统计
val = fetcher.fetch_valuation_stats(CODE)
print('=== fetch_valuation_stats ===')
print(json.dumps(val, ensure_ascii=False, indent=2))

# 2. 财务（营收同比）
fin = fetcher.fetch_financial_data(CODE)
print('\n=== fetch_financial_data 关键指标 ===')
print(json.dumps(fin.get('关键指标', {}), ensure_ascii=False, indent=2))

# 3. _prepare_analysis_data 新字段
stock_data = fetcher.fetch_stock_data(CODE, '1年')
indicators = TechnicalAnalyzer().calculate_indicators(stock_data)
capital = fetcher.fetch_capital_flow(CODE, '1年')
analyzer = AIAnalyzer.__new__(AIAnalyzer)  # 不初始化 API client，只测数据准备
data = analyzer._prepare_analysis_data(stock_data, indicators, fin,
                                       [], CODE, '工业富联', capital, val)
print('\n=== analysis_data 新增/关键字段 ===')
for k in ['MA60', 'MA120', '近30日最高', '近30日最低', '估值数据']:
    print(f'{k}: {json.dumps(data.get(k), ensure_ascii=False)}')
s = data['近20日技术指标']
print('近20日技术指标 序列长度:',
      {k: (len(v) if isinstance(v, list) else v) for k, v in s.items()})

# 4. prompt 构建 + JSON 可序列化
prompt = analyzer._build_prompt(data, CODE, '工业富联')
json.dumps(data, ensure_ascii=False)  # 确保可序列化
print('\n=== prompt 长度:', len(prompt), '===')
print(prompt[:400])
print('...')
assert '预测未来一周上涨的概率' in prompt
assert '近20日技术指标' in prompt
print('\nOK: 全部通过')
