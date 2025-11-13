"""
Test script to verify recommendation analysis logic

This script tests:
1. Whether ML model or rule-based logic is being used
2. Whether FinBERT sentiment analysis is active
3. Position-aware logic (owned vs non-owned stocks)
4. Raw predictions vs final recommendations
"""
import asyncio
from app.ml.infer import recommend
from app.ml.model_store import load_model

# Test configuration
TEST_TICKERS = ["NVDA", "STT", "CFLT", "AAPL", "TSLA"]
OWNED_TICKERS = ["NVDA", "STT", "CFLT"]  # Simulate owned stocks


def print_separator(title: str = ""):
    """Print a visual separator"""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    else:
        print("-" * 80)


def check_model_status():
    """Check if ML model is trained and loaded"""
    print_separator("MODEL STATUS CHECK")

    bundle = load_model()
    if bundle is None:
        print("❌ NO ML MODEL FOUND")
        print("   Using rule-based logic fallback")
        print("   To train a model: POST /ml/train")
        return False

    print("✅ ML MODEL LOADED")
    print(f"   Features: {len(bundle.get('features', []))} features")
    print(f"   Classifier: {type(bundle.get('clf')).__name__}")
    print(f"   Regressor: {type(bundle.get('reg')).__name__}")
    print(f"   Horizon: {bundle.get('horizon_days', 'unknown')} days")
    return True


def check_finbert_status():
    """Check if FinBERT is available"""
    print_separator("FINBERT SENTIMENT STATUS")

    try:
        from app.nlp.finbert import FinBERT
        if FinBERT.is_available():
            print("✅ FINBERT LOADED")
            print("   Using transformer-based sentiment analysis")
            return True
        else:
            print("⚠️  FINBERT NOT AVAILABLE")
            print("   Using keyword-based sentiment fallback")
            return False
    except Exception as e:
        print("❌ FINBERT IMPORT FAILED")
        print(f"   Error: {e}")
        print("   Using keyword-based sentiment fallback")
        return False


def test_single_recommendation(ticker: str, has_position: bool, user_id: str = None):
    """Test recommendation for a single ticker"""
    position_status = "OWNED" if has_position else "NOT OWNED"
    print(f"\n📊 Testing {ticker} ({position_status})")
    print_separator()

    result = recommend(
        ticker,
        horizon_days=21,
        user_id=user_id,
        has_position=has_position
    )

    # Provider info
    provider = result.get("provider", "unknown")
    rec_type = result.get("recommendation_type", "unknown")
    print(f"Provider: {provider.upper()} | Type: {rec_type}")

    # Final recommendation
    final_action = result.get("action", "Unknown")
    final_conf = result.get("confidence", 0.0)
    print(f"\n🎯 FINAL RECOMMENDATION: {final_action} (confidence: {final_conf:.1%})")

    # Component recommendations
    print("\n📋 Component Predictions:")

    if "ml_recommendation" in result:
        ml_rec = result["ml_recommendation"]
        print(f"   ML Raw Prediction:  {ml_rec['action']} (conf: {ml_rec['confidence']:.1%})")

    if "rule_recommendation" in result:
        rule_rec = result["rule_recommendation"]
        print(f"   Rule-Based Prediction: {rule_rec['action']} (conf: {rule_rec['confidence']:.1%})")

    if "sentiment_recommendation" in result:
        sent_rec = result["sentiment_recommendation"]
        print(f"   Sentiment Signal:   {sent_rec['action']} (conf: {sent_rec['confidence']:.1%})")

    # Sentiment analysis details
    if "sentiment_analysis" in result:
        sent_data = result["sentiment_analysis"]
        print("\n💭 Sentiment Analysis:")
        print(f"   Index: {sent_data.get('sentiment_index', 0):.3f} (-1=negative, +1=positive)")
        print(f"   Clarity: {sent_data.get('sentiment_strength', 0):.1%} (% non-neutral articles)")
        print(f"   Distribution: +{sent_data.get('positive', 0)} | ~{sent_data.get('neutral', 0)} | -{sent_data.get('negative', 0)}")

    # Risk metrics
    if "risk" in result:
        risk = result["risk"]
        print("\n⚠️  Risk Metrics:")
        print(f"   Annual Volatility: {risk.get('vol_annual', 0):.2%}")
        print(f"   21-day VaR (95%): {risk.get('var95_h', 0):.2%}")

    # Expected return
    exp_ret = result.get("expected_return_h", 0.0)
    print(f"\n📈 Expected 21-day Return: {exp_ret:.2%}")

    # Position-aware status
    position_aware = result.get("position_aware", False)
    has_pos = result.get("has_position", False)
    print(f"\n🔍 Position Aware: {'Yes' if position_aware else 'No'}")
    print(f"   Has Position: {'Yes' if has_pos else 'No'}")

    print_separator()
    return result


async def run_tests():
    """Run all tests"""
    print_separator("RECOMMENDATION ANALYSIS TEST SUITE")

    # Check system status
    has_ml_model = check_model_status()
    has_finbert = check_finbert_status()

    print_separator("TESTING RECOMMENDATIONS")

    # Test each ticker
    results = []
    for ticker in TEST_TICKERS:
        has_position = ticker in OWNED_TICKERS
        result = test_single_recommendation(ticker, has_position)
        results.append(result)

        # Small delay to avoid rate limits
        await asyncio.sleep(0.5)

    # Summary
    print_separator("SUMMARY")

    print(f"\n✅ Tested {len(results)} stocks")
    print(f"   - Owned stocks: {len([r for r in results if r.get('has_position')])}")
    print(f"   - Non-owned stocks: {len([r for r in results if not r.get('has_position')])}")

    # Count recommendations by action
    actions = {}
    for r in results:
        action = r.get("action", "Unknown")
        has_pos = "owned" if r.get("has_position") else "non-owned"
        key = f"{action} ({has_pos})"
        actions[key] = actions.get(key, 0) + 1

    print("\n📊 Recommendation Distribution:")
    for action, count in sorted(actions.items()):
        print(f"   {action}: {count}")

    # Validate position-aware logic
    print("\n🔍 Position-Aware Logic Validation:")
    owned_buys = sum(1 for r in results if r.get('has_position') and r.get('action') == 'Buy')
    non_owned_sells = sum(1 for r in results if not r.get('has_position') and r.get('action') == 'Sell')

    if owned_buys > 0:
        print(f"   ⚠️  WARNING: {owned_buys} owned stocks showing 'Buy' (should be 'Hold' or 'Sell')")
    else:
        print("   ✅ No owned stocks showing 'Buy' recommendation")

    if non_owned_sells > 0:
        print(f"   ⚠️  WARNING: {non_owned_sells} non-owned stocks showing 'Sell' (should be 'Buy' or 'Don't Buy')")
    else:
        print("   ✅ No non-owned stocks showing 'Sell' recommendation")

    print("\n" + "="*80)
    print("Test complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    print("\n🧪 Starting recommendation analysis test...\n")
    asyncio.run(run_tests())
