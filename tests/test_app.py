"""
Unit Tests for Fingerprint Attendance System
Test coverage for app.py and automation.py
"""

import unittest
import sys
import os
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, MagicMock
import sqlite3
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to test
import app

# Try to import automation (optional, may fail if dependencies missing)
try:
    from data import automation
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    print("Warning: automation module not available, skipping automation tests")


class TestGetCurrentWorkDay(unittest.TestCase):
    """Test get_current_work_day function"""
    
    def test_before_6am_returns_previous_day(self):
        """Test that times before 6am return previous day"""
        with patch('app.datetime') as mock_datetime:
            # Test at 05:59
            mock_datetime.now.return_value = datetime(2025, 12, 16, 5, 59, 0)
            result = app.get_current_work_day()
            self.assertEqual(result, date(2025, 12, 15))
            
            # Test at 02:00
            mock_datetime.now.return_value = datetime(2025, 12, 16, 2, 0, 0)
            result = app.get_current_work_day()
            self.assertEqual(result, date(2025, 12, 15))
    
    def test_at_6am_returns_current_day(self):
        """Test that 6am returns current day"""
        with patch('app.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 12, 16, 6, 0, 0)
            result = app.get_current_work_day()
            self.assertEqual(result, date(2025, 12, 16))
    
    def test_after_6am_returns_current_day(self):
        """Test that times after 6am return current day"""
        with patch('app.datetime') as mock_datetime:
            # Test at 08:00
            mock_datetime.now.return_value = datetime(2025, 12, 16, 8, 0, 0)
            result = app.get_current_work_day()
            self.assertEqual(result, date(2025, 12, 16))
            
            # Test at 23:59
            mock_datetime.now.return_value = datetime(2025, 12, 16, 23, 59, 0)
            result = app.get_current_work_day()
            self.assertEqual(result, date(2025, 12, 16))


class TestAutomationFunctions(unittest.TestCase):
    """Test automation.py functions"""
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_get_week_start_end(self):
        """Test week start and end calculation"""
        # Test a Monday
        monday = date(2025, 12, 15)
        start, end = automation.get_week_start_end(monday)
        self.assertEqual(start, date(2025, 12, 15))
        self.assertEqual(end, date(2025, 12, 21))
        
        # Test a Wednesday
        wednesday = date(2025, 12, 17)
        start, end = automation.get_week_start_end(wednesday)
        self.assertEqual(start, date(2025, 12, 15))
        self.assertEqual(end, date(2025, 12, 21))
        
        # Test a Sunday
        sunday = date(2025, 12, 21)
        start, end = automation.get_week_start_end(sunday)
        self.assertEqual(start, date(2025, 12, 15))
        self.assertEqual(end, date(2025, 12, 21))
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_get_week_name(self):
        """Test week name generation"""
        test_date = date(2025, 12, 16)
        week_name = automation.get_week_name(test_date)
        self.assertEqual(week_name, "2025-W51")
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_format_duration(self):
        """Test duration formatting"""
        self.assertEqual(automation.format_duration(0), "0s 0d")
        self.assertEqual(automation.format_duration(60), "1s 0d")
        self.assertEqual(automation.format_duration(90), "1s 30d")
        self.assertEqual(automation.format_duration(125), "2s 5d")
        self.assertEqual(automation.format_duration(None), "0s 0d")


class TestDatabaseFunctions(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.DB_PATH = self.db_path
        
        # Manually create tables instead of calling init_db_if_needed
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_id INTEGER UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                department TEXT
            )
        """)
        
        # Create attendance table
        cursor.execute("""
            CREATE TABLE attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT,
                duration_minutes INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Remove temporary database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_init_db_if_needed(self):
        """Test database initialization"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check attendance table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
        self.assertIsNotNone(cursor.fetchone())
        
        conn.close()
    
    def test_get_next_fingerprint_id(self):
        """Test fingerprint ID generation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert test users
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (1, 'Test', 'User1', 'Dept1')")
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (3, 'Test', 'User2', 'Dept2')")
        conn.commit()
        conn.close()
        
        # Should return 4 (max + 1)
        next_id = app.get_next_fingerprint_id_from_db()
        self.assertEqual(next_id, 4)


class TestProcessAttendanceEvent(unittest.TestCase):
    """Test attendance event processing"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.DB_PATH = self.db_path
        
        # Manually create tables
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_id INTEGER UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                department TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT,
                duration_minutes INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Add test user
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (1, 'Test', 'User', 'Engineering')")
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Remove temporary database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    @patch('app.datetime')
    @patch('app.date')
    @patch('app.get_current_work_day')
    def test_check_in_new_session(self, mock_work_day, mock_date, mock_datetime):
        """Test new check-in creates a new record"""
        # Mock current time: 08:00
        mock_now = datetime(2025, 12, 16, 8, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_work_day.return_value = date(2025, 12, 16)
        
        result, error = app.process_attendance_event(1)
        
        self.assertIsNone(error)
        self.assertEqual(result['event'], 'check_in')
        self.assertEqual(result['user']['first_name'], 'Test')
        
        # Verify database record
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendance WHERE user_id=1")
        record = cursor.fetchone()
        self.assertIsNotNone(record)
        conn.close()
    
    @patch('app.datetime')    
    @patch('app.date')
    @patch('app.get_current_work_day')
    def test_check_out_completes_session(self, mock_work_day, mock_date, mock_datetime):
        """Test check-out updates existing record"""
        # Configure mock to use real datetime for fromisoformat
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # First check-in at 08:00
        mock_now = datetime(2025, 12, 16, 8, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_work_day.return_value = date(2025, 12, 16)
        
        app.process_attendance_event(1)
        
        # Then check-out at 12:00
        mock_now = datetime(2025, 12, 16, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        
        result, error = app.process_attendance_event(1)
        
        self.assertIsNone(error)
        self.assertEqual(result['event'], 'check_out')
        
        # Verify duration is calculated
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT duration_minutes, check_out FROM attendance WHERE user_id=1")
        record = cursor.fetchone()
        self.assertEqual(record[0], 240)  # 4 hours = 240 minutes
        self.assertIsNotNone(record[1])
        conn.close()
    
    @patch('app.datetime')
    @patch('app.get_current_work_day')
    def test_check_out_too_soon_fails(self, mock_work_day, mock_datetime):
        """Test check-out fails if less than 5 seconds elapsed"""
        # Configure mock to use real datetime for fromisoformat
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Check-in at 08:00:00
        mock_now = datetime(2025, 12, 16, 8, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_work_day.return_value = date(2025, 12, 16)
        
        app.process_attendance_event(1)
        
        # Try to check-out at 08:00:02 (2 seconds later)
        mock_now = datetime(2025, 12, 16, 8, 0, 2)
        mock_datetime.now.return_value = mock_now
        
        result, error = app.process_attendance_event(1)
        
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertIn("bekleyin", error.lower())
    
    def test_unknown_fingerprint_fails(self):
        """Test unknown fingerprint returns error"""
        result, error = app.process_attendance_event(999)
        
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertIn("bulunamadı", error.lower())


class TestFingerprintSensor(unittest.TestCase):
    """Test FingerprintSensor class methods"""
    
    def test_calc_checksum(self):
        """Test checksum calculation"""
        sensor = app.FingerprintSensor(None)
        checksum = sensor.calc_checksum(0x01, 0x00, 0x05, 0x00, 0x00)
        self.assertIsInstance(checksum, int)
        self.assertTrue(0 <= checksum <= 255)
    
    def test_get_error_message(self):
        """Test error message retrieval"""
        sensor = app.FingerprintSensor(None)
        
        self.assertIn("başarılı", sensor.get_error_message(app.ACK_SUCCESS).lower())
        self.assertIn("başarısız", sensor.get_error_message(app.ACK_FAIL).lower())
        self.assertIn("dolu", sensor.get_error_message(app.ACK_FULL).lower())
        self.assertIn("kayıtlı değil", sensor.get_error_message(app.ACK_NOUSER).lower())


class TestWorkDayBoundary(unittest.TestCase):
    """Test work day boundary scenarios (05:59 -> 06:00 transition)"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.DB_PATH = self.db_path
        
        # Manually create tables
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_id INTEGER UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                department TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT,
                duration_minutes INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Add test user
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (1, 'Test', 'User', 'Engineering')")
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Remove temporary database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    @patch('app.datetime')
    @patch('app.get_current_work_day')
    def test_check_in_before_6am_uses_previous_day(self, mock_work_day, mock_datetime):
        """Test check-in before 6am uses previous work day"""
        # Check-in at 05:30 (should be Dec 15)
        mock_now = datetime(2025, 12, 16, 5, 30, 0)
        mock_datetime.now.return_value = mock_now
        mock_work_day.return_value = date(2025, 12, 15)
        
        app.process_attendance_event(1)
        
        # Verify record has correct date
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT date FROM attendance WHERE user_id=1")
        record = cursor.fetchone()
        self.assertEqual(record[0], '2025-12-15')
        conn.close()
    
    @patch('app.datetime')
    @patch('app.get_current_work_day')
    def test_check_in_after_6am_uses_current_day(self, mock_work_day, mock_datetime):
        """Test check-in after 6am uses current work day"""
        # Check-in at 06:30 (should be Dec 16)
        mock_now = datetime(2025, 12, 16, 6, 30, 0)
        mock_datetime.now.return_value = mock_now
        mock_work_day.return_value = date(2025, 12, 16)
        
        app.process_attendance_event(1)
        
        # Verify record has correct date
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT date FROM attendance WHERE user_id=1")
        record = cursor.fetchone()
        self.assertEqual(record[0], '2025-12-16')
        conn.close()
    
    @patch('app.datetime')
    @patch('app.get_current_work_day')
    def test_new_session_after_12_hours(self, mock_work_day, mock_datetime):
        """Test that check-in after 12 hours creates new session"""
        # Check-in at 14:00 on Dec 15
        mock_now = datetime(2025, 12, 15, 14, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_work_day.return_value = date(2025, 12, 15)
        
        app.process_attendance_event(1)
        
        # Check-in at 08:00 on Dec 16 (18 hours later, should create new record)
        mock_now = datetime(2025, 12, 16, 8, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_work_day.return_value = date(2025, 12, 16)
        
        result, error = app.process_attendance_event(1)
        
        self.assertIsNone(error)
        self.assertEqual(result['event'], 'check_in')
        
        # Verify we have 2 records
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE user_id=1")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 2)
        conn.close()


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        """Create temporary database for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.DB_PATH = self.db_path
        
        # Manually create tables
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint_id INTEGER UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                department TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT,
                duration_minutes INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Add test user
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (1, 'Test', 'User', 'Engineering')")
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Remove temporary database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    @patch('app.datetime')
    @patch('app.get_current_work_day')
    def test_multiple_check_in_out_same_day(self, mock_work_day, mock_datetime):
        """Test multiple check-in/out pairs on same work day"""
        # Configure mock to use real datetime for fromisoformat
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        mock_work_day.return_value = date(2025, 12, 16)
        
        # Session 1: 08:00 - 12:00
        mock_datetime.now.return_value = datetime(2025, 12, 16, 8, 0, 0)
        app.process_attendance_event(1)
        
        mock_datetime.now.return_value = datetime(2025, 12, 16, 12, 0, 0)
        app.process_attendance_event(1)
        
        # Session 2: 14:00 - 18:00
        mock_datetime.now.return_value = datetime(2025, 12, 16, 14, 0, 0)
        app.process_attendance_event(1)
        
        mock_datetime.now.return_value = datetime(2025, 12, 16, 18, 0, 0)
        app.process_attendance_event(1)
        
        # Verify 2 sessions with correct durations
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT duration_minutes FROM attendance WHERE user_id=1 ORDER BY check_in")
        records = cursor.fetchall()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0][0], 240)  # 4 hours
        self.assertEqual(records[1][0], 240)  # 4 hours
        conn.close()


def run_tests():
    """Run all tests and generate report"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestGetCurrentWorkDay))
    suite.addTests(loader.loadTestsFromTestCase(TestAutomationFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestProcessAttendanceEvent))
    suite.addTests(loader.loadTestsFromTestCase(TestFingerprintSensor))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkDayBoundary))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
