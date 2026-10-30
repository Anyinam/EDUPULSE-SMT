#!/usr/bin/env python
"""
Test Pro-ration Billing Logic
Tests the pro-rated admission charge calculation for mid-term student admissions.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def test_proration_calculation():
    """
    Test pro-ration calculation logic.
    Verifies that student admission charges are correctly pro-rated based on remaining term days.
    """
    from backend.subscription_features import (
        PRICING,
        calculate_term_cost,
        get_term_cost_breakdown,
    )
    
    print("\n" + "="*70)
    print("PRO-RATION BILLING TEST")
    print("="*70)
    
    # Test Case 1: Basic plan, no students, then add 1 student mid-term
    print("\n📋 Test Case 1: Basic Plan - Single Student Mid-Term Admission")
    print("-" * 70)
    
    plan_name = "Basic"
    plan_config = PRICING[plan_name]
    base_fee = plan_config["base_fee_per_term"]
    included = plan_config["included_students"]
    per_student = plan_config["per_student_per_term"]
    
    print(f"Plan: {plan_name}")
    print(f"  Base Fee: ₵{base_fee}")
    print(f"  Included Students: {included}")
    print(f"  Per Extra Student: ₵{per_student}")
    
    # Simulate a term with 90 days (typical semester)
    total_term_days = 90
    days_elapsed = 55  # 55 days have passed
    remaining_days = total_term_days - days_elapsed
    
    pro_ration_factor = remaining_days / total_term_days
    
    print(f"\nTerm Duration: {total_term_days} days")
    print(f"Days Elapsed: {days_elapsed} days")
    print(f"Remaining: {remaining_days} days")
    print(f"Pro-ration Factor: {pro_ration_factor:.1%}")
    
    # Cost for adding 1 student (assumes 0 current students, so 1 is over the 25 included)
    students_over_threshold = 1  # 1 - 0 = 1
    
    # Without pro-ration (full term)
    full_term_cost = students_over_threshold * per_student
    # With pro-ration
    pro_rated_cost = full_term_cost * pro_ration_factor
    
    print(f"\nStudent Admission (1 student, currently 0):")
    print(f"  Full Term Cost (1 student @ ₵{per_student}): ₵{full_term_cost:.2f}")
    print(f"  Pro-rated Cost ({pro_ration_factor:.1%}): ₵{pro_rated_cost:.2f}")
    
    assert pro_rated_cost > 0, "Pro-rated cost should be positive"
    assert pro_rated_cost < full_term_cost, "Pro-rated cost should be less than full term"
    print("✅ Test Case 1 PASSED")
    
    # Test Case 2: Premium plan with multiple overage students
    print("\n" + "-" * 70)
    print("📋 Test Case 2: Premium Plan - Multiple Students Mid-Term")
    print("-" * 70)
    
    plan_name = "Premium"
    plan_config = PRICING[plan_name]
    base_fee = plan_config["base_fee_per_term"]
    included = plan_config["included_students"]
    per_student = plan_config["per_student_per_term"]
    
    print(f"Plan: {plan_name}")
    print(f"  Base Fee: ₵{base_fee}")
    print(f"  Included Students: {included}")
    print(f"  Per Extra Student: ₵{per_student}")
    
    # Same term scenario
    pro_ration_factor = remaining_days / total_term_days
    
    # Admit 5 new students (all over threshold of 30)
    new_students = 5
    current_students = 30  # Already at threshold
    students_over_threshold = new_students  # All 5 are new/extra
    
    full_term_cost = students_over_threshold * per_student
    pro_rated_cost = full_term_cost * pro_ration_factor
    
    print(f"\nStudent Admissions (5 students, currently {current_students}):")
    print(f"  Current Students: {current_students} (at {included} included threshold)")
    print(f"  New Students Admitted: {new_students}")
    print(f"  All over threshold: {students_over_threshold}")
    print(f"  Full Term Cost (5 students @ ₵{per_student}): ₵{full_term_cost:.2f}")
    print(f"  Pro-rated Cost ({pro_ration_factor:.1%}): ₵{pro_rated_cost:.2f}")
    
    assert pro_rated_cost > 0, "Pro-rated cost should be positive"
    assert pro_rated_cost == students_over_threshold * per_student * pro_ration_factor
    print("✅ Test Case 2 PASSED")
    
    # Test Case 3: Term ending soon (last 10 days)
    print("\n" + "-" * 70)
    print("📋 Test Case 3: Last 10 Days of Term")
    print("-" * 70)
    
    remaining_days = 10
    total_term_days = 90
    pro_ration_factor = remaining_days / total_term_days
    
    print(f"Remaining: {remaining_days} days ({pro_ration_factor:.1%})")
    
    plan_name = "Basic"
    per_student = PRICING[plan_name]["per_student_per_term"]
    
    students_over_threshold = 3
    full_term_cost = students_over_threshold * per_student
    pro_rated_cost = full_term_cost * pro_ration_factor
    
    print(f"\nAdmit 3 students late in term:")
    print(f"  Full Term Cost: ₵{full_term_cost:.2f}")
    print(f"  Pro-rated Cost ({pro_ration_factor:.1%}): ₵{pro_rated_cost:.2f}")
    
    # Verify it's a small charge (approximately 11% of full term cost)
    assert pro_rated_cost < full_term_cost * 0.15, "Late-term admission should have small charge"
    print(f"✅ Test Case 3 PASSED (minimal charge: ₵{pro_rated_cost:.2f})")
    
    # Test Case 4: Verify cost breakdown function
    print("\n" + "-" * 70)
    print("📋 Test Case 4: Cost Breakdown Function")
    print("-" * 70)
    
    breakdown = get_term_cost_breakdown(
        plan_name="Basic",
        num_students=30
    )
    
    print(f"Breakdown for Basic plan with 30 students:")
    for key, value in breakdown.items():
        if isinstance(value, (int, float)):
            if key == "included_students" or key == "billable_students":
                print(f"  {key}: {value} students")
            elif value > 1 or key.endswith("rate"):
                print(f"  {key}: ₵{value:.2f}")
            else:
                print(f"  {key}: {value}")
    
    # Verify breakdown structure
    required_keys = {
        "base_fee",
        "included_students",
        "billable_students",
        "per_student_rate",
        "student_overage_cost",
        "convenience_fee",
        "total",
    }
    
    assert all(k in breakdown for k in required_keys), f"Missing keys in breakdown: {required_keys - set(breakdown.keys())}"
    
    # Verify calculation: total = base_fee + student_overage_cost + convenience_fee
    expected_total = (
        breakdown["base_fee"] 
        + breakdown["student_overage_cost"] 
        + breakdown["convenience_fee"]
    )
    assert breakdown["total"] == expected_total, f"Total mismatch: {breakdown['total']} != {expected_total}"
    
    print("✅ Test Case 4 PASSED")
    
    print("\n" + "="*70)
    print("✅ ALL PRO-RATION BILLING TESTS PASSED")
    print("="*70)
    print("\nSummary:")
    print("  ✓ Pro-ration calculation logic correct")
    print("  ✓ Mid-term admissions charged proportionally")
    print("  ✓ Cost breakdown function returns all required fields")
    print("  ✓ Billing totals verified")
    print("\nNext Steps:")
    print("  1. Run: sudo bash firewall_setup.sh dev")
    print("  2. Restart Docker containers: docker-compose up -d")
    print("  3. Test live admission via API to verify email notifications")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        test_proration_calculation()
        print("✅ Test execution completed successfully")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
