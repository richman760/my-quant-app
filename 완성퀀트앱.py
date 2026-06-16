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
    st.set_page_config(page_title="리치 글로벌 마스터 퀀트", layout="wide")
    st.title("👑 리치 글로벌 마스터 퀀트 (경량화 Ver)")

    DB_FILE = "퀀트_히스토리.json"

    def load_history():
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
        return {}

    def save_history(strategy, result):
        hist = load_history()
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        if date not in hist: hist[date] = {}
        hist[date][strategy] = result
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(hist, f, ensure_ascii=False, indent=4)

    # 4대 퀀트 엔진 로직 (공통)
    def scan_strategy(is_us, is_1pct):
        st.info(f"⚡ 스캔 시작...")
        target_list = fdr.StockListing('S&P500') if is_us else fdr.StockListing('KRX')
        results = []
        for _, row in target_list.head(50).iterrows(): # 속도를 위해 50개만
            try:
                code = row['Symbol'] if is_us else row['Code']
                df = fdr.DataReader(code.replace('.', '-'), '2026-01-01')
                rsi = 100 - (100 / (1 + df['Close'].diff().rolling(14).mean() / df['Close'].diff().rolling(14).mean().abs()))
                
                # 전략별 조건 (PASS 기준)
                if is_1pct and rsi.iloc[-1] < 30: # 1% 단타 전략
                    results.append(f"{row['Name']} ({code}) - 타점 발생")
                elif not is_1pct and rsi.iloc[-1] < 35: # 기본 스윙 전략
                    results.append(f"{row['Name']} ({code}) - 눌림목 발생")
            except: continue
        
        save_history("스캔", results)
        st.success("스캔 완료!")
        st.write(results)

    # 추천 시간대 가이드
    st.markdown("""
    ### ⏰ 전략별 황금 시간대
    * **🇰🇷 한국 기본형:** 15:10 ~ 15:30 (종가 매수)
    * **⚡ 한국 1% 단타:** 09:05 ~ 09:30 (장초반)
    * **🇺🇸 미국 확장판:** 23:40 ~ 01:00 (본장 안정)
    * **⚡ 미국 1% 단타:** 22:35 ~ 23:00 (개장 직후)
    """)

    # 4대 스캔 버튼
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("🇰🇷 한국 일봉 눌림목 스캔"): scan_strategy(False, False)
    if c2.button("⚡ 한국 1% 단타 스캔"): scan_strategy(False, True)
    if c3.button("🇺🇸 미국 일봉 확장 스캔"): scan_strategy(True, False)
    if c4.button("⚡ 미국 1% 단타 스캔"): scan_strategy(True, True)

    # 히스토리 확인
    st.subheader("💾 히스토리 내역")
    history = load_history()
    date_select = st.selectbox("날짜 선택", sorted(history.keys(), reverse=True))
    if date_select: st.write(history[date_select])
