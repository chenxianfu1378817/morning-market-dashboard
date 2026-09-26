const fmt = (value, digits = 1) => value == null || Number.isNaN(Number(value)) ? '--' : Number(value).toFixed(digits);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const weatherText = { 0: '晴', 1: '基本晴', 2: '少云', 3: '阴', 45: '雾', 48: '雾凇', 51: '小毛毛雨', 53: '毛毛雨', 61: '小雨', 63: '中雨', 65: '大雨', 80: '阵雨', 81: '中阵雨', 82: '强阵雨', 95: '雷雨' };

function renderChart(history) {
  const rows = history.filter(row => row.oil?.some(item => item.price != null)).slice(-28);
  if (!rows.length) return '<div class="sub">历史数据积累中，稍后会显示走势。</div>';
  const colors = ['#65d6a1', '#f08b82'];
  const symbols = ['CL=F', 'BZ=F'];
  const all = rows.flatMap(row => row.oil.map(item => item.price).filter(value => value != null));
  const min = Math.min(...all), max = Math.max(...all), width = 640, height = 190, padding = 24;
  const lines = symbols.map((symbol, index) => {
    const values = rows.map(row => row.oil.find(item => item.symbol === symbol)?.price ?? null);
    const points = values.map((value, position) => value == null ? null : `${padding + position * (width - padding * 2) / Math.max(1, values.length - 1)},${height - padding - (value - min) / (max - min || 1) * (height - padding * 2)}`).filter(Boolean).join(' ');
    return points ? `<polyline points="${points}" fill="none" stroke="${colors[index]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>` : '';
  }).join('');
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="原油价格走势图"><line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#263241"/><line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" stroke="#263241"/>${lines}</svg><div class="legend"><span class="wti">● WTI</span><span class="brent">● Brent</span><span class="sub">${fmt(min, 2)} – ${fmt(max, 2)} 美元</span></div>`;
}

function renderOil(oil) {
  const cards = oil.map(item => {
    const direction = item.change > 0 ? 'up' : item.change < 0 ? 'down' : '';
    const changeText = item.change_pct == null ? '涨跌幅暂无' : `${item.change >= 0 ? '+' : ''}${fmt(item.change, 2)} (${fmt(item.change_pct, 2)}%)`;
    return `<article class="card oil-card ${item.stale ? 'is-stale' : ''}"><h3>${esc(item.name)}${item.stale ? ' · 沿用上次数据' : ''}</h3><div class="big">$${fmt(item.price, 2)}</div><div class="${direction}">${changeText}</div><div class="sub">昨收 $${fmt(item.previous_close, 2)} · 行情时间 ${esc(item.market_time || '--')}</div></article>`;
  }).join('');
  document.querySelector('#oil').innerHTML = cards || '<div class="sub">暂无原油行情。</div>';
}

function renderAlerts(data) {
  const messages = [];
  for (const city of data.weather || []) {
    if (city.stale) messages.push(`${city.name}天气暂时无法更新，当前显示上次有效数据。`);
    if (!city.unavailable && city.rain_probability >= 70) messages.push(`${city.name}降水概率 ${fmt(city.rain_probability, 0)}%，出门建议带伞`);
    if (!city.unavailable && city.max >= 35) messages.push(`${city.name}最高温 ${fmt(city.max)}°，注意防暑`);
  }
  for (const item of data.oil || []) if (item.stale) messages.push(`${item.name}行情暂时无法更新，当前显示上次有效数据。`);
  if ((data.errors || []).length) messages.push(`有 ${data.errors.length} 项数据源暂时不可用，已尽量保留上次有效内容。`);
  document.querySelector('#alerts').innerHTML = messages.length
    ? messages.map(message => `<div class="notice">${esc(message)}</div>`).join('')
    : '<div class="notice good">暂无明显天气预警，数据源工作正常。</div>';
}

function renderDashboard(data, history) {
  const updated = data.updated_at_iso ? new Date(data.updated_at_iso) : new Date(`${(data.updated_at || '').replace(' ', 'T')}+08:00`);
  const ageHours = (Date.now() - updated.getTime()) / 3600000;
  const staleDashboard = !Number.isFinite(ageHours) || ageHours > 36;
  document.querySelector('#updated').textContent = `更新于 ${data.updated_at || '时间未知'} · ${data.timezone || 'Asia/Shanghai'}${staleDashboard ? ' · 数据可能已过期' : ''}`;

  document.querySelector('#weather').innerHTML = (data.weather || []).map(city => city.unavailable
    ? `<article class="card is-stale"><h3>${esc(city.name)}</h3><div class="big">暂无数据</div><div class="sub">天气源暂时不可用</div></article>`
    : `<article class="card ${city.stale ? 'is-stale' : ''}"><h3>${esc(city.name)}</h3><div class="big">${fmt(city.temperature)}°</div><div>${weatherText[city.code] || '天气'} · 体感 ${fmt(city.feels_like)}°</div><div class="sub">最高 ${fmt(city.max)}° / 最低 ${fmt(city.min)}°<br>降水概率 ${fmt(city.rain_probability, 0)}%${city.stale ? '<br>沿用上次有效数据' : ''}</div></article>`).join('');

  renderOil(data.oil || []);
  document.querySelector('#oil-chart').innerHTML = renderChart(history || []);

  const warnings = (data.weather || []).filter(city => !city.unavailable && (city.rain_probability >= 70 || city.max >= 35));
  const oilSummary = (data.oil || []).filter(item => item.price != null).map(item => `${item.name} $${fmt(item.price, 2)}`).join('，');
  const changes = (data.oil || []).filter(item => item.change_pct != null).map(item => `${item.name}${item.change_pct >= 0 ? '上涨' : '下跌'} ${fmt(Math.abs(item.change_pct), 2)}%`).join('，');
  document.querySelector('#summary').textContent = `今日摘要：${warnings.length ? warnings.slice(0, 2).map(city => city.rain_probability >= 70 ? `${city.name}降水概率较高` : `${city.name}高温`).join('；') : '华南暂无明显天气预警。'} ${oilSummary ? `原油：${oilSummary}。` : ''}${changes ? `${changes}。` : ''}`;

  document.querySelector('#truth').innerHTML = (data.truth_posts || []).map(item => `<a class="truth-item ${item.stale ? 'is-stale' : ''}" href="${esc(item.link)}" target="_blank" rel="noopener"><strong>${esc(item.translated)}</strong><small>原文：${esc(item.original)} · ${esc(item.published)}${item.stale ? ' · 上次有效内容' : ''}</small></a>`).join('') || '<div class="sub">暂无动态数据。</div>';
  document.querySelector('#news').innerHTML = (data.news || []).map(item => `<a class="news-item ${item.stale ? 'is-stale' : ''}" href="${esc(item.link)}" target="_blank" rel="noopener"><span>${esc(item.title)}</span><small>${esc(item.published)}${item.stale ? ' · 上次有效内容' : ''}</small></a>`).join('') || '<div class="sub">暂无新闻数据。</div>';
  renderAlerts(data);
  if (staleDashboard) document.querySelector('#alerts').insertAdjacentHTML('afterbegin', '<div class="notice bad">看板数据已超过 36 小时未更新，请稍后重试或检查自动任务。</div>');
}

async function loadDashboard(forceRefresh = false) {
  const button = document.querySelector('#refresh');
  const status = document.querySelector('#refresh-status');
  if (forceRefresh) {
    button.disabled = true;
    status.textContent = '正在重新获取数据…';
  }
  try {
    const cacheBust = forceRefresh ? `?t=${Date.now()}` : '';
    const [dataResponse, historyResponse] = await Promise.all([
      fetch(`data/latest.json${cacheBust}`, { cache: 'no-store' }),
      fetch(`data/history.json${cacheBust}`, { cache: 'no-store' }).catch(() => null),
    ]);
    if (!dataResponse.ok) throw new Error(`HTTP ${dataResponse.status}`);
    const data = await dataResponse.json();
    const history = historyResponse?.ok ? await historyResponse.json() : [];
    renderDashboard(data, history);
    if (forceRefresh) status.textContent = '已重新读取仓库中的最新数据。';
  } catch (error) {
    document.querySelector('#updated').textContent = '数据读取失败';
    document.querySelector('#alerts').innerHTML = `<div class="notice bad">无法读取看板数据：${esc(error.message)}。请稍后重试。</div>`;
    if (forceRefresh) status.textContent = '刷新失败，请检查网络后重试。';
  } finally {
    button.disabled = false;
  }
}

document.querySelector('#refresh').addEventListener('click', () => loadDashboard(true));
loadDashboard();
