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
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

warnings.filterwarnings("ignore", category=FutureWarning)

# === [보안 설정] 환경 변수에서 키 로드 ===
API_KEY = os.environ.get('GEMINI_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

def send_email_with_file(file_path, found_count, report_content):
    """메일 본문 출력 + result.txt 파일 첨부 (이중 보장)"""
    try:
        sender_email = os.environ.get('SENDER_EMAIL')
        sender_pw = os.environ.get('SENDER_PW')
        receiver_email = os.environ.get('RECEIVER_EMAIL')

        if not all([sender_email, sender_pw, receiver_email]):
            print("❌ 메일 설정 환경변수(SENDER_EMAIL, SENDER_PW, RECEIVER_EMAIL)가 없습니다.")
            return

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = f"🚀 [Stock Scan] {datetime.now().strftime('%Y-%m-%d')} 리포트 ({found_count}종목)"

        # 파일이 안 보일 것에 대비해 본문에도 요약 내용 삽입
        body = f"오늘 조건에 부합하는 {found_count}개 종목 리포트입니다.\n\n"
        body += "--- 요약 내용 ---\n"
        body += report_content[:2000] + "\n... (상세 내용은 첨부파일 확인)"
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 파일 첨부 로직
        if os.path.exists(file_path):
            with open(file_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename=result.txt")
                msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_pw)
        server.send_message(msg)
        server.quit()
        print(f"📧 이메일 발송 완료")
    except Exception as e:
        print(f"❌ 메일 발송 실패: {e}")

def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    if not API_KEY: return "API 키 미설정"
    for attempt in range(3):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash') 
            prompt = f"{ticker} 분석: 현재가 ${price}, 준비도 {readiness}%, 거래량 {vol_ratio}배, OBV {obv_status}. 매수 추천 이유 1,2,3번 상세히 한국어로 작성."
            response = model.generate_content(prompt)
            return response.text.strip()
        except: time.sleep(2)
    return "AI 분석 지연 중"

def scan_logic(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=15)
        if df is None or df.empty or len(df) < 100: return None
        
        close = df['Close']
        # [2026-01-19] OBV 계산 필수 포함
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]: obv.append(obv[-1] + df['Volume'].iloc[i])
            elif close.iloc[i] < close.iloc[i-1]: obv.append(obv[-1] - df['Volume'].iloc[i])
            else: obv.append(obv[-1])
        df['OBV'] = obv
        
        sma20, sma200 = close.rolling(20).mean(), close.rolling(200).mean()
        vol_ma = df['Volume'].rolling(20).mean()
        o_score = 15 if df['OBV'].iloc[-1] > pd.Series(obv).rolling(20).mean().iloc[-1] else 0
        
        # 준비도 계산 (기준 90%)
        readiness = (30 if df['Low'].iloc[-1] <= sma20.iloc[-1] * 1.04 else 0) + \
                    (30 if close.iloc[-1] > sma200.iloc[-1] else 0) + 15 + o_score
        
        vol_p = df['Volume'].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] != 0 else 0
        
        if readiness >= 90 and vol_p > 1.1:
            analysis = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_p, "수급우수" if o_score > 0 else "보통")
            return {'ticker': ticker, 'readiness': readiness, 'price': round(close.iloc[-1], 2), 'analysis': analysis}
    except: return None

if __name__ == "__main__":
    # 티커 리스트 (간략화 예시, 위에서 드린 25개 카테고리 전체를 여기에 넣으세요)
    raw_sectors = {"Main": ["NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "META"]} 
    
    all_tickers = []
    for t_list in raw_sectors.values(): all_tickers.extend(t_list)
    all_tickers = list(set(all_tickers))
    
    print(f"🚀 분석 시작... (API KEY 체크: {'OK' if API_KEY else 'EMPTY'})")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(scan_logic, all_tickers))
    
    found = [r for r in results if r and "지연" not in r['analysis']]
    
    if found:
        report_text = f"=== Stock Scanner Report ===\n포착: {len(found)}개\n\n"
        for item in found:
            report_text += f"[{item['ticker']}] 준비도: {item['readiness']}% | 가격: ${item['price']}\n{item['analysis']}\n\n"
        
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(report_text)
            
        send_email_with_file("result.txt", len(found), report_text)
    else:
        print("🚩 조건 부합 종목 없음.")
