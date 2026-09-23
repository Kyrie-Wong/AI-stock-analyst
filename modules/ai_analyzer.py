import os
import re
from PIL import Image
from openai import OpenAI
# from google import genai
# from google.genai import types
import pandas as pd
import json
from datetime import datetime
import io
import base64
import threading
import logging
from dotenv import load_dotenv


# 配置日志以调试线程问题
logging.basicConfig(level=logging.DEBUG, format='%(threadName)s: %(message)s')

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://api.x.ai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "grok-2-vision-1212")  # 默认模型名称

class AIAnalyzer:
    """
    AI分析类，负责使用Gemini API分析股票数据并预测未来走势
    """
    
    def __init__(self):
        # 初始化Gemini API
        if API_KEY:
            # self.client = genai.Client(api_key=api_key)
            # Initialize OpenAI client with API key
            self.client = OpenAI(
                api_key=API_KEY,
                base_url=BASE_URL,
            )
        else:
            print("警告: 未设置API_KEY环境变量，AI分析功能将无法使用")
            print("请在.env文件中添加: API_KEY=your_api_key")
    
    def analyze(self, stock_data, indicators, financial_data, news_data, stock_code, save_path, capital_flow_data=None, valuation_data=None):
        """
        使用Gemini分析股票数据并预测未来走势

        参数:
            stock_data (pandas.DataFrame): 股票历史数据
            indicators (dict): 技术指标数据
            financial_data (dict): 财务数据
            news_data (list): 新闻数据
            stock_code (str): 股票代码
            capital_flow_data (dict): 资金流数据 {'moneyflow': DataFrame, 'margin': DataFrame}，可为 None
            valuation_data (dict): 估值数据（fetch_valuation_stats 返回值），可为 None

        返回:
            str: 分析结果文本
        """
        if not os.getenv("API_KEY"):
            return "错误: 未设置API_KEY环境变量，无法使用AI分析功能。请在.env文件中添加API_KEY。"
        
        try:
            # 记录当前线程以调试
            logging.debug(f"运行 analyze 方法的线程: {threading.current_thread().name}")
            
            # 获取股票名称
            try:
                import akshare as ak
                stock_info = ak.stock_individual_info_em(symbol=stock_code)
                if not stock_info.empty:
                    stock_name = stock_info.loc[stock_info['item'] == '股票简称', 'value'].values[0]
                else:
                    stock_name = stock_code
            except:
                stock_name = stock_code
            
            # 准备分析数据
            analysis_data = self._prepare_analysis_data(stock_data, indicators, financial_data, news_data, stock_code, stock_name, capital_flow_data, valuation_data)
            
            # 构建提示词
            prompt = self._build_prompt(analysis_data, stock_code, stock_name)


            image_path = os.path.join(save_path, f"charts/{stock_code}_technical_analysis.png")
            logging.debug(f"打开图像: {image_path}")
            # image = Image.open(image_path)
            img = Image.open(image_path)
            try:
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            finally:
                logging.debug("关闭图像")
                img.close()  # 显式关闭图像以避免延迟清理
                
            # 调用Gemini API
            # response = self.client.models.generate_content(
            #     model="gemini-2.5-flash-preview-04-17",
            #     config=types.GenerateContentConfig(
            #         system_instruction="你是一位专业的股票分析师，请基于以下数据分析股票的K线图和基本面情况，并预测上涨的概率。",
            #         temperature=0,
            #         top_p=0.95,
            #         top_k=1,
            #         candidate_count=1,
            #         seed=5,
            #         presence_penalty=0.0,
            #         frequency_penalty=0.0,
            #     ),
            #     contents=[image, prompt]
            # )
            response = self.client.chat.completions.create(
                model=MODEL_NAME,  # Replace with an appropriate OpenAI-compatible model
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的股票分析师，请基于以下数据分析股票的K线图和基本面情况，并预测上涨的概率。"
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                        ]  # Assuming image is properly formatted
                    }
                ],
                temperature=0,
                top_p=0.95,
                n=1,  # Equivalent to candidate_count
                seed=5,
                presence_penalty=0.0,
                frequency_penalty=0.0
            )
            
            # 处理响应
            # analysis_result = response.text
            # 处理响应
            analysis_result = response.choices[0].message.content

            # 去掉模型输出首行的报告标题（如 "# 601138（工业富联）投资分析报告"），
            # 但保留 "# 1. xxx" 这类编号章节标题（负向断言：数字+点开头不删）
            analysis_result = re.sub(r'^# (?!\d+\.)[^\n]*\n+', '', analysis_result.strip(), count=1)

            # 去掉模型输出的数据来源/真实性声明等元信息行（如"数据来源：…盘后数据。所有分析均基于…"）
            analysis_result = re.sub(r'^数据来源[:：].*(?:\n|$)', '', analysis_result, flags=re.MULTILINE).strip()

            # 添加免责声明
            disclaimer = "\n\n免责声明：本分析报告仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。"

            full_result = f"{analysis_result}\n\n{disclaimer}"

            return full_result
            
        except Exception as e:
            return f"AI分析过程中出错: {str(e)}"
    
    def _prepare_analysis_data(self, stock_data, indicators, financial_data, news_data, stock_code, stock_name, capital_flow_data=None, valuation_data=None):
        """
        准备用于分析的数据
        """
        analysis_data = {}
        
        # 基本信息
        analysis_data['股票代码'] = stock_code
        analysis_data['股票名称'] = stock_name
        
        # 提取最近的价格数据
        if not stock_data.empty:
            latest_data = stock_data.iloc[-1]
            earliest_data = stock_data.iloc[0]
            
            analysis_data['当前价格'] = float(latest_data['close'])
            analysis_data['开盘价'] = float(latest_data['open'])
            analysis_data['最高价'] = float(latest_data['high'])
            analysis_data['最低价'] = float(latest_data['low'])
            analysis_data['成交量'] = float(latest_data['volume'])
            analysis_data['日期'] = latest_data['date'].strftime('%Y-%m-%d')
            
            # 计算区间涨跌幅
            price_change = (latest_data['close'] - earliest_data['close']) / earliest_data['close'] * 100
            analysis_data['区间涨跌幅'] = round(price_change, 2)
            
            # 提取最近N天的收盘价和成交量趋势
            recent_days = min(30, len(stock_data))
            analysis_data['最近价格趋势'] = stock_data['close'].tail(recent_days).tolist()
            analysis_data['最近成交量趋势'] = stock_data['volume'].tail(recent_days).tolist()
            analysis_data['最近日期'] = [d.strftime('%Y-%m-%d') for d in stock_data['date'].tail(recent_days)]

            # 近30日价格区间
            recent30 = stock_data.tail(min(30, len(stock_data)))
            analysis_data['近30日最高'] = float(recent30['high'].max())
            analysis_data['近30日最低'] = float(recent30['low'].min())
        
        # 提取关键技术指标
        if indicators:
            latest_idx = -1  # 最新数据索引
            
            # 移动平均线
            analysis_data['MA5'] = float(indicators['MA5'].iloc[latest_idx]) if 'MA5' in indicators and not indicators['MA5'].empty else None
            analysis_data['MA10'] = float(indicators['MA10'].iloc[latest_idx]) if 'MA10' in indicators and not indicators['MA10'].empty else None
            analysis_data['MA20'] = float(indicators['MA20'].iloc[latest_idx]) if 'MA20' in indicators and not indicators['MA20'].empty else None
            analysis_data['MA30'] = float(indicators['MA30'].iloc[latest_idx]) if 'MA30' in indicators and not indicators['MA30'].empty else None
            analysis_data['MA60'] = float(indicators['MA60'].iloc[latest_idx]) if 'MA60' in indicators and not indicators['MA60'].empty else None
            # MA120 指标计算器未提供，直接用收盘价序列计算
            if not stock_data.empty and len(stock_data) >= 120:
                analysis_data['MA120'] = round(float(stock_data['close'].rolling(120).mean().iloc[-1]), 3)
            else:
                analysis_data['MA120'] = None
            
            # MACD
            analysis_data['MACD'] = float(indicators['MACD'].iloc[latest_idx]) if 'MACD' in indicators and not indicators['MACD'].empty else None
            analysis_data['MACD_signal'] = float(indicators['MACD_signal'].iloc[latest_idx]) if 'MACD_signal' in indicators and not indicators['MACD_signal'].empty else None
            analysis_data['MACD_hist'] = float(indicators['MACD_hist'].iloc[latest_idx]) if 'MACD_hist' in indicators and not indicators['MACD_hist'].empty else None
            
            # KDJ
            analysis_data['KDJ_K'] = float(indicators['K'].iloc[latest_idx]) if 'K' in indicators and not indicators['K'].empty else None
            analysis_data['KDJ_D'] = float(indicators['D'].iloc[latest_idx]) if 'D' in indicators and not indicators['D'].empty else None
            analysis_data['KDJ_J'] = float(indicators['J'].iloc[latest_idx]) if 'J' in indicators and not indicators['J'].empty else None
            
            # RSI
            analysis_data['RSI6'] = float(indicators['RSI6'].iloc[latest_idx]) if 'RSI6' in indicators and not indicators['RSI6'].empty else None
            analysis_data['RSI12'] = float(indicators['RSI12'].iloc[latest_idx]) if 'RSI12' in indicators and not indicators['RSI12'].empty else None
            analysis_data['RSI24'] = float(indicators['RSI24'].iloc[latest_idx]) if 'RSI24' in indicators and not indicators['RSI24'].empty else None
            
            # 布林带
            analysis_data['BOLL_upper'] = float(indicators['BOLL_upper'].iloc[latest_idx]) if 'BOLL_upper' in indicators and not indicators['BOLL_upper'].empty else None
            analysis_data['BOLL_middle'] = float(indicators['BOLL_middle'].iloc[latest_idx]) if 'BOLL_middle' in indicators and not indicators['BOLL_middle'].empty else None
            analysis_data['BOLL_lower'] = float(indicators['BOLL_lower'].iloc[latest_idx]) if 'BOLL_lower' in indicators and not indicators['BOLL_lower'].empty else None

            # 近20日指标序列（供斜率、背离、带宽变化判断），按日期从旧到新排列
            series_days = 20
            def _recent_series(key):
                if key not in indicators or indicators[key].empty:
                    return None
                s = indicators[key].dropna().tail(series_days)
                if s.empty:
                    return None
                return [round(float(v), 3) for v in s.tolist()]

            analysis_data['近20日技术指标'] = {
                '日期': analysis_data.get('最近日期', [])[-series_days:],
                'MACD_DIF': _recent_series('MACD'),
                'MACD_DEA': _recent_series('MACD_signal'),
                'MACD_HIST': _recent_series('MACD_hist'),
                'K': _recent_series('K'),
                'D': _recent_series('D'),
                'J': _recent_series('J'),
                'RSI6': _recent_series('RSI6'),
                'RSI12': _recent_series('RSI12'),
                'RSI24': _recent_series('RSI24'),
                'BOLL上轨': _recent_series('BOLL_upper'),
                'BOLL中轨': _recent_series('BOLL_middle'),
                'BOLL下轨': _recent_series('BOLL_lower'),
            }
        
        # 提取关键财务数据
        if financial_data:
            analysis_data['财务数据'] = financial_data
        
        # 提取新闻数据
        if news_data:
            analysis_data['新闻数据'] = news_data

        # 提取资金流向与两融数据
        if capital_flow_data:
            moneyflow = capital_flow_data.get('moneyflow')
            if moneyflow is not None and not moneyflow.empty:
                mf = moneyflow.copy()
                # 主力净流入 = 大单+超大单买入额 - 卖出额（万元）
                mf['main_net'] = (mf['buy_lg_amount'] + mf['buy_elg_amount']
                                  - mf['sell_lg_amount'] - mf['sell_elg_amount'])
                recent = mf.tail(5)
                analysis_data['资金流向(万元)'] = {
                    '最新日期': mf['trade_date'].iloc[-1],
                    '最新主力净流入': round(float(mf['main_net'].iloc[-1]), 2),
                    '最新全单净流入': round(float(mf['net_mf_amount'].iloc[-1]), 2),
                    '近5日主力净流入合计': round(float(recent['main_net'].sum()), 2),
                    '近5日主力净流入天数': int((recent['main_net'] > 0).sum()),
                    '近5日全单净流入合计': round(float(recent['net_mf_amount'].sum()), 2),
                }

            margin = capital_flow_data.get('margin')
            if margin is not None and not margin.empty:
                latest = margin.iloc[-1]
                prev = margin.iloc[-2] if len(margin) >= 2 else latest
                analysis_data['融资融券(元)'] = {
                    '最新日期': latest['trade_date'],
                    '融资余额': round(float(latest['rzye']), 2),
                    '融资余额较前日变化': round(float(latest['rzye'] - prev['rzye']), 2),
                    '融券余额': round(float(latest['rqye']), 2),
                    '融资买入额': round(float(latest['rzmre']), 2),
                    '融资融券余额': round(float(latest['rzrqye']), 2),
                }

        # 提取估值数据（最新值 + 近一年分位）
        if valuation_data:
            analysis_data['估值数据'] = valuation_data

        return analysis_data
    
    def _build_prompt(self, analysis_data, stock_code, stock_name):
        """
        构建提示词
        """
        # 将分析数据转换为JSON字符串
        data_json = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        
        # 构建提示词
        prompt = f"""
        你是一位专业的股票分析师，请基于以下数据分析 {stock_name}({stock_code}) 的技术面和基本面情况，并预测未来可能的走势。

        数据信息如下（JSON 中缺失或 null 的字段表示无该数据，严禁编造数据中不存在的数值）：
        ```json
        {data_json}
        ```

        请严格按以下 7 个部分输出分析，并在每个部分中尽可能引用数据中的具体数值作为证据：

        1. 股票基本情况概述
        公司所属行业、主营业务、市值规模（如有）、近期股价区间及成交量特征。
        结合数据时间点，说明当前股价所处的历史相对位置（如数据包含历史价格）。
        若某类数据缺失，请明确说明，不要推测。

        2. 技术指标分析
        - 移动平均线：分析短期（5/10/20日）与长期（60/120日）均线排列关系（多头/空头/纠缠）、均线斜率与股价位置。
        - MACD：分析 DIF/DEA 位置、金叉/死叉、柱状图变化，以及是否出现顶/底背离（可结合"近20日技术指标"序列判断）。
        - KDJ：分析 K/D/J 值超买超卖区间、金叉/死叉、钝化现象。
        - RSI：分析 RSI 数值区间、超买超卖、与价格走势的背离。
        - 布林带：分析股价处于上/中/下轨位置、带宽变化（收缩/扩张，可结合近20日上下轨序列判断）、突破信号。
        - 综合判断：多个指标是否共振？是否存在背离信号？量价关系是否配合？给出技术面多空倾向的结论。

        3. 基本面分析
        - 盈利能力：毛利率、净利率、ROE、EPS 及其同比变化。
        - 成长能力：营收、净利润增长率及趋势。
        - 财务健康：资产负债率。
        - 估值水平：PE、PB、股息率（如"估值数据"提供了一年分位，请与历史区间对比）。
        若数据仅包含单一报告期，请勿虚构趋势或多期对比；缺少的维度（如现金流、流动比率、行业均值）请明确说明局限。
        请结合上述指标，判断公司基本面是改善、恶化还是平稳，并指出主要驱动因素。

        4. 市场情绪分析
        对新闻数据区分：长期基本面新闻（如业绩、战略）与短期事件（如政策、传闻）。
        判断新闻情感是积极、消极还是中性，并评估其可能的影响持续时间和强度。
        分析新闻是否可能已被市场提前定价（例如股价在新闻前已大幅波动）。
        若无新闻数据或新闻极少，请说明对情绪判断的局限性。

        5. 资金流向分析（如数据缺失则跳过并说明）
        - 主力资金：分析主力净流入/流出规模、连续天数、与股价走势的关系。
        - 散户资金：对比主力与全单资金流向，判断分歧程度。
        - 融资融券：分析融资余额、融券余额变化，判断杠杆资金做多/做空意愿。
        综合判断资金面的主动性和持续性，避免仅看单日数据。

        6. 预测未来一周上涨的概率
        先结合上述所有分析，在正文中简要说明该概率的主要驱动因子、不确定性和可能的失效条件；
        然后在最后一行单独输出未来一周上涨的概率（范围 0-100，0 为下跌，100 为上涨），
        该行只允许出现一个整数数字外加百分号，不要输出其他任何内容。

        7. 投资建议和风险提示
        - 区分短期（1周）、中期（1-3个月）、长期（6个月以上）三个时间维度。
        - 给出关键支撑位和阻力位（基于技术分析），以及建议的止损/止盈参考。
        - 评估当前风险收益比，明确在何种情况下应放弃或调整观点。
        - 风险提示需包含但不限于：数据滞后性、市场系统性风险、个股流动性风险、模型过拟合风险、政策/行业突发事件风险。

        请使用专业、客观的语言，避免过度乐观或悲观的偏见。所有结论必须基于提供的数据，不得使用数据中不存在的信息进行推断。
        请使用 markdown 格式输出，适当使用标题、列表和强调。
        格式要求：
        - 报告中所有数值一律保留两位小数，百分数同样保留两位小数（如 65.00%）。
        - 报告中所有字体（文字和数字）大小保持一致
        - 不要输出"数据来源：…"之类的元信息声明行，直接从第 1 部分开始。
        """
        
        return prompt

    def _build_score_prompt(self, analysis_data, stock_code, stock_name):
        """
        构建提示词
        """
        # 将分析数据转换为JSON字符串
        data_json = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        
        # 构建提示词
        prompt = f"""
        你是一位专业的股票分析师，请基于以下数据分析 {stock_name}({stock_code}) 的K线图和基本面情况，并预测未来可能的走势。
        
        数据信息如下：
        ```json
        {data_json}
        ```
        
        请基于以上分析输出股票未来一周的上涨概率，范围为0-100，0为下跌，100为上涨, 只输出数字，不要输出其他任何内容。
        """
        
        return prompt