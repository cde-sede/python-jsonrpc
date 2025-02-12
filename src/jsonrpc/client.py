from typing import TypedDict, NotRequired, Literal, Any, TypeAlias, Self
from collections.abc import Callable
import os
import socket
import select
import json

MAX_MSG_LEN = 65536

class JSONRPCCommand(TypedDict):
	jsonrpc: Literal["2.0"]
	id: int | None
	params: NotRequired[list | dict]
	method: str


class JSONRPCResponse(TypedDict):
	jsonrpc: Literal["2.0"]
	id: int | None
	__type__: str

class JSONRPCSuccess(JSONRPCResponse):
	result: Any

class JSONRPCError(JSONRPCResponse):
	error: dict

JSONRPCCommandBatch: TypeAlias = list[JSONRPCCommand]
JSONRPCResponseBatch: TypeAlias = list[JSONRPCResponse]


_id = 0
def request(method: str, params: list | dict) -> JSONRPCCommand:
	global _id
	_id += 1
	r = JSONRPCCommand(jsonrpc="2.0", id=_id, params=params, method=method)
	return r

class SocketClientSession:
	def __init__(self, ip: str='localhost', port: int=8089):
		self.ip = ip
		self.port = port
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect((ip, port))
		self.callbacks = {}

	def send(self, command: JSONRPCCommand | JSONRPCCommandBatch,
		  then: Callable[[Self, JSONRPCSuccess], None] | None=None,
		  error: Callable[[Self, JSONRPCError], None] | None=None):
		if isinstance(command, dict):
			payload = json.dumps(command).encode()
			content_length = len(payload)
			self.socket.send(f"Content-Length:{content_length}\r\nContent-Type: application/jsonrpc; charset=utf-8\r\n\r\n".encode() + payload)

			if not then:	then = (lambda s, p: None)
			if not error:	error = (lambda s, p: None)

			self.callbacks[str(command['id'])] = (then, error)

		elif isinstance(command, list):
			payload = json.dumps(command).encode()
			content_length = len(payload)
			self.socket.send(f"Content-Length:{content_length}\r\nContent-Type: application/jsonrpc; charset=utf-8\r\n\r\n".encode() + payload)

			if not then:	then = (lambda s, p: None)
			if not error:	error = (lambda s, p: None)

			for i in command:
				self.callbacks[str(i['id'])] = (then, error)

	def handle_message(self, msg: dict):
		if msg.get('result') and msg.get('error'):
			raise ValueError()
		if msg.get('result'):
			return JSONRPCSuccess(**msg, __type__ = 'success')
		elif msg.get('error'):
			return JSONRPCError(**msg, __type__ = 'error')
		else:
			raise ValueError()

	def recv(self) -> JSONRPCResponse | JSONRPCResponseBatch:
		msg = self.socket.recv(MAX_MSG_LEN).decode()
		if not msg:
			raise ValueError("Connection closed") # TODO proper connection close
		r = json.loads(msg)
		if isinstance(r, dict):
			return self.handle_message(r)
		elif isinstance(r, list):
			return list(map(self.handle_message, r))
		raise ValueError()

	def loop(self) -> bool:
		r, w, e = select.select([self.socket], [self.socket], [])
		if r:
			msg = self.recv()
			if isinstance(msg, dict):
				msg = [msg]
			for i in msg:
				then, error = self.callbacks.get(str(i['id']), (None, None))
				if not (then is None or error is None):
					if i['__type__'] == 'success':
						self.callbacks[str(i['id'])][0](self, i)
					if i['__type__'] == 'error':
						self.callbacks[str(i['id'])][1](self, i)
					del self.callbacks[str(i['id'])]
				else:
					print(i)
		return True

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass

class IOClientSession:
	def __init__(self, pipe):
		self.pipe = pipe

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass
