from typing import Callable, Protocol, TypeAlias, NamedTuple
from dataclasses import field, dataclass
from queue import Queue
import json


JSON: TypeAlias = dict | list | int | str
class JSONRPCResult(Exception): ...
class JSONRPCError(JSONRPCResult): ...
class JSONRPCSuccess(JSONRPCResult): ...


def Error(code: int, message: str) -> JSONRPCError:
	raise JSONRPCError({"jsonrpc": "2.0", "id": None, "error": {"code": code, "message": message}})

def Success(id: str | int, result: JSON) -> JSONRPCSuccess:
	raise JSONRPCSuccess({"jsonrpc": "2.0", "id": str(id), "result": result})

class Dispatcher[T](Protocol):
	def __call__(self, name: str) -> T: ...
	def __setitem__(self, name: str, f: T): ...


class BaseDispatcher:
	def __init__(self):
		self._fs: dict[str, Callable] = {}

	def __setitem__(self, name: str, f: Callable):
		if self._fs.get(name, None) is not None:
			raise ValueError("Redefining a key")
		self._fs[name] = f

	def __call__(self, name: str):
		if self._fs.get(name, None) is None:
			raise ValueError("Unknown key")
		return self._fs[name]


class JSONRPC:
	def __init__(self,
			  reader: Callable[[], bytes],
			  writer: Callable[[bytes], None],
			  dispatcher: Dispatcher[Callable[[str, dict, str | int], JSONRPCResult]]):

		self._queue = Queue()
		self._reader = reader
		self._writer = writer
		self._dispatcher = dispatcher

	def parse(self, msg):
		try:
			msg = json.loads(msg)
		except:
			raise Error(-32700, "Parse error")

		match msg:
			case {"jsonrpc": "2.0", "method": method, "params": params, "id": id}:
				if not isinstance(method, (str,)):
					raise Error(-32600, "Invalid Request")
				self._dispatcher(method)(method, params, id)

	def handler(self, msg):
		try:
			self.parse(msg)
		except JSONRPCResult as e:
			self._writer(json.dumps(e.args[0]).encode('utf8'))

	def endpoint(self, path: str):
		def decorator(_f: Callable[[JSONRPC, str, dict, str | int], JSONRPCResult]):
			def wrapper(name, params, id) -> JSONRPCResult:
				raise _f(self, name, params, id)
			self._dispatcher[path] = wrapper
			return wrapper
		return decorator


def read():
	return b'{"jsonrpc": "2.0", "method": "initialize", "params": [1, 2, 3], "id": 1}'

def write(b):
	print("decoded:", b.decode())

jrpc = JSONRPC(read, write, BaseDispatcher())

@jrpc.endpoint(path='initialize')
def initialize(self, name, msg, id) -> JSONRPCResult:
	return Error(-32601, "Method not found")

jrpc.handler(jrpc._reader())
