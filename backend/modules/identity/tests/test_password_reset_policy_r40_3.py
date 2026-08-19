from __future__ import annotations

import unittest

from modules.identity.application.password_reset_policy import password_reset_delivery_mode


class PasswordResetEnvironmentPolicyTests(unittest.TestCase):
    def test_demo_is_inline(self):
        self.assertEqual(password_reset_delivery_mode("demo"), "INLINE")

    def test_development_is_inline(self):
        self.assertEqual(password_reset_delivery_mode("development"), "INLINE")

    def test_testing_is_email(self):
        self.assertEqual(password_reset_delivery_mode("testing"), "EMAIL")

    def test_production_is_email(self):
        self.assertEqual(password_reset_delivery_mode("production"), "EMAIL")

    def test_staging_is_email(self):
        self.assertEqual(password_reset_delivery_mode("staging"), "EMAIL")


if __name__ == "__main__":
    unittest.main()
