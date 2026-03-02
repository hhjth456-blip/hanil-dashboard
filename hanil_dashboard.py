import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta, timezone

# ========================================
# 페이지 설정
# ========================================
st.set_page_config(
    page_title="한일전기 원자재 대시보드",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================================
# 커스텀 CSS
# ========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
    * { font-family: 'Noto Sans KR', sans-serif; }
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .main-header h1 { color: #ffffff; font-size: 1.8rem; font-weight: 700; margin: 0; }
    .main-header p { color: #a0aec0; font-size: 0.95rem; margin: 0.5rem 0 0 0; }
    .metric-card {
        background: linear-gradient(145deg, #ffffff, #f7fafc);
        border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem;
        text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.1); }
    .metric-label { font-size: 0.85rem; color: #718096; font-weight: 500; letter-spacing: 0.5px; margin-bottom: 0.3rem; }
    .metric-value { font-size: 2rem; font-weight: 900; margin: 0.3rem 0; letter-spacing: -1px; }
    .metric-change-up { color: #e53e3e; font-size: 0.95rem; font-weight: 700; }
    .metric-change-down { color: #3182ce; font-size: 0.95rem; font-weight: 700; }
    .metric-change-flat { color: #718096; font-size: 0.95rem; font-weight: 700; }
    .impact-badge-danger {
        display: inline-block; background: linear-gradient(135deg, #fff5f5, #fed7d7);
        color: #c53030; padding: 0.3rem 0.8rem; border-radius: 20px;
        font-size: 0.8rem; font-weight: 700; border: 1px solid #feb2b2;
    }
    .impact-badge-safe {
        display: inline-block; background: linear-gradient(135deg, #f0fff4, #c6f6d5);
        color: #276749; padding: 0.3rem 0.8rem; border-radius: 20px;
        font-size: 0.8rem; font-weight: 700; border: 1px solid #9ae6b4;
    }
    .impact-badge-warning {
        display: inline-block; background: linear-gradient(135deg, #fffff0, #fefcbf);
        color: #975a16; padding: 0.3rem 0.8rem; border-radius: 20px;
        font-size: 0.8rem; font-weight: 700; border: 1px solid #f6e05e;
    }
    .insight-box {
        background: linear-gradient(135deg, #ebf8ff, #bee3f8);
        border-left: 4px solid #3182ce; border-radius: 0 12px 12px 0;
        padding: 1.2rem 1.5rem; margin: 1rem 0; font-size: 0.95rem;
        color: #2d3748; line-height: 1.7;
    }
    .alert-box {
        background: linear-gradient(135deg, #fff5f5, #fed7d7);
        border-left: 4px solid #e53e3e; border-radius: 0 12px 12px 0;
        padding: 1.2rem 1.5rem; margin: 1rem 0; font-size: 0.95rem;
        color: #2d3748; line-height: 1.7;
    }
    .section-header {
        font-size: 1.3rem; font-weight: 700; color: #1a202c;
        margin: 2rem 0 1rem 0; padding-bottom: 0.5rem;
        border-bottom: 3px solid #3182ce; display: inline-block;
    }
    .footer {
        text-align: center; color: #a0aec0; font-size: 0.8rem;
        margin-top: 3rem; padding: 1.5rem; border-top: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


# ========================================
# 단위 변환
# HG=F 원시 데이터: 달러/파운드 (예: 6.05 = $6.05/lb)
# 1톤 = 2204.62 파운드
# 달러/톤 = 달러/파운드 × 2204.62
# ========================================
LBS_PER_TON = 2204.62


def copper_to_ton(dollar_per_lb):
    return dollar_per_lb * LBS_PER_TON


# ========================================
# 데이터 수집
# ========================================
@st.cache_data(ttl=3600)
def fetch_data(ticker, period="6mo"):
    try:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        st.error(f"데이터 수집 오류 ({ticker}): {e}")
        return None


@st.cache_data(ttl=3600)
def fetch_all_data(period):
    tickers = {
        "구리": "HG=F",
        "원/달러 환율": "KRW=X",
        "WTI 원유": "CL=F",
        "브렌트 원유": "BZ=F",
        "금": "GC=F",
    }
    all_data = {}
    for name, ticker in tickers.items():
        data = fetch_data(ticker, period)
        if data is not None:
            all_data[name] = data
    return all_data


def get_price_info(data):
    if data is None or len(data) < 2:
        return None, None, None
    current = float(data['Close'].iloc[-1])
    previous = float(data['Close'].iloc[-2])
    change = current - previous
    change_pct = (change / previous) * 100
    return current, change, change_pct


def get_period_change(data, days=30):
    if data is None or len(data) < days:
        return None
    current = float(data['Close'].iloc[-1])
    past = float(data['Close'].iloc[-min(days, len(data))])
    return ((current - past) / past) * 100


# ========================================
# 사이드바
# ========================================
with st.sidebar:
    st.markdown("### ⚙️ 대시보드 설정")
    st.markdown("---")
    period_options = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y", "2년": "2y"}
    selected_period_label = st.selectbox("📅 조회 기간", list(period_options.keys()), index=2)
    selected_period = period_options[selected_period_label]
    st.markdown("---")
    st.markdown("### 🏭 한일전기 원가 파라미터")
    copper_bom_ratio = st.slider("구리 BOM 비중 (%)", min_value=5, max_value=50, value=25, step=1)
    import_ratio = st.slider("수입 부자재 비중 (%)", min_value=10, max_value=80, value=40, step=5)
    st.markdown("---")
    st.markdown("### 📌 기준가격 (2025년 평균)")
    copper_base = st.number_input("구리 기준가 ($/톤)", value=9500, step=100)
    fx_base = st.number_input("환율 기준가 (원/$)", value=1350, step=10)
    wti_base = st.number_input("WTI 기준가 ($/배럴)", value=72.0, step=1.0)
    st.markdown("---")
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center; color:#a0aec0; font-size:0.75rem;'>"
        "데이터: Yahoo Finance<br>갱신주기: 1시간<br>v2.2</div>",
        unsafe_allow_html=True
    )


# ========================================
# 메인
# ========================================
st.markdown(f"""
<div class="main-header">
    <h1>📊 한일전기 원자재 인텔리전스 대시보드</h1>
    <p>구리 · 환율 · 에너지 — 실시간 모니터링 & 원가 영향 분석 | {datetime.now(timezone(timedelta(hours=9))).strftime('%Y년 %m월 %d일 %H:%M')} 기준</p>
</div>
""", unsafe_allow_html=True)

with st.spinner("📡 글로벌 시장 데이터를 수집하고 있습니다..."):
    all_data = fetch_all_data(selected_period)

if not all_data:
    st.error("데이터를 불러올 수 없습니다. 인터넷 연결을 확인해주세요.")
    st.stop()


# ========================================
# 핵심 지표 카드
# ========================================
st.markdown('<div class="section-header">📈 핵심 지표 현황</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)

# --- 구리 ---
if "구리" in all_data:
    copper_raw, copper_change, copper_pct = get_price_info(all_data["구리"])
    if copper_raw:
        copper_per_ton = copper_to_ton(copper_raw)
        copper_change_class = "metric-change-up" if copper_pct > 0 else "metric-change-down" if copper_pct < 0 else "metric-change-flat"
        copper_arrow = "▲" if copper_pct > 0 else "▼" if copper_pct < 0 else "—"
        copper_vs_base = ((copper_per_ton - copper_base) / copper_base) * 100
        badge = 'impact-badge-danger' if copper_vs_base > 10 else 'impact-badge-warning' if copper_vs_base > 0 else 'impact-badge-safe'
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🔶 구리 ($/톤)</div>
                <div class="metric-value" style="color: #e53e3e;">${copper_per_ton:,.0f}</div>
                <div class="{copper_change_class}">{copper_arrow} {abs(copper_pct):.2f}% (전일비)</div>
                <div style="margin-top:0.5rem;"><span class="{badge}">기준가 대비 {copper_vs_base:+.1f}%</span></div>
                <div style="font-size:0.7rem; color:#a0aec0; margin-top:0.3rem;">원시: ${copper_raw:.4f}/lb × {LBS_PER_TON:.0f} = ${copper_per_ton:,.0f}/톤</div>
            </div>
            """, unsafe_allow_html=True)

# --- 환율 ---
if "원/달러 환율" in all_data:
    fx_price, fx_change, fx_pct = get_price_info(all_data["원/달러 환율"])
    if fx_price:
        fx_change_class = "metric-change-up" if fx_pct > 0 else "metric-change-down" if fx_pct < 0 else "metric-change-flat"
        fx_arrow = "▲" if fx_pct > 0 else "▼" if fx_pct < 0 else "—"
        fx_vs_base = ((fx_price - fx_base) / fx_base) * 100
        badge = 'impact-badge-danger' if fx_vs_base > 5 else 'impact-badge-warning' if fx_vs_base > 0 else 'impact-badge-safe'
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">💱 원/달러 환율</div>
                <div class="metric-value" style="color: #3182ce;">₩{fx_price:,.1f}</div>
                <div class="{fx_change_class}">{fx_arrow} {abs(fx_pct):.2f}% (전일비)</div>
                <div style="margin-top:0.5rem;"><span class="{badge}">기준가 대비 {fx_vs_base:+.1f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

# --- WTI ---
if "WTI 원유" in all_data:
    wti_price, wti_change, wti_pct = get_price_info(all_data["WTI 원유"])
    if wti_price:
        wti_change_class = "metric-change-up" if wti_pct > 0 else "metric-change-down" if wti_pct < 0 else "metric-change-flat"
        wti_arrow = "▲" if wti_pct > 0 else "▼" if wti_pct < 0 else "—"
        wti_vs_base = ((wti_price - wti_base) / wti_base) * 100
        badge = 'impact-badge-danger' if wti_vs_base > 10 else 'impact-badge-warning' if wti_vs_base > 0 else 'impact-badge-safe'
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🛢️ WTI 원유 ($/배럴)</div>
                <div class="metric-value" style="color: #38a169;">${wti_price:,.2f}</div>
                <div class="{wti_change_class}">{wti_arrow} {abs(wti_pct):.2f}% (전일비)</div>
                <div style="margin-top:0.5rem;"><span class="{badge}">기준가 대비 {wti_vs_base:+.1f}%</span></div>
            </div>
            """, unsafe_allow_html=True)

# --- 브렌트 ---
if "브렌트 원유" in all_data:
    brent_price, brent_change, brent_pct = get_price_info(all_data["브렌트 원유"])
    if brent_price:
        brent_change_class = "metric-change-up" if brent_pct > 0 else "metric-change-down" if brent_pct < 0 else "metric-change-flat"
        brent_arrow = "▲" if brent_pct > 0 else "▼" if brent_pct < 0 else "—"
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🛢️ 브렌트 원유 ($/배럴)</div>
                <div class="metric-value" style="color: #805ad5;">${brent_price:,.2f}</div>
                <div class="{brent_change_class}">{brent_arrow} {abs(brent_pct):.2f}% (전일비)</div>
            </div>
            """, unsafe_allow_html=True)

# --- 금 ---
if "금" in all_data:
    gold_price, gold_change, gold_pct = get_price_info(all_data["금"])
    if gold_price:
        gold_change_class = "metric-change-up" if gold_pct > 0 else "metric-change-down" if gold_pct < 0 else "metric-change-flat"
        gold_arrow = "▲" if gold_pct > 0 else "▼" if gold_pct < 0 else "—"
        with col5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">🥇 금 ($/oz)</div>
                <div class="metric-value" style="color: #d69e2e;">${gold_price:,.1f}</div>
                <div class="{gold_change_class}">{gold_arrow} {abs(gold_pct):.2f}% (전일비)</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ========================================
# 한일전기 원가 영향 시뮬레이션
# ========================================
st.markdown('<div class="section-header">🏭 한일전기 원가 영향 시뮬레이션</div>', unsafe_allow_html=True)

copper_cost_impact = 0
fx_cost_impact = 0
total_cost_impact = 0

if "구리" in all_data and "원/달러 환율" in all_data:
    copper_raw_val, _, _ = get_price_info(all_data["구리"])
    fx_price_val, _, _ = get_price_info(all_data["원/달러 환율"])
    if copper_raw_val and fx_price_val:
        copper_per_ton_val = copper_to_ton(copper_raw_val)
        copper_cost_impact = ((copper_per_ton_val - copper_base) / copper_base) * (copper_bom_ratio / 100) * 100
        fx_cost_impact = ((fx_price_val - fx_base) / fx_base) * (import_ratio / 100) * 100
        total_cost_impact = copper_cost_impact + fx_cost_impact
        copper_krw_per_ton = copper_per_ton_val * fx_price_val
        copper_krw_base = copper_base * fx_base
        copper_krw_change = ((copper_krw_per_ton - copper_krw_base) / copper_krw_base) * 100

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">구리 원가 영향</div>
                <div class="metric-value" style="color: {'#e53e3e' if copper_cost_impact > 0 else '#38a169'};">{copper_cost_impact:+.2f}%p</div>
                <div style="font-size:0.85rem; color:#718096;">BOM 비중 {copper_bom_ratio}% 기준<br>원화환산 {copper_krw_per_ton/10000:,.0f}만원/톤 ({copper_krw_change:+.1f}%)</div>
            </div>
            """, unsafe_allow_html=True)
        with col_b:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">환율 원가 영향</div>
                <div class="metric-value" style="color: {'#e53e3e' if fx_cost_impact > 0 else '#38a169'};">{fx_cost_impact:+.2f}%p</div>
                <div style="font-size:0.85rem; color:#718096;">수입 비중 {import_ratio}% 기준</div>
            </div>
            """, unsafe_allow_html=True)
        with col_c:
            impact_color = '#e53e3e' if total_cost_impact > 3 else '#d69e2e' if total_cost_impact > 0 else '#38a169'
            st.markdown(f"""
            <div class="metric-card" style="border: 2px solid {impact_color};">
                <div class="metric-label">⚡ 총 원가율 영향 (추정)</div>
                <div class="metric-value" style="color: {impact_color};">{total_cost_impact:+.2f}%p</div>
                <div style="font-size:0.85rem; color:#718096;">구리 + 환율 복합 영향</div>
            </div>
            """, unsafe_allow_html=True)

        if total_cost_impact > 5:
            st.markdown(f'<div class="alert-box"><strong>🚨 원가 경보:</strong> 원가율 기준 대비 <strong>{total_cost_impact:+.2f}%p</strong> 상승 추정. 구리 선재 2Q 발주 전략 긴급 검토 및 판가 연동 조항 협의 필요.</div>', unsafe_allow_html=True)
        elif total_cost_impact > 2:
            st.markdown(f'<div class="insight-box"><strong>⚠️ 원가 주의:</strong> 원가율 기준 대비 <strong>{total_cost_impact:+.2f}%p</strong> 상승 추정. 주간 모니터링 강화 권장.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="insight-box"><strong>✅ 원가 안정:</strong> 원가율 변동 <strong>{total_cost_impact:+.2f}%p</strong>로 관리 가능 수준.</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ========================================
# 차트 섹션
# ========================================
st.markdown('<div class="section-header">📉 가격 추이 차트</div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🔶 구리", "💱 환율", "🛢️ 에너지", "📊 종합 비교"])

with tab1:
    if "구리" in all_data:
        data = all_data["구리"].copy()
        data_ton = data.copy()
        for col in ['Open', 'High', 'Low', 'Close']:
            data_ton[col] = data[col] * LBS_PER_TON

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                            row_heights=[0.7, 0.3], subplot_titles=("구리 가격 ($/톤)", "거래량"))
        fig.add_trace(go.Candlestick(
            x=data_ton.index, open=data_ton['Open'], high=data_ton['High'],
            low=data_ton['Low'], close=data_ton['Close'], name="구리 ($/톤)",
            increasing_line_color='#e53e3e', decreasing_line_color='#3182ce',
            increasing_fillcolor='#fc8181', decreasing_fillcolor='#63b3ed',
        ), row=1, col=1)
        ma20 = data_ton['Close'].rolling(window=20).mean()
        fig.add_trace(go.Scatter(x=data_ton.index, y=ma20, name="20일 이평선",
                                 line=dict(color='#d69e2e', width=2, dash='dot')), row=1, col=1)
        ma60 = data_ton['Close'].rolling(window=60).mean()
        fig.add_trace(go.Scatter(x=data_ton.index, y=ma60, name="60일 이평선",
                                 line=dict(color='#805ad5', width=2, dash='dash')), row=1, col=1)
        fig.add_hline(y=copper_base, line_dash="dash", line_color="#e53e3e",
                      annotation_text=f"기준가 ${copper_base:,}/톤", annotation_position="top left",
                      annotation_font_color="#e53e3e", row=1, col=1)
        colors = ['#e53e3e' if c >= o else '#3182ce' for c, o in zip(data['Close'], data['Open'])]
        fig.add_trace(go.Bar(x=data.index, y=data['Volume'], name="거래량",
                             marker_color=colors, opacity=0.5), row=2, col=1)
        fig.update_layout(height=650, showlegend=True,
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                          xaxis_rangeslider_visible=False, template="plotly_white",
                          font=dict(family="Noto Sans KR"), margin=dict(l=20, r=20, t=60, b=20))
        fig.update_yaxes(title_text="$/톤", row=1, col=1)
        st.plotly_chart(fig, use_container_width=True)

        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1: st.metric("기간 최고가", f"${data_ton['High'].max():,.0f}/톤")
        with col_s2: st.metric("기간 최저가", f"${data_ton['Low'].min():,.0f}/톤")
        with col_s3: st.metric("기간 평균가", f"${data_ton['Close'].mean():,.0f}/톤")
        with col_s4: st.metric("일간 변동성", f"{data_ton['Close'].pct_change().std() * 100:.2f}%")

with tab2:
    if "원/달러 환율" in all_data:
        data = all_data["원/달러 환율"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name="USD/KRW", line=dict(color='#3182ce', width=2.5)))
        ma20 = data['Close'].rolling(window=20).mean()
        fig.add_trace(go.Scatter(x=data.index, y=ma20, name="20일 이평선", line=dict(color='#d69e2e', width=2, dash='dot')))
        fig.add_hline(y=fx_base, line_dash="dash", line_color="#e53e3e", annotation_text=f"기준가 ₩{fx_base:,}", annotation_position="top left", annotation_font_color="#e53e3e")
        y_min = float(data['Close'].min()) * 0.995
        y_max = float(data['Close'].max()) * 1.005
        fig.update_layout(height=500, title="원/달러 환율 추이", template="plotly_white", font=dict(family="Noto Sans KR"), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=20, r=20, t=60, b=20), yaxis_title="원/달러 (₩)", yaxis=dict(range=[y_min, y_max]))
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    fig = go.Figure()
    if "WTI 원유" in all_data:
        d = all_data["WTI 원유"]
        fig.add_trace(go.Scatter(x=d.index, y=d['Close'], name="WTI", line=dict(color='#38a169', width=2.5)))
    if "브렌트 원유" in all_data:
        d = all_data["브렌트 원유"]
        fig.add_trace(go.Scatter(x=d.index, y=d['Close'], name="브렌트", line=dict(color='#805ad5', width=2.5)))
    fig.add_hline(y=wti_base, line_dash="dash", line_color="#e53e3e",
                  annotation_text=f"WTI 기준가 ${wti_base}", annotation_position="top left",
                  annotation_font_color="#e53e3e")
    fig.update_layout(height=500, title="WTI & 브렌트 원유 가격 비교", template="plotly_white",
                      font=dict(family="Noto Sans KR"), showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      margin=dict(l=20, r=20, t=60, b=20), yaxis_title="가격 ($/배럴)")
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("**기간 시작일 대비 누적 변동률 (%) — 한눈에 보는 원가 리스크**")
    comparison_data = {}
    colors_map = {"구리": "#e53e3e", "원/달러": "#3182ce", "WTI": "#38a169", "금": "#d69e2e"}
    for name, key in [("구리", "구리"), ("원/달러", "원/달러 환율"), ("WTI", "WTI 원유"), ("금", "금")]:
        if key in all_data:
            d = all_data[key]
            base_val = float(d['Close'].iloc[0])
            comparison_data[name] = ((d['Close'] / base_val) - 1) * 100
    fig = go.Figure()
    for name, series in comparison_data.items():
        fig.add_trace(go.Scatter(x=series.index, y=series.values, name=name,
                                 line=dict(color=colors_map.get(name, '#718096'), width=2.5)))
    fig.add_hline(y=0, line_dash="solid", line_color="#a0aec0", line_width=1)
    fig.update_layout(height=500, title="기간 시작일 대비 누적 변동률 (%)", template="plotly_white",
                      font=dict(family="Noto Sans KR"), showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      margin=dict(l=20, r=20, t=60, b=20), yaxis_title="변동률 (%)")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# ========================================
# 시나리오 분석
# ========================================
st.markdown('<div class="section-header">🎯 구리 가격 시나리오별 원가 영향</div>', unsafe_allow_html=True)

if "구리" in all_data and "원/달러 환율" in all_data:
    copper_raw_now, _, _ = get_price_info(all_data["구리"])
    fx_now, _, _ = get_price_info(all_data["원/달러 환율"])
    if copper_raw_now and fx_now:
        copper_ton_now = copper_to_ton(copper_raw_now)
        scenarios = [
            {"name": "🟢 하락", "price": 10000, "desc": "Goldman Sachs 하반기"},
            {"name": "🟡 현행", "price": round(copper_ton_now / 100) * 100, "desc": f"현재 ${copper_ton_now:,.0f} 수준"},
            {"name": "🔴 상승", "price": 13000, "desc": "J.P.Morgan 2Q 정점"},
            {"name": "🔴🔴 극단", "price": 15000, "desc": "BofA 최고치"},
        ]
        cols = st.columns(4)
        for i, s in enumerate(scenarios):
            ci = ((s["price"] - copper_base) / copper_base) * (copper_bom_ratio / 100)
            krw = s["price"] * fx_now
            bc = "impact-badge-safe" if ci < 0.02 else "impact-badge-warning" if ci < 0.05 else "impact-badge-danger"
            with cols[i]:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">{s['name']}</div>
                    <div class="metric-value" style="font-size:1.5rem;">${s['price']:,}/톤</div>
                    <div style="font-size:0.8rem; color:#718096; margin-bottom:0.5rem;">{s['desc']}</div>
                    <div class="{bc}">원가 영향 {ci*100:+.2f}%p</div>
                    <div style="font-size:0.8rem; color:#718096; margin-top:0.5rem;">원화환산 {krw/10000:,.0f}만원/톤</div>
                </div>
                """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ========================================
# 위클리 코멘트
# ========================================
st.markdown('<div class="section-header">📝 자동 생성 위클리 코멘트</div>', unsafe_allow_html=True)

parts = [f"**[원자재 위클리] {datetime.now().strftime('%Y.%m.%d')} 기준**\n"]
if "구리" in all_data:
    cp, _, cpct = get_price_info(all_data["구리"])
    if cp:
        cpt = copper_to_ton(cp)
        wk = get_period_change(all_data["구리"], 5) or 0
        parts.append(f"🔶 **구리** ${cpt:,.0f}/톤 (전일비 {cpct:+.2f}%, 주간 {wk:+.1f}%) — {'⚠️ 고가 경계. 2Q 발주 점검.' if cpt > 12000 else '모니터링 유지.'}")
if "원/달러 환율" in all_data:
    fp, _, fpct = get_price_info(all_data["원/달러 환율"])
    if fp:
        wk = get_period_change(all_data["원/달러 환율"], 5) or 0
        parts.append(f"💱 **환율** ₩{fp:,.1f} (전일비 {fpct:+.2f}%, 주간 {wk:+.1f}%) — {'⚠️ 고환율 지속.' if fp > 1400 else '안정적.'}")
if "WTI 원유" in all_data:
    wp, _, wpct = get_price_info(all_data["WTI 원유"])
    if wp:
        wk = get_period_change(all_data["WTI 원유"], 5) or 0
        parts.append(f"🛢️ **WTI** ${wp:,.2f} (전일비 {wpct:+.2f}%, 주간 {wk:+.1f}%) — {'✅ 물류비 안정.' if wp < 75 else '⚠️ 상승 압력.'}")
parts.append(f"\n🏭 **한일전기 원가 영향**: 총 {total_cost_impact:+.2f}%p (구리 {copper_cost_impact:+.2f}%p + 환율 {fx_cost_impact:+.2f}%p)")

weekly = "\n\n".join(parts)
st.markdown(f'<div class="insight-box" style="background: linear-gradient(135deg, #f7fafc, #edf2f7); border-left-color: #4a5568;">{weekly.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

with st.expander("📋 사내 메신저 복사용 텍스트"):
    st.code(weekly.replace("**", "").replace("🔶", "▶").replace("💱", "▶").replace("🛢️", "▶").replace("🏭", "▶").replace("⚠️", "[주의]").replace("✅", "[안정]"), language=None)

st.markdown(f"""
<div class="footer">
    한일전기 미래전략본부 원자재 인텔리전스 대시보드 v2.2<br>
    데이터: Yahoo Finance | 갱신: 1시간 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
    구리: HG=F ($/lb × 2204.62 = $/톤) | 환율: KRW=X | 원유: CL=F, BZ=F | 금: GC=F<br>
    ⚠️ 본 대시보드는 참고용이며, 최종 판단은 담당 부서에서 수행하시기 바랍니다.
</div>
""", unsafe_allow_html=True)





