# Testing Documentation

This document describes the comprehensive test suite for the qsource3-mqtt project.

## Test Structure

The test suite is organized into several categories:

### Unit Tests

- `test_qsource3_logic.py` - Tests for the QSource3Logic class
- `test_qsource3_mqtt_client.py` - Tests for the QSource3MQTTClient class  
- `test_utils.py` - Tests for utility functions

### Integration Tests

- `test_integration.py` - End-to-end integration tests

## Running Tests

### Using the Test Runner

The project includes a custom test runner (`tests/run_tests.py`) that provides several options:

```bash
# Run all tests
python tests/run_tests.py

# Run only unit tests
python tests/run_tests.py --type unit

# Run only integration tests  
python tests/run_tests.py --type integration

# Run specific test class
python tests/run_tests.py --class TestQSource3Logic

# Run specific test method
python tests/run_tests.py --class TestQSource3Logic --method test_init
```

### Using unittest (built-in Python)

```bash
# Run all tests
python -m unittest discover tests -v

# Run specific test file
python -m unittest tests.test_qsource3_logic -v

# Run specific test class
python -m unittest tests.test_qsource3_logic.TestQSource3Logic -v

# Run specific test method
python -m unittest tests.test_qsource3_logic.TestQSource3Logic.test_init -v
```

### Using pytest (requires installation)

First install pytest and dependencies:

```bash
pip install -r requirements-test.txt
```

Then run tests:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=qsource3_mqtt --cov-report=html

# Run only unit tests
pytest tests/test_qsource3_logic.py tests/test_qsource3_mqtt_client.py tests/test_utils.py

# Run only integration tests
pytest tests/test_integration.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_qsource3_logic.py::TestQSource3Logic::test_init
```

## Test Coverage

The test suite provides comprehensive coverage of:

### QSource3Logic Class

- ✅ Initialization and configuration
- ✅ Connection handling and error recovery
- ✅ Device communication (mocked)
- ✅ Settings persistence (load/save)
- ✅ Property getters and setters
- ✅ Range management
- ✅ Calibration point validation
- ✅ Status reporting
- ✅ Error handling and exceptions

### QSource3MQTTClient Class

- ✅ Configuration loading and validation
- ✅ MQTT client setup and connection
- ✅ Message handling and routing
- ✅ Payload validation
- ✅ Command processing
- ✅ Response publishing
- ✅ Error handling and reporting
- ✅ Status publishing
- ✅ Connection lifecycle management

### Utility Functions

- ✅ Client ID generation
- ✅ UUID formatting and validation

### Integration Tests

- ✅ Complete client lifecycle
- ✅ Settings persistence across restarts  
- ✅ Command message flow
- ✅ Error handling integration
- ✅ Status publishing workflow
- ✅ Configuration validation

## Mocking Strategy

The tests use extensive mocking to isolate components and avoid dependencies on:

- **Hardware devices** - QSource3 driver and serial communication
- **Network services** - MQTT broker connections
- **File system** - Using temporary files for settings
- **Time-dependent operations** - Controlling timing for predictable tests

### Key Mocked Components

1. **QSource3Driver** - Hardware interface
2. **Quadrupole** - Mass filter logic
3. **paho.mqtt.Client** - MQTT communication
4. **File I/O operations** - Settings persistence
5. **Socket operations** - Network communication

## Test Data Management

Tests use:

- **Temporary files** for configuration and settings
- **Controlled mock data** for device responses  
- **Predefined test configurations** for various scenarios
- **Automatic cleanup** of test artifacts

## Best Practices Implemented

1. **Test Isolation** - Each test is independent and can run in any order
2. **Comprehensive Setup/Teardown** - Proper resource management
3. **Clear Test Names** - Descriptive method names indicating what is tested
4. **Multiple Assertion Types** - Testing both positive and negative cases
5. **Error Condition Testing** - Explicit testing of error paths
6. **Mock Verification** - Ensuring mocked methods are called correctly
7. **Edge Case Coverage** - Testing boundary conditions and invalid inputs

## Continuous Integration

The test suite is designed to run in CI/CD environments:

- **No external dependencies** required (everything mocked)
- **Fast execution** - Tests complete in seconds
- **Deterministic results** - No flaky time-dependent tests
- **Clear pass/fail criteria** - Proper exit codes and reporting

## Adding New Tests

When adding new functionality, follow these patterns:

### For Unit Tests

1. Create test class inheriting from `unittest.TestCase`
2. Add `setUp()` and `tearDown()` methods for test fixtures
3. Mock external dependencies  
4. Test both success and failure scenarios
5. Verify mock interactions with `assert_called_with()`

### For Integration Tests

1. Use temporary files for configuration
2. Mock hardware but test real component interactions
3. Test complete workflows end-to-end
4. Include error recovery scenarios

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`  
- Test methods: `test_<specific_behavior>`
- Helper methods: `_<helper_name>` (underscore prefix)

## Debugging Failed Tests

When tests fail:

1. **Check the test output** - Look for specific assertion failures
2. **Run with verbose mode** - Use `-v` flag for detailed output
3. **Run single test** - Isolate the failing test
4. **Check mock setup** - Verify mocks are configured correctly
5. **Add print statements** - Temporarily add debugging output
6. **Use debugger** - Set breakpoints in your IDE

Example debugging a specific test:

```bash
# Run with maximum verbosity
python -m unittest tests.test_qsource3_logic.TestQSource3Logic.test_init -v

# Or with pytest for better output
pytest tests/test_qsource3_logic.py::TestQSource3Logic::test_init -v -s
```

## Performance Considerations

The test suite is optimized for:

- **Fast execution** - All tests complete in under 30 seconds
- **Minimal resource usage** - No real hardware or network connections
- **Parallel execution support** - Tests can run concurrently if needed
- **Memory efficiency** - Proper cleanup prevents memory leaks

## Test Metrics

Target metrics for the test suite:

- **Code Coverage**: >90% line coverage
- **Test Execution Time**: <30 seconds total
- **Test Count**: 100+ individual test methods
- **Success Rate**: 100% pass rate in CI/CD
