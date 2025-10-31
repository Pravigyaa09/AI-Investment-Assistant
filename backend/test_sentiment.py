"""Test sentiment analysis on specific headlines"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.nlp.finbert import FinBERT

# Test headline
headline = "Oracle's stock surged on billions in new cloud contracts. Can it fund its AI promise?"

print("=" * 80)
print("Testing FinBERT Sentiment Analysis")
print("=" * 80)
print(f"\nHeadline: {headline}")
print()

if not FinBERT.is_available():
    print("[X] FinBERT not available! Using keyword fallback.")
    print("\nKeyword analysis:")
    low = headline.lower()
    pos_words = [w for w in ["surge", "surged", "jumps", "beats", "rises", "gain", "profit", "record", "soar"] if w in low]
    neg_words = [w for w in ["falls", "misses", "slump", "drop", "loss", "cuts", "plunge"] if w in low]
    print(f"  Positive keywords found: {pos_words}")
    print(f"  Negative keywords found: {neg_words}")
else:
    print("[OK] FinBERT is available!")

    # Get prediction
    result = FinBERT.predict(headline, use_cache=False)

    print(f"\n[RESULTS] Sentiment Analysis Results:")
    print(f"  Label: {result['label'].upper()}")
    print(f"  Confidence: {result['confidence']} ({result['score']:.2%})")
    print(f"\n  Detailed Scores:")
    print(f"    Negative: {result['all_scores']['negative']:.2%}")
    print(f"    Neutral:  {result['all_scores']['neutral']:.2%}")
    print(f"    Positive: {result['all_scores']['positive']:.2%}")

    print(f"\n[INTERPRETATION] Interpretation:")
    if result['label'] == 'negative':
        print("  The model detected NEGATIVE sentiment.")
        print("  Possible reasons:")
        print("    - The question 'Can it fund its AI promise?' suggests doubt/uncertainty")
        print("    - Questions often imply skepticism in financial news")
        print("    - The model weighs the entire context, not just 'surged'")
    elif result['label'] == 'positive':
        print("  The model detected POSITIVE sentiment.")
        print("  Reasons: 'surged', 'billions' outweigh the questioning tone")
    else:
        print("  The model detected NEUTRAL sentiment.")
        print("  The positive news and questioning tone balance each other")

print("\n" + "=" * 80)
print("Testing different variations:")
print("=" * 80)

test_headlines = [
    "Oracle's stock surged on billions in new cloud contracts",  # Without question
    "Can Oracle fund its AI promise?",  # Just the question
    "Oracle secures billions in new cloud contracts",  # Positive without 'surge'
    "Oracle's stock plunged after missing earnings",  # Clearly negative
]

for i, test in enumerate(test_headlines, 1):
    print(f"\n{i}. \"{test}\"")
    if FinBERT.is_available():
        result = FinBERT.predict(test, use_cache=False)
        print(f"   -> {result['label'].upper()} ({result['score']:.2%})")
    else:
        print("   -> FinBERT not available")

print("\n" + "=" * 80)
