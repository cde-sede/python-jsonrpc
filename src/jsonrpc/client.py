from typing import TypedDict, NotRequired, Literal, Any, TypeAlias
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

	def send(self, command: JSONRPCCommand):
		payload = json.dumps(command).encode()
		content_length = len(payload)
		self.socket.send(f"Content-Length:{content_length}\r\nContent-Type: application/jsonrpc; charset=utf-8\r\n\r\n".encode() + payload)

	def recv(self) -> JSONRPCResponse:
		r = json.loads(self.socket.recv(MAX_MSG_LEN).decode())
		if isinstance(r, dict):
			if r.get('result'):
				return JSONRPCSuccess(**r)
			elif r.get('error'):
				return JSONRPCError(**r)
			raise ValueError()
		elif isinstance(r, list):
			pass
		raise ValueError()

	def loop(self):
		r, w, e = select.select([self.socket], [self.socket], [])
		for s in r:
			print(s.recv(MAX_MSG_LEN))

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
