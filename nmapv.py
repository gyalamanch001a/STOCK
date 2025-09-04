#!/usr/bin/env python3
import socket
import time
import sys
import signal
import argparse
import logging

colors = True  # Output should be colored
machine = sys.platform  # Detecting the os of current system

if machine.lower().startswith(('os', 'win', 'darwin', 'ios')):
	colors = False  # Colors shouldn't be displayed in mac & windows
if not colors:
    end = red = white = green = yellow = run = bad = good = info = que = ''
else:

    end = '\033[1;m'
    red = '\033[91m'
    white = '\033[1;97m'
    green = '\033[1;32m'
    yellow = '\033[1;33m'

nmapdata = 1024
server_sock = None
def mrecv(c):
	tab = []
	bytes_recd = 0
	while bytes_recd < nmapdata:
		data = c.recv(min(nmapdata - bytes_recd, 2048))
		if not data:
			break
		tab.append(data)
		bytes_recd += len(data)
	# Return bytes for Python 3; caller can decode
	return b''.join(tab)

def prequest(c, addr, datainput):
	try:
		data = datainput.decode('utf-8', errors='replace')
		parts = data.split(' ')
		method = parts[0] if len(parts) > 0 else ''
		requested_file = parts[1] if len(parts) > 1 else '/'
		logging.info('Method: %s', method)
		logging.info('Peer: %s', addr)
		# Log only the first 200 chars to avoid noisy logs
		logging.info('Payload: %s', data[:200].replace('\n', ' '))
		req_file = requested_file.split('?')[0]
		req_file = req_file.lstrip('/')
		# do something with req_file if needed
	except Exception as e:
		logging.exception('Error processing request: %s', e)

		
def signal_exit(sig, frame):
	global server_sock
	try:
		if server_sock is not None:
			try:
				server_sock.shutdown(socket.SHUT_RDWR)
			except Exception:
				pass
			try:
				server_sock.close()
			except Exception:
				pass
	finally:
		logging.info('Shutting down (Ctrl+C).')
		sys.exit(0)

signal.signal(signal.SIGINT, signal_exit)

def Main(host: str = '', port: int = 1234, backlog: int = 5, rate_limit: float = 0.0):
	"""
	Start a simple TCP listener.

	host: interface to bind ('' = all)
	port: TCP port
	backlog: listen backlog
	rate_limit: max accepted connections per second (0 to disable)
	"""
	global server_sock
	server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server_sock.bind((host, port))
	server_sock.listen(backlog)
	logging.info('NMAP Vision listening on %s:%s (backlog=%s, rate_limit=%s/s)', host or '0.0.0.0', port, backlog, rate_limit or 'off')

	min_interval = 1.0 / rate_limit if rate_limit and rate_limit > 0 else 0.0
	last_accept = 0.0

	try:
		while True:
			if min_interval:
				now = time.time()
				delta = now - last_accept
				if delta < min_interval:
					time.sleep(min_interval - delta)
			data = None
			(c, addr) = server_sock.accept()
			last_accept = time.time()
			logging.info('Accepted connection from %s', addr)
			try:
				data = mrecv(c)
			except socket.error as ex:
				logging.warning("%s ~~~ NMAP SCAN LOADED ~~~", red)
			if data:
				prequest(c, addr, data)
			try:
				c.close()
			except Exception:
				pass
	except Exception as ex:
		logging.exception('Server error: %s', ex)
	finally:
		try:
			server_sock.close()
		except Exception:
			pass
 

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Simple TCP listener for NMAP Vision logs')
	parser.add_argument('--host', default='', help="Host/interface to bind (default: all interfaces)")
	parser.add_argument('--port', type=int, default=1234, help='Port to listen on (default: 1234)')
	parser.add_argument('--backlog', type=int, default=5, help='Listen backlog (default: 5)')
	parser.add_argument('--rate-limit', type=float, default=0.0, dest='rate_limit', help='Max accepted connections per second (0 to disable)')
	parser.add_argument('--log-level', default='INFO', choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'], help='Logging level (default: INFO)')
	args = parser.parse_args()

	logging.basicConfig(level=getattr(logging, args.log_level), format='%(asctime)s %(levelname)s %(message)s')
	Main(host=args.host, port=args.port, backlog=args.backlog, rate_limit=args.rate_limit)