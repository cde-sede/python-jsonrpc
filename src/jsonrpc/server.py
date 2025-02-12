from typing import TypedDict, NotRequired, Literal, Any, Optional
from collections.abc import Callable
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
		self._cleanup = None
		self.msg: dict[socket.socket, str] = {}


	def cleanup(self, f):
		self._cleanup = f
		return f

	def __cleanup(self):
		if self._cleanup:
			self._cleanup(self)

	def callback(self, b: bytes, *, socket: socket.socket):
		self.queues[socket].put(b)

	def loop(self) -> bool:
		r, w, e = select.select([self.socket, *self.connections], self.connections, [])

		for s in r:
			if s == self.socket:
				client, address = self.socket.accept()
				self.connections.append(client)
				self.queues[client] = Queue()
				self.msg[client] = ''
			else:
				msg = s.recv(MAX_MSG_LEN).decode()
				if not msg:
					self.connections.remove(s)
					continue
				self.msg[s] += msg

				bodies = []
				while True:
					pairs, body = self.jrpc.parse_header(self.msg[s])
					if not pairs:
						break
					if not pairs.get('Content-Length'):
						break
					length = int(pairs['Content-Length'])
					if length <= len(body):
						body, self.msg[s] = body[:length], body[length:]
						bodies.append(body)
					else:
						break

				if not bodies:
					continue

				for body in bodies:
					try:
						self.jrpc.handler(body, partial(self.callback, socket=s))
					except (JSONRPCExit, JSONRPCShutdown) as e:
						self.__cleanup()
						return False

		for s in w:
			if s not in self.connections:
				del self.queues[s]
				del self.msg[s]
				continue
			if self.queues[s].empty(): continue

			data = self.queues[s].get()
			s.send(data)
		return True

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
