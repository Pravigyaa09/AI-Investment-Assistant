from transformers import pipeline
from typing import List, Union

# Load FinBERT pipeline globally (loaded once)
try:
    sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
except Exception as e:
    print(f"Error loading FinBERT model: {e}")
    sentiment_pipeline = None

def run_finbert(text: Union[str, List[str]]):
    """
    Run FinBERT sentiment analysis on input text(s).

    Args:
        text (str or List[str]): Single sentence or list of sentences.

    Returns:
        dict or List[dict]: Label (str) and Score (float) for each input.
    """
    if sentiment_pipeline is None:
        return {"error": "FinBERT model not loaded"}

    if isinstance(text, str):
        text = text.strip()
        if not text:
            return {"error": "Input text is empty"}
        result = sentiment_pipeline(text)[0]
        return {
            "label": result["label"].lower(),
            "score": round(float(result["score"]), 4)
        }

    elif isinstance(text, list):
        results = []
        for item in text:
            item = item.strip()
            if not item:
                results.append({"error": "Empty input"})
                continue
            try:
                output = sentiment_pipeline(item)[0]
                results.append({
                    "label": output["label"].lower(),
                    "score": round(float(output["score"]), 4)
                })
            except Exception as e:
                results.append({"error": str(e)})
        return results

    else:
        return {"error": "Invalid input type"}

# Optional CLI test
if __name__ == "__main__":
    sample_texts = [
        "The market outlook is positive for technology stocks.",
        "Economic indicators are showing signs of a recession.",
        "",
        "Investors are cautiously optimistic."
    ]
    print(run_finbert(sample_texts))
