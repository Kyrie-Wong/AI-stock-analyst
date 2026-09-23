import os
import re
import time
import pandas as pd
import tushare as ts
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


class StockDataFetcher:
    """
    股票数据获取类，负责从Tushare获取股票的历史K线数据、财务数据和新闻信息

    需要在 .env 中配置 TUSHARE_TOKEN（https://tushare.pro 注册获取）。
    注意 Tushare 积分门槛：
      - 日线行情 pro_bar/daily：120 积分（注册+完善资料即可达到）
      - 财务指标 fina_indicator：2000 积分
      - 新闻 news/major_news：按接口要求积分
    积分不足的接口会返回空数据并打印提示，不影响其他模块运行。
    """

    def __init__(self):
        self.today = datetime.now().strftime('%Y%m%d')
        token = os.getenv('TUSHARE_TOKEN', '').strip()
        if not token or token == 'YOUR_TUSHARE_TOKEN_HERE':
            print("警告: 未配置 TUSHARE_TOKEN，请在 .env 中填写后重试")
            self.pro = None
        else:
            ts.set_token(token)
            self.pro = ts.pro_api()

    @staticmethod
    def _parse_ts_date(value):
        """把 YYYY-MM-DD / YYYYMMDD 解析为 YYYYMMDD 字符串，无效返回 None"""
        if not value:
            return None
        digits = re.sub(r'\D', '', str(value))
        if len(digits) != 8:
            return None
        try:
            return datetime.strptime(digits, '%Y%m%d').strftime('%Y%m%d')
        except ValueError:
            return None

    @staticmethod
    def _to_ts_code(stock_code):
        """将 6 位代码转为 Tushare ts_code 格式，如 000001 -> 000001.SZ"""
        code = stock_code.strip().upper()
        # 已经是 ts_code 格式
        if '.' in code:
            return code
        # 去掉可能的前缀 sz/sh
        for prefix in ('SZ', 'SH', 'BJ'):
            if code.startswith(prefix):
                code = code[len(prefix):]
        code = code.strip('.')
        if code.startswith(('6', '9')):
            return f"{code}.SH"
        elif code.startswith(('0', '2', '3')):
            return f"{code}.SZ"
        elif code.startswith(('4', '8')):
            return f"{code}.BJ"
        return f"{code}.SZ"

    def fetch_stock_data(self, stock_code, period='1年', start_date=None, end_date=None):
        """
        获取股票的历史K线数据（前复权）

        参数:
            stock_code (str): 股票代码，如 '000001'
            period (str): 获取数据的时间周期，默认为'1年'
            start_date (str): 开始日期（YYYYMMDD 或 YYYY-MM-DD），
                              指定后优先于 period；None 或无效值则按 period 计算
            end_date (str): 结束日期，None 或无效值默认为今天

        返回:
            pandas.DataFrame: 包含 date/open/close/high/low/volume/amount 等列，
                              按日期升序排列（与下游技术指标/可视化模块的契约一致）
        """
        if self.pro is None:
            return pd.DataFrame()

        ts_code = self._to_ts_code(stock_code)

        # 解析起止日期：优先使用用户指定的日期区间
        start = self._parse_ts_date(start_date)
        end = self._parse_ts_date(end_date) or self.today
        if start and start > end:
            start, end = end, start  # 防止起止填反
        if start is None:
            days_map = {'1年': 365, '6个月': 183, '3个月': 91, '1个月': 30, '1周': 7}
            start = (datetime.now() - timedelta(days=days_map.get(period, 365))).strftime('%Y%m%d')

        try:
            # pro_bar 支持前复权（adj='qfq'），与 AKShare 版行为一致
            stock_data = ts.pro_bar(ts_code=ts_code, adj='qfq',
                                    start_date=start, end_date=end,
                                    freq='D', asset='E')

            if stock_data is None or stock_data.empty:
                print(f"未找到股票 {stock_code} 的数据（Tushare 返回为空，请检查代码或积分权限）")
                return pd.DataFrame()

            # Tushare 返回按日期降序，翻转为升序
            stock_data = stock_data.sort_values('trade_date').reset_index(drop=True)

            # 重命名列以对齐下游模块契约
            # 注意单位差异：tushare vol 单位为"手"、amount 单位为"千元"
            stock_data.rename(columns={
                'trade_date': 'date',
                'vol': 'volume',
                'pct_chg': 'pct_change',
            }, inplace=True)

            # 将日期列转换为日期时间格式
            stock_data['date'] = pd.to_datetime(stock_data['date'])

            # 保留下游需要的列（若存在）
            keep_cols = [c for c in ['date', 'open', 'close', 'high', 'low',
                                     'volume', 'amount', 'pct_change', 'change']
                         if c in stock_data.columns]
            return stock_data[keep_cols]

        except Exception as e:
            print(f"获取股票数据时出错: {e}")
            return pd.DataFrame()

    def lookup_stock_code(self, name, max_items=10):
        """
        按股票简称查询代码（模糊匹配）

        参数:
            name (str): 股票简称，如 '宁德时代'
            max_items (int): 最大返回条数

        返回:
            list: [{'代码': '300750.SZ', '名称': '宁德时代', '行业': ..., '市场': ...}]
        """
        if self.pro is None:
            return []
        try:
            df = self.pro.stock_basic(fields='ts_code,name,industry,market')
            if df is None or df.empty:
                return []
            matched = df[df['name'].str.contains(str(name).strip(), na=False)].head(max_items)
            return [
                {'代码': r['ts_code'], '名称': r['name'],
                 '行业': r.get('industry', ''), '市场': r.get('market', '')}
                for _, r in matched.iterrows()
            ]
        except Exception as e:
            print(f"按名称查询股票代码时出错: {e}")
            return []

    def fetch_financial_data(self, stock_code):
        """
        获取股票的财务数据

        参数:
            stock_code (str): 股票代码，如 '000001'

        返回:
            dict: {'基本信息': {...}, '关键指标': {...}}
        """
        financial_data = {}
        if self.pro is None:
            return financial_data

        ts_code = self._to_ts_code(stock_code)

        try:
            # 基本信息（stock_basic，无积分门槛）
            basic = self.pro.stock_basic(ts_code=ts_code,
                                         fields='ts_code,name,industry,market,list_date,area')
            if basic is not None and not basic.empty:
                row = basic.iloc[0]
                financial_data['基本信息'] = {
                    '股票代码': row['ts_code'],
                    '股票简称': row['name'],
                    '所属行业': row['industry'],
                    '市场': row['market'],
                    '上市日期': row['list_date'],
                    '地区': row.get('area', ''),
                }

            # 关键财务指标（fina_indicator，需 2000 积分；积分不足时跳过）
            try:
                ind = self.pro.fina_indicator(ts_code=ts_code, limit=1,
                                              fields='end_date,eps,roe,grossprofit_margin,'
                                                     'netprofit_margin,debt_to_assets,bps,'
                                                     'basic_eps_yoy,netprofit_yoy,or_yoy')
                if ind is not None and not ind.empty:
                    r = ind.iloc[0]
                    financial_data['关键指标'] = {
                        '报告期': r['end_date'],
                        '每股收益EPS': r.get('eps'),
                        '净资产收益率ROE(%)': r.get('roe'),
                        '销售毛利率(%)': r.get('grossprofit_margin'),
                        '销售净利率(%)': r.get('netprofit_margin'),
                        '资产负债率(%)': r.get('debt_to_assets'),
                        '每股净资产': r.get('bps'),
                        'EPS同比(%)': r.get('basic_eps_yoy'),
                        '净利润同比(%)': r.get('netprofit_yoy'),
                        '营业收入同比(%)': r.get('or_yoy'),
                    }
            except Exception as e:
                print(f"获取财务指标时出错（可能积分不足，fina_indicator 需 2000 积分）: {e}")

            return financial_data

        except Exception as e:
            print(f"获取财务数据时出错: {e}")
            return financial_data

    def fetch_news_data(self, stock_code, max_items=10):
        """
        获取与股票相关的新闻信息

        策略：优先 Tushare（拉取近期新闻快讯，按股票简称过滤）；
        若 Tushare 无权限/无匹配/无 token，自动回退到 AKShare 东财个股新闻。

        参数:
            stock_code (str): 股票代码，如 '000001'
            max_items (int): 最大获取新闻条数

        返回:
            list: [{'title':..., 'date':..., 'content':...}, ...]
        """
        news_list = self._fetch_news_tushare(stock_code, max_items)
        if not news_list:
            print("Tushare 新闻不可用，回退到 AKShare 东财个股新闻...")
            news_list = self._fetch_news_akshare(stock_code, max_items)
        return news_list

    def _fetch_news_tushare(self, stock_code, max_items):
        """Tushare 新闻快讯按股票简称过滤（news 接口需要相应积分）"""
        news_list = []
        if self.pro is None:
            return news_list

        ts_code = self._to_ts_code(stock_code)

        try:
            # 先取股票简称用于过滤
            basic = self.pro.stock_basic(ts_code=ts_code, fields='name')
            if basic is None or basic.empty:
                return news_list
            stock_name = basic.iloc[0]['name']

            # 拉取近3天的新闻快讯
            start = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d 00:00:00')
            end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                news_data = self.pro.news(src='sina', start_date=start, end_date=end,
                                          fields='datetime,title,content')
            except Exception as e:
                print(f"Tushare news 接口不可用（积分可能不足）: {e}")
                return news_list

            if news_data is not None and not news_data.empty:
                matched = news_data[
                    news_data['title'].str.contains(stock_name, na=False) |
                    news_data['content'].str.contains(stock_name, na=False)
                ].head(max_items)

                for _, row in matched.iterrows():
                    news_list.append({
                        'title': row['title'],
                        'date': row['datetime'],
                        'content': row['content'] if 'content' in row else '',
                    })

            if not news_list:
                print(f"近3天 Tushare 新闻中未匹配到「{stock_name}」相关报道")
            return news_list

        except Exception as e:
            print(f"Tushare 获取新闻数据时出错: {e}")
            return news_list

    def fetch_moneyflow_data(self, stock_code, period='1年', start_date=None, end_date=None):
        """
        获取个股资金流向数据（Tushare moneyflow 接口）

        参数:
            stock_code (str): 股票代码，如 '000001'
            period (str): 时间周期，与 fetch_stock_data 一致
            start_date (str): 开始日期（YYYYMMDD 或 YYYY-MM-DD），指定后优先于 period
            end_date (str): 结束日期，None 或无效值默认为今天

        返回:
            pandas.DataFrame: 按日期升序，包含 trade_date/buy_sm_amount/.../net_mf_amount，
                              成交额单位均为万元；无权限或无数据时返回空 DataFrame
        """
        if self.pro is None:
            return pd.DataFrame()

        ts_code = self._to_ts_code(stock_code)
        start = self._parse_ts_date(start_date)
        end = self._parse_ts_date(end_date) or self.today
        if start and start > end:
            start, end = end, start
        if start is None:
            days_map = {'1年': 365, '6个月': 183, '3个月': 91, '1个月': 30, '1周': 7}
            start = (datetime.now() - timedelta(days=days_map.get(period, 365))).strftime('%Y%m%d')

        try:
            df = self.pro.moneyflow(ts_code=ts_code, start_date=start, end_date=end)
            if df is None or df.empty:
                print(f"未获取到 {stock_code} 资金流向数据（Tushare 返回为空，moneyflow 接口需 2000 积分）")
                return pd.DataFrame()
            return df.sort_values('trade_date').reset_index(drop=True)
        except Exception as e:
            print(f"获取资金流向数据时出错（moneyflow 接口需 2000 积分）: {e}")
            return pd.DataFrame()

    def fetch_margin_data(self, stock_code, start_date=None, end_date=None, days=120):
        """
        获取个股融资融券明细数据（Tushare margin_detail 接口）

        参数:
            stock_code (str): 股票代码，如 '000001'
            start_date (str): 开始日期（YYYYMMDD 或 YYYY-MM-DD），None 时回溯 days 天
            end_date (str): 结束日期，None 或无效值默认为今天
            days (int): 未指定 start_date 时的回溯天数

        返回:
            pandas.DataFrame: 按日期升序，字段含 trade_date/rzye(融资余额)/rqye(融券余额)/
                              rzmre(融资买入额)/rzche(融资偿还额)/rzrqye(融资融券余额)，
                              金额单位均为元；无权限或无数据时返回空 DataFrame
        """
        if self.pro is None:
            return pd.DataFrame()

        ts_code = self._to_ts_code(stock_code)
        start = self._parse_ts_date(start_date)
        end = self._parse_ts_date(end_date) or self.today
        if start and start > end:
            start, end = end, start
        if start is None:
            start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        try:
            df = self.pro.margin_detail(ts_code=ts_code, start_date=start, end_date=end)
            if df is None or df.empty:
                print(f"未获取到 {stock_code} 融资融券数据（Tushare 返回为空，margin_detail 接口需 2000 积分）")
                return pd.DataFrame()
            return df.sort_values('trade_date').reset_index(drop=True)
        except Exception as e:
            print(f"获取融资融券数据时出错（margin_detail 接口需 2000 积分）: {e}")
            return pd.DataFrame()

    def fetch_capital_flow(self, stock_code, period='1年', start_date=None, end_date=None):
        """
        汇总个股资金流向与融资融券数据

        返回:
            dict: {'moneyflow': DataFrame, 'margin': DataFrame}
        """
        return {
            'moneyflow': self.fetch_moneyflow_data(stock_code, period, start_date, end_date),
            'margin': self.fetch_margin_data(stock_code, start_date, end_date),
        }

    def fetch_daily_basic(self, stock_code):
        """
        获取估值与交易指标（Tushare daily_basic 接口，需 120 积分）

        返回:
            dict: {'pe_ttm':..., 'pb':..., 'ps':..., 'dv_ttm':...,
                   'total_mv':..., 'circ_mv':..., 'volume_ratio':..., 'turnover_rate_f':...}
                   市值单位为万元， None 表示该字段无数据
        """
        if self.pro is None:
            return {}

        ts_code = self._to_ts_code(stock_code)
        fields = ('trade_date,pe_ttm,pb,ps,dv_ttm,'
                  'total_mv,circ_mv,volume_ratio,turnover_rate_f')
        keys = ['pe_ttm', 'pb', 'ps', 'dv_ttm', 'total_mv', 'circ_mv',
                'volume_ratio', 'turnover_rate_f']

        try:
            df = self.pro.daily_basic(ts_code=ts_code, fields=fields)
            if df is None or df.empty:
                print(f"未获取到 {stock_code} 的 daily_basic 数据（Tushare 返回为空）")
                return {}
            r = df.sort_values('trade_date').iloc[-1]
            result = {}
            for k in keys:
                v = r.get(k)
                result[k] = None if v is None or pd.isna(v) else float(v)
            return result
        except Exception as e:
            print(f"获取估值指标时出错（daily_basic 接口需 120 积分）: {e}")
            return {}

    def fetch_valuation_stats(self, stock_code, days=366):
        """
        获取最新估值指标及近一年历史分位（Tushare daily_basic 接口，需 120 积分）

        参数:
            stock_code (str): 股票代码，如 '000001'
            days (int): 回溯的自然日天数（默认约一年）

        返回:
            dict: {'最新日期','pe_ttm','pb','dv_ttm','total_mv_亿元',
                   'pe_ttm_一年分位','pb_一年分位','dv_ttm_一年分位'}
                  分位为 0-100 的百分数（最新值在近一年全部样本中的百分位），
                  无数据字段为 None
        """
        if self.pro is None:
            return {}

        ts_code = self._to_ts_code(stock_code)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        try:
            df = self.pro.daily_basic(ts_code=ts_code, start_date=start_date,
                                      fields='trade_date,pe_ttm,pb,dv_ttm,total_mv')
            if df is None or df.empty:
                print(f"未获取到 {stock_code} 的近一年 daily_basic 数据")
                return {}
            df = df.sort_values('trade_date')
            latest = df.iloc[-1]

            def percentile(col):
                series = pd.to_numeric(df[col], errors='coerce').dropna()
                if series.empty:
                    return None
                v = latest.get(col)
                if v is None or pd.isna(v):
                    return None
                return round(float((series <= v).sum()) / len(series) * 100, 1)

            total_mv = latest.get('total_mv')
            return {
                '最新日期': latest['trade_date'],
                'pe_ttm': None if pd.isna(latest.get('pe_ttm')) else float(latest['pe_ttm']),
                'pb': None if pd.isna(latest.get('pb')) else float(latest['pb']),
                'dv_ttm': None if pd.isna(latest.get('dv_ttm')) else float(latest['dv_ttm']),
                'total_mv_亿元': None if total_mv is None or pd.isna(total_mv)
                                 else round(float(total_mv) / 10000, 2),
                'pe_ttm_一年分位': percentile('pe_ttm'),
                'pb_一年分位': percentile('pb'),
                'dv_ttm_一年分位': percentile('dv_ttm'),
            }
        except Exception as e:
            print(f"获取估值历史分位时出错（daily_basic 接口需 120 积分）: {e}")
            return {}

    def fetch_daily_amount(self, stock_code):
        """
        获取最新日成交额（Tushare daily 接口）

        返回:
            dict: {'trade_date':..., 'amount':...}，amount 已换算为亿元
                  （daily 原始单位为千元，1 亿元 = 100000 千元）
        """
        if self.pro is None:
            return {}

        ts_code = self._to_ts_code(stock_code)
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')

        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=self.today)
            if df is None or df.empty:
                return {}
            r = df.sort_values('trade_date').iloc[-1]
            amount_wy = float(r['amount']) if not pd.isna(r['amount']) else None  # 千元
            return {
                'trade_date': r['trade_date'],
                'amount': None if amount_wy is None else round(amount_wy / 100000, 2),  # 亿元
            }
        except Exception as e:
            print(f"获取成交额时出错: {e}")
            return {}

    def fetch_top_list(self, stock_code, days=90, lookback_days=15):
        """
        获取龙虎榜数据（Tushare top_list 接口，需 2000 积分）

        注意：top_list 必须按 trade_date 逐日查询，这里回溯最近 lookback_days 个
        交易日，返回该股票最近一次上榜记录。

        参数:
            stock_code (str): 股票代码，如 '000001'
            days (int): 回溯自然日上限（用于取交易日历）
            lookback_days (int): 回溯最近多少个交易日

        返回:
            dict: {'trade_date':..., 'close':..., 'pct_change':...,
                   'net_amount':..., 'net_rate':..., 'reason':...}
                   net_amount 单位为元；近期未上榜返回空 dict
        """
        if self.pro is None:
            return {}

        ts_code = self._to_ts_code(stock_code)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        def _to_float(v):
            return None if v is None or pd.isna(v) else float(v)

        try:
            cal = self.pro.trade_cal(exchange='SSE', start_date=start_date,
                                     end_date=self.today, is_open='1')
            if cal is None or cal.empty:
                return {}
            trade_days = sorted(cal['cal_date'].tolist())[-lookback_days:]

            for d in reversed(trade_days):
                try:
                    df = self.pro.top_list(trade_date=d)
                except Exception:
                    continue  # 单日查询失败（无权限/限流）则跳过
                if df is None or df.empty:
                    continue
                hit = df[df['ts_code'] == ts_code]
                if not hit.empty:
                    r = hit.iloc[0]
                    # 收盘价以 daily 表为准（top_list 的 close 偶发缺失/不一致）
                    close = _to_float(r.get('close'))
                    try:
                        daily = self.pro.daily(ts_code=ts_code, trade_date=r['trade_date'],
                                               fields='close')
                        if daily is not None and not daily.empty:
                            close = _to_float(daily.iloc[0]['close'])
                    except Exception:
                        pass
                    return {
                        'trade_date': r['trade_date'],
                        'close': close,
                        'pct_change': _to_float(r.get('pct_change')),
                        'net_amount': _to_float(r.get('net_amount')),
                        'net_rate': _to_float(r.get('net_rate')),
                        'reason': r.get('reason', ''),
                    }
            return {}
        except Exception as e:
            print(f"获取龙虎榜数据时出错（top_list 接口需 2000 积分）: {e}")
            return {}

    def _fetch_news_akshare(self, stock_code, max_items, retries=3):
        """AKShare 东财个股新闻（无需积分；东财接口偶发限流，带重试）"""
        import akshare as ak

        # 提取 6 位纯数字代码
        code = stock_code.strip().upper()
        for prefix in ('SZ', 'SH', 'BJ'):
            if code.startswith(prefix):
                code = code[len(prefix):]
        code = code.split('.')[0]

        for attempt in range(1, retries + 1):
            try:
                news_data = ak.stock_news_em(symbol=code)
                if news_data is None or news_data.empty:
                    return []

                news_list = []
                for _, row in news_data.head(max_items).iterrows():
                    news_list.append({
                        'title': row['新闻标题'],
                        'date': row['发布时间'],
                        'content': row['新闻内容'] if '新闻内容' in row else '',
                    })
                print(f"AKShare 回退成功，获取 {len(news_list)} 条个股新闻")
                return news_list

            except Exception as e:
                print(f"AKShare 获取新闻失败（第 {attempt}/{retries} 次）: {e}")
                if attempt < retries:
                    time.sleep(3 * attempt)  # 递增间隔，缓解限流
        return []
