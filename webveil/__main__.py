"""
WebVeil CLI Entry Point.
Usage: python -m webveil --task "..." --url "..." [--provider gemini] [--scenario kyc]
"""

import argparse
import sys
import json
import logging
import threading
import time
import webbrowser

from webveil.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WebVeil")


def main():
    parser = argparse.ArgumentParser(
        description="WebVeil — Privacy-Preserving Browser Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m webveil --scenario kyc
  python -m webveil --scenario visual
  python -m webveil --task "Search Wikipedia for ISRO" --url "https://wikipedia.org"
  python -m webveil --task "Fill this form" --url "http://localhost:8080/index.html" --provider mock
        """,
    )
    parser.add_argument("--task", type=str, help="Natural language task description")
    parser.add_argument("--url", type=str, help="Starting URL")
    parser.add_argument("--scenario", type=str, choices=["kyc", "web", "visual"],
                        help="Run a predefined demo scenario")
    parser.add_argument("--provider", type=str, default=None,
                        help="Reasoning provider: gemini, openai, ollama, mock")
    parser.add_argument("--headless", action="store_true", help="Run browser headlessly")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable web dashboard")
    parser.add_argument("--max-steps", type=int, default=None, help="Maximum agent steps")

    args = parser.parse_args()

    # Override config with CLI args
    if args.provider:
        config.provider = args.provider
    if args.headless:
        config.headless = True
    if args.max_steps:
        config.max_steps = args.max_steps

    # Resolve scenario or custom task
    if args.scenario:
        from webveil.demos.scenarios import get_scenario
        scenario = get_scenario(args.scenario)
        task = scenario["task"]
        url = scenario["url"]
        setup_fn = scenario.get("setup")
        if setup_fn:
            setup_fn()
    elif args.task and args.url:
        task = args.task
        url = args.url
    else:
        parser.print_help()
        print("\nError: Provide either --scenario or both --task and --url")
        sys.exit(1)

    # Start dashboard if enabled
    dashboard_events = []
    event_lock = threading.Lock()

    def on_event(event):
        with event_lock:
            dashboard_events.append(event)

    dashboard_thread = None
    if not args.no_dashboard:
        try:
            from webveil.dashboard.server import start_dashboard_server
            dashboard_thread = threading.Thread(
                target=start_dashboard_server,
                args=(config.dashboard_port, dashboard_events, event_lock),
                daemon=True,
            )
            dashboard_thread.start()
            time.sleep(0.5)
            dashboard_url = f"http://localhost:{config.dashboard_port}"
            logger.info(f"Dashboard: {dashboard_url}")
            webbrowser.open(dashboard_url)
        except Exception as e:
            logger.warning(f"Dashboard failed to start: {e}")

    # Run agent
    from webveil.agent_loop import WebVeilAgent

    agent = WebVeilAgent(
        max_steps=config.max_steps,
        headless=config.headless,
        provider_name=config.provider,
        on_event=on_event,
    )

    result = agent.run_task(start_url=url, task=task)
    sih = result["sih_report"]

    # Print results
    print("\n" + "=" * 70)
    print("WEBVEIL V1 EXECUTION REPORT")
    print("=" * 70)
    print(f"Status:    {result['status']}")
    print(f"Provider:  {result['provider']}")
    print(f"Steps:     {result['steps']}")
    print(f"PII Found: {result['pii_detected_count']}")
    print(f"LLM Calls: {result['token_usage']['total_calls']}")
    print(f"Tokens:    {result['token_usage']['input']} in / {result['token_usage']['output']} out")

    print("\n" + "-" * 70)
    print("SIH 26171 EVALUATION METRICS")
    print("-" * 70)
    print(f"1. Visual Context Accuracy    (25%): {sih.visual_accuracy}%")
    print(f"2. PII Detection F1 Score     (20%): {sih.pii_f1_score}%  (P: {sih.pii_precision}%, R: {sih.pii_recall}%)")
    print(f"3. Redaction Precision        (20%): {sih.redaction_precision}%")
    print(f"4. Resource Utilization Score  (20%): {sih.resource_score}%")
    print(f"   Python RSS: {sih.python_memory_mb}MB | Chromium RSS: {sih.chromium_memory_mb}MB | Peak: {sih.combined_peak_memory_mb}MB")
    print(f"5. Latency Score              (15%): {sih.latency_score}%  ({sih.end_to_end_latency_ms:.0f}ms)")
    print("-" * 70)
    print(f"OVERALL SIH SCORE: {sih.overall_sih_score}% / 100%")
    print("=" * 70)

    # Keep dashboard alive for viewing
    if dashboard_thread and dashboard_thread.is_alive():
        print(f"\nDashboard running at http://localhost:{config.dashboard_port}")
        print("Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
