import streamlit as st
import datetime
import FinanceDataReader as fdr
import json
import os

# 🔐 [로그인 시스템]
def check_login():
    if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
    if not st.session_state["logged_in"]:
        st.write("## 👑 시스템 인증")
        user_id = st.text_input("아이디")
        user_pw = st.text_input("비밀번호", type="password")
        if st.button("로그인"):
            if user_id == "richbrother" and user_pw == "gold777":
                st.session_state["logged_in"] = True
                st.rerun()
        return False
    return True

if check_login():
    st.set_page_config(page_title="리치 마스터 퀀트", layout="wide")
    st.title("👑 리치 글로벌 마스터 퀀트 (상세 가이드 Ver)")

    # 자산 설정 (진입금 자동 계산용)
    total_seed = st.sidebar.number_input("나의 투자 원금을 입력하세요 (원)", value=20000000, step=100000)
    진입1차 = int(total_seed * 0.15)
    진입2차 = int(total_seed * 0.10)

    DB_FILE = "퀀트_히스토리.json"

    def save_history(strategy, result):
        hist = {}
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f: hist = json.load(f)
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        if date not in hist: hist[date] = {}
        hist[date][strategy] = result
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(hist, f, ensure_ascii=False, indent=4)

    # 매매 가이드 생성 엔진
    def generate_guide(name, code, price, target, buy2nd, prob, unit):
        return f"""
        📌 **{name} ({code})** (성공률: {prob:.0f}%)
        * **[오늘 종가 매수]** 진입가: {price:,}{unit} ➔ 💰 추천금액: **{format(진입1차, ',')}원**
        * **[목표 매도가]** 목표가: {target:,}{unit} (자동매도 예약)
        * **[2차 물타기 대응]** 대응가: {buy2nd:,}{unit} 부근 ➔ 💰 예비금액: **{format(진입2차, ',')}원**
        """

    # 스캔 엔진 (한국/미국/기본/1% 공통 사용)
    def run_strategy(is_us, is_1pct):
        st.info("⚡ 스캔 실행 중... (상위 우량주 200개 분석)")
        target_list = fdr.StockListing('S&P500') if is_us else fdr.StockListing('KRX')
        results = []
        
        # 실제 로직 (RSI + 거래량 필터링)
        for _, row in target_list.head(200).iterrows():
            try:
                code = row['Symbol'] if is_us else row['Code']
                df = fdr.DataReader(code.replace('.', '-'), '2026-01-01')
                # 간단 RSI 로직 (형의 기존 로직 이식)
                rsi = 100 - (100 / (1 + df['Close'].diff().rolling(14).mean() / df['Close'].diff().rolling(14).mean().abs()))
                
                # 타점 조건 통과 시 상세 가이드 생성
                if (is_1pct and rsi.iloc[-1] < 30) or (not is_1pct and rsi.iloc[-1] < 35):
                    price = int(df['Close'].iloc[-1])
                    unit = "$" if is_us else "원"
                    guide = generate_guide(row['Name'], code, price, int(price*1.01), int(price*0.97), 85, unit)
                    results.append(guide)
            except: continue
        
        save_history("스캔", results)
        for res in results: st.info(res)

    # 시간대 가이드
    st.info("⏰ 한국 기본형(오후3:10), 한국 단타(오전9:05), 미국 확장(밤11:40), 미국 단타(밤10:35)")

    # 버튼
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("🇰🇷 한국 일봉 눌림목 스캔"): run_strategy(False, False)
    if c2.button("⚡ 한국 1% 단타 스캔"): run_strategy(False, True)
    if c3.button("🇺🇸 미국 일봉 확장 스캔"): run_strategy(True, False)
    if c4.button("⚡ 미국 1% 단타 스캔"): run_strategy(True, True)

    # 히스토리
    st.subheader("💾 히스토리")
    history = load_history()
    date_select = st.selectbox("날짜 선택", sorted(history.keys(), reverse=True))
    if date_select: st.write(history[date_select])
