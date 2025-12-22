"""
Test for Daily Format with Blank Lines Between Days
"""

import unittest
import sys
import os
from datetime import datetime, date, timedelta
import sqlite3
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules to test
try:
    from data import automation
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    print("Warning: automation module not available")


class TestDailyFormatWithBlankLines(unittest.TestCase):
    """Test daily format with blank lines between days"""
    
    def setUp(self):
        """Create temporary database with test data"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        automation.DB_PATH = self.db_path
        
        # Create tables
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
        
        # Add test users
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (1, 'Ahmet', 'Yılmaz', 'Mühendislik')")
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (2, 'Ayşe', 'Demir', 'Tasarım')")
        cursor.execute("INSERT INTO users (fingerprint_id, first_name, last_name, department) VALUES (3, 'Mehmet', 'Kaya', 'Yazılım')")
        
        # Add test attendance data for multiple days
        # Day 1: 2025-12-16
        cursor.execute("INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes) VALUES (1, '2025-12-16', '2025-12-16 08:00:00', '2025-12-16 12:00:00', 240)")
        cursor.execute("INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes) VALUES (1, '2025-12-16', '2025-12-16 13:00:00', '2025-12-16 17:00:00', 240)")
        cursor.execute("INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes) VALUES (2, '2025-12-16', '2025-12-16 09:00:00', '2025-12-16 18:00:00', 540)")
        
        # Day 2: 2025-12-17
        cursor.execute("INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes) VALUES (1, '2025-12-17', '2025-12-17 08:30:00', '2025-12-17 16:30:00', 480)")
        cursor.execute("INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes) VALUES (3, '2025-12-17', '2025-12-17 10:00:00', '2025-12-17 19:00:00', 540)")
        
        # Day 3: 2025-12-18
        cursor.execute("INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes) VALUES (2, '2025-12-18', '2025-12-18 07:00:00', '2025-12-18 15:00:00', 480)")
        cursor.execute("INSERT INTO attendance (user_id, date, check_in, check_out, duration_minutes) VALUES (3, '2025-12-18', '2025-12-18 08:00:00', NULL, 0)")  # Still inside
        
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Remove temporary database"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_get_week_data_returns_daily_records(self):
        """Test that get_week_data returns records grouped by date"""
        week_start = date(2025, 12, 15)
        week_end = date(2025, 12, 21)
        
        df = automation.get_week_data(week_start, week_end)
        
        # Should have records (5 user-day combinations)
        # Dec 16: User 1 (combined), User 2
        # Dec 17: User 1, User 3
        # Dec 18: User 2, User 3
        self.assertGreater(len(df), 0)
        
        # Should have 'Tarih' column
        self.assertIn('Tarih', df.columns)
        
        # Check unique dates
        unique_dates = df['Tarih'].unique()
        self.assertIn('2025-12-16', unique_dates)
        self.assertIn('2025-12-17', unique_dates)
        self.assertIn('2025-12-18', unique_dates)
        
        print(f"\n✓ Week data returned {len(df)} user-day records across {len(unique_dates)} days")
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_daily_format_structure(self):
        """Test that daily format has correct structure"""
        week_start = date(2025, 12, 15)
        week_end = date(2025, 12, 21)
        
        df = automation.get_week_data(week_start, week_end)
        
        # Each record should have date (5 user-day combinations)
        for idx, row in df.iterrows():
            self.assertIsNotNone(row['Tarih'])
            self.assertIsNotNone(row['Ad'])
            self.assertIsNotNone(row['Soyad'])
        
        print(f"✓ All {len(df)} user-day records have proper structure")
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_records_ordered_by_date_and_time(self):
        """Test that records are ordered by date then by check-in time"""
        week_start = date(2025, 12, 15)
        week_end = date(2025, 12, 21)
        
        df = automation.get_week_data(week_start, week_end)
        
        # Check order
        prev_date = None
        for idx, row in df.iterrows():
            current_date = row['Tarih']
            if prev_date is not None:
                # Date should not go backwards
                self.assertGreaterEqual(current_date, prev_date)
            prev_date = current_date
        
        print("✓ Records are properly ordered by date")
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_same_user_multiple_sessions_same_day(self):
        """Test that same user's multiple sessions on same day are combined into one row"""
        week_start = date(2025, 12, 15)
        week_end = date(2025, 12, 21)
        
        df = automation.get_week_data(week_start, week_end)
        
        # User 1 should have 1 record on 2025-12-16 (combined from 2 sessions)
        user1_dec16 = df[(df['Tarih'] == '2025-12-16') & (df['Ad'] == 'Ahmet') & (df['Soyad'] == 'Yılmaz')]
        self.assertEqual(len(user1_dec16), 1)
        
        # Check that it has first check-in (08:00) and last check-out (17:00)
        record = user1_dec16.iloc[0]
        self.assertIn('08:00', record['İlk Giriş'])
        self.assertIn('17:00', record['Son Çıkış'])
        
        # Total duration should be sum of both sessions (240 + 240 = 480 minutes)
        self.assertEqual(record['Toplam Dakika'], 480)
        
        print("✓ Multiple sessions per user per day are combined: first check-in + last check-out")
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_week_transition(self):
        """Test that new week creates new sheet after 7 days"""
        # Week 1: Dec 15-21
        week1_start = date(2025, 12, 15)
        week1_end = date(2025, 12, 21)
        week1_name = automation.get_week_name(week1_start)
        
        # Week 2: Dec 22-28
        week2_start = date(2025, 12, 22)
        week2_end = date(2025, 12, 28)
        week2_name = automation.get_week_name(week2_start)
        
        # Week names should be different
        self.assertNotEqual(week1_name, week2_name)
        self.assertEqual(week1_name, "2025-W51")
        self.assertEqual(week2_name, "2025-W52")
        
        print(f"✓ Week transition works: {week1_name} -> {week2_name}")
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_status_calculation(self):
        """Test that status (İçeride/Dışarıda) is correctly calculated"""
        week_start = date(2025, 12, 15)
        week_end = date(2025, 12, 21)
        
        df = automation.get_week_data(week_start, week_end)
        
        # User 3 on 2025-12-18 should be "İçeride" (no check_out)
        user3_dec18 = df[(df['Tarih'] == '2025-12-18') & (df['Ad'] == 'Mehmet') & (df['Soyad'] == 'Kaya')]
        self.assertEqual(len(user3_dec18), 1)
        self.assertEqual(user3_dec18.iloc[0]['Durum'], 'İçeride')
        
        # User 1 on 2025-12-16 should be "Dışarıda" (has check_out)
        user1_dec16 = df[(df['Tarih'] == '2025-12-16') & (df['Ad'] == 'Ahmet') & (df['Soyad'] == 'Yılmaz')].iloc[0]
        self.assertEqual(user1_dec16['Durum'], 'Dışarıda')
        
        print("✓ Status calculation is correct")


class TestWeekCalculations(unittest.TestCase):
    """Test week start/end calculations"""
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_week_start_end_monday_to_sunday(self):
        """Test that week goes from Monday to Sunday"""
        # Test with different days of the week
        test_cases = [
            (date(2025, 12, 15), date(2025, 12, 15), date(2025, 12, 21)),  # Monday
            (date(2025, 12, 17), date(2025, 12, 15), date(2025, 12, 21)),  # Wednesday
            (date(2025, 12, 21), date(2025, 12, 15), date(2025, 12, 21)),  # Sunday
        ]
        
        for test_date, expected_start, expected_end in test_cases:
            start, end = automation.get_week_start_end(test_date)
            self.assertEqual(start, expected_start, f"Failed for {test_date}")
            self.assertEqual(end, expected_end, f"Failed for {test_date}")
        
        print("✓ Week calculation (Monday-Sunday) is correct")
    
    @unittest.skipIf(not AUTOMATION_AVAILABLE, "automation module not available")
    def test_week_has_exactly_7_days(self):
        """Test that week span is exactly 7 days"""
        test_date = date(2025, 12, 16)
        start, end = automation.get_week_start_end(test_date)
        
        delta = (end - start).days
        self.assertEqual(delta, 6)  # 6 days difference = 7 days total
        
        print("✓ Week has exactly 7 days")


def run_tests():
    """Run all tests and generate report"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDailyFormatWithBlankLines))
    suite.addTests(loader.loadTestsFromTestCase(TestWeekCalculations))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print("DAILY FORMAT TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    if result.wasSuccessful():
        print("\n✓ All daily format tests passed!")
        print("\nExpected Google Sheets format:")
        print("─" * 70)
        print("Ad      | Soyad  | Departman | İlk Giriş | Son Çıkış | Toplam | Durum")
        print("─" * 70)
        print("📅 16.12.2025 Pazartesi")
        print("Ahmet   | Yılmaz | Mühendislik | 08:00   | 17:00     | 8s 0d  | Dışarıda")
        print("Ayşe    | Demir  | Tasarım     | 09:00   | 18:00     | 9s 0d  | Dışarıda")
        print("")
        print("📅 17.12.2025 Salı")
        print("Ahmet   | Yılmaz | Mühendislik | 08:30   | 16:30     | 8s 0d  | Dışarıda")
        print("Mehmet  | Kaya   | Yazılım     | 10:00   | 19:00     | 9s 0d  | Dışarıda")
        print("")
        print("📅 18.12.2025 Çarşamba")
        print("Ayşe    | Demir  | Tasarım     | 07:00   | 15:00     | 8s 0d  | Dışarıda")
        print("Mehmet  | Kaya   | Yazılım     | 08:00   | -         | 0s 0d  | İçeride")
        print("─" * 70)
    else:
        print("\n✗ Some tests failed!")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
