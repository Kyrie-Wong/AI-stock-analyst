import os
import argparse
from dotenv import load_dotenv

from modules.data_fetcher import StockDataFetcher
from modules.technical_analyzer import TechnicalAnalyzer
from modules.visualizer import Visualizer
from modules.ai_analyzer import AIAnalyzer

# 加载环境变量
load_dotenv()

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='AI看线 - A股技术分析与AI预测工具')
    parser.add_argument('--stock_code', type=str, required=True, help='股票代码，例如：000001')
    parser.add_argument('--period', type=str, default='1年', help='分析周期，默认为1年')
    parser.add_argument('--start_date', type=str, default=None, help='开始日期 YYYY-MM-DD，指定后优先于周期')
    parser.add_argument('--end_date', type=str, default=None, help='结束日期 YYYY-MM-DD，默认为今天')
    parser.add_argument('--save_path', type=str, default='./output', help='结果保存路径')
    args = parser.parse_args()
    
    # 确保输出目录存在
    os.makedirs(args.save_path, exist_ok=True)
    
    # 初始化各模块
    data_fetcher = StockDataFetcher()
    technical_analyzer = TechnicalAnalyzer()
    visualizer = Visualizer()
    ai_analyzer = AIAnalyzer()
    
    # 获取股票数据
    print(f"正在获取 {args.stock_code} 的历史数据...")
    stock_data = data_fetcher.fetch_stock_data(args.stock_code, args.period, args.start_date, args.end_date)
    
    # 获取财务和新闻数据
    print(f"正在获取 {args.stock_code} 的财务和新闻数据...")
    financial_data = data_fetcher.fetch_financial_data(args.stock_code)
    news_data = data_fetcher.fetch_news_data(args.stock_code)

    # 获取资金流向与两融数据
    print(f"正在获取 {args.stock_code} 的资金流向与两融数据...")
    capital_flow = data_fetcher.fetch_capital_flow(args.stock_code, args.period, args.start_date, args.end_date)

    # 获取估值数据（最新值 + 近一年分位）
    valuation = data_fetcher.fetch_valuation_stats(args.stock_code)
    
    # 计算技术指标
    print("正在计算技术指标...")
    indicators = technical_analyzer.calculate_indicators(stock_data)
    
    # 生成可视化图表
    print("正在生成K线图和技术指标图...")
    chart_path = visualizer.create_charts(stock_data, indicators, args.stock_code, args.save_path, capital_flow)
    
    # AI分析预测
    print("正在使用AI分析预测未来走势...")
    analysis_result = ai_analyzer.analyze(stock_data, indicators, financial_data, news_data, args.stock_code, args.save_path, capital_flow, valuation)
    
    # 保存分析结果
    result_path = os.path.join(args.save_path, f"{args.stock_code}_analysis_result.txt")
    with open(result_path, 'w', encoding='utf-8') as f:
        f.write(analysis_result)
    
    print(f"\n分析完成！")
    print(f"K线图和技术指标图已保存至: {chart_path}")
    print(f"AI分析结果已保存至: {result_path}")

if __name__ == "__main__":
    main()