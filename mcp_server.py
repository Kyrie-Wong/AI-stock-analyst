from mcp.server.fastmcp import FastMCP

import os
import sys
import argparse
import json
import logging
import asyncio
from dotenv import load_dotenv

from modules.data_fetcher import StockDataFetcher
from modules.technical_analyzer import TechnicalAnalyzer
from modules.visualizer import Visualizer
from modules.ai_analyzer import AIAnalyzer

# Initialize FastMCP server
mcp = FastMCP("AI-Kline")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

@mcp.tool()
async def ashare_analysis(symbol: str
                                   ) -> str:
    """
    分析股票
    Args:
        symbol: A股股票代码或者指数代码 (股票代码： 000001, 600001, 300001)。
                若只知道股票名称（如"宁德时代"），请先调用 lookup_ashare_code 查询代码。
    """
    try:
        analysis_result = await run_in_threadpool(pattern_run, symbol=symbol)
        return analysis_result
    except Exception as e:
        logger.error(f"Error analyzing stock pattern: {e}")
        return f"Failed to analyze stock pattern: {str(e)}"
    
@mcp.tool()
async def get_ashare_quote(symbol: str, period: str = '1周'
                                   ) -> str:
    """
    获取股票行情数据
    Args:
        symbol: A股股票代码或者指数代码 (股票代码： 000001, 600001, 300001)
        period: 分析周期 (1年, 6个月, 3个月, 1个月, 1周)
    """
    try:
        data_fetcher = StockDataFetcher()
        stock_data = data_fetcher.fetch_stock_data(symbol, period)
        analysis_result = stock_data.to_dict()
        return str(analysis_result)
    except Exception as e:
        logger.error(f"Error analyzing stock pattern: {e}")
        return f"Failed to analyze stock pattern: {str(e)}"

@mcp.tool()
async def get_ashare_news(symbol: str
                                   ) -> str:
    """
    获取股票新闻
    Args:
        symbol: A股股票代码或者指数代码 (股票代码： 000001, 600001, 300001)
    """
    try:
        financial_data = {}
        data_fetcher = StockDataFetcher()
        news_data = data_fetcher.fetch_news_data(symbol)
        financial_data['news'] = news_data
        analysis_result = json.dumps(financial_data, ensure_ascii=False, indent=2)
        return analysis_result
    except Exception as e:
        logger.error(f"Error analyzing stock pattern: {e}")
        return f"Failed to analyze stock pattern: {str(e)}"
    
@mcp.tool()
async def get_ashare_financial(symbol: str
                                   ) -> str:
    """
    获取股票财务数据
    Args:
        symbol: A股股票代码或者指数代码 (股票代码： 000001, 600001, 300001)
    """
    try:
        data_fetcher = StockDataFetcher()
        financial_data = data_fetcher.fetch_financial_data(symbol)
        analysis_result = json.dumps(financial_data, ensure_ascii=False, indent=2)
        return analysis_result
    except Exception as e:
        logger.error(f"Error analyzing stock pattern: {e}")
        return f"Failed to analyze stock pattern: {str(e)}"
    

@mcp.tool()
async def get_ashare_capital_flow(symbol: str
                                   ) -> str:
    """
    获取股票资金流向与融资融券数据
    Args:
        symbol: A股股票代码 (股票代码： 000001, 600001, 300001)
    """
    try:
        data_fetcher = StockDataFetcher()
        capital_flow = data_fetcher.fetch_capital_flow(symbol)
        result = {}
        for key, df in capital_flow.items():
            result[key] = df.tail(10).to_dict('records') if df is not None and not df.empty else []
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error getting capital flow: {e}")
        return f"Failed to get capital flow: {str(e)}"


@mcp.tool()
async def lookup_ashare_code(name: str
                                   ) -> str:
    """
    按股票名称查询A股代码
    Args:
        name: 股票简称，支持模糊匹配（如"宁德时代" -> 300750.SZ）
    """
    try:
        data_fetcher = StockDataFetcher()
        result = data_fetcher.lookup_stock_code(name)
        if not result:
            return f"未找到名称包含 {name} 的股票"
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error looking up stock code: {e}")
        return f"Failed to look up stock code: {str(e)}"


async def run_in_threadpool(func, *args, **kwargs):
    """Run a synchronous function in a threadpool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

def pattern_run(symbol: str, period: str = '1年', start_date: str = None,
                end_date: str = None, save_path: str = './output') -> str:
    # 统一用6位纯代码命名输出文件，避免 300750 与 300750.SZ 生成两套图表
    symbol = symbol.strip().split('.')[0].upper().removeprefix('SH').removeprefix('SZ').removeprefix('BJ').strip('.')


    # 初始化各模块
    data_fetcher = StockDataFetcher()
    technical_analyzer = TechnicalAnalyzer()
    visualizer = Visualizer()
    ai_analyzer = AIAnalyzer()

    # 获取股票数据
    print(f"正在获取 {symbol} 的历史数据...")
    stock_data = data_fetcher.fetch_stock_data(symbol, period, start_date, end_date)

    # 获取财务和新闻数据
    print(f"正在获取 {symbol} 的财务和新闻数据...")
    financial_data = data_fetcher.fetch_financial_data(symbol)
    news_data = data_fetcher.fetch_news_data(symbol)

    # 获取资金流向与两融数据
    print(f"正在获取 {symbol} 的资金流向与两融数据...")
    capital_flow = data_fetcher.fetch_capital_flow(symbol, period, start_date, end_date)

    # 获取估值数据（最新值 + 近一年分位）
    valuation = data_fetcher.fetch_valuation_stats(symbol)
    
    # 计算技术指标
    print("正在计算技术指标...")
    indicators = technical_analyzer.calculate_indicators(stock_data)
    
    # 生成可视化图表
    print("正在生成K线图和技术指标图...")
    chart_path = visualizer.create_charts(stock_data, indicators, symbol, save_path, capital_flow)
    
    # AI分析预测
    print("正在使用AI分析预测未来走势...")
    analysis_result = ai_analyzer.analyze(stock_data, indicators, financial_data, news_data, symbol, save_path, capital_flow, valuation)

    return analysis_result 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-Kline MCP Server")
    parser.add_argument('--transport', choices=['stdio', 'streamable-http'],
                        default='streamable-http',
                        help='传输方式：stdio 供 MCP 客户端（如 Kimi Code）本地启动；'
                             'streamable-http 供远程/常驻连接（默认）')
    args = parser.parse_args()

    if args.transport == 'stdio':
        # stdio 协议独占 stdout：把 print 等输出重定向到 stderr，
        # 但保留 sys.stdout.buffer 给 SDK 写 JSON-RPC，避免协议被污染
        class _StdoutShim:
            def __init__(self, real_stdout):
                self.buffer = real_stdout.buffer  # SDK 协议写入仍走真实 stdout
                self._stderr = sys.stderr

            def write(self, s):
                return self._stderr.write(s)

            def flush(self):
                return self._stderr.flush()

        sys.stdout = _StdoutShim(sys.stdout)
        mcp.run(transport='stdio')
    else:
        mcp.run(transport='streamable-http')
