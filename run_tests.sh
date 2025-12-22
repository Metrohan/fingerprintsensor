#!/bin/bash
# Test runner script for fingerprint attendance system

echo "======================================"
echo "Fingerprint Attendance System Tests"
echo "======================================"
echo ""

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(dirname $0)"

# Run tests
python3 tests/test_app.py

# Capture exit code
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ All tests passed!"
else
    echo "✗ Some tests failed!"
fi

exit $EXIT_CODE
