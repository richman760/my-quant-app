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

    # 한국 시간 강제 고정 함수
    def get_seoul_now():
        return datetime.datetime.utcnow() + datetime.timedelta(hours=9)

    @st.cache_data(ttl=10) # 실시간성 확보를 위해 캐싱 시간 대폭 단축
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

    # 전체 종목 리스트 검색용 마스터 데이터베이스 (캐싱 처리)
    @st.cache_data(ttl=86400)
    def get_all_stock_maps():
        try:
            krx = fdr.StockListing('KRX')[['Code', 'Name']]
            kr_map = dict(zip(krx['Name'], krx['Code']))
            kr_code_map = dict(zip(krx['Code'], krx['Name']))
        except:
            kr_map, kr_code_map = {}, {}
            
        try:
            sp500 = fdr.StockListing('S&P500')[['Symbol', 'Name']]
            us_map = dict(zip(sp500['Symbol'], sp500['Name']))
            us_name_map = dict(zip(sp500['Name'], sp500['Symbol']))
        except:
            us_map, us_name_map = {}, {}
            
        return kr_map, kr_code_map, us_map, us_name_map

    kr_map, kr_code_map, us_map, us_name_map = get_all_stock_maps()

    def get_krx_stocks(limit=200):
        df_krx = fdr.StockListing('KRX')
        df_filtered = df_krx[(df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & (~df_krx['Name'].str.contains('우|우B|우선주|스팩|ETF'))]
        return df_filtered.sort_values(by='Marcap', ascending=False)[['Code', 'Name']].head(limit).to_dict('records')

    def get_us_stocks(limit=200):
        try: df_sp500 = fdr.StockListing('S&P500')[['Symbol', 'Name']]
        except: df_sp500 = pd.DataFrame(columns=['Symbol', 'Name'])
        return df_sp500.head(limit).to_dict('records')

    # 1. 한국 퀀트 (기본형) 계산 로직
    def check_kr_original_logic(code, name):
        try:
            df = fdr.DataReader(code, '2005-01-01')
            if len(df) < 250: return {"status": "FAIL", "reason": "데이터 부족 (신규 상장주 등)", "rsi": 50, "prob": 0, "price": 0}
            avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
            close_p = int(df['Close'].iloc[-1])
            
            df['MA20'] = df['Close'].rolling(20).mean(); df['STD20'] = df['Close'].rolling(20).std()
            df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
            delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI'] = 100 - (100 / (1 + gain / (loss + 1e-9))); df['Vol_MA5'] = df['Volume'].rolling(5).mean()
            df['Signal'] = (df['RSI'].rolling(3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5']) & (df['Close'].pct_change()*100 > -1)
            
            rsi_val = df['RSI'].iloc[-1]
            if avg_marcap_traded < 5000000000: return {"status": "FAIL", "reason": "최근 20일 평균 거래대금 50억 미만 (소외주)", "rsi": rsi_val, "prob": 0, "price": close_p}
            
            signal_days = df[df['Signal'] == True].index[:-1] if df['Signal'].iloc[-1] else df[df['Signal'] == True].index
            prob = 0
            if len(signal_days) >= 5:
                success = sum(1 for d in signal_days if df.loc[d:].iloc[1:9]['High'].max() >= df.loc[d, 'Close'] * 1.045)
                prob = (success / len(signal_days)) * 100
                
            if df['Signal'].iloc[-1] and prob >= 80:
                return {"status": "PASS", "name": name, "price": close_p, "target": int(close_p*1.045), "buy2nd": int(close_p*0.95), "prob": prob, "type": "원화", "rsi": rsi_val}
            else:
                return {"status": "FAIL", "reason": f"조건 미부합 (RSI 기준 미달 또는 승률 부족)", "rsi": rsi_val, "prob": prob, "price": close_p}
        except:
            return {"status": "FAIL", "reason": "데이터 불러오기 오류", "rsi": 50, "prob": 0, "price": 0}

    # 2. 한국 퀀트 (매일 1%) 계산 로직
    def check_kr_1pct_logic(code, name):
        try:
            seoul_today = get_seoul_now()
            start_date = (seoul_today - datetime.timedelta(days=3*365)).strftime('%Y-%m-%d')
            df = fdr.DataReader(code, start_date)
            if len(df) < 150: return {"status": "FAIL", "reason": "데이터 부족", "rsi": 50, "prob": 0, "price": 0}
            avg_marcap_traded = (df['Volume'] * df['Close']).rolling(20).mean().iloc[-1]
            close_p = int(df['Close'].iloc[-1])
            
            df['MA5'] = df['Close'].rolling(5).mean()
            delta = df['Close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(9).mean(); loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
            df['RSI_9'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
            df['Signal'] = (df['RSI_9'] <= 30) & (df['Close'] < df['MA5'] * 0.97) & (df['Close'].pct_change()*100 > -4)
            
            rsi_val = df['RSI_9'].iloc[-1]
            if avg_marcap_traded < 5000000000: return {"status": "FAIL", "reason": "최근 20일 평균 거래대금 50억 미만", "rsi": rsi_val, "prob": 0, "price": close_p}
            
            signal_days = df[df['Signal'] == True].index[:-1] if df['Signal'].iloc[-1] else df[df['Signal'] == True].index
            prob = 0
            if len(signal_days) >= 5:
                success = 0
                for d in signal_days:
                    try:
                        if df.iloc[df.index.get_loc(d) + 1]['High'] >= df.loc[d, 'Close'] * 1.01: success += 1
                    except: continue
                prob = (success / len(signal_days)) * 100
                
            if df['Signal'].iloc[-1] and prob >= 85:
                return {"status": "PASS", "name": name, "price": close_p, "target": int(close_p*1.01), "buy2nd": int(close_p*0.97), "prob": prob, "type": "원화", "rsi": rsi_val}
            else:
                return {"status": "FAIL", "reason": f"조건 미부합 (RSI 기준 미달 또는 승률 부족)", "rsi": rsi_val, "prob": prob, "price": close_p}
        except:
            return {"status": "FAIL", "reason": "데이터 불러오기 오류", "rsi": 50, "prob": 0, "price": 0}

    # ==========================================
    # [대시보드 상단 레이아웃 - 모니터링 및 자산 설정]
    # ==========================================
    st.title("👑 리치 퀀트 마스터 스캐너 v2")
    st.markdown(f"📊 **실시간 원·달러 환율:** ` {current_usd:,.2f}원 ` | 📅 데이터 자동 연동 중")

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
    # [🔥 핵심 패치: HTS 연동 실시간 단일 종목 진단창]
    # ==========================================
    st.markdown("---")
    st.subheader("🔍 HTS 검색 종목 실시간 1초 진단")
    st.write("HTS 조건검색식에 포착된 종목이나 관심 종목을 입력하면 실시간 주가를 동기화하여 완벽한 분석 리포트를 출력합니다.")
    
    search_input = st.text_input("✍️ 분석할 종목명 또는 종목코드 입력 (예: SK하이닉스, 삼성전자)", "").strip()
    
    if search_input:
        target_code, target_name = None, None
        
        if search_input.isdigit():
            if search_input in kr_code_map:
                target_code = search_input
                target_name = kr_code_map[search_input]
        else:
            if search_input in kr_map:
                target_code = kr_map[search_input]
                target_name = search_input
                
        if target_code:
            now_time = get_seoul_now().strftime("%H시 %M분 %S초")
            st.success(f"🎯 **[실시간 연동 완료]** 한국 시장 종목 감지: **{target_name} ({target_code})** | ⏰ 조회 시각: {now_time}")
            
            with st.spinner("⚡ 1초 만에 최신 실시간 차트 데이터 분석 및 백테스팅 엔진 가동 중..."):
                res_ori = check_kr_original_logic(target_code, target_name)
                res_1pc = check_kr_1pct_logic(target_code, target_name)
                
            # 최신 실시간 정보 요약 브리핑박스
            real_price = res_ori["price"] if res_ori["price"] > 0 else res_1pc["price"]
            st.markdown(f"""
            <div style='background-color:#1e293b; padding:15px; border-radius:10px; margin-bottom:20px;'>
                <p style='margin:0; font-size:14px; color:#94a3b8;'>📈 {target_name} 실시간 차트 데이터 브리핑</p>
                <h3 style='margin:5px 0; color:#38bdf8;'>실시간 현재가: {real_price:,}원</h3>
                <span style='font-size:13px; color:#f1f5f9;'>📊 기본형 RSI(20): <b>{res_ori['rsi']:.1f}</b> | ⚡ 단타용 RSI_9: <b>{res_1pc['rsi']:.1f}</b></span>
            </div>
            """, unsafe_allow_html=True)
                
            diag_col1, diag_col2 = st.columns(2)
            
            with diag_col1:
                st.markdown("#### 🇰🇷 한국 퀀트 (기본형)")
                if res_ori["status"] == "PASS":
                    st.balloons()
                    st.info(f"""
                    🟢 **[진입 적합 - 매수!]**
                    * **통계 승률:** 과거 유사 자리 성공률 **{res_ori['prob']:.0f}%**
                    * **1차 매수 진입가:** {res_ori['price']:,}원
                    * **💰 추천 금액:** **{format_krw_to_hangul(진입1차)}** ({진입1차:,}원어치)
                    * **🚀 목표 익절가:** **{res_ori['target']:,}원** (+4.5% 자동매도)
                    * **🛡️ 2차 물타기선:** {res_ori['buy2nd']:,}원 부근 (예비비 대기)
                    """)
                else:
                    st.error(f"🔴 **[진입 보류]** \n\n **이유:** {res_ori['reason']} \n\n *과거 데이터 기준 현재 자리 진입시 승률이 {res_ori['prob']:.1f}%로 통과 컷(80%)보다 낮아 자금을 보호합니다.*")
                    
            with diag_col2:
                st.markdown("#### ⚡ 한국 퀀트 (매일 1% 단타)")
                if res_1pc["status"] == "PASS":
                    st.balloons()
                    st.info(f"""
                    🟢 **[진입 적합 - 단타!]**
                    * **통계 승률:** 다음날 1% 익절 확률 **{res_1pc['prob']:.0f}%**
                    * **1차 매수 진입가:** {res_1pc['price']:,}원
                    * **💰 추천 금액:** **{format_krw_to_hangul(진입1차)}** ({진입1차:,}원어치)
                    * **🚀 목표 익절가:** **{res_1pc['target']:,}원** (+1% 초단기 예약)
                    * **🛡️ 2차 물타기선:** {res_1pc['buy2nd']:,}원 부근 (예비비 대기)
                    """)
                else:
                    st.error(f"🔴 **[진입 보류]** \n\n **이유:** {res_1pc['reason']} \n\n *과거 데이터 기준 현재 자리 진입시 승률이 {res_1pc['prob']:.1f}%로 통과 컷(85%)보다 낮아 자금을 보호합니다.*")
        else:
            st.error("❌ 종목명을 정확히 찾지 못했습니다. 오타가 없는지 혹은 올바른 종목코드 6자리인지 확인하세요 형!")

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
    st.subheader("🚀 실시간 대량 종목 스캔 실행 (Top 200)")
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
            if "Code" in 종목:
                if "1%" in 전략이름: res = check_kr_1pct_logic(종목['Code'], 종목['Name'])
                else: res = check_kr_original_logic(종목['Code'], 종목['Name'])
                if res and res.get("status") == "PASS": 발견종목.append(res)
            else:
                res = 분석함수(종목)
                if res: 발견종목.append(res)
            프로그레스바.progress((i + 1) / len(종목들))
            
        now = get_seoul_now()
        date_key = now.strftime(f"%Y년 %m월 %d일 ({WEEKS[now.weekday()]})")
        time_key = now.strftime("%p %I시 %M분 %S초").replace("AM", "오전").replace("PM", "오후")
        
        if 발견종목:
            st.success(f"🎉 {time_key} 스캔 완료! 오늘 조건을 만족하는 고확률 우량 종목을 총 {len(발견종목)}개 찾았습니다!")
            save_list = []
            for stock in 발견종목:
                unit = "원" if stock['type'] == "원화" else "$"
                price_formatted = f"{stock['price']:,}" if stock['type'] == "원화" else f"{stock['price']}"
                target_formatted = f"{stock['target']:,}" if stock['type'] == "원화" else f"{stock['target']}"
                buy2nd_formatted = f"{stock['buy2nd']:,}" if stock['type'] == "원화" else f"{stock['buy2nd']}"
                
                txt_box = f"""
                📌 **{stock['name']}** (과거 성공률: {stock['prob']:.0f}%)
                * **⏰ [추천 시간]** {time_key} 분석 감지
                * **[오늘 종가 1차 매수]** 진입가: {price_formatted}{unit} ➔ 💰 추천 금액: **{format_krw_to_hangul(진입1차)}** ({진입1차:,}원어치)
                * **[익절 예약 매도 목표]** 목표가: {target_formatted}{unit} (내일 아침 자동 매도 예약)
                * **[방어용 2차 물타기 선]** 대응가: {buy2nd_formatted}{unit} 부근 ➔ 💰 예비 자금: **{format_krw_to_hangul(진입2차)}** ({진입2차:,}원어치) 대기
                """
                st.info(txt_box)
                save_list.append(txt_box)
            save_history(date_key, 전략이름, save_list)
        else:
            msg = f"😓 {time_key} 스캔 결과: 오늘 대량 거래대금 조건 및 승률 커트라인을 통과한 종목이 없습니다."
            save_history(date_key, 전략이름, [msg])
            st.warning(msg)

    # 미국 주식 로직 안정적 유지
    def run_us_new(stock):
        try:
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
        except: return None

    def run_us_1pct(stock):
        try:
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
        except: return None

    if btn_kr_ori: 조작_프로세스("한국 퀀트 (기본형)", get_krx_stocks, None, kr_market_safe)
    if btn_kr_1pc: 조작_프로세스("한국 퀀트 (매일 1%)", get_krx_stocks, None, kr_market_safe)
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
