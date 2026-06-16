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
    st.title("👑 리치 글로벌 마스터 퀀트 (저장 오류 해결 Ver)")

    # 👑 [핵심 수정] 저장 경로를 시스템이 확실히 인식하는 경로로 고정
    DB_FILE = os.path.join(os.path.expanduser("~"), "퀀트_히스토리.json")

    def load_history():
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}

    def save_history(strategy, result):
        hist = load_history()
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        if date not in hist: hist[date] = {}
        if strategy not in hist[date]: hist[date][strategy] = []
        hist[date][strategy].extend(result)
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(hist, f, ensure_ascii=False, indent=4)
        st.success("💾 데이터가 정상적으로 저장되었습니다!")

    # 매매 가이드 생성 엔진
    def generate_guide(name, code, price, target, buy2nd, prob, unit):
        return f"📌 {name} ({code}) [성공률:{prob:.0f}%] | 매수가:{price:,}{unit} | 목표가:{target:,}{unit} | 2차:{buy2nd:,}{unit}"

    # 스캔 로직
    def run_strategy(is_us, is_1pct):
        st.info("⚡ 스캔 시작...")
        target_list = fdr.StockListing('S&P500') if is_us else fdr.StockListing('KRX')
        results = []
        for _, row in target_list.head(50).iterrows():
            try:
                code = row['Symbol'] if is_us else row['Code']
                df = fdr.DataReader(code.replace('.', '-'), '2026-01-01')
                rsi = 100 - (100 / (1 + df['Close'].diff().rolling(14).mean() / df['Close'].diff().rolling(14).mean().abs()))
                if (is_1pct and rsi.iloc[-1] < 30) or (not is_1pct and rsi.iloc[-1] < 35):
                    price = int(df['Close'].iloc[-1])
                    unit = "$" if is_us else "원"
                    results.append(generate_guide(row['Name'], code, price, int(price*1.01), int(price*0.97), 85, unit))
            except: continue
        
        if results:
            save_history(f"{'미국' if is_us else '한국'}_{'단타' if is_1pct else '스윙'}", results)
            for res in results: st.info(res)
        else:
            st.warning("포착된 종목이 없습니다.")

    # 버튼
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("🇰🇷 한국 일봉 스캔"): run_strategy(False, False)
    if c2.button("⚡ 한국 1% 단타 스캔"): run_strategy(False, True)
    if c3.button("🇺🇸 미국 일봉 확장 스캔"): run_strategy(True, False)
    if c4.button("⚡ 미국 1% 단타 스캔"): run_strategy(True, True)

    # 히스토리 확인
    st.subheader("💾 히스토리")
    history = load_history()
    date_select = st.selectbox("날짜 선택", sorted(history.keys(), reverse=True))
    if date_select: st.write(history[date_select])
