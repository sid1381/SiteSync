#!/usr/bin/env python3
"""
Test script to verify semantic validation is catching workload/manageability questions
that incorrectly receive age data as answers.

This tests the fix for the bug where "Is the workload manageable?" returns "18-75 years"
instead of "Yes - based on site resources and staffing".
"""

import logging
from app.services.ai_question_mapper import AIQuestionMapper

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

def test_semantic_validation():
    """Test semantic validation catches age data in feasibility questions"""

    mapper = AIQuestionMapper()

    # Test cases: (question, bad_answer, expected_correction)
    test_cases = [
        # MAIN BUG: Workload/manageability questions getting age data
        ("Is the workload manageable?", "18-75 years", "Yes - based on site resources and staffing"),
        ("Is the study workload manageable for your site?", "18-65 years", "Yes - based on site resources and staffing"),
        ("Is this feasible for your team?", "Age range: 18-75 years", "Yes - based on site resources and staffing"),
        ("Is the timeline realistic?", "Patient age: 18-75 yrs", "Yes - based on site resources and staffing"),

        # Should also catch other feasibility keywords
        ("Is patient recruitment adequate?", "18-75 years", "Yes - based on site resources and staffing"),
        ("Do you have sufficient resources?", "Age: 18-75", "Yes - based on site resources and staffing"),
        ("Is the budget enough?", "18 years and older", "Yes - based on site resources and staffing"),

        # Valid answers should pass through unchanged
        ("Is the workload manageable?", "Yes - based on current staffing levels", None),  # No correction
        ("Is this feasible?", "No - would require additional staff", None),  # No correction
        ("Is it manageable?", "Partially - may need overtime", None),  # No correction

        # Age questions should get age data (not corrected)
        ("What is the patient age range?", "18-75 years", None),  # Correct answer for age question
        ("What age group is eligible?", "18-65 years", None),  # Correct answer for age question
    ]

    print("=" * 100)
    print("SEMANTIC VALIDATION TEST - Workload/Manageability Bug Fix")
    print("=" * 100)
    print()

    passed = 0
    failed = 0

    for i, (question, bad_answer, expected_correction) in enumerate(test_cases, 1):
        print(f"\nTest {i}/{len(test_cases)}")
        print(f"Question: {question}")
        print(f"Original Answer: {bad_answer}")

        # Run semantic validation
        corrected_answer, corrected_confidence, validation_note = mapper._validate_answer_semantics(
            question_text=question,
            answer=bad_answer,
            confidence=85.0
        )

        print(f"Corrected Answer: {corrected_answer}")
        print(f"Validation Note: {validation_note}")

        # Check if correction matches expected
        if expected_correction is None:
            # Should NOT be corrected
            if corrected_answer == bad_answer:
                print("✅ PASS - Answer correctly NOT changed")
                passed += 1
            else:
                print(f"❌ FAIL - Answer should NOT have been changed")
                print(f"   Expected: {bad_answer}")
                print(f"   Got: {corrected_answer}")
                failed += 1
        else:
            # Should BE corrected
            if corrected_answer == expected_correction:
                print("✅ PASS - Answer correctly changed")
                passed += 1
            else:
                print(f"❌ FAIL - Answer not corrected as expected")
                print(f"   Expected: {expected_correction}")
                print(f"   Got: {corrected_answer}")
                failed += 1

        print("-" * 100)

    print()
    print("=" * 100)
    print(f"RESULTS: {passed}/{len(test_cases)} tests passed, {failed} failed")
    print("=" * 100)

    if failed == 0:
        print("✅ ALL TESTS PASSED - Semantic validation is working correctly!")
    else:
        print(f"❌ {failed} TEST(S) FAILED - Semantic validation needs fixes")

    return failed == 0

if __name__ == "__main__":
    success = test_semantic_validation()
    exit(0 if success else 1)
