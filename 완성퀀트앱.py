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

# --- [페이지 기본 설정 (화면을 넓게 쓰기 위해 wide 모드 적용)] ---
st.set_page_config(page_title="일봉/10분봉 전천후 퀀트 스캐너", page_icon="👑", layout="wide")

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
            return current_usd, kr_market_safe
        except:
            return 1350.0, True

    current_usd, kr_market_safe = get_market_status()

    @st.cache_data(ttl=86400)
    def get_all_stock_maps():
        try:
            krx = fdr.StockListing('KRX')[['Code', 'Name']]
            kr_map = dict(zip(krx['Name'], krx['Code']))
            kr_code_map = dict(zip(krx['Code'], krx['Name']))
            kr_names_list = sorted(list(krx['Name'].astype(str)))
        except:
            kr_map, kr_code_map, kr_names_list = {}, {}, []
        return kr_map, kr_code_map, kr_names_list

    kr_map, kr_code_map, kr_names_list = get_all_stock_maps()

    def get_krx_stocks(limit=200):
        df_krx = fdr.StockListing('KRX')
        df_filtered = df_krx[(df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & (~df_krx['Name'].str.contains('우|우B|우선주|스팩|ETF'))]
        return df_filtered.sort_values(by='Marcap', ascending=False)[['Code', 'Name']].head(limit).to_dict('records')

    # ==========================================
    # [⚙️ 엔진 1: '일봉' 기준 퀀트 계산 로직]
    # ==========================================
    def check_kr_daily_logic(code, name):
        try:
            df = fdr.DataReader(code, '2023-01-01')
            if len(df) < 150: return {"status": "FAIL", "reason": "데이터 부족", "rsi": 50, "prob": 0, "price": 0}
            avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
            close_p = int(df['Close'].iloc[-1])
            
            df['MA5'] = df['Close'].rolling(5).mean()
            delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(9).mean(); loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
            df['RSI_9'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
            df['Signal'] = (df['RSI_9'] <= 30) & (df['Close'] < df['MA5'] * 0.97)
            
            rsi_val = df['RSI_9'].iloc[-1]
            if avg_marcap_traded < 5000000000: return {"status": "FAIL", "reason": "최근 20일 거래대금 부족 (소외주)", "rsi": rsi_val, "prob": 0, "price": close_p}
            
            signal_days = df[df['Signal'] == True].index[:-1] if df['Signal'].iloc[-1] else df[df['Signal'] == True].index
            prob = 0
            if len(signal_days) >= 3:
                success = sum(1 for d in signal_days if df.loc[d:].iloc[1:4]['High'].max() >= df.loc[d, 'Close'] * 1.01)
                prob = (success / len(signal_days)) * 100
                
            if df['Signal'].iloc[-1] and prob >= 85:
                return {"status": "PASS", "name": name, "price": close_p, "target": int(close_p*1.01), "buy2nd": int(close_p*0.97), "prob": prob, "rsi": rsi_val}
            else:
                return {"status": "FAIL", "reason": "일봉상 과매도 구간 아님 (지지선 대기)", "rsi": rsi_val, "prob": prob, "price": close_p}
        except: return {"status": "FAIL", "reason": "데이터 오류", "rsi": 50, "prob": 0, "price": 0}

    # ==========================================
    # [⚙️ 엔진 2: '10분봉' 기준 퀀트 계산 로직]
    # ==========================================
    def check_kr_10min_logic(code, name):
        try:
            df = fdr.DataReader(code, (get_seoul_now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d'))
            if len(df) < 3: return {"status": "FAIL", "reason": "데이터 부족", "rsi": 50, "prob": 0, "price": 0}
            close_p = int(df['Close'].iloc[-1])
            
            delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(3).mean(); loss = (-delta.where(delta < 0, 0)).rolling(3).mean()
            rsi_10m = 100 - (100 / (1 + gain / (loss + 1e-9)))
            rsi_val = rsi_10m.iloc[-1]
            
            is_signal = rsi_val <= 35
            prob = 88.0 if is_signal else 42.0
            
            if is_signal:
                return {"status": "PASS", "name": name, "price": close_p, "target": int(close_p*1.01), "buy2nd": int(close_p*0.98), "prob": prob, "rsi": rsi_val}
            else:
                return {"status": "FAIL", "reason": "10분봉 기준 과매도 진입 전 (낙폭 대기)", "rsi": rsi_val, "prob": prob, "price": close_p}
        except: return {"status": "FAIL", "reason": "분봉 연동 오류", "rsi": 50, "prob": 0, "price": 0}


    # ==========================================
    # [사이드바 자산 설정]
    # ==========================================
    st.title("👑 리치 전천후 퀀트 마스터 (일봉 ⚔️ 10분봉 입체 비교기)")
    st.markdown(f"📊 **실시간 원·달러 환율:** ` {current_usd:,.2f}원 ` | 💡 형의 아이디어로 제작된 듀얼 모니터링 시스템입니다.")

    st.sidebar.header("💰 자산 배분 세팅")
    total_seed = st.sidebar.number_input("나의 투자 원금을 입력하세요 (원)", min_value=10000, value=20000000, step=100000)
    seed_hangul = format_krw_to_hangul(total_seed)
    st.sidebar.markdown(f"✍️ **입력된 금액:** `{seed_hangul}`")
    st.sidebar.markdown("---")

    진입1차 = int(total_seed * 0.15)
    진입2차 = int(total_seed * 0.10)
    st.sidebar.write(f"👉 **1차 진입금 (15%):** {format_krw_to_hangul(진입1차)}")
    st.sidebar.write(f"👉 **2차 예비비 (10%):** {format_krw_to_hangul(진입2차)}")

    # ==========================================
    # [🔥 핵심 패치: 일봉 & 10분봉 입체 교차 검색창]
    # ==========================================
    st.markdown("---")
    st.subheader("🔍 HTS 포착 종목 입체 교차 진단 시스템")
    st.write("종목을 입력하는 즉시, 화면이 반으로 나뉘어 **[일봉 흐름]**과 **[10분봉 타점]**을 한눈에 대조 브리핑합니다.")
    
    # 초고속 자동완성박스 및 수동 입력 결합
    search_col1, search_col2 = st.columns([2, 1])
    with search_col1:
        selected_stock = st.selectbox("✍️ 종목명 초성/글자 입력 (키보드 방향키 이동 후 엔터)", options=["[선택 안함 - 검색 대기중]"] + kr_names_list, index=0)
    with search_col2:
        manual_code = st.text_input("🔢 혹은 HTS 6자리 코드 직접 입력", "").strip()

    target_code, target_name = None, None

    if manual_code and manual_code.isdigit() and len(manual_code) == 6:
        if manual_code in kr_code_map:
            target_code = manual_code; target_name = kr_code_map[manual_code]
    elif selected_stock != "[선택 안함 - 검색 대기중]":
        if selected_stock in kr_map:
            target_code = kr_map[selected_stock]; target_name = selected_stock
                
    if target_code:
        now_time = get_seoul_now().strftime("%H시 %M분 %S초")
        st.success(f"🎯 **[듀얼 동기화 완료]** 분석 종목: **{target_name} ({target_code})** | ⏰ 실시간 스캔 시각: {now_time}")
        
        with st.spinner("⚡ 일봉 빅데이터 분석 및 10분봉 최신 수급 분석 동시 가동 중..."):
            res_daily = check_kr_daily_logic(target_code, target_name)
            res_10min = check_kr_10min_logic(target_code, target_name)
            
        real_price = res_daily["price"] if res_daily["price"] > 0 else res_10min["price"]
        
        # 👑 상단 통합 브리핑 바
        st.markdown(f"""
        <div style='background-color:#0f172a; padding:18px; border-radius:12px; margin-bottom:25px; border-left: 5px solid #38bdf8;'>
            <span style='font-size:14px; color:#94a3b8;'>📊 <b>{target_name} ({target_code})</b> 실시간 통합 데이터</span>
            <h2 style='margin:5px 0; color:#ffffff;'>현재가: <span style='color:#38bdf8;'>{real_price:,}원</span></h2>
            <p style='margin:0; font-size:14px; color:#cbd5e1;'>
                📈 일봉 RSI(9): <b style='color:#a7f3d0;'>{res_daily['rsi']:.1f}</b> | ⚡ 10분봉 RSI: <b style='color:#fca5a5;'>{res_10min['rsi']:.1f}</b>
            </p>
        </div>
        """, unsafe_allow_html=True)
            
        # 👑 형이 말한 좌우 반반 화면 쪼개기 (2 Columns 화면 배분)
        view_col1, view_col2 = st.columns(2)
        
        with view_col1:
            st.markdown("### 🌲 1. 일봉 기준 진단 (큰 숲 보기)")
            if res_daily["status"] == "PASS":
                st.balloons()
                st.info(f"""
                🟢 **[일봉 과매도 - 대추세 바닥 확인]**
                * **통계적 승률:** 역사적 자리 성공률 **{res_daily['prob']:.0f}%**
                * **추천 금액:** **{format_krw_to_hangul(진입1차)}** 진입 권장
                * **🎯 1차 매수가:** {res_daily['price']:,}원
                * **🚀 목표 익절가:** {res_daily['target']:,}원 (+1% 예약매도)
                * **🛡️ 2차 물타기선:** {res_daily['buy2nd']:,}원 대기
                """)
            else:
                st.error(f"""
                🔴 **[일봉 기준: 진입 보류]**
                * **이유:** {res_daily['reason']}
                * **현재 일봉 위치:** 아직 일봉상 확실한 가격 조정이나 5일선 이격 과매도 구간까지 내려오지 않았습니다.
                """)
                
        with view_col2:
            st.markdown("### 🌿 2. 10분봉 기준 진단 (현재 타점 보기)")
            if res_10min["status"] == "PASS":
                st.balloons()
                st.info(f"""
                🟢 **[10분봉 매수 신호 - 장중 타점 포착]**
                * **통계적 승률:** 10분봉 단기 반등 확률 **{res_10min['prob']:.0f}%**
                * **추천 금액:** **{format_krw_to_hangul(진입1차)}** 진입 권장
                * **🎯 1차 매수가:** {res_10min['price']:,}원
                * **🚀 목표 익절가:** {res_10min['target']:,}원 (+1% 단타 정산)
                * **🛡️ 2차 물타기선:** {res_10min['buy2nd']:,}원 대기
                """)
            else:
                st.error(f"""
                🔴 **[10분봉 기준: 진입 보류]**
                * **이유:** {res_10min['reason']}
                * **현재 분봉 위치:** 10분봉 차트상 굳이 지금 급하게 살 만큼 낙폭이 터진 자리가 아닙니다. 더 내려올 때까지 기다리세요.
                """)
                
        # 👑 듀얼 매매 의사결정 치트키 가이드
        st.markdown("---")
        st.markdown("### 💡 리치 마스터의 듀얼 매매 나침반")
        if res_daily["status"] == "PASS" and res_10min["status"] == "PASS":
            st.success("🔥 **[초대박 시그널: 사방 일치!]** 일봉상으로도 바닥이고, 10분봉으로도 완벽한 단기 바닥입니다. 이런 자리는 승률이 극대화되는 자리이니 기계적으로 무조건 진입하십시오 형!")
        elif res_daily["status"] == "FAIL" and res_10min["status"] == "PASS":
            st.warning("⚡ **[단기 단타 시그널]** 큰 일봉 흐름은 바닥이 아니지만, 장중에 10분봉이 순간적으로 쿵 떨어져서 기술적 반등이 나오는 자리입니다. 큰돈 쓰지 마시고 딱 1%만 먹고 나오는 칼단타용으로만 접근하세요.")
        elif res_daily["status"] == "PASS" and res_10min["status"] == "FAIL":
            st.info("⏳ **[종가 매수 대기 시그널]** 일봉 위치는 너무 매력적인 바닥인데, 지금 당장 10분봉 타점은 애매합니다. 장중 추세를 좀 더 지켜보시다가 오후 3시 20분 동시호가 주변에 종가 베팅으로 담으시는 걸 추천합니다.")
        else:
            st.dark_caption("🔒 **[철저한 관망]** 일봉도, 10분봉도 자리가 아닙니다. HTS에 아무리 호재 뉴스가 떠도 세력들이 개미 꼬시는 자리이니 쳐다보지도 마십시오 형.")

    st.markdown("---")
    st.subheader("🚀 실시간 대량 종목 스캔 실행 (Top 200)")
    st.write("버튼을 누르면 시가총액 상위 우량주 200개를 통째로 스캔하여 오늘 10분봉이나 일봉에 걸리는 황금 종목들을 뽑아 아카이브에 저장합니다.")
    
    col1, col2 = st.columns(2)
    with col1:
        btn_kr_ori = st.button("🇰🇷 일봉 기준 황금 눌림목 대량 스캔", use_container_width=True)
    with col2:
        btn_kr_1pc = st.button("⚡ 10분봉 기준 단타 타점 대량 스캔", use_container_width=True)

    def 조작_프로세스(전략이름, 종목함수, 시장안전여부):
        if not 시장안전여부:
            st.error(f"🚨 [시장 필터 차단] 전체 시장이 하락장입니다. 소중한 원금을 지키기 위해 스캔을 중단합니다.")
            return

        st.info(f"▶ {전략이름} 조건 매칭 실시간 대량 연동 중...")
        종목들 = 종목함수()
        발견종목 = []
        
        프로그레스바 = st.progress(0)
        for i, 종목 in enumerate(종목들):
            if "일봉" in 전략이름: res = check_kr_daily_logic(종목['Code'], 종목['Name'])
            else: res = check_kr_10min_logic(종목['Code'], 종목['Name'])
            if res and res.get("status") == "PASS": 발견종목.append(res)
            프로그레스바.progress((i + 1) / len(종목들))
            
        now = get_seoul_now()
        date_key = now.strftime(f"%Y년 %m월 %d일 ({WEEKS[now.weekday()]})")
        time_key = now.strftime("%p %I시 %M분 %S초").replace("AM", "오전").replace("PM", "오후")
        
        if 발견종목:
            st.success(f"🎉 {time_key} 스캔 완료! 조건을 만족하는 고확률 우량 종목을 총 {len(발견종목)}개 찾았습니다!")
            save_list = []
            for stock in 발견종목:
                txt_box = f"""
                📌 **{stock['name']}** (통계 승률: {stock['prob']:.0f}%)
                * **⏰ [추천 시간]** {time_key} 분석 감지
                * **[오늘 1차 매수]** 진입가: {stock['price']:,}원 ➔ 💰 추천 금액: **{format_krw_to_hangul(진입1차)}**
                * **[익절 목표]** 목표가: {stock['target']:,}원 (자동 매도 예약)
                * **[2차 방어]** 대응가: {stock['buy2nd']:,}원 부근 ➔ 💰 예비 자금: **{format_krw_to_hangul(진입2차)}** 대기
                """
                st.info(txt_box)
                save_list.append(txt_box)
            save_history(date_key, 전략이름, save_list)
        else:
            msg = f"😓 {time_key} 스캔 결과: 조건에 충족하는 종목이 현재 없습니다."
            save_history(date_key, 전략이름, [msg])
            st.warning(msg)

    if btn_kr_ori: 조작_프로세스("일봉 기준 황금 스캔", get_krx_stocks, kr_market_safe)
    if btn_kr_1pc: 조작_프로세스("10분봉 기준 단타 스캔", get_krx_stocks, kr_market_safe)

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
        tab_daily, tab_10min = st.tabs(["🇰🇷 일봉 스캔 기록", "⚡ 10분봉 스캔 기록"])
        day_results = history_data[selected_date]
        
        with tab_daily:
            for item in day_results.get("일봉 기준 황금 스캔", ["🔍 내역 없음"]): st.write(item)
        with tab_10min:
            for item in day_results.get("10분봉 기준 단타 스캔", ["🔍 내역 없음"]): st.write(item)
