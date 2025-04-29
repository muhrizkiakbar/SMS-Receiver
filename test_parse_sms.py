# test_parse_sms.py

import unittest
from parse_sms import parse_sms


class TestParseSMS(unittest.TestCase):
    def setUp(self):
        self.sample_sms = """
+CMGL: 4,"REC READ","+628115010759",,"25/04/29,07:57:31+28"
DIN0:0;
AIN0:0.10,Normal;
AIN1:7.62,Normal;
AIN2:22.59,Normal;

+CMGL: 5,"REC READ","+628115010756",,"25/04/29,07:59:22+28"
RTU Power On;
ID:0001;
Status:Armed;
GSM Signal Value:19;
Power:09;
IMEI:867105078593984;
Version:V2.0.7_EN_4;
2025-04-29 08:59;
+CMGL: 6,"REC READ","+628115113510",,"25/04/29,08:00:42+28"
AIN0:0.38,Normal;
AIN1:4.02,Normal;
AIN2:39.38,Normal;
AIN3:46.11,Normal;

+CMGL: 7,"REC READ","+6282195446469",,"25/04/29,08:02:18+28"
RTU Power On;
ID:0001;
Status:Armed;
GSM Signal Value:22;
Power:13;
IMEI:867105079780267;
Version:V2.0.7_EN_4;
2025-04-29 09:02;
+CMGL: 8,"REC READ","+6282213735684",,"25/04/29,08:07:30+28"
AIN0:2.51,Normal;
AIN1:7.23,Normal;
AIN2:28.35,Normal;
AIN3:47.47,Normal;

+CMGL: 9,"REC READ","+6282195446469",,"25/04/29,08:12:18+28"
RTU Power On;
ID:0001;
Status:Armed;
GSM Signal Value:21;
Power:13;
IMEI:867105079780267;
Version:V2.0.7_EN_4;
2025-04-29 09:12;
+CMGL: 10,"REC READ","+628115113503",,"25/04/29,08:14:18+28"
AIN0:0.00,Normal;
AIN1:0.01,Normal;
AIN2:0.23,Normal;
AIN3:80.90,Normal;
"""

    def test_parse_sms_success(self):
        result = parse_sms(self.sample_sms)
        print((result))
        self.assertEqual(len(result), 4)

        self.assertEqual(result[0]["phone_number"], "+628115010759")
        self.assertEqual(result[0]["timestamp"], "2025-04-29 08:57:31")
        self.assertIn("AIN0", result[1]["message"])

        self.assertEqual(result[1]["phone_number"], "+628115113510")
        self.assertEqual(result[1]["timestamp"], "2025-04-29 09:00:42")
        self.assertIn("AIN0", result[1]["message"])

        self.assertEqual(result[2]["phone_number"], "+6282213735684")
        self.assertEqual(result[2]["timestamp"], "2025-04-29 09:07:30")
        self.assertIn("AIN0", result[3]["message"])

        self.assertEqual(result[3]["phone_number"], "+628115113503")
        self.assertEqual(result[3]["timestamp"], "2025-04-29 09:14:18")
        self.assertIn("AIN0", result[3]["message"])

    def test_parse_sms_empty(self):
        empty_sms = ""
        result = parse_sms(empty_sms)
        self.assertEqual(result, [])

    def test_parse_sms_invalid_format(self):
        invalid_sms = "Invalid Data Here"
        result = parse_sms(invalid_sms)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
