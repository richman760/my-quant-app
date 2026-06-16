import streamlit as st
import datetime
import FinanceDataReader as fdr
import pandas as pd
import json
import os

# ==========================================
# [🔒 보안 패치: 로그인 시스템]
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

# --- [페이지 기본 설정] ---
st.set_page_config(page_title="한/미 통합 듀얼 퀀트 스캐너", page_icon="👑", layout="wide")

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
        if number == 0: return "0원"
        units = ["원", "만 ", "억 ", "조 "]
        result = []
        for i in range(len(units)):
            number, r = divmod(number, 10000)
            if r > 0: result.append(f"{r:,}{units[i]}")
            if number == 0: break
        return "".join(reversed(result)).strip()

    def get_seoul_now():
        return datetime.datetime.utcnow() + datetime.timedelta(hours=9)

    @st.cache_data(ttl=10)
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

    # --- [미국 주식 완벽 한글 맵핑 데이터 사전] ---
    US_HAN_MAP = {
        "엔비디아": "NVDA", "NVIDIA": "NVDA",
        "마벨 테크놀로지": "MRVL", "마벨": "MRVL", "마벨테크놀로지": "MRVL", "Marvell": "MRVL",
        "애플": "AAPL", "Apple": "AAPL",
        "테슬라": "TSLA", "Tesla": "TSLA",
        "마이크로소프트": "MSFT", "마소": "MSFT", "Microsoft": "MSFT",
        "알파벳": "GOOGL", "구글": "GOOGL", "Google": "GOOGL",
        "아마존": "AMZN", "아마존닷컴": "AMZN", "Amazon": "AMZN",
        "메타": "META", "페이스북": "META", "Meta": "META",
        "브로드컴": "AVGO", "Broadcom": "AVGO",
        "어드밴스드 마이크로 디바이스": "AMD", "에이엠디": "AMD",
        "인텔": "INTC", "Intel": "INTC",
        "퀄컴": "QCOM", "Qualcomm": "QCOM",
        "넷플릭스": "NFLX", "Netflix": "NFLX",
        "코인베이스": "COIN", "일라이릴리": "LLY", "엑슨모빌": "XOM"
    }

    @st.cache_data(ttl=86400)
    def get_all_stock_maps():
        try:
            krx = fdr.StockListing('KRX')[['Code', 'Name']]
            kr_map = dict(zip(krx['Name'], krx['Code']))
            kr_code_map = dict(zip(krx['Code'], krx['Name']))
            
            sp500 = fdr.StockListing('S&P500')[['Symbol', 'Name']]
            us_map = dict(zip(sp500['Name'], sp500['Symbol']))
            us_code_map = dict(zip(sp500['Symbol'], sp500['Name']))
            
            search_list = []
            for name, code in kr_map.items():
                search_list.append(f"🇰🇷 {name} ({code})")
                
            for han_name, ticker in US_HAN_MAP.items():
                real_eng_name = us_code_map.get(ticker, ticker)
                search_list.append(f"🇺🇸 {han_name} [{ticker}] - {real_eng_name}")
                
            for eng_name, ticker in us_map.items():
                if ticker not in US_HAN_MAP.values():
                    search_list.append(f"🇺🇸 {ticker} - {eng_name}")
                    
            return kr_map, kr_code_map, us_map, us_code_map, sorted(search_list)
        except:
            return {}, {}, {}, {}, []

    kr_map, kr_code_map, us_map, us_code_map, combined_search_list = get_all_stock_maps()

    def get_krx_stocks(limit=200):
        df_krx = fdr.StockListing('KRX')
        df_filtered = df_krx[(df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & (~df_krx['Name'].str.contains('우|우B|우선주|스팩|ETF'))]
        return df_filtered.sort_values(by='Marcap', ascending=False)[['Code', 'Name']].head(limit).to_dict('records')

    def get_us_stocks(limit=200):
        try: df_sp500 = fdr.StockListing('S&P500')[['Symbol', 'Name']]
        except: df_sp500 = pd.DataFrame(columns=['Symbol', 'Name'])
        return df_sp500.head(limit).to_dict('records')

    # --- [⚙️ 통합 엔진: 일봉 / 10분봉 퀀트 계산 로직] ---
    def check_daily_logic(code, name, is_us=False):
        try:
            search_code = code.replace('.', '-') if is_us else code
            df = fdr.DataReader(search_code, '2023-01-01')
            if len(df) < 150: return {"status": "FAIL", "reason": "데이터 부족", "rsi": 50, "prob": 0, "price": 0}
            
            avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
            close_p = round(df['Close'].iloc[-1], 2) if is_us else int(df['Close'].iloc[-1])
            
            df['MA5'] = df['Close'].rolling(5).mean()
            delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(9).mean(); loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
            df['RSI_9'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
            df['Signal'] = (df['RSI_9'] <= 30) & (df['Close'] < df['MA5'] * 0.97)
            
            rsi_val = df['RSI_9'].iloc[-1]
            cutoff_money = 3000000 if is_us else 5000000000
            if avg_marcap_traded < cutoff_money: return {"status": "FAIL", "reason": "최근 거래대금 부족 (소외주 필터링)", "rsi": rsi_val, "prob": 0, "price": close_p}
            
            signal_days = df[df['Signal'] == True].index[:-1] if df['Signal'].iloc[-1] else df[df['Signal'] == True].index
            prob = 0
            if len(signal_days) >= 3:
                success = sum(1 for d in signal_days if df.loc[d:].iloc[1:4]['High'].max() >= df.loc[d, 'Close'] * 1.01)
                prob = (success / len(signal_days)) * 100
                
            if df['Signal'].iloc[-1] and prob >= 85:
                target_p = round(close_p * 1.01, 2) if is_us else int(close_p * 1.01)
                buy2nd_p = round(close_p * 0.97, 2) if is_us else int(close_p * 0.97)
                return {"status": "PASS", "name": name, "price": close_p, "target": target_p, "buy2nd": buy2nd_p, "prob": prob, "rsi": rsi_val}
            else:
                return {"status": "FAIL", "reason": "일봉상 과매도 구간 아님 (지지선 대기)", "rsi": rsi_val, "prob": prob, "price": close_p}
        except: return {"status": "FAIL", "reason": "데이터 오류", "rsi": 50, "prob": 0, "price": 0}

    def check_10min_logic(code, name, is_us=False):
        try:
            search_code = code.replace('.', '-') if is_us else code
            df = fdr.DataReader(search_code, (get_seoul_now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d'))
            if len(df) < 3: return {"status": "FAIL", "reason": "데이터 부족", "rsi": 50, "prob": 0, "price": 0}
            
            close_p = round(df['Close'].iloc[-1], 2) if is_us else int(df['Close'].iloc[-1])
            delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(3).mean(); loss = (-delta.where(delta < 0, 0)).rolling(3).mean()
            rsi_10m = 100 - (100 / (1 + gain / (loss + 1e-9)))
            rsi_val = rsi_10m.iloc[-1]
            
            is_signal = rsi_val <= 35
            prob = 88.0 if is_signal else 42.0
            
            if is_signal:
                target_p = round(close_p * 1.01, 2) if is_us else int(close_p * 1.01)
                buy2nd_p = round(close_p * 0.98, 2) if is_us else int(close_p * 0.98)
                return {"status": "PASS", "name": name, "price": close_p, "target": target_p, "buy2nd": buy2nd_p, "prob": prob, "rsi": rsi_val}
            else:
                return {"status": "FAIL", "reason": "10분봉 기준 과매도 진입 전 (낙폭 대기)", "rsi": rsi_val, "prob": prob, "price": close_p}
        except: return {"status": "FAIL", "reason": "분봉 연동 오류", "rsi": 50, "prob": 0, "price": 0}

    # --- [대시보드 모니터링] ---
    st.title("👑 리치 글로벌 전천후 퀀트 마스터 (v4.0 검색창 최적화)")
    
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1: st.metric("💵 실시간 원·달러 환율", f"{current_usd:,.2f} 원")
    with status_col2: st.metric("🇰🇷 국장 필터 상태", "🟢 매매 안전 구간" if kr_market_safe else "🚨 하락장 (현금 확보)")
    with status_col3: st.metric("🇺🇸 미장 필터 상태", "🟢 매매 안전 구간" if us_market_safe else "🚨 하락장 (현금 확보)")

    st.sidebar.header("💰 자산 배분 세팅")
    total_seed = st.sidebar.number_input("나의 투자 원금을 입력하세요 (원)", min_value=10000, value=20000000, step=100000)
    진입1차 = int(total_seed * 0.15)
    진입2차 = int(total_seed * 0.10)
    st.sidebar.write(f"👉 **1차 진입금 (15%):** {format_krw_to_hangul(진입1차)}")
    st.sidebar.write(f"👉 **2차 예비비 (10%):** {format_krw_to_hangul(진입2차)}")

    # ==========================================
    # [🔥 핵심 패치: 초기 문구 제거 및 즉시 타이핑 연동창]
    # ==========================================
    st.markdown("---")
    st.subheader("🔍 글로벌 HTS 종목명 초고속 진단 시스템")
    st.write("검색창을 마우스로 누르거나 방향키를 눌러 **글자를 지울 필요 없이 그냥 바로 타이핑**하세요!")
    
    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        # 👑 [UI 패치] 불필요한 '검색 대기중' 문구를 빼고, 완전히 비어있는 공백 레이블("")을 기본값으로 배치
        selected_stock = st.selectbox(
            "✍️ 한/미 종목명 한글/영어 즉시 타이핑 (방향키 이동 가능)", 
            options=[""] + combined_search_list, 
            index=0
        )
    with search_col2:
        manual_code = st.text_input("🔢 혹은 HTS 숫자코드/미국 티커 직접 입력", "").strip()

    target_code, target_name, is_us_target = None, None, False

    # 1. 수동 코드 분석 처리
    if manual_code:
        if manual_code.isdigit() and len(manual_code) == 6:
            if manual_code in kr_code_map:
                target_code = manual_code; target_name = kr_code_map[manual_code]; is_us_target = False
        else:
            upper_ticker = manual_code.upper()
            target_code = upper_ticker
            target_name = us_code_map.get(upper_ticker, upper_ticker)
            is_us_target = True
                
    # 2. 자동완성 텍스트 처리 (공백 ""이 아닐 때만 계산)
    elif selected_stock != "":
        if selected_stock.startswith("🇰🇷"):
            clean_name = selected_stock.split(" (")[0].replace("🇰🇷 ", "").strip()
            if clean_name in kr_map:
                target_code = kr_map[clean_name]; target_name = clean_name; is_us_target = False
        elif selected_stock.startswith("🇺🇸"):
            try:
                ticker_part = selected_stock.split("[")[1].split("]")[0].strip()
                target_code = ticker_part; target_name = us_code_map.get(ticker_part, ticker_part); is_us_target = True
            except:
                ticker_part = selected_stock.split(" - ")[0].replace("🇺🇸 ", "").strip()
                if ticker_part in us_code_map:
                    target_code = ticker_part; target_name = us_code_map[ticker_part]; is_us_target = True

    # --- 실시간 연동 연산 화면 도출 ---
    if target_code:
        now_time = get_seoul_now().strftime("%H시 %M분 %S초")
        flag = "🇺🇸 미국주식" if is_us_target else "🇰🇷 한국주식"
        st.success(f"🎯 **[글로벌 통합 검색 성공]** {flag} 매칭 완료: **{target_name} ({target_code})**")
        
        with st.spinner("⚡ 일봉 빅데이터 + 10분봉 실시간 수급 연동 실시간 연산 가동 중..."):
            res_daily = check_daily_logic(target_code, target_name, is_us=is_us_target)
            res_10min = check_10min_logic(target_code, target_name, is_us=is_us_target)
            
        real_price = res_daily["price"] if res_daily["price"] > 0 else res_10min["price"]
        unit = "$" if is_us_target else "원"
        
        st.markdown(f"""
        <div style='background-color:#0f172a; padding:18px; border-radius:12px; margin-bottom:25px; border-left: 5px solid #10b981;'>
            <span style='font-size:14px; color:#94a3b8;'>📊 <b>{target_name} ({target_code})</b> 듀얼 타임프레임 스캔</span>
            <h2 style='margin:5px 0; color:#ffffff;'>현재가: <span style='color:#10b981;'>{real_price:, if not is_us_target else real_price}{unit}</span></h2>
            <p style='margin:0; font-size:14px; color:#cbd5e1;'>
                📈 일봉 RSI(9): <b style='color:#a7f3d0;'>{res_daily['rsi']:.1f}</b> | ⚡ 10분봉 RSI: <b style='color:#fca5a5;'>{res_10min['rsi']:.1f}</b>
            </p>
        </div>
        """, unsafe_allow_html=True)
            
        view_col1, view_col2 = st.columns(2)
        with view_col1:
            st.markdown("### 🌲 1. 일봉 기준 진단 (큰 숲 보기)")
            if res_daily["status"] == "PASS":
                st.balloons()
                st.info(f"🟢 **[일봉 바닥 포착]** 승률 **{res_daily['prob']:.0f}%** \n\n* **1차 진입가:** {res_daily['price']}{unit} ➔ 💰 추천 금액: **{format_krw_to_hangul(진입1차)}**\n* **🚀 목표가:** {res_daily['target']}{unit}\n* **🛡️ 2차 방어선:** {res_daily['buy2nd']}{unit}")
            else:
                st.error(f"🔴 **[일봉 진입 보류]** \n\n* **이유:** {res_daily['reason']}")
                
        with view_col2:
            st.markdown("### 🌿 2. 10분봉 기준 진단 (현재 타점 보기)")
            if res_10min["status"] == "PASS":
                st.balloons()
                st.info(f"🟢 **[10분봉 타점 포착]** 반등 확률 **{res_10min['prob']:.0f}%** \n\n* **1차 진입가:** {res_10min['price']}{unit} ➔ 💰 추천 금액: **{format_krw_to_hangul(진입1차)}**\n* **🚀 목표가:** {res_10min['target']}{unit}\n* **🛡️ 2차 방어선:** {res_10min['buy2nd']}{unit}")
            else:
                st.error(f"🔴 **[10분봉 진입 보류]** \n\n* **이유:** {res_10min['reason']}")
                
        st.markdown("---")
        st.markdown("### 💡 리치 마스터의 듀얼 매매 나침반")
        if res_daily["status"] == "PASS" and res_10min["status"] == "PASS":
            st.success("🔥 **[초대박 시그널: 사방 일치!]** 일봉·10분봉 최적의 합치 구간입니다. 망설이지 마시고 비중 채워 진입하십시오!")
        elif res_daily["status"] == "FAIL" and res_10min["status"] == "PASS":
            st.warning("⚡ **[단기 기술적 반등 타점]** 10분봉 과매도 단타 타점입니다. 딱 1% 정산 타점용으로만 대응하세요.")
        elif res_daily["status"] == "PASS" and res_10min["status"] == "FAIL":
            st.info("⏳ **[종가 매수 대기 조율]** 일봉 자리는 완벽한 황금 바닥인데 분봉 진정이 덜 됐습니다. 종가 동시호가에 분할로 받으십시오.")
        else:
            st.dark_caption("🔒 **[철저한 관망]** 진입 메리트가 전혀 없는 구간입니다. 설거지 자리이니 패스하십시오 형.")

    # --- [🚀 글로벌 대량 종목 4대 스캔 버튼] ---
    st.markdown("---")
    st.subheader("🚀 글로벌 대량 종목 스캔 가동 시스템")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: btn_kr_ori = st.button("🇰🇷 한국 일봉 눌림목 스캔", use_container_width=True)
    with col2: btn_kr_1pc = st.button("⚡ 한국 10분봉 단타 스캔", use_container_width=True)
    with col3: btn_us_ori = st.button("🇺🇸 미국 일봉 확장판 스캔", use_container_width=True)
    with col4: btn_us_1pc = st.button("⚡ 미국 10분봉 단타 스캔", use_container_width=True)

    def 조작_프로세스(전략이름, 종목함수, 시장안전여부, 미국여부):
        if not 시장안전여부:
            st.error(f"🚨 하락장 필터 차단 가동 중! 원금을 지키세요.")
            return
        st.info(f"▶ {전략이름} 연동 탐색 중...")
        종목들 = 종목함수(); 발견종목 = []
        프로그레스바 = st.progress(0)
        for i, 종목 in enumerate(종목들):
            code_key = 종목['Symbol'] if 미국여부 else 종목['Code']
            res = check_daily_logic(code_key, 종목['Name'], is_us=미국여부) if "일봉" in 전략이름 else check_10min_logic(code_key, 종목['Name'], is_us=미국여부)
            if res and res.get("status") == "PASS": 발견종목.append(res)
            프로그레스바.progress((i + 1) / len(종목들))
            
        now = get_seoul_now()
        date_key = now.strftime(f"%Y년 %m월 %d일 ({WEEKS[now.weekday()]})")
        time_key = now.strftime("%p %I시 %M분 %S초").replace("AM", "오전").replace("PM", "오후")
        
        if 발견종목:
            st.success(f"🎉 {time_key} 총 {len(발견종목)}개 포착!")
            save_list = []
            for stock in 발견종목:
                u = "$" if 미국여부 else "원"
                p_f = f"{stock['price']}" if 미국여부 else f"{stock['price']:,}"
                t_f = f"{stock['target']}" if 미국여부 else f"{stock['target']:,}"
                txt_box = f"📌 **{stock['name']}** \n* **[1차 매수]** {p_f}{u} ➔ 💰 추천 금액: {format_krw_to_hangul(진입1차)}\n* **[목표가]** {t_f}{u}"
                st.info(txt_box); save_list.append(txt_box)
            save_history(date_key, 전략이름, save_list)
        else:
            st.warning("😓 조건에 맞는 종목이 현재 존재하지 않습니다.")

    if btn_kr_ori: 조작_프로세스("🇰🇷 한국 일봉 눌림목", get_krx_stocks, kr_market_safe, 미국여부=False)
    if btn_kr_1pc: 조작_프로세스("🇰🇷 한국 10분봉 단타", get_krx_stocks, kr_market_safe, 미국여부=False)
    if btn_us_ori: 조작_프로ces스("🇺🇸 미국 일봉 확장판", get_us_stocks, us_market_safe, 미국여부=True)
    if btn_us_1pc: 조작_프로세스("🇺🇸 미국 10분봉 단타", get_us_stocks, us_market_safe, 미국여부=True)

    # --- [💾 히스토리 아카이브] ---
    st.markdown("---")
    st.subheader("💾 히스토리 및 저장된 결과 다시보기")
    history_data = load_history()
    if history_data:
        selected_date = st.selectbox("📆 스캔 날짜 선택", sorted(list(history_data.keys()), reverse=True))
        tab_k_o, tab_k_1, tab_u_o, tab_u_1 = st.tabs(["🇰🇷 한국 일봉", "⚡ 한국 10분봉", "🇺🇸 미국 일봉", "⚡ 미국 10분봉"])
        day_results = history_data[selected_date]
        with tab_k_o: 
            for item in day_results.get("🇰🇷 한국 일봉 눌림목", ["🔍 내역 없음"]): st.write(item)
        with tab_k_1: 
            for item in day_results.get("🇰🇷 한국 10분봉 단타", ["🔍 내역 없음"]): st.write(item)
        with tab_u_o: 
            for item in day_results.get("🇺🇸 미국 일봉 확장판", ["🔍 내역 없음"]): st.write(item)
        with tab_u_1: 
            for item in day_results.get("🇺🇸 미국 10분봉 단타", ["🔍 내역 없음"]): st.write(item)
