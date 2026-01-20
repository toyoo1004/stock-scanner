import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import gspread
import json
import os
import time
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

# === [1. 설정부] ===
genai.configure(api_key="AIzaSyD45Cht5i2fiv19NBxdatFZLTDFrkon47A")

def update_google_sheet_rows(found_data):
    """데이터가 유효한 경우에만 시트에 기록"""
    try:
        key_content = os.environ.get('GSPREAD_KEY')
        if not key_content: return
        
        secret_json = json.loads(key_content)
        gc = gspread.service_account_from_dict(secret_json)
        
        sheet_url = "https://docs.google.com/spreadsheets/d/1nX2rx6Mkx98zPQqkOJEYigxnAYwBxsartKDX-vFLvjQ/edit"
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        for item in found_data:
            # AI 분석이 실패한 데이터("AI 분석 지연 중")는 시트에 올리지 않음
            if "지연 중" in item['analysis']:
                continue
                
            row = [now, item['ticker'], f"{item['readiness']:.2f}%", f"${item['price']}", item['analysis']]
            worksheet.append_row(row)
            print(f"✅ {item['ticker']} 리포트 기록 완료")
            
    except Exception as e:
        print(f"❌ 시트 업데이트 에러: {e}")

def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    """AI 분석 지연 방지를 위해 재시도 로직 추가"""
    for attempt in range(3):  # 최대 3번 재시도
        try:
            model = genai.GenerativeModel('gemini-1.5-flash') 
            prompt = f"""
            {ticker} 주식의 수급 분석 리포트를 작성하세요.
            현재가: ${price:.2f}, 준비도: {readiness:.2f}%, 거래량: {vol_ratio:.1f}배, OBV: {obv_status}.
            매수 추천 이유를 1, 2, 3번으로 나누어 전문적인 한국어로 상세히 작성하세요.
            """
            response = model.generate_content(prompt, generation_config={"temperature": 0.2})
            if response.text:
                return response.text.strip()
        except Exception as e:
            print(f"⚠️ {ticker} AI 분석 시도 {attempt+1}회 실패: {e}")
            time.sleep(2) # 2초 대기 후 재시도
    return "AI 분석 지연 중 (API 응답 없음)"

def scan_logic(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=15)
        
        if df is None or df.empty or len(df) < 100:
            return None
        
        close = df['Close']
        # OBV 상시 계산 (사용자 요청 반영)
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]: obv.append(obv[-1] + df['Volume'].iloc[i])
            elif close.iloc[i] < close.iloc[i-1]: obv.append(obv[-1] - df['Volume'].iloc[i])
            else: obv.append(obv[-1])
        df['OBV'] = obv
        
        sma20, sma200 = close.rolling(20).mean(), close.rolling(200).mean()
        vol_ma = df['Volume'].rolling(20).mean()
        highest_22 = close.rolling(22).max()
        wvf = ((highest_22 - df['Low']) / highest_22) * 100
        wvf_limit = wvf.rolling(50).mean() + (2.1 * wvf.rolling(50).std())
        
        o_score = 15 if df['OBV'].iloc[-1] > pd.Series(obv).rolling(20).mean().iloc[-1] else 0
        readiness = (30 if df['Low'].iloc[-1] <= sma20.iloc[-1] * 1.04 else 0) + \
                    (30 if close.iloc[-1] > sma200.iloc[-1] else 0) + \
                    min((wvf.iloc[-1] / wvf_limit.iloc[-1]) * 25, 25) + o_score
        
        vol_p = df['Volume'].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] != 0 else 0
        
        if readiness >= 90 and vol_p > 1.2:
            print(f"🎯 신호 포착: {ticker}")
            # AI 분석 시 호출 간격 조절 (Rate Limit 방지)
            time.sleep(1) 
            obv_status = "상승 강세(기관 매집)" if o_score > 0 else "보통"
            analysis = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_p, obv_status)
            return {'ticker': ticker, 'readiness': readiness, 'price': round(close.iloc[-1], 2), 'analysis': analysis}
    except:
        return None
    return None

if __name__ == "__main__":
    # 25개 카테고리 티커 리스트
    raw_sectors = {
        # ... (사용자님이 주신 25개 카테고리 티커들) ...
    }

    all_tickers = []
    for t_list in raw_sectors.values():
        all_tickers.extend(t_list)
    all_tickers = list(set(all_tickers))

    print(f"🚀 {len(all_tickers)}개 종목 분석 시작...")

    # 병렬 처리 숫자를 10 -> 5로 낮추어 AI 서버 과부하 방지
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(scan_logic, all_tickers))
    
    found = [r for r in results if r and "지연 중" not in r['analysis']]
    
    if found:
        print(f"📊 {len(found)}개 종목의 AI 리포트 생성 완료. 시트 및 메일 전송을 시작합니다.")
        update_google_sheet_rows(found)
        # 메일 발송 함수가 있다면 여기서 found 데이터를 인자로 호출하세요.
    else:
        print("🚩 오늘 조건에 맞는 종목이 없거나 AI 분석이 지연되었습니다.")
