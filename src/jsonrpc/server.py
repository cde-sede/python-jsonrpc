from typing import TypedDict, NotRequired, Literal, Any
from queue import Queue
from functools import partial

import os
import socket
import select

from .endpoints import (
	JSONRPC,
	BaseDispatcher,

	Success,
	Error,
	CustomError,

	JSONRPCShutdown,
	JSONRPCExit,
)

MAX_MSG_LEN = 65536

class SocketServer:
	def __init__(self, ip: str='localhost', port: int=8089):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind((ip, port))
		self.socket.listen(5)
		self.connections = []

		self.jrpc = JSONRPC(BaseDispatcher())
		self.queues: dict[socket.socket, Queue] = {}
		
	def callback(self, b: bytes, *, socket: socket.socket):
		self.queues[socket].put(b)

	def loop(self):
		r, w, e = select.select([self.socket, *self.connections], self.connections, [])

		for s in r:
			if s == self.socket:
				client, address = self.socket.accept()
				self.connections.append(client)
				self.queues[client] = Queue()
			else:
				msg = s.recv(MAX_MSG_LEN).decode()
				if not msg:
					self.connections.remove(s)
					continue
				length, _, body = self.jrpc.parse_header(msg)
				try:
					self.jrpc.handler(body, partial(self.callback, socket=s))
				except (JSONRPCExit, JSONRPCShutdown) as e:
					raise e

		for s in w:
			if s not in self.connections:
				del self.queues[s]
				continue
			if self.queues[s].empty(): continue

			data = self.queues[s].get()
			s.send(data)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		for i in self.connections:
			self.socket.close()

class IOServer:
	def __init__(self, pipe):
		self.pipe = pipe

	def loop(self):
		pass

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass
