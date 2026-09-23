document.addEventListener('DOMContentLoaded', function () {
    const analyzeForm = document.getElementById('analyzeForm');
    const stockCodeInput = document.getElementById('stockCode');
    const periodSelect = document.getElementById('period');
    const periodPills = document.getElementById('periodPills');
    const runBtn = document.getElementById('runBtn');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');

    // 日期最大值为今天，防止选择未来日期
    const fmtDate = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const today = new Date();
    const oneMonthAgo = new Date(today.getFullYear(), today.getMonth() - 1, today.getDate());
    startDateInput.max = fmtDate(today);
    endDateInput.max = fmtDate(today);
    // 默认值：结束日期为当天，开始日期为一个月前
    startDateInput.value = fmtDate(oneMonthAgo);
    endDateInput.value = fmtDate(today);
    const emptyState = document.getElementById('emptyState');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const chartsArea = document.getElementById('chartsArea');
    const chartImages = document.getElementById('chartImages');
    const analysisResult = document.getElementById('analysisResult');
    const analysisText = document.getElementById('analysisText');
    const stockInfoCard = document.getElementById('stockInfoCard');
    const stockInfoBody = document.getElementById('stockInfoBody');
    const metricCards = document.getElementById('metricCards');
    const toast = document.getElementById('toast');

    // 周期 pill 按钮联动隐藏的 select（保持后端契约），并同步日期区间
    const PERIOD_MONTHS = { '1年': 12, '6个月': 6, '3个月': 3, '1个月': 1 };
    periodPills.addEventListener('click', function (e) {
        const btn = e.target.closest('.pill');
        if (!btn) return;
        periodPills.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        periodSelect.value = btn.dataset.value;

        // 周期对应日期区间：结束日期为当天，开始日期为对应月份前
        const months = PERIOD_MONTHS[btn.dataset.value];
        if (months) {
            endDateInput.value = fmtDate(today);
            startDateInput.value = fmtDate(new Date(today.getFullYear(), today.getMonth() - months, today.getDate()));
        }
    });

    // 手动修改日期时取消周期高亮（进入自定义区间模式）
    [startDateInput, endDateInput].forEach(el => {
        el.addEventListener('change', function () {
            periodPills.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
            periodSelect.value = '';
        });
    });

    // Toast 提示
    let toastTimer = null;
    function showToast(message) {
        toast.textContent = message;
        toast.classList.remove('hidden');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.add('hidden'), 4000);
    }

    // 表单提交
    analyzeForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const stockCode = stockCodeInput.value.trim();
        if (!stockCode) {
            showToast('请输入股票代码');
            return;
        }

        emptyState.classList.add('hidden');
        loadingIndicator.classList.remove('hidden');
        chartsArea.classList.add('hidden');
        analysisResult.classList.add('hidden');
        metricCards.classList.add('hidden');
        runBtn.disabled = true;

        fetchStockInfo(stockCode);
        fetchMetricCards(stockCode);

        const formData = new FormData(analyzeForm);
        fetch('/analyze', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                loadingIndicator.classList.add('hidden');
                if (data.success) {
                    displayCharts(data.charts, stockCode);
                    displayAnalysisResult(data.analysis_result);
                } else {
                    showToast(data.error || '分析失败，请检查股票代码');
                    emptyState.classList.remove('hidden');
                }
            })
            .catch(err => {
                loadingIndicator.classList.add('hidden');
                showToast('分析过程中出错：' + err.message);
                emptyState.classList.remove('hidden');
                console.error('Error:', err);
            })
            .finally(() => {
                runBtn.disabled = false;
            });
    });

    /** 获取股票基本信息 */
    function fetchStockInfo(stockCode) {
        stockInfoCard.classList.add('hidden');
        fetch(`/stock_info/${stockCode}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) displayStockInfo(data.data);
            })
            .catch(err => console.error('Error fetching stock info:', err));
    }

    /** 获取估值与交易指标卡片 */
    function fetchMetricCards(stockCode) {
        metricCards.innerHTML = '';
        metricCards.classList.add('hidden');
        fetch(`/daily_basic/${stockCode}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) displayMetricCards(data.data);
            })
            .catch(err => console.error('Error fetching daily_basic:', err))
            .finally(() => {
                // 等估值卡片渲染完成后再追加龙虎榜卡片，避免竞态覆盖
                fetchTopListCards(stockCode);
            });
    }

    /** 渲染指标卡片（市盈率/市净率/市销率/股息率/总市值/流通市值/量比/换手率） */
    function displayMetricCards(data) {
        metricCards.innerHTML = '';

        const fmt = v => v === null || v === undefined ? '--' : v.toFixed(2);
        const fmtPct = v => v === null || v === undefined ? '--' : v.toFixed(2) + '%';
        const fmtYi = v => v === null || v === undefined ? '--' : (v / 10000).toFixed(0) + '亿';

        const items = [
            { label: '市盈率TTM', value: fmt(data.pe_ttm) },
            { label: '市净率', value: fmt(data.pb) },
            { label: '市销率', value: fmt(data.ps) },
            { label: '股息率TTM', value: fmtPct(data.dv_ttm) },
            { label: '总市值', value: fmtYi(data.total_mv) },
            { label: '流通市值', value: fmtYi(data.circ_mv) },
            { label: '成交额', value: data.amount === null || data.amount === undefined ? '--' : data.amount.toFixed(2) + '亿' },
            { label: '量比', value: fmt(data.volume_ratio) },
            { label: '换手率', value: fmtPct(data.turnover_rate_f) },
        ];

        for (const item of items) {
            metricCards.appendChild(createMetricCard(item.label, item.value));
        }

        metricCards.classList.remove('hidden');
    }

    /** 创建一张指标卡片 */
    function createMetricCard(label, value, valueClass, cardClass) {
        const card = document.createElement('div');
        card.className = 'metric-card' + (cardClass ? ' ' + cardClass : '');
        const labelEl = document.createElement('div');
        labelEl.className = 'm-label';
        labelEl.textContent = label;
        const valueEl = document.createElement('div');
        valueEl.className = 'm-value' + (valueClass ? ' ' + valueClass : '');
        valueEl.textContent = value;
        card.appendChild(labelEl);
        card.appendChild(valueEl);
        return card;
    }

    /** 获取龙虎榜指标卡片 */
    function fetchTopListCards(stockCode) {
        fetch(`/top_list/${stockCode}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    displayTopListCards(data.data);
                } else {
                    // 近期未上榜：展示一张占位卡片
                    metricCards.appendChild(createMetricCard('龙虎榜', '近90日未上榜'));
                    metricCards.classList.remove('hidden');
                }
            })
            .catch(err => console.error('Error fetching top_list:', err));
    }

    /** 渲染龙虎榜卡片（收盘价/涨跌幅/净买入额/净买额占比/上榜理由） */
    function displayTopListCards(data) {
        const fmt = v => v === null || v === undefined ? '--' : v.toFixed(2);
        const fmtAmt = v => {
            if (v === null || v === undefined) return '--';
            const abs = Math.abs(v);
            if (abs >= 1e8) return (v / 1e8).toFixed(2) + '亿';
            return (v / 1e4).toFixed(0) + '万';
        };

        const pct = data.pct_change;
        const pctClass = pct === null || pct === undefined ? '' : (pct >= 0 ? 'up' : 'down');
        const pctText = pct === null || pct === undefined ? '--' : (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';

        metricCards.appendChild(createMetricCard('龙虎榜收盘价', fmt(data.close)));
        metricCards.appendChild(createMetricCard('龙虎榜涨跌幅', pctText, pctClass));
        metricCards.appendChild(createMetricCard('龙虎榜净买入额', fmtAmt(data.net_amount)));
        metricCards.appendChild(createMetricCard('净买额占比', data.net_rate === null || data.net_rate === undefined ? '--' : data.net_rate.toFixed(2) + '%'));

        const dateStr = data.trade_date ? `${data.trade_date.slice(0, 4)}-${data.trade_date.slice(4, 6)}-${data.trade_date.slice(6, 8)}` : '';
        const reason = data.reason ? `${dateStr} ${data.reason}`.trim() : '--';
        metricCards.appendChild(createMetricCard('上榜理由', reason, 'm-reason-text', 'm-wide'));

        metricCards.classList.remove('hidden');
    }

    /** 显示股票基本信息 */
    function displayStockInfo(data) {
        stockInfoBody.innerHTML = '';

        if (!data || Object.keys(data).length === 0) {
            stockInfoBody.innerHTML = '<p class="info-empty">无法获取股票信息</p>';
            stockInfoCard.classList.remove('hidden');
            return;
        }

        const table = document.createElement('table');
        table.className = 'info-table';
        const tbody = document.createElement('tbody');

        const priorityFields = [
            '股票简称', '股票代码', '所处行业', '所属行业',
            '最新价', '涨跌幅', '成交量(万)', '成交额(万)',
            '总市值', '流通市值', '市盈率', '市净率'
        ];

        for (const field of priorityFields) {
            if (data[field] !== undefined && data[field] !== null && data[field] !== '') {
                tbody.appendChild(createInfoRow(field, data[field]));
            }
        }
        for (const [key, value] of Object.entries(data)) {
            if (!priorityFields.includes(key)) {
                tbody.appendChild(createInfoRow(key, value));
            }
        }

        table.appendChild(tbody);
        stockInfoBody.appendChild(table);
        stockInfoCard.classList.remove('hidden');
    }

    /** 创建信息行（红涨绿跌） */
    function createInfoRow(label, value) {
        const row = document.createElement('tr');
        const th = document.createElement('th');
        th.textContent = label;
        const td = document.createElement('td');
        td.textContent = value;

        if (label === '涨跌幅') {
            const v = String(value);
            if (v.includes('-')) td.className = 'down';
            else if (v.includes('+') || parseFloat(v) > 0) td.className = 'up';
        }

        row.appendChild(th);
        row.appendChild(td);
        return row;
    }

    /** 显示图表 */
    function displayCharts(charts, stockCode) {
        chartImages.innerHTML = '';

        const htmlCharts = (charts || []).filter(c => c.endsWith('.html'));
        if (htmlCharts.length === 0) {
            chartImages.innerHTML = '<p class="info-empty">未找到交互式图表</p>';
            chartsArea.classList.remove('hidden');
            return;
        }

        for (const chart of htmlCharts) {
            const chartDiv = document.createElement('div');
            chartDiv.className = 'chart-container';

            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'chart-loading';
            loadingMsg.textContent = '图表加载中…';
            chartDiv.appendChild(loadingMsg);

            const iframe = document.createElement('iframe');
            iframe.src = `/output/charts/${chart}`;
            iframe.onload = () => { loadingMsg.style.display = 'none'; };
            chartDiv.appendChild(iframe);

            const link = document.createElement('a');
            link.href = `/output/charts/${chart}`;
            link.target = '_blank';
            link.className = 'chart-open-link';
            link.textContent = '在新窗口中查看 ↗';
            chartDiv.appendChild(link);

            chartImages.appendChild(chartDiv);
        }

        chartsArea.classList.remove('hidden');
    }

    /** 显示分析结果 */
    function displayAnalysisResult(result) {
        if (!result) {
            analysisResult.classList.add('hidden');
            return;
        }
        analysisText.innerHTML = convertMarkdownToHTML(result);
        analysisResult.classList.remove('hidden');
    }

    /** Markdown → HTML */
    function convertMarkdownToHTML(markdown) {
        if (!markdown) return '';

        // 统一换行符（分析结果文件是 Windows \r\n）
        let html = markdown.replace(/\r\n/g, '\n');

        // 上涨概率：把标题后第一个独占一行的数值追加 % 符号（普通文本，不高亮）
        // 如 "…预测未来一周上涨的概率\n（驱动因子说明……）\n\n65.00" → "…65.00%"
        // 注意要在标题转换之前处理；% 用实体 &#37; 防止后续涨跌高亮规则二次包裹
        html = html.replace(/(预测未来一周上涨的概率[：:]?[^\n]*\n[\s\S]*?)^[ \t]*(\d{1,3}(?:\.\d+)?)[ \t]*$(?=\n)/m,
            '$1$2&#37;');

        // 模型有时用 "# 1. xxx" 写章节标题：统一提升为 ## 级别，保证样式一致
        html = html.replace(/^# (\d+\..*)$/gm, '## $1');

        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');

        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
        html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

        // 去掉模型输出中小节之间的 --- 分隔符
        html = html.replace(/^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$/gm, '');

        // 表格：逐行扫描，把连续的管道行解析为真正的 <table>
        html = convertPipeTables(html);

        // 无序列表
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        let parts = html.split('\n');
        let inList = false;
        for (let i = 0; i < parts.length; i++) {
            if (parts[i].startsWith('<li>') && !inList) {
                parts[i] = '<ul>' + parts[i];
                inList = true;
            } else if (!parts[i].startsWith('<li>') && inList) {
                parts[i - 1] = parts[i - 1] + '</ul>';
                inList = false;
            }
        }
        if (inList) parts[parts.length - 1] = parts[parts.length - 1] + '</ul>';
        html = parts.join('\n');

        // 段落
        html = html.replace(/^([^<\n].+)$/gm, '<p>$1</p>');
        html = html.replace(/\n\s*\n/g, '<br>');

        // 高亮：股票代码 / 涨跌百分比（红涨绿跌）/ 关键价位 / 提示词
        // 代码带 .SZ/.SH/.BJ 后缀时整体包一个徽章，避免只包数字导致字号不一致
        html = html.replace(/\b(\d{6}(?:\.(?:SZ|SH|BJ))?)\b/g, '<span class="badge">$1</span>');
        html = html.replace(/([^-])([\d.]+%)/g, '$1<span class="up">$2</span>');
        html = html.replace(/(-[\d.]+%)/g, '<span class="down">$1</span>');
        html = html.replace(/([（(]?)((?:目标价|支撑位|压力位|止损位)[：:]([\d.]+)([）)]?))/g,
            '$1<span class="stock-highlight">$2</span>');
        html = html.replace(/(注意|提示|风险|建议|总结|结论|策略)[:：]/g,
            '<span class="up fw-bold">$1：</span>');

        return html;
    }

    /**
     * 把 Markdown 管道表格解析为 <table>
     * 兼容三种风格：
     *   1. 标准管道表格（行首带 |）
     *   2. 无边框管道表格（`指标 | 数值` + `------|------`）
     *   3. ASCII 制表符风格（|------|、+------+、│ ... │、┌──┬──┐ 等）
     */
    // 分隔/边框行允许的字符（连字符、冒号、管道、各种制表符边角）
    const TABLE_BORDER_RE = /^[\s\-–—_:+|=│┃║┆┇┊┋┌┍┎┏┐┑┒┓└├┤┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻═╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬]*$/;
    const hasDash = l => /[-–—─━=]{2,}/.test(l);

    function isSeparatorRow(l) {
        const t = l.trim();
        return TABLE_BORDER_RE.test(t) && hasDash(t);
    }

    function isTableDataRow(l) {
        const t = l.trim();
        if (!t) return false;
        if (!t.includes('|') && !/[│┃║]/.test(t)) return false;
        if (/https?:\/\//.test(t)) return false;
        return !isSeparatorRow(t);
    }

    function convertPipeTables(text) {
        const lines = text.split('\n');
        const out = [];

        let i = 0;
        while (i < lines.length) {
            // 表头行 + 紧随的分隔行 = 一个表格的起点
            if (isTableDataRow(lines[i]) && i + 1 < lines.length && isSeparatorRow(lines[i + 1])) {
                const tableLines = [];
                while (i < lines.length && (isTableDataRow(lines[i]) || isSeparatorRow(lines[i]))) {
                    tableLines.push(lines[i]);
                    i++;
                }
                out.push(buildTableHTML(tableLines));
            } else {
                out.push(lines[i]);
                i++;
            }
        }
        return out.join('\n');
    }

    function buildTableHTML(tableLines) {
        // 统一制表符为普通管道符
        const normalize = line => line
            .replace(/[│┃║┆┇┊┋]/g, '|')
            .replace(/[┌┍┎┏┐┑┒┓└├┤┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻]/g, '|');

        const splitRow = line => normalize(line)
            .trim().replace(/^\|/, '').replace(/\|$/, '')
            .split('|').map(c => c.trim());

        // 跳过 |---| / +---+---+ / ├──┼──┤ 之类的分隔与边框行
        const rows = tableLines
            .filter(l => !isSeparatorRow(l))
            .map(splitRow)
            .filter(cells => cells.some(c => c !== ''));

        if (rows.length === 0) return '';

        const headers = rows[0];
        const bodyRows = rows.slice(1);

        const thead = '<thead><tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr></thead>';
        const tbody = '<tbody>' + bodyRows.map(cells =>
            '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>'
        ).join('') + '</tbody>';

        return `<div class="table-responsive"><table>${thead}${tbody}</table></div>`;
    }
});
