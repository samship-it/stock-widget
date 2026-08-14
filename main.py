from fastapi import FastAPI
import yfinance as yf
import pandas as pd
import ta

app = FastAPI()

def get_clean_price_history(ticker_symbol: str):
    """야후 파이낸스에서 데이터를 가져오고 빈값을 방지하는 안전 함수"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="6mo")
        if df.empty or len(df) < 2:
            return None
        # 필요 컬럼 내 null 값 제거
        df = df.dropna(subset=['Close'])
        return df
    except Exception:
        return None

@app.get("/")
def read_root():
    return {"status": "online", "message": "HoiStock API Server"}

@app.get("/api/widget/{ticker}")
def get_widget_data(ticker: str):
    try:
        ticker_upper = ticker.upper()
        
        # 1. 대상 종목 데이터 가져오기
        df = get_clean_price_history(ticker_upper)
        if df is None or len(df) < 120:
            return {"status": "error", "message": f"{ticker_upper} 데이터 부족"}

        # 이격도 및 기술적 지표 계산
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA120'] = df['Close'].rolling(window=120).mean()
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()

        curr_price = float(df['Close'].iloc[-1])
        disp_60 = float((curr_price / df['MA60'].iloc[-1]) * 100) if not pd.isna(df['MA60'].iloc[-1]) else 0.0
        disp_120 = float((curr_price / df['MA120'].iloc[-1]) * 100) if not pd.isna(df['MA120'].iloc[-1]) else 0.0

        # 거래량 검증
        curr_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Vol_MA20'].iloc[-1]) if not pd.isna(df['Vol_MA20'].iloc[-1]) else curr_vol
        vol_ratio = (curr_vol / avg_vol * 100) if avg_vol > 0 else 0.0
        vol_pass = vol_ratio >= 100.0

        # 캔들 검증 (양봉 여부)
        open_price = float(df['Open'].iloc[-1])
        candle_pass = curr_price >= open_price

        # 2. 매크로 필터 (HYG & 10년물 국채금리 ^TNX)
        hyg_df = get_clean_price_history("HYG")
        tnx_df = get_clean_price_history("^TNX")

        hyg_val = round(float(hyg_df['Close'].iloc[-1]), 2) if (hyg_df is not None and not hyg_df.empty) else 75.00
        us10y_val = round(float(tnx_df['Close'].iloc[-1]), 2) if (tnx_df is not None and not tnx_df.empty) else 4.25

        # 안전 매수 조건 계산
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
