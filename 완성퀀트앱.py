import streamlit as st
import datetime
import FinanceDataReader as fdr
import pandas as pd
import json
import os

# ==========================================
# [🔒 보안 패치: 해킹 및 타인 접근 방지 로그인 시스템]
# ==========================================
def check_login():
    MY_ID = "richbrother"
    MY_PW = "gold777"
    
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        st.markdown("<h2 style='text-align: center;'>👑 리치 퀀트 마스터 보안 시스템</h2>", unsafe_allow_html=True)
        st.write("본 프로그램은 개인 자산 관리용 보안 앱입니다. 인증 후 이용 가능합니다.")
        
        user_id = st.text_input("🔑 아이디(ID) 입력", key="input_id")
        user_pw = st.text_input("🔒 비밀번호(PW) 입력", type="password", key="input_pw")
        
        if st.button("보안 로그인 하기", use_container_width=True):
            if user_id == MY_ID and user_pw == MY_PW:
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ 접근 권한이 없습니다. 아이디 또는 비밀번호를 다시 확인하세요.")
        return False
    return True

# --- [페이지 기본 설정 (모바일 최적화)] ---
st.set_page_config(page_title="종합 마스터 퀀트 스캐너", page_icon="👑", layout="centered")

if check_login():

    DB_FILE = "완성퀀트_역사기록.json"

    def load_history():
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}

    def save_history(date_key, strategy_name, results):
        history = load_history()
        if date_key not in history: history[date_key] = {}
        history[date_key][strategy_name] = results
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)

    WEEKS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

    def format_krw_to_hangul(number):
        if number == 0:
            return "0원"
        units = ["원", "만 ", "억 ", "조 "]
        result = []
        for i in range(len(units)):
            number, r = divmod(number, 10000)
            if r > 0:
                result.append(f"{r:,}{units[i]}")
            if number == 0:
                break
        return "".join(reversed(result)).strip()

    # 🔥 [시간 패치] 외국 서버 시간이 아닌 '대한민국 서울 시간'으로 강제 고정하는 함수
    def get_seoul_now():
        # 서버 시간에 한국 시간 차이(9시간)를 더해서 정확한 한국 시각을 계산합니다.
        return datetime.datetime.utcnow() + datetime.timedelta(hours=9)

    @st.cache_data(ttl=3600)
    def get_market_status():
        try:
            df_usd = fdr.DataReader('USD/KRW')
            current_usd = df_usd['Close'].iloc[-1]
            
            df_kospi = fdr.DataReader('KS11')
            kospi_ma5 = df_kospi['Close'].rolling(5).mean().iloc[-1]
            kr_market_safe = df_kospi['Close'].iloc[-1] >= kospi_ma5
            
            df_nasdaq = fdr.DataReader('IXIC')
            nasdaq_ma5 = df_nasdaq['Close'].rolling(5).mean().iloc[-1]
            us_market_safe = df_nasdaq['Close'].iloc[-1] >= nasdaq_ma5
            
            return current_usd, kr_market_safe, us_market_safe
        except:
            return 1350.0, True, True

    current_usd, kr_market_safe, us_market_safe = get_market_status()

    def get_krx_stocks(limit=200):
        df_krx = fdr.StockListing('KRX')
        df_filtered = df_krx[(df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & (~df_krx['Name'].str.contains('우|우B|우선주|스팩|ETF'))]
        return df_filtered.sort_values(by='Marcap', ascending=False)[['Code', 'Name']].head(limit).to_dict('records')

    def get_us_stocks(limit=200):
        try: df_sp500 = fdr.StockListing('S&P500')[['Symbol', 'Name']]
        except: df_sp500 = pd.DataFrame(columns=['Symbol', 'Name'])
        return df_sp500.head(limit).to_dict('records')

    # 1. 한국 퀀트 (기본형)
    def run_kr_original(stock):
        df = fdr.DataReader(stock['Code'], '2005-01-01')
        if len(df) < 250: return None
        avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
        if avg_marcap_traded < 5000000000: return None 
        
        df['MA20'] = df['Close'].rolling(20).mean(); df['STD20'] = df['Close'].rolling(20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-9))); df['Vol_MA5'] = df['Volume'].rolling(5).mean()
        df['Signal'] = (df['RSI'].rolling(3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5']) & (df['Close'].pct_change()*100 > -1)
        
        if not df['Signal'].iloc[-1]: return None
        signal_days = df[df['Signal'] == True].index[:-1]
        if len(signal_days) < 5: return None
        success = sum(1 for d in signal_days if df.loc[d:].iloc[1:9]['High'].max() >= df.loc[d, 'Close'] * 1.045)
        prob = (success / len(signal_days)) * 100
        if prob < 80: return None
        
        close_p = int(df['Close'].iloc[-1])
        return {"name": stock['Name'], "price": close_p, "target": int(close_p*1.045), "buy2nd": int(close_p*0.95), "prob": prob, "type": "원화"}

    # 2. 한국 퀀트 (매일 1%)
    def run_kr_1pct(stock):
        # 오늘 날짜 구하기 (한국 시간 기준)
        seoul_today = get_seoul_now()
        start_date = (seoul_today - datetime.timedelta(days=3*365)).strftime('%Y-%m-%d')
        df = fdr.DataReader(stock['Code'], start_date)
        if len(df) < 150: return None
        avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
        if avg_marcap_traded < 5000000000: return None 
        
        df['MA5'] = df['Close'].rolling(5).mean()
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(9).mean(); loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
        df['RSI_9'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
        df['Signal'] = (df['RSI_9'] <= 30) & (df['Close'] < df['MA5'] * 0.97) & (df['Close'].pct_change()*100 > -4)
        
        if not df['Signal'].iloc[-1]: return None
        signal_days = df[df['Signal'] == True].index[:-1]
        if len(signal_days) < 5: return None
        success = 0
        for d in signal_days:
            try:
                if df.iloc[df.index.get_loc(d) + 1]['High'] >= df.loc[d, 'Close'] * 1.01: success += 1
            except: continue
        prob = (success / len(signal_days)) * 100
        if prob < 85: return None
        
        close_p = int(df['Close'].iloc[-1])
        return {"name": stock['Name'], "price": close_p, "target": int(close_p*1.01), "buy2nd": int(close_p*0.97), "prob": prob, "type": "원화"}

    # 3. 미국 퀀트 (확장판)
    def run_us_new(stock):
        df = fdr.DataReader(stock['Symbol'].replace('.', '-'), '2005-01-01')
        if len(df) < 250: return None
        avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
        if avg_marcap_traded < 3000000: return None
        
        df['MA20'] = df['Close'].rolling(20).mean(); df['STD20'] = df['Close'].rolling(20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-9))); df['Vol_MA5'] = df['Volume'].rolling(5).mean()
        df['Signal'] = (df['RSI'].rolling(3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5']) & (df['Close'].pct_change()*100 > -1)
        
        if not df['Signal'].iloc[-1]: return None
        signal_days = df[df['Signal'] == True].index[:-1]
        if len(signal_days) < 5: return None
        success = sum(1 for d in signal_days if df.loc[d:].iloc[1:9]['High'].max() >= df.loc[d, 'Close'] * 1.045)
        prob = (success / len(signal_days)) * 100
        if prob < 80: return None
        
        close_p = round(df['Close'].iloc[-1], 2)
        return {"name": f"{stock['Name']} ({stock['Symbol']})", "price": close_p, "target": round(close_p*1.045, 2), "buy2nd": round(close_p*0.95, 2), "prob": prob, "type": "달러"}

    # 4. 미국 퀀트 (매일 1%)
    def run_us_1pct(stock):
        seoul_today = get_seoul_now()
        start_date = (seoul_today - datetime.timedelta(days=3*365)).strftime('%Y-%m-%d')
        df = fdr.DataReader(stock['Symbol'].replace('.', '-'), start_date)
        if len(df) < 150: return None
        avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
        if avg_marcap_traded < 3000000: return None
        
        df['MA5'] = df['Close'].rolling(5).mean()
        delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(9).mean(); loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
        df['RSI_9'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
        df['Signal'] = (df['RSI_9'] <= 30) & (df['Close'] < df['MA5']) & (df['Close'].pct_change()*100 > -2)
        
        if not df['Signal'].iloc[-1]: return None
        signal_days = df[df['Signal'] == True].index[:-1]
        if len(signal_days) < 5: return None
        success = 0
        for d in signal_days:
            try:
                if df.iloc[df.index.get_loc(d) + 1]['High'] >= df.loc[d, 'Close'] * 1.01: success += 1
            except: continue
        prob = (success / len(signal_days)) * 100
        if prob < 85: return None
        
        close_p = round(df['Close'].iloc[-1], 2)
        return {"name": f"{stock['Name']} ({stock['Symbol']})", "price": close_p, "target": round(close_p*1.01, 2), "buy2nd": round(close_p*0.97, 2), "prob": prob, "type": "달러"}


    # ==========================================
    # [대시보드 상단 레이아웃 - 모니터링 및 자산 설정]
    # ==========================================
    st.title("👑 리치 퀀트 마스터 스캐너 v2")
    st.markdown(f"📊 **실시간 원·달러 환율:** ` {current_usd:,.2f}원 ` | 📅 데이터 자동 연동 중")

    st.sidebar.header("💰 자산 배분 세팅")
    total_seed = st.sidebar.number_input("나의 투자 원금을 입력하세요 (원)", min_value=10000, value=10000000, step=100000)

    seed_hangul = format_krw_to_hangul(total_seed)
    st.sidebar.markdown(f"✍️ **입력된 금액:** `{seed_hangul}`")
    st.sidebar.markdown("---")

    진입1차 = int(total_seed * 0.15)
    진입2차 = int(total_seed * 0.10)
    st.sidebar.write(f"👉 **1차 진입금 (15%):** {format_krw_to_hangul(진입1차)}")
    st.sidebar.write(f"👉 **2차 예비비 (10%):** {format_krw_to_hangul(진입2차)}")

    st.markdown("---")

    # ==========================================
    # [⏰ 전략별 황금 추천 시간표 가이드 박아두기]
    # ==========================================
    st.markdown("""
    ### ⏰ **전략별 황금 추천 시간표 (언제 누르면 가장 좋나요?)**
    형, 주식 시장 성격에 맞춰 아래 지정된 **황금 시간대**에 버튼을 눌러야 정확하고 확실한 종목이 걸러집니다! 
    
    * **🇰🇷 한국 퀀트 (기본형)** ➔ **`오후 3시 10분 ~ 3시 30분 (장마감 직전 종가 매수용)`**
      * 하루 주가가 거의 다 결정된 장 마감 직전에 눌러서 내일 아침 폭등할 우량주를 낚아채는 황금 시간입니다.
    * **⚡ 한국 퀀트 (매일 1% 단타)** ➔ **`오전 9시 05분 ~ 9시 30분 (장초반 급등 단타용)`**
      * 아침에 시장이 열리자마자 쿵쾅거리는 거래량을 분석해 빠르게 1% 먹고 나오는 당일치기용 시간입니다.
    * **🇺🇸 미국 퀀트 (확장판)** ➔ **`밤 11시 40분 ~ 새벽 1시 (본장 개장 직후 안정화 단계)`**
      * 미국 주식 본장이 개장(밤 10시 반 또는 11시 반)하고 초반 변동성이 조금 진정된 야간 황금 시간입니다.
    * **⚡ 미국 퀀트 (매일 1% 단타)** ➔ **`밤 10시 35분 ~ 11시 (서머타임 기준 개장 직후 폭발 단타)`**
      * 미국 시장 문 열리자마자 불타오르는 미국 단타 종목을 선점하는 시간입니다.
    """)
    st.markdown("---")

    # ==========================================
    # [스캔 버튼 및 시장 필터 제어]
    # ==========================================
    st.subheader("🚀 실시간 종목 스캔 실행")
    col1, col2 = st.columns(2)
    with col1:
        btn_kr_ori = st.button("🇰🇷 한국 퀀트 (기본형) 실행", use_container_width=True)
        btn_kr_1pc = st.button("⚡ 한국 퀀트 (매일 1%) 실행", use_container_width=True)
    with col2:
        btn_us_new = st.button("🇺🇸 미국 퀀트 (확장판) 실행", use_container_width=True)
        btn_us_1pc = st.button("⚡ 미국 퀀트 (매일 1%) 실행", use_container_width=True)

    def 조작_프로세스(전략이름, 종목함수, 분석함수, 시장안전여부):
        if not 시장안전여부:
            st.error(f"🚨 [시장 필터 차단] 현재 대형 하락세 구간입니다. 돈을 잃을 확률이 비정상적으로 높으므로 오늘 매매는 패스하고 현금을 지키세요!")
            return

        st.info(f"▶ {전략이름} 백테스팅 및 대량 거래량 필터링 가동 중...")
        종목들 = 종목함수()
        발견종목 = []
        
        프로그레스바 = st.progress(0)
        for i, 종목 in enumerate(종목들):
            res = 분석함수(종목)
            if res: 발견종목.append(res)
            프로그레스바.progress((i + 1) / len(종목들))
            
        # 🔥 [시간 수정 완료] 이제 무조건 대한민국 서울 시간으로 칼같이 가져옵니다.
        now = get_seoul_now()
        date_key = now.strftime(f"%Y년 %m월 %d일 ({WEEKS[now.weekday()]})")
        time_key = now.strftime("%p %I시 %M분 %S초").replace("AM", "오전").replace("PM", "오후")
        
        if 발견종목:
            st.success(f"🎉 {time_key} 스캔 완료! 오늘 조건을 만족하는 고확률 우량 종목을 총 {len(발견종목)}개 찾았습니다!")
            save_list = []
            for stock in 발견종목:
                진입1차_금액 = int(total_seed * 0.15)
                진입2차_금액 = int(total_seed * 0.10)
                
                unit = "원" if stock['type'] == "원화" else "$"
                price_formatted = f"{stock['price']:,}" if stock['type'] == "원화" else f"{stock['price']}"
                target_formatted = f"{stock['target']:,}" if stock['type'] == "원화" else f"{stock['target']}"
                buy2nd_formatted = f"{stock['buy2nd']:,}" if stock['type'] == "원화" else f"{stock['buy2nd']}"
                
                txt_box = f"""
                📌 **{stock['name']}** (과거 성공률: {stock['prob']:.0f}%)
                * **⏰ [추천 시간]** {time_key} 분석 감지
                * **[오늘 종가 1차 매수]** 진입가: {price_formatted}{unit} ➔ 💰 추천 금액: **{format_krw_to_hangul(진입1차_금액)}** ({진입1차_금액:,}원어치)
                * **[익절 예약 매도 목표]** 목표가: {target_formatted}{unit} (내일 아침 자동 매도 예약)
                * **[방어용 2차 물타기 선]** 대응가: {buy2nd_formatted}{unit} 부근 ➔ 💰 예비 자금: **{format_krw_to_hangul(진입2차_금액)}** ({진입2차_금액:,}원어치) 대기
                """
                st.info(txt_box)
                save_list.append(txt_box)
            save_history(date_key, 전략이름, save_list)
        else:
            msg = f"😓 {time_key} 스캔 결과: 오늘 대량 거래대금 조건 및 승률 커트라인을 통과한 종목이 없습니다."
            save_history(date_key, 전략이름, [msg])
            st.warning(msg)

    if btn_kr_ori: 조작_프로세스("한국 퀀트 (기본형)", get_krx_stocks, run_kr_original, kr_market_safe)
    if btn_kr_1pc: 조작_프로세스("한국 퀀트 (매일 1%)", get_krx_stocks, run_kr_1pct, kr_market_safe)
    if btn_us_new: 조작_프로세스("미국 퀀트 (확장판)", get_us_stocks, run_us_new, us_market_safe)
    if btn_us_1pc: 조작_프로세스("미국 퀀트 (매일 1%)", get_us_stocks, run_us_1pct, us_market_safe)

    # ==========================================
    # [💾 영구 저장 히스토리 시스템]
    # ==========================================
    st.markdown("---")
    st.subheader("💾 히스토리 및 저장된 결과 다시보기")

    history_data = load_history()
    if not history_data:
        st.write("아직 스캔 이력이 없습니다.")
    else:
        selected_date = st.selectbox("📆 조회할 스캔 날짜 선택", sorted(list(history_data.keys()), reverse=True))
        tab_kr_ori, tab_kr_1pc, tab_us_new, tab_us_1pc = st.tabs(["🇰🇷 한국 퀀트 (기본)", "⚡ 한국 1% 단타", "🇺🇸 미국 퀀트 (확장)", "⚡ 미국 1% 단타"])
        day_results = history_data[selected_date]
        
        with tab_kr_ori:
            for item in day_results.get("한국 퀀트 (기본형)", ["🔍 내역 없음"]): st.write(item)
        with tab_kr_1pc:
            for item in day_results.get("한국 퀀트 (매일 1%)", ["🔍 내역 없음"]): st.write(item)
        with tab_us_new:
            for item in day_results.get("미국 퀀트 (확장판)", ["🔍 내역 없음"]): st.write(item)
        with tab_us_1pc:
            for item in day_results.get("미국 퀀트 (매일 1%)", ["🔍 내역 없음"]): st.write(item)
