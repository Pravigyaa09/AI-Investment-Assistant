from flask import Blueprint, request, jsonify
from logger import get_logger
from utils.sentiment_model import analyze_sentiment, map_sentiment_to_signal

logger = get_logger(__name__)
sentiment_bp = Blueprint('sentiment', __name__)

@sentiment_bp.route('/signal', methods=['GET'])
def get_trading_signal():
    ticker = request.args.get('ticker')
    if not ticker:
        logger.error('Ticker is required')
        return jsonify({'error': 'Ticker is required'}), 400

    logger.info(f"Getting trading signal for ticker: {ticker}")

    # 1. Fetch news articles about the ticker (your Finnhub/news fetch code here)
    # 2. Analyze each article with analyze_sentiment (already in utils/sentiment_model.py)
    # 3. Count positive, negative, neutral sentiments
    # Example dummy values for now:
    positive, negative, neutral = 8, 2, 5  # Replace with real values

    # 4. Get trading signal
    signal_info = map_sentiment_to_signal(positive, negative, neutral)
    logger.info(f"Signal for {ticker}: {signal_info}")

    return jsonify(signal_info)
