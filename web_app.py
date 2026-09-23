import os
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from modules.data_fetcher import StockDataFetcher
from modules.technical_analyzer import TechnicalAnalyzer
from modules.visualizer import Visualizer
from modules.ai_analyzer import AIAnalyzer
from dotenv import load_dotenv
import matplotlib
# 设置 matplotlib 使用非 GUI 后端以避免 tkinter 依赖
matplotlib.use('Agg')

# 加载环境变量
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')

# 确保输出目录存在
os.makedirs('./output', exist_ok=True)
os.makedirs('./output/charts', exist_ok=True)

# 初始化各模块
data_fetcher = StockDataFetcher()
technical_analyzer = TechnicalAnalyzer()
visualizer = Visualizer()
ai_analyzer = AIAnalyzer()

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """分析股票"""
    data = request.form
    stock_code = data.get('stock_code')
    period = data.get('period') or '1年'  # 未选择周期时按默认1年（日期区间优先）
    start_date = data.get('start_date') or None  # 留空则按周期计算
    end_date = data.get('end_date') or None      # 留空默认为今天
    save_path = './output'

    if not stock_code:
        return jsonify({'error': '请输入股票代码'}), 400

    try:
        # 获取股票数据
        stock_data = data_fetcher.fetch_stock_data(stock_code, period, start_date, end_date)

        if stock_data.empty:
            return jsonify({'error': f'未找到股票 {stock_code} 的数据'}), 404

        # 获取财务和新闻数据
        financial_data = data_fetcher.fetch_financial_data(stock_code)
        news_data = data_fetcher.fetch_news_data(stock_code)

        # 获取资金流向与两融数据
        capital_flow = data_fetcher.fetch_capital_flow(stock_code, period, start_date, end_date)

        # 获取估值数据（最新值 + 近一年分位）
        valuation = data_fetcher.fetch_valuation_stats(stock_code)

        # 计算技术指标
        indicators = technical_analyzer.calculate_indicators(stock_data)

        # 生成可视化图表
        chart_path = visualizer.create_charts(stock_data, indicators, stock_code, save_path, capital_flow)

        # AI分析预测
        analysis_result = ai_analyzer.analyze(stock_data, indicators, financial_data, news_data, stock_code, save_path, capital_flow, valuation)
        
        # 保存分析结果
        result_path = os.path.join(save_path, f"{stock_code}_analysis_result.txt")
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(analysis_result)
        
        # 准备返回数据：K线图在前，资金流图在后
        chart_files = []
        for file in os.listdir(os.path.join(save_path, 'charts')):
            # 只匹配以"代码_"开头的文件，避免 002436 也命中 002436.SZ_ 等重复图表
            if file.startswith(f"{stock_code}_") and (file.endswith('.png') or file.endswith('.html')):
                chart_files.append(file)

        def chart_order(name):
            if 'interactive_chart' in name:
                return 0   # K线图
            if 'capital_flow' in name:
                return 1   # 资金流图
            return 2

        chart_files.sort(key=chart_order)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'charts': chart_files,
            'analysis_result': analysis_result
        })
    
    except Exception as e:
        return jsonify({'error': f'分析过程中出错: {str(e)}'}), 500

@app.route('/output/charts/<path:filename>')
def serve_chart(filename):
    """提供图表文件"""
    return send_from_directory('output/charts', filename)

@app.route('/daily_basic/<stock_code>')
def get_daily_basic(stock_code):
    """获取估值与交易指标（市盈率/市净率/市值/量比/换手率/成交额）"""
    try:
        data = data_fetcher.fetch_daily_basic(stock_code)
        if not data:
            return jsonify({'success': False, 'error': f'未获取到 {stock_code} 的估值指标'}), 404
        # 合并最新日成交额（亿元）
        amount_info = data_fetcher.fetch_daily_amount(stock_code)
        if amount_info:
            data['amount'] = amount_info['amount']
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'error': f'获取估值指标时出错: {str(e)}'}), 500

@app.route('/top_list/<stock_code>')
def get_top_list(stock_code):
    """获取龙虎榜数据（收盘价/涨跌幅/净买入额/净买额占比/上榜理由）"""
    try:
        data = data_fetcher.fetch_top_list(stock_code)
        if not data:
            return jsonify({'success': False, 'error': f'{stock_code} 近90日未上龙虎榜或无权限'}), 404
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'error': f'获取龙虎榜数据时出错: {str(e)}'}), 500

@app.route('/stock_info/<stock_code>')
def get_stock_info(stock_code):
    """获取股票基本信息"""
    try:
        import akshare as ak
        stock_info = ak.stock_individual_info_em(symbol=stock_code)
        if not stock_info.empty:
            # 转换为字典列表
            info_dict = {
                row['item']: row['value'] 
                for _, row in stock_info.iterrows()
            }
            return jsonify({'success': True, 'data': info_dict})
        else:
            return jsonify({'error': f'未找到股票 {stock_code} 的信息'}), 404
    except Exception as e:
        return jsonify({'error': f'获取股票信息时出错: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=False)  # 禁用多线程