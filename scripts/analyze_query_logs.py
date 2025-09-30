#!/usr/bin/env python3
"""
Query Log Analysis Script
Analyzes logged queries and generates insights for improvement
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.query_logger import query_logger
from colorama import Fore, Style, init
from collections import Counter

init(autoreset=True)


def print_section(title):
    """Print formatted section header"""
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}{title}")
    print(f"{Fore.MAGENTA}{'='*70}\n")


def analyze_statistics():
    """Display overall statistics"""
    print_section("OVERALL STATISTICS")

    stats = query_logger.get_statistics()

    print(f"{Fore.WHITE}Total Queries: {Fore.CYAN}{stats.get('total_queries', 0)}")
    print(f"{Fore.WHITE}Failed Queries: {Fore.RED}{stats.get('failed_queries', 0)}")
    print(f"{Fore.WHITE}Success Rate: {Fore.GREEN}{stats.get('success_rate', 0):.1f}%")
    print(f"{Fore.WHITE}Avg Confidence: {Fore.YELLOW}{stats.get('avg_confidence', 0):.2f}")
    print(f"{Fore.WHITE}Avg Response Time: {Fore.YELLOW}{stats.get('avg_response_time', 0):.2f}s")

    # Intent distribution
    print(f"\n{Fore.CYAN}Intent Distribution:")
    for intent, count in stats.get('intent_distribution', {}).items():
        print(f"  {Fore.WHITE}{intent}: {Fore.YELLOW}{count}")

    # Tool distribution
    print(f"\n{Fore.CYAN}Tool Distribution:")
    for tool, count in sorted(stats.get('tool_distribution', {}).items(), key=lambda x: x[1], reverse=True):
        print(f"  {Fore.WHITE}{tool}: {Fore.YELLOW}{count}")


def analyze_failed_queries():
    """Analyze and display failed queries"""
    print_section("FAILED QUERIES ANALYSIS")

    failed = query_logger.get_failed_queries(limit=100)

    if not failed:
        print(f"{Fore.GREEN}No failed queries found! System is working perfectly.")
        return

    print(f"{Fore.RED}Found {len(failed)} failed queries\n")

    # Group by error type
    error_counts = Counter()
    for query in failed:
        error = query.get('error', 'Unknown error')
        error_counts[error] += 1

    print(f"{Fore.YELLOW}Errors by Type:")
    for error, count in error_counts.most_common(10):
        print(f"  {Fore.WHITE}[{count}x] {Fore.RED}{error}")

    # Show recent failed queries
    print(f"\n{Fore.YELLOW}Recent Failed Queries (last 10):")
    for i, query in enumerate(failed[-10:], 1):
        print(f"\n{Fore.CYAN}{i}. Question: {Fore.WHITE}{query['question']}")
        print(f"   {Fore.RED}Error: {query.get('error', 'Unknown')}")
        print(f"   {Fore.YELLOW}Tool: {query.get('tool_used', 'N/A')}")
        print(f"   {Fore.YELLOW}Confidence: {query.get('confidence', 0):.2f}")
        print(f"   {Fore.YELLOW}Time: {query['timestamp']}")


def analyze_low_confidence():
    """Analyze queries with low confidence scores"""
    print_section("LOW CONFIDENCE QUERIES")

    low_conf = query_logger.get_low_confidence_queries(threshold=0.5, limit=100)

    if not low_conf:
        print(f"{Fore.GREEN}No low-confidence queries found!")
        return

    print(f"{Fore.YELLOW}Found {len(low_conf)} queries with confidence < 0.5\n")

    # Show success rate for low-confidence queries
    success_count = sum(1 for q in low_conf if q.get('success', False))
    success_rate = (success_count / len(low_conf) * 100) if low_conf else 0

    print(f"{Fore.WHITE}Success Rate: {Fore.YELLOW}{success_rate:.1f}% ({success_count}/{len(low_conf)})")

    # Show recent low-confidence queries
    print(f"\n{Fore.YELLOW}Recent Low-Confidence Queries (last 10):")
    for i, query in enumerate(low_conf[-10:], 1):
        status = f"{Fore.GREEN}✓" if query.get('success') else f"{Fore.RED}✗"
        print(f"\n{status} {Fore.CYAN}{i}. Question: {Fore.WHITE}{query['question']}")
        print(f"   {Fore.YELLOW}Confidence: {query.get('confidence', 0):.2f}")
        print(f"   {Fore.YELLOW}Tool: {query.get('tool_used', 'N/A')}")
        if query.get('answer'):
            answer = query['answer'][:100] + "..." if len(query['answer']) > 100 else query['answer']
            print(f"   {Fore.WHITE}Answer: {answer}")


def analyze_response_quality():
    """Analyze response quality metrics"""
    print_section("RESPONSE QUALITY ANALYSIS")

    import json
    from pathlib import Path

    log_file = Path("query_logs/success_queries.jsonl")

    if not log_file.exists():
        print(f"{Fore.YELLOW}No success queries logged yet.")
        return

    queries = []
    with open(log_file, 'r') as f:
        for line in f:
            queries.append(json.loads(line))

    if not queries:
        print(f"{Fore.YELLOW}No success queries found.")
        return

    print(f"{Fore.WHITE}Total Successful Queries: {Fore.GREEN}{len(queries)}\n")

    # Response time distribution
    response_times = [q['response_time'] for q in queries if 'response_time' in q]
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)

        print(f"{Fore.CYAN}Response Time Distribution:")
        print(f"  {Fore.WHITE}Average: {Fore.YELLOW}{avg_time:.2f}s")
        print(f"  {Fore.WHITE}Min: {Fore.GREEN}{min_time:.2f}s")
        print(f"  {Fore.WHITE}Max: {Fore.RED}{max_time:.2f}s")

    # Confidence distribution
    confidences = [q['confidence'] for q in queries if 'confidence' in q]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)

        print(f"\n{Fore.CYAN}Confidence Distribution:")
        print(f"  {Fore.WHITE}Average: {Fore.YELLOW}{avg_conf:.2f}")

        # Group by confidence ranges
        high_conf = sum(1 for c in confidences if c >= 0.8)
        med_conf = sum(1 for c in confidences if 0.5 <= c < 0.8)
        low_conf = sum(1 for c in confidences if c < 0.5)

        total = len(confidences)
        print(f"  {Fore.GREEN}High (≥0.8): {high_conf} ({high_conf/total*100:.1f}%)")
        print(f"  {Fore.YELLOW}Medium (0.5-0.8): {med_conf} ({med_conf/total*100:.1f}%)")
        print(f"  {Fore.RED}Low (<0.5): {low_conf} ({low_conf/total*100:.1f}%)")


def export_training_data():
    """Export data for fine-tuning"""
    print_section("EXPORT FINE-TUNING DATA")

    output_file = query_logger.export_for_finetuning()

    if output_file:
        print(f"{Fore.GREEN}✓ Fine-tuning data exported successfully!")
        print(f"{Fore.WHITE}Location: {Fore.CYAN}{output_file}")

        # Count lines
        from pathlib import Path
        if Path(output_file).exists():
            with open(output_file, 'r') as f:
                count = sum(1 for _ in f)
            print(f"{Fore.WHITE}Training Examples: {Fore.CYAN}{count}")
    else:
        print(f"{Fore.RED}✗ Failed to export fine-tuning data")


def show_recommendations():
    """Show recommendations based on analysis"""
    print_section("RECOMMENDATIONS")

    stats = query_logger.get_statistics()
    failed = query_logger.get_failed_queries(limit=100)
    low_conf = query_logger.get_low_confidence_queries(threshold=0.5, limit=100)

    total = stats.get('total_queries', 0)
    success_rate = stats.get('success_rate', 0)
    avg_conf = stats.get('avg_confidence', 0)

    recommendations = []

    # Success rate recommendations
    if success_rate < 80:
        recommendations.append(
            f"{Fore.RED}⚠ Success rate is {success_rate:.1f}% (target: >95%)\n"
            f"   → Review failed queries and improve error handling"
        )
    elif success_rate < 95:
        recommendations.append(
            f"{Fore.YELLOW}⚠ Success rate is {success_rate:.1f}% (target: >95%)\n"
            f"   → Minor improvements needed"
        )
    else:
        recommendations.append(
            f"{Fore.GREEN}✓ Success rate is excellent ({success_rate:.1f}%)"
        )

    # Confidence recommendations
    if avg_conf < 0.6:
        recommendations.append(
            f"{Fore.RED}⚠ Average confidence is low ({avg_conf:.2f})\n"
            f"   → Improve keyword matching or LLM prompts"
        )
    elif avg_conf < 0.8:
        recommendations.append(
            f"{Fore.YELLOW}⚠ Average confidence is moderate ({avg_conf:.2f})\n"
            f"   → Consider fine-tuning for better confidence"
        )
    else:
        recommendations.append(
            f"{Fore.GREEN}✓ Average confidence is good ({avg_conf:.2f})"
        )

    # Training data recommendations
    if total < 100:
        recommendations.append(
            f"{Fore.YELLOW}⚠ Only {total} queries logged (target: >500)\n"
            f"   → Run more tests to collect training data"
        )
    elif total < 500:
        recommendations.append(
            f"{Fore.YELLOW}⚠ {total} queries logged (target: >500)\n"
            f"   → Collect more queries for better fine-tuning"
        )
    else:
        recommendations.append(
            f"{Fore.GREEN}✓ Sufficient queries for fine-tuning ({total})"
        )

    # Failed query recommendations
    if failed:
        error_types = set(q.get('error', 'Unknown') for q in failed)
        recommendations.append(
            f"{Fore.YELLOW}⚠ {len(failed)} failed queries found\n"
            f"   → Focus on fixing: {list(error_types)[:3]}"
        )

    # Low confidence recommendations
    if low_conf:
        recommendations.append(
            f"{Fore.YELLOW}⚠ {len(low_conf)} low-confidence queries\n"
            f"   → Review and improve keyword matching"
        )

    # Print all recommendations
    for rec in recommendations:
        print(rec)

    # Overall recommendation
    print(f"\n{Fore.CYAN}Next Steps:")
    if total >= 500 and success_rate >= 95:
        print(f"{Fore.GREEN}→ Ready to fine-tune! Run: python train_flan_t5.py")
    elif total < 500:
        print(f"{Fore.YELLOW}→ Collect more queries: python tests/extensive_test.py")
    else:
        print(f"{Fore.YELLOW}→ Fix failed queries before fine-tuning")


def main():
    """Main analysis function"""
    print(f"{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}QUERY LOG ANALYSIS")
    print(f"{Fore.MAGENTA}{'='*70}\n")

    # Run all analyses
    analyze_statistics()
    analyze_failed_queries()
    analyze_low_confidence()
    analyze_response_quality()
    show_recommendations()

    # Export option
    print(f"\n{Fore.CYAN}Export fine-tuning data? (y/n): ", end="")
    try:
        response = input().strip().lower()
        if response == 'y':
            export_training_data()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Skipped export.")


if __name__ == "__main__":
    main()