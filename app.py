import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
import requests
import yfinance as yf

# --- [설정] ---
st.set_page_config(page_title="오복완 - 트레이딩 저널", layout="wide")
FILE_PATH = 'oh_bok_wan_data.csv'

# --- [함수: 시장 데이터 자동 수집] ---
@st.cache_data(ttl=3600)
def get_market_context(target_date):
    try:
        # 1. 공포/탐욕 지수
        fng_response = requests.get("https://api.alternative.me/fng/?limit=0")
        fng_data = fng_response.json()['data']
        
        fear_greed_value = None
        fear_greed_text = "-"
        
        for item in fng_data:
            item_date = datetime.fromtimestamp(int(item['timestamp'])).date()
            if item_date == target_date:
                fear_greed_value = int(item['value'])
                fear_greed_text = item['value_classification']
                break
        
        if fear_greed_value is None:
            fear_greed_value = int(fng_data[0]['value'])
            fear_greed_text = fng_data[0]['value_classification']

        # 2. 비트코인 추세
        btc = yf.download("BTC-USD", start=target_date, end=target_date + pd.Timedelta(days=2), progress=False)
        btc_trend = "-"
        
        if not btc.empty:
            close_price = btc['Close'].iloc[0]
            open_price = btc['Open'].iloc[0]
            if close_price > open_price:
                btc_trend = "양봉(상승)"
            else:
                btc_trend = "음봉(하락)"

        return fear_greed_value, fear_greed_text, btc_trend

    except Exception:
        return 0, "-", "데이터 없음"

# --- [함수: 데이터 로드/저장] ---
def load_data():
    if os.path.exists(FILE_PATH):
        try:
            df = pd.read_csv(FILE_PATH)
            if '진입일시' in df.columns:
                df['진입일시'] = pd.to_datetime(df['진입일시'])
            return df
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def save_data(data):
    df = load_data()
    new_df = pd.DataFrame([data])
    if df.empty:
        final_df = new_df
    else:
        final_df = pd.concat([df, new_df], ignore_index=True)
    final_df.to_csv(FILE_PATH, index=False)

# --- [메인 화면] ---
st.title("오복완 (Oh-Bok-Wan)")

tab1, tab2, tab3 = st.tabs(["매매 기록", "기록장", "통계"])

# === 탭 1: 매매 입력 ===
with tab1:
    with st.form("trade_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        ticker = c1.text_input("종목명", value="BTC/USDT")
        date = c2.date_input("진입 날짜")
        time = c3.time_input("진입 시간")
        
        c4, c5, c6 = st.columns(3)
        position = c4.selectbox("포지션", ["Long", "Short"])
        leverage = c5.number_input("레버리지", value=1, min_value=1)
        
        st.markdown("---")
        cc1, cc2, cc3, cc4 = st.columns(4)
        entry_price = cc1.number_input("진입가", min_value=0.0, format="%.4f")
        exit_price = cc2.number_input("청산가", min_value=0.0, format="%.4f")
        stop_loss = cc3.number_input("손절가", min_value=0.0, format="%.4f")
        take_profit = cc4.number_input("익절가", min_value=0.0, format="%.4f")
        
        submitted = st.form_submit_button("저장", use_container_width=True)

        if submitted:
            if entry_price > 0 and exit_price > 0:
                # 1. 계산 로직
                if "Long" in position:
                    pnl_rate = ((exit_price - entry_price) / entry_price) * leverage * 100
                    pnl_status = "Win" if pnl_rate > 0 else "Lose"
                else:
                    pnl_rate = ((entry_price - exit_price) / entry_price) * leverage * 100
                    pnl_status = "Win" if pnl_rate > 0 else "Lose"
                
                risk = abs(entry_price - stop_loss) if stop_loss > 0 else 0
                reward = abs(take_profit - entry_price) if take_profit > 0 else 0
                rr_ratio = reward / risk if risk > 0 else 0

                # 2. 데이터 수집 (조용히 처리)
                fng_value, fng_text, btc_trend = get_market_context(date)

                # 3. 저장
                trade_data = {
                    "진입일시": datetime.combine(date, time),
                    "종목": ticker,
                    "포지션": position,
                    "레버리지": leverage,
                    "수익률(%)": round(pnl_rate, 2),
                    "결과": pnl_status,
                    "손익비": round(rr_ratio, 2),
                    "공포지수": fng_value,
                    "시장심리": fng_text,
                    "비트추세": btc_trend
                }
                save_data(trade_data)
                
                # 4. 결과 출력 (객관적 수치만 표시)
                st.success("저장되었습니다.")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("수익률", f"{pnl_rate:.2f}%", delta=pnl_status)
                col2.metric("손익비", f"1 : {rr_ratio:.2f}")
                col3.metric("공포지수", f"{fng_value} ({fng_text})")
                col4.metric("당일 추세", btc_trend)
                    
            else:
                st.error("가격을 입력하십시오.")

# === 탭 2: 기록장 ===
with tab2:
    df = load_data()
    if not df.empty:
        st.dataframe(df.sort_index(ascending=False), use_container_width=True)
    else:
        st.info("데이터가 없습니다.")

# === 탭 3: 통계 ===
with tab3:
    df = load_data()
    if not df.empty and '공포지수' in df.columns:
        c1, c2 = st.columns(2)
        
        # 공포지수 상관관계
        fig = px.scatter(df, x="공포지수", y="수익률(%)", color="결과", 
                         title="공포지수 대비 수익률",
                         hover_data=["종목", "진입일시"])
        c1.plotly_chart(fig, use_container_width=True)
        
        # 추세별 승패
        trend_win = df.groupby(['비트추세', '결과']).size().reset_index(name='count')
        fig2 = px.bar(trend_win, x="비트추세", y="count", color="결과", title="추세별 승패 횟수")
        c2.plotly_chart(fig2, use_container_width=True)
    else:
        st.write("데이터가 충분하지 않습니다.")
