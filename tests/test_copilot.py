import unittest
from pathlib import Path
import pandas as pd

from ong_chrome_automation import LocalChromeBrowser, CopilotAutomation

class TestCopilotAutomation(unittest.TestCase):
    pass
    def setUp(self):
        self.browser = LocalChromeBrowser().__enter__()
        self.copilot = CopilotAutomation(self.browser)

    def tearDown(self):
        self.copilot = None
        self.browser.__exit__(None, None, None)


    def test_chat_text_response(self):
        self.copilot.chat("Write a 100-word poem about the importance of sustainability in urban development.")
        response = self.copilot.get_text_response()
        self.assertIsInstance(response, str, "Response should be a string.")
        self.assertGreater(len(response.split()), 20, "Response should be more than 20 words.")

    def test_chat_code_response(self):
        self.copilot.chat("Generate a Python code with a function named factorial "
                          "that calculates the factorial of a positive integer.")
        codes = self.copilot.get_response_code_blocks()
        self.assertIsInstance(codes, list, "Response should be a list of code blocks.")
        self.assertGreater(len(codes), 0, "Expected at least one code block in the response.")
        # Check if the first code block is not empty and contains the expected function definition
        code = codes[0]
        self.assertNotEqual(code, "", "Code block should not be empty.")
        self.assertIn("def factorial", code,
                      "Expected code block to contain the 'factorial' function definition.")

    def test_chat_tables_response(self):
        self.copilot.chat("Give me the tables you find in this PDF.",
                          [Path(__file__).with_name("sample_tables.pdf").as_posix()])
        tables = self.copilot.get_response_tables()
        self.assertIsInstance(tables, list, "Response should be a list of tables.")
        self.assertGreater(len(tables), 0, "Expected at least one table in the response.")
        for table in tables:
            self.assertIsInstance(table, pd.DataFrame, "Each table should be a pandas DataFrame.")

    def test_chat_files_response(self):
        self.copilot.chat("Generate an Excel file with the numbers from 1 to 10.")
        files = self.copilot.get_response_files()
        self.assertIsInstance(files, list, "Response should be a list of files.")
        self.assertGreater(len(files), 0, "Expected at least one file in the response.")
        for file in files:
            self.assertIn(".xlsx", file.get_attribute("download").lower(),
                          "Expected an excel file in the download attribute.")

    def test_multiple_chats(self):
        self.copilot.chat("What is the capital of France?")
        response1 = self.copilot.get_text_response()
        self.assertIn("Paris", response1)

        self.copilot.chat("What is the population of France?")
        response2 = self.copilot.get_text_response()
        self.assertIn("million", response2)

        self.copilot.chat("What is the currency of France?")
        response3 = self.copilot.get_text_response()
        self.assertIn("euro", response3.lower())

    def test_long_chat(self):
        with self.assertRaises(ValueError):
            self.copilot.chat("1" * 10000)
            # This should raise an exception due to the length of the input exceeding the limit.

    def test_no_tables(self):
        self.copilot.chat("What is the capital of France?")
        tables = self.copilot.get_response_tables()
        self.assertEqual(len(tables), 0, "Expected no tables in response for this query.")

if __name__ == "__main__":
    unittest.main()
