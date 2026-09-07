"""
Task-Aware DOM Intelligence Benchmark.
Measures Before vs After DOM Node count, Token reduction %, and Latency.
"""

import time
from webveil.browser.playwright_adapter import PlaywrightAdapter
from webveil.core.nlp.task_analyzer import TaskAnalyzer
from webveil.core.observation.dom_ranker import DOMRanker


def run_dom_compression_benchmark(url: str, prompt: str):
    print("\n" + "=" * 70)
    print("WEBVEIL TASK-AWARE DOM INTELLIGENCE BENCHMARK")
    print("=" * 70)
    print(f"Target URL: {url}")
    print(f"Task Prompt: '{prompt}'")
    print("-" * 70)

    # 1. Local NLP Task Analysis
    analyzer = TaskAnalyzer()
    task_rep = analyzer.analyze_task(prompt)

    # 2. Extract DOM
    browser = PlaywrightAdapter()
    browser.start(headless=True)

    try:
        browser.navigate(url)
        raw_nodes, raw_formatted = browser.extract_dom()
        raw_count = len(raw_nodes)

        # 3. DOM Compression
        ranker = DOMRanker(target_top_k=100)
        t0 = time.time()
        filtered_nodes, metrics = ranker.rank_and_compress(raw_nodes, task_rep)
        ranking_ms = (time.time() - t0) * 1000

        print(f"\nMetric                          Before (Raw)     After (WebVeil)")
        print("-" * 70)
        print(f"DOM Elements Count              {raw_count:<16} {metrics.filtered_nodes}")
        print(f"Compression Ratio               0.0%             {metrics.compression_ratio}%")
        print(f"Estimated Tokens Saved          0                ~{metrics.estimated_tokens_saved}")
        print(f"DOM Ranking Latency             —                {ranking_ms:.2f} ms")
        print("-" * 70)

    finally:
        browser.stop()


if __name__ == "__main__":
    run_dom_compression_benchmark(
        url="https://www.amazon.in",
        prompt="Find three laptops under Rs 80000 with 16GB RAM and compare prices"
    )
