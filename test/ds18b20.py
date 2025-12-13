import time

try:
	while True:
		tempfile = open("/sys/bus/w1/devices/10-00000007bfec/w1_slave")
		thetext = tempfile.read()
		tempfile.close()
		tempdata = thetext.split("\n")[1].split(" ")[9]
		temperature = float(tempdata[2:])
		temperature = temperature / 1000
		print(temperature)

		time.sleep(1)
except KeyboardInterrupt:
	pass
