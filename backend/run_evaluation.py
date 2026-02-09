#!/usr/bin/env python3
"""
Kanso.AI Evaluation Runner

Seed benchmark datasets and run Opik evaluation experiments
to systematically measure multi-agent pipeline quality.

Usage:
    # Seed the dataset only
    uv run python run_evaluation.py --seed-only

    # Run analyst experiment (fast, ~2 min)
    uv run python run_evaluation.py --experiment analyst

    # Run full pipeline experiment (slower, ~10-15 min)
    uv run python run_evaluation.py --experiment plan

    # Run both experiments
    uv run python run_evaluation.py --experiment all

    # Custom experiment name
    uv run python run_evaluation.py --experiment plan --name "baseline-v1"
"""

import argparse
import sys
import time


def main():
    parser = argparse.ArgumentParser(
        description="Kanso.AI Evaluation Runner — Opik Datasets & Experiments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --seed-only                    Seed benchmark dataset in Opik
  %(prog)s --experiment analyst            Run analyst clarification experiment
  %(prog)s --experiment plan               Run full pipeline plan quality experiment
  %(prog)s --experiment all                Run all experiments
  %(prog)s --experiment plan --name v2     Run with custom experiment name
        """
    )
    
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Only seed the benchmark dataset, don't run experiments"
    )
    parser.add_argument(
        "--experiment",
        choices=["plan", "analyst", "all"],
        default=None,
        help="Which experiment to run"
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="Custom experiment name (auto-generated if not provided)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Custom dataset name (uses benchmark dataset if not provided)"
    )
    
    args = parser.parse_args()
    
    if not args.seed_only and not args.experiment:
        parser.print_help()
        print("\n❌ Error: Specify --seed-only or --experiment")
        sys.exit(1)
    
    # Import after argparse so --help is fast
    from app.evaluation import (
        seed_benchmark_dataset,
        run_plan_quality_experiment,
        run_analyst_experiment,
        get_benchmark_dataset_info,
    )
    from app.opik_service import is_opik_enabled, get_dashboard_url, flush_traces
    
    # Check Opik is configured
    if not is_opik_enabled():
        print("❌ Opik is not configured. Set OPIK_API_KEY and OPIK_WORKSPACE in .env")
        sys.exit(1)
    
    print(f"📊 Opik Dashboard: {get_dashboard_url()}")
    print()
    
    # Always seed the dataset first
    print("=" * 60)
    print("📦 Step 1: Seeding Benchmark Dataset")
    print("=" * 60)
    
    info = get_benchmark_dataset_info()
    print(f"   Dataset: {info['name']}")
    print(f"   Items:   {info['total_items']}")
    print(f"   Difficulties: {info['difficulties']}")
    print(f"   Domains: {info['domains']}")
    print()
    
    success = seed_benchmark_dataset()
    if success:
        print("   ✅ Dataset seeded successfully")
    else:
        print("   ❌ Failed to seed dataset")
        sys.exit(1)
    
    if args.seed_only:
        print("\n✅ Done! Dataset is ready in Opik.")
        print(f"   View at: {get_dashboard_url()}")
        flush_traces()
        return
    
    # Run experiments
    print()
    
    if args.experiment in ("analyst", "all"):
        print("=" * 60)
        print("🔬 Experiment: Analyst Clarification Quality")
        print("=" * 60)
        
        exp_name = args.name or None  # auto-generated if not provided
        
        start = time.time()
        print("   Running analyst agent on each dataset item...")
        print("   (This runs the Analyst agent only — should take ~2-3 minutes)")
        print()
        
        result = run_analyst_experiment(
            experiment_name=exp_name,
            dataset_name=args.dataset,
        )
        
        elapsed = time.time() - start
        if result:
            print(f"\n   ✅ Analyst experiment complete in {elapsed:.1f}s")
        else:
            print(f"\n   ⚠️ Analyst experiment returned no result ({elapsed:.1f}s)")
        print()
    
    if args.experiment in ("plan", "all"):
        print("=" * 60)
        print("🔬 Experiment: Full Pipeline Plan Quality")
        print("=" * 60)
        
        exp_name = args.name or None  # auto-generated if not provided
        
        start = time.time()
        print("   Running full multi-agent pipeline on each dataset item...")
        print("   (This runs all 6 agents per item — may take 10-15 minutes)")
        print()
        
        result = run_plan_quality_experiment(
            experiment_name=exp_name,
            dataset_name=args.dataset,
        )
        
        elapsed = time.time() - start
        if result:
            print(f"\n   ✅ Plan quality experiment complete in {elapsed:.1f}s")
        else:
            print(f"\n   ⚠️ Plan quality experiment returned no result ({elapsed:.1f}s)")
        print()
    
    # Flush traces
    flush_traces()
    
    print("=" * 60)
    print("🎉 All experiments complete!")
    print(f"📊 View results at: {get_dashboard_url()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
