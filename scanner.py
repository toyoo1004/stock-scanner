import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import os
import time
import warnings
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

warnings.filterwarnings("ignore", category=FutureWarning)

# API 설정
API_KEY = os.environ.get('GEMINI_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

def send_combined_report(report_content, found_count):
    try:
        sender_email = os.environ.get('SENDER_EMAIL')
        sender_pw = os.environ.get('SENDER_PW')
        receiver_email = os.environ.get('RECEIVER_EMAIL')

        if not all([sender_email, sender_pw, receiver_email]):
            print("❌ 메일 설정 누락")
            return

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = f"🚀 [Stock Scan] {datetime.now().strftime('%Y-%m-%d')} 리포트 ({found_count}종목)"

        msg.attach(MIMEText(report_content, 'plain', 'utf-8'))

        file_name = "result.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(report_content)

        if os.path.exists(file_name):
            with open(file_name, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={file_name}")
                msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_pw)
        server.send_message(msg)
        server.quit()
        print(f"📧 전송 완료 (포착: {found_count}개)")
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    if not API_KEY: return "API 키 미설정"
    for _ in range(3):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash') 
            prompt = f"{ticker} 주식 분석: 현재가 ${price}, 준비도 {readiness}%, 거래량 {vol_ratio:.1f}배, OBV {obv_status}. 매수 이유 1,2,3번을 상세히 한국어로 작성."
            response = model.generate_content(prompt)
            return response.text.strip() if response.text else "AI 분석 오류"
        except: time.sleep(2)
    return "AI 지연 중"

def scan_logic(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=15)
        if df is None or df.empty or len(df) < 100: return None
        
        close = df['Close']
        # OBV 상시 계산
        obv = [0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i-1]: obv.append(obv[-1] + df['Volume'].iloc[i])
            elif close.iloc[i] < close.iloc[i-1]: obv.append(obv[-1] - df['Volume'].iloc[i])
            else: obv.append(obv[-1])
        df['OBV'] = obv
        
        sma20 = close.rolling(20).mean()
        vol_ma = df['Volume'].rolling(20).mean()
        o_score = 15 if df['OBV'].iloc[-1] > pd.Series(obv).rolling(20).mean().iloc[-1] else 0
        
        readiness = (30 if df['Low'].iloc[-1] <= sma20.iloc[-1] * 1.05 else 0) + 45 + o_score
        vol_p = df['Volume'].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] != 0 else 0
        
        if readiness >= 90 and vol_p > 1.1:
            analysis = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_p, "수급우수" if o_score > 0 else "보통")
            return {'ticker': ticker, 'readiness': readiness, 'price': round(close.iloc[-1], 2), 'analysis': analysis}
    except: return None

if __name__ == "__main__":
    # 데이터 오류 티커(FEYE, DFS, FFIE 등) 제거 완료
    raw_sectors = {
        "1. AI & Cloud": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "AVGO", "ADBE", "CRM", "AMD", "IBM", "NOW", "INTC", "QCOM", "AMAT", "MU", "LRCX", "ADI", "SNOW", "DDOG", "NET", "MDB", "PANW", "CRWD", "ZS", "FTNT", "TEAM", "WDAY", "SMCI", "ARM", "PATH", "AI", "SOUN", "BBAI", "ORCL", "CSCO"],
        "2. Semiconductors": ["TSM", "ASML", "AMAT", "LRCX", "MU", "QCOM", "TXN", "MRVL", "KLAC", "NXPI", "STM", "ON", "MCHP", "MPWR", "TER", "ENTG", "SWKS", "QRVO", "WOLF", "COHR", "IPGP", "LSCC", "RMBS", "FORM", "ACLS", "CAMT", "UCTT", "ICHR", "AEHR", "GFS"],
        "3. Rare Earth": ["MP", "UUUU", "LAC", "SGML", "REMX", "TMC", "NB", "TMQ", "TMRC", "UAMY", "AREC", "IDR", "RIO", "BHP", "VALE", "FCX", "SCCO", "AA", "CENX", "KALU", "CRS", "ATI", "HAYW"],
        "4. Weight Loss & Bio": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "ALT", "GILD", "BMY", "JNJ", "ABBV", "MRK", "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "NVS", "AZN", "SNY", "ALNY", "SRPT", "BMRN", "INCY", "UTHR", "GERN", "CRSP", "EDIT", "NTLA", "BEAM", "AXSM"],
        "5. Fintech & Crypto": ["COIN", "MSTR", "HOOD", "PYPL", "SOFI", "AFRM", "UPST", "MARA", "RIOT", "CLSK", "HUT", "WULF", "CIFR", "BTBT", "IREN", "CORZ", "BITF", "V", "MA", "AXP", "COF", "NU", "DAVE", "LC", "GLBE", "BILL", "TOST", "MQ", "FOUR"],
        "6. Defense & Space": ["RTX", "LMT", "NOC", "GD", "BA", "LHX", "HII", "LDOS", "TXT", "HWM", "AXON", "KTOS", "AVAV", "RKLB", "SPCE", "ASTS", "LUNR", "PL", "SPIR", "BKSY", "VSAT", "IRDM", "SAIC", "CACI", "CW", "HEI", "TDY", "MTSI", "RCAT", "SHLD"],
        "7. Uranium & Nuclear": ["CCJ", "UUUU", "NXE", "UEC", "DNN", "SMR", "BWXT", "LEU", "OKLO", "FLR", "URA", "URNM", "NLR", "SRUUF", "PDN", "BOE", "PENMF", "CEG", "PEG", "EXC", "D", "SO", "NEE", "DUK", "ETR", "PCG", "VST"],
        "8. Consumer & Luxury": ["LVMUY", "RACE", "NKE", "LULU", "ONON", "DECK", "CROX", "RL", "TPR", "CPRI", "PVH", "VFC", "UAA", "COLM", "ANF", "AEO", "URBN", "ROST", "TJX", "HESAY", "CFRUY", "PPRUY", "BURBY", "EL", "COTY", "ULTA", "ELF"],
        "9. Meme & Reddit": ["GME", "AMC", "RDDT", "DJT", "TSLA", "PLTR", "SOFI", "OPEN", "LCID", "RIVN", "CHPT", "NKLA", "SPCE", "TLRY", "CGC", "SNDL", "BB", "NOK", "KOSS", "CVNA", "AI", "CLOV"],
        "10. Quantum": ["IONQ", "RGTI", "QUBT", "HON", "IBM", "MSFT", "GOOGL", "INTC", "FORM", "AMAT", "ASML", "KEYS", "ADI", "TXN", "NVDA", "AMD", "QCOM", "AVGO", "TSM", "MU", "ARQQ", "QBTS", "QMCO"],
        "11. Robotics": ["ISRG", "TER", "PATH", "SYM", "CGNX", "ROCK", "ROBO", "BOTZ", "IRBT", "NVDA", "TSLA", "DE", "CAT", "EMR", "PH", "YASKY", "SIEGY"],
        "12. Biotech Growth": ["VRTX", "AMGN", "MRNA", "BNTX", "REGN", "GILD", "BIIB", "ILMN", "CRSP", "BEAM", "NTLA", "EDIT", "ARWR", "IONS", "SRPT", "BMRN", "INCY", "UTHR", "EXEL", "HALO", "TECH", "WST", "RGEN", "TXG", "PACB", "QGEN", "GMAB", "ARGX"],
        "13. E-commerce": ["AMZN", "WMT", "COST", "HD", "SHOP", "MELI", "BABA", "PDD", "EBAY", "ETSY", "CPNG", "SE", "JMIA", "JD", "VIPS", "TGT", "LOW", "BBY", "M", "KSS", "ANF", "AEO", "URBN", "ROST", "TJX", "DLTR", "DG", "BJ"],
        "14. Gaming": ["RBLX", "U", "EA", "TTWO", "SONY", "NTES", "SE", "PLTK", "SKLZ", "MSFT", "NVDA", "GME", "UBSFY", "NCBDY", "TCEHY", "BILI", "DOYU", "HUYA", "CRSR", "LOGI"],
        "15. Media": ["NFLX", "DIS", "WBD", "SPOT", "ROKU", "AMC", "CNK", "LYV", "TKO", "FOXA", "CMCSA", "IQ", "FUBO", "GOOGL", "AMZN", "AAPL", "SIRI", "WMG", "TR", "NXST", "SBGI"],
        "16. Banking": ["JPM", "BAC", "WFC", "C", "GS", "MS", "HSBC", "RY", "TD", "UBS", "NU", "SOFI", "ALLY", "FITB", "HBAN", "USB", "PNC", "TFC", "COF", "AXP", "V", "MA", "SYF", "KEY", "CFG", "RF", "MTB", "CMA", "ZION"],
        "17. Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "OXY", "PSX", "VLO", "HAL", "BKR", "DVN", "FANG", "APA", "CTRA", "WMB", "KMI", "OKE", "TRGP", "LNG", "EQT", "RRC", "MTDR"],
        "18. Renewables": ["ENPH", "SEDG", "FSLR", "NEE", "BEP", "RUN", "ARRY", "CSIQ", "DQ", "JKS", "MAXN", "SPWR", "SHLS", "GEV", "CWEN", "HASI", "ORA", "TPIC", "BLDP", "PLUG", "FCEL", "BE", "AMRC", "STEM", "FLNC", "AES", "CEG", "VST"],
        "19. Gold": ["GOLD", "NEM", "AU", "GDX", "GDXJ", "AEM", "FNV", "WPM", "KGC", "PAAS", "OR", "PHYS", "HMY", "GFI", "IAG", "NGD", "EGO", "DRD", "SBSW", "CDE", "HL", "AG", "EXK", "FSM", "MUX", "USAS", "GORO"],
        "20. Industrial": ["UPS", "FDX", "CAT", "DE", "HON", "GE", "MMM", "UNP", "EMR", "ITW", "PH", "ETN", "NSC", "CSX", "CMI", "ROK", "AME", "DOV", "XYL", "TT", "CARR", "OTIS", "JCI", "LII", "GWW", "FAST", "URI", "PWR", "EME", "ACM"],
        "21. REITs": ["AMT", "PLD", "CCI", "EQIX", "PSA", "O", "DLR", "WELL", "AVB", "EQR", "VTR", "ARE", "SPG", "WY", "SBAC", "VICI", "GLPI", "IRM", "MAA", "ESS", "UDR", "CPT", "INVH", "AMH", "SUI", "ELS", "LAMR", "OUT", "KIM", "REG"],
        "22. Travel": ["BKNG", "ABNB", "MAR", "H", "RCL", "CCL", "NCLH", "DAL", "UAL", "LUV", "EXPE", "TRIP", "MGM", "WYNN", "CZR", "LVS", "PENN", "DKNG", "BYD", "CHH", "WH", "HLT", "IHG", "VAC", "TNL"],
        "23. Food": ["PEP", "KO", "MDLZ", "MNST", "HSY", "KDP", "STZ", "BUD", "KR", "SYY", "ADM", "GIS", "K", "HRL", "SBUX", "CMG", "YUM", "QSR", "DPZ", "WEN", "MCD", "DRI", "TXRH", "CBRL", "BJRI", "CAKE", "WING", "SHAK", "DNUT", "BRC"],
        "24. Cybersecurity": ["PANW", "CRWD", "FTNT", "NET", "ZS", "OKTA", "S", "QLYS", "CHKP", "TENB", "RPD", "GEN", "VRNS", "CYBR", "BB", "HACK", "CIBR", "BUG"],
        "25. Space": ["SPCE", "RKLB", "ASTS", "BKSY", "PL", "SPIR", "LUNR", "VSAT", "IRDM", "JOBY", "ACHR", "UP", "MNTS", "RDW", "SIDU", "BA", "LMT", "NOC", "RTX", "LHX", "GD", "HII", "LDOS", "TXT", "HWM"]
    }

    all_tickers = []
    for t_list in raw_sectors.values(): all_tickers.extend(t_list)
    all_tickers = list(set(all_tickers))
    
    print(f"🚀 {len(all_tickers)}개 종목 분석 시작...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(scan_logic, all_tickers))
    
    found = [r for r in results if r and "지연" not in r['analysis']]
    
    if found:
        report_text = f"=== Stock Scanner Report ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n"
        report_text += f"포착된 종목: {len(found)}개\n\n"
        for item in sorted(found, key=lambda x: x['readiness'], reverse=True):
            report_text += f"[{item['ticker']}] 준비도: {item['readiness']}% | ${item['price']}\n{item['analysis']}\n{'-'*30}\n"
        
        send_combined_report(report_text, len(found))
    else:
        print("🚩 조건 부합 종목 없음.")
