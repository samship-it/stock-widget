from fastapi import FastAPI
import yfinance as yf
import pandas as pd

app = FastAPI()

def get_clean_price_history(ticker_symbol: str):
    """
    주말/공휴일 공백을 자동으로 건너뛰고 
    가장 최근 거래일 기준 데이터를 안전하게 수집하는 함수
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        # 120일 이동평균선 계산을 위해 영업일 기준 1년(1y) 치 수집
        df = ticker.history(period="1y")
        
        if df.empty:
            return None
        
        # 주말/공휴일 등으로 주가가 없는 빈 행(NaN) 완벽 제거
        df = df.dropna(subset=['Close'])
        
        if len(df) < 5:  # 최소한의 데이터도 없으면 에러 방지
            return None
            
        return df
    except Exception:
        return None

@app.get("/")
def read_root():
    return {"status": "online", "message": "HoiStock API Server is Running!"}

@app.get("/api/widget/macro")
def get_macro_only():
    """거시경제 전용 엔드포인트 (HYG & 10년물 국채금리 ^TNX)"""
    try:
        hyg_df = get_clean_price_history("HYG")
        tnx_df = get_clean_price_history("^TNX")

        # 주말/공휴일이어도 가장 최근 마감일자(.iloc[-1]) 종가를 추출
        hyg_val = round(float(hyg_df['Close'].iloc[-1]), 2) if (hyg_df is not None and not hyg_df.empty) else 75.00
        us10y_val = round(float(tnx_df['Close'].iloc[-1]), 2) if (tnx_df is not None and not tnx_df.empty) else 4.25

        return {
            "status": "success",
            "data": {
                "hyg_price": f"${hyg_val}",
                "us10y_rate": f"{us10y_val}%",
                "is_safe": (hyg_val >= 74.0) and (us10y_val < 4.8)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/widget/{ticker}")
def get_widget_data(ticker: str):
    try:
        ticker_upper = ticker.upper()
        
        # 1. 대상 종목 주가 데이터 수집
        df = get_clean_price_history(ticker_upper)
        if df is None:
            return {"status": "error", "message": f"{ticker_upper} 데이터를 가져올 수 없습니다."}

        total_rows = len(df)
        
        # .iloc[-1]은 주말/공휴일 상관없이 '가장 최근 장이 열린 날'의 종가를 짚음
        curr_price = float(df['Close'].iloc[-1])

        # 2. 이동평균선 안전 계산 (영업일 기준)
        ma60_window = min(60, total_rows)
        ma120_window = min(120, total_rows)

        df['MA60'] = df['Close'].rolling(window=ma60_window).mean()
        df['MA120'] = df['Close'].rolling(window=ma120_window).mean()
        df['Vol_MA20'] = df['Volume'].rolling(window=min(20, total_rows)).mean()

        # 결측치 방지 및 이격도 산출
        ma60_clean = df['MA60'].dropna()
        ma120_clean = df['MA120'].dropna()

        ma60_val = float(ma60_clean.iloc[-1]) if not ma60_clean.empty else curr_price
        ma120_val = float(ma120_clean.iloc[-1]) if not ma120_clean.empty else curr_price

        disp_60 = float((curr_price / ma60_val) * 100) if ma60_val > 0 else 100.0
        disp_120 = float((curr_price / ma120_val) * 100) if ma120_val > 0 else 100.0

        # 거래량 및 캔들 검증
        curr_vol = float(df['Volume'].iloc[-1])
        vol_ma_clean = df['Vol_MA20'].dropna()
        avg_vol = float(vol_ma_clean.iloc[-1]) if not vol_ma_clean.empty else curr_vol
        
        vol_ratio = (curr_vol / avg_vol * 100) if avg_vol > 0 else 100.0
        vol_pass = vol_ratio >= 100.0

        open_price = float(df['Open'].iloc[-1])
        candle_pass = curr_price >= open_price

        # 3. 매크로 필터 (HYG & ^TNX)
        hyg_df = get_clean_price_history("HYG")
        tnx_df = get_clean_price_history("^TNX")

        hyg_val = round(float(hyg_df['Close'].iloc[-1]), 2) if (hyg_df is not None and not hyg_df.empty) else 75.00
        us10y_val = round(float(tnx_df['Close'].iloc[-1]), 2) if (tnx_df is not None and not tnx_df.empty) else 4.25

        # 조건 점수 계산
        buy_score_count = 0
        if disp_60 < 100: buy_score_count += 1
        if disp_120 < 100: buy_score_count += 1
        if vol_pass: buy_score_count += 1
        if candle_pass: buy_score_count += 1
        if hyg_val >= 75.0: buy_score_count += 1
        if us10y_val < 4.5: buy_score_count += 1

        is_safe = (hyg_val >= 74.0) and (us10y_val < 4.8)

        return {
            "status": "success",
            "data": {
                "symbol": ticker_upper,
                "price": round(curr_price, 2),
                "disp_60": round(disp_60, 1),
                "disp_120": round(disp_120, 1),
                "buy_score": f"{buy_score_count}/6",
                "verification": {
                    "vol_ratio": f"{round(vol_ratio, 1)}%",
                    "vol_pass": vol_pass,
                    "candle_pass": candle_pass
                },
                "macro_filter": {
                    "hyg_price": f"${hyg_val}",
                    "us10y_rate": f"{us10y_val}%",
                    "is_safe": is_safe
                }
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
