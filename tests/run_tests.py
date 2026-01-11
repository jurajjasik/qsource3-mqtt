"""
Test runner for qsource3-mqtt tests.

This module provides convenient ways to run all tests or specific test suites.
"""

import sys
import unittest
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_all_tests():
    """Run all tests in the test suite."""
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(str(start_dir), pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def run_unit_tests():
    """Run only unit tests (excluding integration tests)."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add specific unit test modules
    from tests.test_qsource3_logic import TestQSource3Logic
    from tests.test_qsource3_mqtt_client import (
        TestHandleConnectionErrorDecorator,
        TestQSource3MQTTClient,
    )
    from tests.test_utils import TestGenerateClientId

    # Add unit test classes
    suite.addTest(loader.loadTestsFromTestCase(TestQSource3Logic))
    suite.addTest(loader.loadTestsFromTestCase(TestQSource3MQTTClient))
    suite.addTest(loader.loadTestsFromTestCase(TestHandleConnectionErrorDecorator))
    suite.addTest(loader.loadTestsFromTestCase(TestGenerateClientId))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def run_integration_tests():
    """Run only integration tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    from tests.test_integration import TestQSource3MQTTIntegration

    suite.addTest(loader.loadTestsFromTestCase(TestQSource3MQTTIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def run_specific_test(test_class_name, test_method_name=None):
    """Run a specific test class or test method."""
    loader = unittest.TestLoader()

    # Import all test modules to make classes available
    from tests import (
        test_integration,
        test_qsource3_logic,
        test_qsource3_mqtt_client,
        test_utils,
    )

    # Find the test class
    test_class = None
    for module in [
        test_qsource3_logic,
        test_qsource3_mqtt_client,
        test_utils,
        test_integration,
    ]:
        if hasattr(module, test_class_name):
            test_class = getattr(module, test_class_name)
            break

    if not test_class:
        print(f"Test class '{test_class_name}' not found")
        return False

    if test_method_name:
        # Run specific test method
        suite = unittest.TestSuite()
        suite.addTest(test_class(test_method_name))
    else:
        # Run all tests in the class
        suite = loader.loadTestsFromTestCase(test_class)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run qsource3-mqtt tests")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration"],
        default="all",
        help="Type of tests to run (default: all)",
    )
    parser.add_argument(
        "--class",
        dest="test_class",
        help="Run tests for specific class (e.g., TestQSource3Logic)",
    )
    parser.add_argument(
        "--method",
        dest="test_method",
        help="Run specific test method (requires --class)",
    )

    args = parser.parse_args()

    success = False

    if args.test_class:
        success = run_specific_test(args.test_class, args.test_method)
    elif args.type == "unit":
        success = run_unit_tests()
    elif args.type == "integration":
        success = run_integration_tests()
    else:
        success = run_all_tests()

    if not success:
        sys.exit(1)

    print("\n✅ All tests passed!")
