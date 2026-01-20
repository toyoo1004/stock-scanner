import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime
import google.generativeai as genai
import gspread
import json
import os
import warnings

# 불필요한 경고 메시지 무시
warnings.filterwarnings("ignore", category=FutureWarning)

# === [1. 설정부] ===
genai.configure(api_key="AIzaSyD45Cht5i2fiv19NBxdatFZLTDFrkon47A")

def update_google_sheet_combined(found_data):
    try:
        key_content = os.environ.get('GSPREAD_KEY')
        if not key_content: return
        secret_json = json.loads(key_content)
        gc = gspread.service_account_from_dict(secret_json)
        
        sheet_url = "https://docs.google.com/spreadsheets/d/1nX2rx6Mkx98zPQqkOJEYigxnAYwBxsartKDX-vFLvjQ/edit"
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.get_worksheet(0)
        
        combined_report = ""
        # 준비도 높은 순서로 정렬
        for item in sorted(found_data, key=lambda x: x['readiness'], reverse=True):
            readiness_fmt = f"{item['readiness']:.2f}%"
            combined_report += f"[{item['ticker']}] {readiness_fmt} | ${item['price']}\n"
            combined_report += f"{item['analysis']}\n"
            combined_report += "=" * 45 + "\n"

        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        worksheet.append_row([now, f"{len(found_data)}개 종목 포착", combined_report])
        print(f"✅ {len(found_data)}개 종목 분석 완료 및 시트 전송!")
    except Exception as e:
        print(f"❌ 시트 업데이트 실패: {e}")

def analyze_with_gemini(ticker, readiness, price, vol_ratio, obv_status):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash') 
        prompt = f"""
        주식 수급 전문가로서 {ticker} 분석 리포트를 작성하세요.
        조건: 현재가 ${price:.2f}, 준비도 {readiness:.2f}%, 거래량 {vol_ratio:.1f}배, OBV {obv_status}.
        매수 추천 이유를 1, 2, 3번 번호를 붙여 아주 상세하게 한국어로 작성하세요. 
        기술적 지표와 수급의 연관성을 강조하여 전문적인 통찰을 제공하세요.
        """
        response = model.generate_content(prompt, generation_config={"temperature": 0.2})
        return response.text.strip()
    except: return "AI 분석 지연 중"

def scan_logic(ticker):
    try:
        # 에러 발생 시 사용자 화면에 에러를 출력하지 않고 조용히 스킵함
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y", timeout=5)
        
        # 데이터가 없거나, 상장 폐지되었거나, 데이터 길이가 부족하면 조용히 스킵(None 반환)
        if df is None or df.empty or len(df) < 100:
            return None
        
        close = df['Close']
        # [2026-01-19] OBV 상시 계산
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
        
        # 포착 기준 (데이터가 있는 종목 중 조건에 맞는 것만 필터링)
        if readiness >= 90 and vol_p > 1.2:
            obv_status = "상승 강세(기관 매집 확인)" if o_score > 0 else "보통"
            analysis = analyze_with_gemini(ticker, readiness, close.iloc[-1], vol_p, obv_status)
            return {'ticker': ticker, 'readiness': readiness, 'price': round(close.iloc[-1], 2), 'analysis': analysis}
    except:
        # 어떤 종류의 에러가 나더라도 그냥 무시하고 다음 종목으로 넘어감
        return None
    return None

if __name__ == "__main__":
    # 요청하신 25개 카테고리 전체 리스트 (에러 나는 종목 포함되어 있어도 상관없음)
    raw_sectors = {
        "1. AI & Cloud": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "AVGO", "ADBE", "CRM", "AMD", "IBM", "NOW", "INTC", "QCOM", "AMAT", "MU", "LRCX", "ADI", "SNOW", "DDOG", "NET", "MDB", "PANW", "CRWD", "ZS", "FTNT", "TEAM", "WDAY", "SMCI", "ARM", "PATH", "AI", "SOUN", "BBAI", "ORCL", "CSCO"],
        "2. Semiconductors": ["TSM", "ASML", "AMAT", "LRCX", "MU", "QCOM", "TXN", "MRVL", "KLAC", "NXPI", "STM", "ON", "MCHP", "MPWR", "TER", "ENTG", "SWKS", "QRVO", "WOLF", "COHR", "IPGP", "LSCC", "RMBS", "FORM", "ACLS", "CAMT", "UCTT", "ICHR", "AEHR", "GFS"],
        "3. Rare Earth": ["MP", "UUUU", "LAC", "SGML", "PLL", "REMX", "TMC", "NB", "TMQ", "TMRC", "UAMY", "AREC", "IDR", "RIO", "BHP", "VALE", "FCX", "SCCO", "AA", "CENX", "KALU", "CRS", "ATI", "HAYW"],
        "4. Weight Loss & Bio": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "ALT", "GILD", "BMY", "JNJ", "ABBV", "MRK", "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "NVS", "AZN", "SNY", "ALNY", "SRPT", "BMRN", "INCY", "UTHR", "GERN", "CRSP", "EDIT", "NTLA", "BEAM", "SAGE", "ITCI", "AXSM"],
        "5. Fintech & Crypto": ["COIN", "MSTR", "HOOD", "PYPL", "SOFI", "AFRM", "UPST", "MARA", "RIOT", "CLSK", "HUT", "WULF", "CIFR", "BTBT", "IREN", "CORZ", "SDIG", "GREE", "BITF", "V", "MA", "AXP", "DFS", "COF", "NU", "DAVE", "LC", "GLBE", "BILL", "TOST", "MQ", "FOUR"],
        "6. Defense & Space": ["RTX", "LMT", "NOC", "GD", "BA", "LHX", "HII", "LDOS", "TXT", "HWM", "AXON", "KTOS", "AVAV", "RKLB", "SPCE", "ASTS", "LUNR", "PL", "SPIR", "BKSY", "VSAT", "IRDM", "SAIC", "CACI", "CW", "HEI", "TDY", "AJRD", "MTSI", "RCAT", "SHLD"],
        "7. Uranium & Nuclear": ["CCJ", "UUUU", "NXE", "UEC", "DNN", "SMR", "BWXT", "LEU", "OKLO", "FLR", "URA", "URNM", "NLR", "SRUUF", "FCU", "GLO", "PDN", "BOE", "DYL", "PENMF", "CEG", "PEG", "EXC", "D", "SO", "NEE", "DUK", "ETR", "PCG", "VST"],
        "8. Consumer & Luxury": ["LVMUY", "RACE", "NKE", "LULU", "ONON", "DECK", "CROX", "SKX", "RL", "TPR", "CPRI", "PVH", "VFC", "UAA", "COLM", "GPS", "ANF", "AEO", "URBN", "ROST", "TJX", "HESAY", "CFRUY", "PPRUY", "BURBY", "BOSS.DE", "EL", "COTY", "ULTA", "ELF"],
        "9. Meme & Reddit": ["GME", "AMC", "RDDT", "DJT", "TSLA", "PLTR", "SOFI", "OPEN", "LCID", "RIVN", "CHPT", "NKLA", "SPCE", "TLRY", "CGC", "SNDL", "BB", "NOK", "KOSS", "EXPR", "MULN", "FFIE", "HOLO", "GNS", "CVNA", "AI", "BIG", "RAD", "WISH", "CLOV"],
        "10. Quantum": ["IONQ", "RGTI", "QUBT", "HON", "IBM", "MSFT", "GOOGL", "INTC", "FORM", "AMAT", "ASML", "KEYS", "ADI", "TXN", "NVDA", "AMD", "QCOM", "AVGO", "TSM", "MU", "D-WAVE", "ARQQ", "QBTS", "QMCO"],
        "11. Robotics": ["ISRG", "TER", "PATH", "SYM", "ABB", "CGNX", "ROCK", "ATSG", "ROBO", "BOTZ", "IRBT", "NVDA", "TSLA", "DE", "CAT", "EMR", "PH", "FANUC", "YASKY", "KUKAY", "SIEGY"],
        "12. Biotech Growth": ["VRTX", "AMGN", "MRNA", "BNTX", "REGN", "GILD", "BIIB", "ILMN", "CRSP", "BEAM", "NTLA", "EDIT", "NVTA", "ARWR", "IONS", "SRPT", "BMRN", "INCY", "UTHR", "EXEL", "HALO", "TECH", "WST", "RGEN", "TXG", "PACB", "QGEN", "GMAB", "ARGX", "BGNE"],
        "13. E-commerce": ["AMZN", "WMT", "COST", "HD", "SHOP", "MELI", "BABA", "PDD", "EBAY", "ETSY", "CPNG", "SE", "JMIA", "JD", "VIPS", "TGT", "LOW", "BBY", "M", "KSS", "JWN", "GPS", "ANF", "AEO", "URBN", "ROST", "TJX", "DLTR", "DG", "BJ"],
        "14. Gaming": ["RBLX", "U", "EA", "TTWO", "SONY", "NTES", "SE", "PLTK", "SKLZ", "EDR", "MSFT", "NVDA", "GME", "UBSFY", "NCBDY", "TCEHY", "BILI", "DOYU", "HUYA", "CRSR", "LOGI", "HEAR"],
        "15. Media": ["NFLX", "DIS", "WBD", "SPOT", "ROKU", "AMC", "CNK", "LYV", "TKO", "FOXA", "CMCSA", "IQ", "FUBO", "GOOGL", "AMZN", "AAPL", "SIRI", "LGF-A", "WMG", "UMG", "TR", "NXST", "SBGI"],
        "16. Banking": ["JPM", "BAC", "WFC", "C", "GS", "MS", "HSBC", "RY", "TD", "UBS", "NU", "SOFI", "ALLY", "FITB", "HBAN", "USB", "PNC", "TFC", "COF", "AXP", "V", "MA", "DFS", "SYF", "KEY", "CFG", "RF", "MTB", "CMA", "ZION"],
        "17. Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "OXY", "PSX", "VLO", "HAL", "BKR", "HES", "DVN", "FANG", "MRO", "APA", "CTRA", "PXD", "WMB", "KMI", "OKE", "TRGP", "LNG", "EQT", "RRC", "SWN", "CHK", "MTDR", "PDCE", "CIVI"],
        "18. Renewables": ["ENPH", "SEDG", "FSLR", "NEE", "BEP", "RUN", "ARRY", "CSIQ", "DQ", "JKS", "MAXN", "SPWR", "NOVA", "SHLS", "GEV", "CWEN", "AY", "HASI", "ORA", "TPIC", "BLDP", "PLUG", "FCEL", "BE", "AMRC", "STEM", "FLNC", "AES", "CEG", "VST"],
        "19. Gold": ["GOLD", "NEM", "AU", "GDX", "GDXJ", "AEM", "FNV", "WPM", "KGC", "PAAS", "MAG", "SAND", "OR", "PHYS", "HMY", "GFI", "IAG", "NGD", "EGO", "DRD", "SBSW", "CDE", "HL", "AG", "EXK", "FSM", "MUX", "USAS", "GORO"],
        "20. Industrial": ["UPS", "FDX", "CAT", "DE", "HON", "GE", "MMM", "UNP", "EMR", "ITW", "PH", "ETN", "NSC", "CSX", "CMI", "ROK", "AME", "DOV", "XYL", "TT", "CARR", "OTIS", "JCI", "LII", "GWW", "FAST", "URI", "PWR", "EME", "ACM"],
        "21. REITs": ["AMT", "PLD", "CCI", "EQIX", "PSA", "O", "DLR", "WELL", "AVB", "EQR", "VTR", "ARE", "SPG", "WY", "SBAC", "VICI", "GLPI", "IRM", "MAA", "ESS", "UDR", "CPT", "INVH", "AMH", "SUI", "ELS", "LAMR", "OUT", "KIM", "REG"],
        "22. Travel": ["BKNG", "ABNB", "MAR", "H", "RCL", "CCL", "NCLH", "DAL", "UAL", "LUV", "EXPE", "TRIP", "MGM", "WYNN", "CZR", "LVS", "PENN", "DKNG", "BYD", "CHH", "WH", "HLT", "IHG", "VAC", "TNL", "PLYA", "SAVE", "JBLU", "ALK", "HA"],
        "23. Food": ["PEP", "KO", "MDLZ", "MNST", "HSY", "KDP", "STZ", "BUD", "KR", "SYY", "ADM", "GIS", "K", "HRL", "SBUX", "CMG", "YUM", "QSR", "DPZ", "WEN", "MCD", "DRI", "TXRH", "CBRL", "BJRI", "CAKE", "WING", "SHAK", "DNUT", "BRC"],
        "24. Cybersecurity": ["PANW", "CRWD", "FTNT", "NET", "ZS", "OKTA", "S", "QLYS", "CHKP", "TENB", "RPD", "GEN", "VRNS", "CYBR", "BB", "HACK", "CIBR", "BUG", "FEYE", "MIME", "PFPT", "SAIL", "PING", "SUMO", "FROG", "NCNO", "WK", "DOCU", "DBX", "BOX"],
        "25. Space": ["SPCE", "RKLB", "ASTS", "BKSY", "PL", "SPIR", "LUNR", "VSAT", "IRDM", "JOBY", "ACHR", "UP", "MNTS", "RDW", "SIDU", "LLAP", "VORB", "ASTR", "DCO", "TL0", "BA", "LMT", "NOC", "RTX", "LHX", "GD", "HII", "LDOS", "TXT", "HWM"]
    }

    # 전체 종목 리스트 합치기 (중복 제거)
    all_tickers = []
    for t_list in raw_sectors.values():
        all_tickers.extend(t_list)
    
    all_tickers = list(set(all_tickers))
    print(f"🚀 총 {len(all_tickers)}개 종목 스캔 시작 (에러 종목 자동 스킵)...")

    # 병렬 처리로 속도 향상
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(scan_logic, all_tickers))
    
    found = [r for r in results if r]
    if found:
        update_google_sheet_combined(found)
    else:
        print("🚩 신호가 포착된 종목이 없습니다.")
