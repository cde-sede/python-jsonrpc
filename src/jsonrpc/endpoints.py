from typing import Callable, Protocol, TypeAlias, NamedTuple, Iterable, Type, Any
from dataclasses import field, dataclass
from queue import Queue
import json


JSON: TypeAlias = dict | list | int | str
class JSONRPCResult(Exception): ...
class JSONRPCError(JSONRPCResult): ...
class JSONRPCSuccess(JSONRPCResult): ...
class JSONRPCBatch(JSONRPCResult): ...

class JSONRPCShutdown(JSONRPCResult): ...
class JSONRPCExit(JSONRPCResult): ...


def Error(code: int, message: str) -> JSONRPCError:
	raise JSONRPCError({"jsonrpc": "2.0", "id": None, "error": {"code": code, "message": message}})

def CustomError(obj: Any) -> JSONRPCError:
	raise JSONRPCError({"jsonrpc": "2.0", "id": None, "error": obj})

def Success(id: str | int, result: JSON) -> JSONRPCSuccess:
	raise JSONRPCSuccess({"jsonrpc": "2.0", "id": str(id), "result": result})

def Batch(batch: list[JSONRPCSuccess | JSONRPCError]) -> JSONRPCBatch:
	raise JSONRPCBatch([i.args[0] for i in batch])

def Shutdown() -> JSONRPCShutdown:
	raise JSONRPCShutdown()

def Exit() -> JSONRPCExit:
	raise JSONRPCExit()

class Dispatcher[T](Protocol):
	def __call__(self, name: str) -> T: ...
	def __setitem__(self, name: str, f: T) -> None: ...
	def default(self, f: T | None) -> None: ...


class BaseDispatcher:
	def __init__(self):
		self._fs: dict[str, Callable] = {}
		self._default: Callable | None = None

	def default(self, f: Callable | None):
		self._default = f
		
	def __setitem__(self, name: str, f: Callable):
		self._fs[name] = f

	def __call__(self, name: str) -> Callable:
		if self._fs.get(name, self._default) is None:
			raise ValueError("Unknown key")
		# if name not found and _default, _default is not None return default
		# if name not found and _default not set raise unknown key
												 # so ignore required
		return self._fs.get(name, self._default) # pyright: ignore

def emap(_func: Callable, _iter: Iterable, excepts: list[Type[Exception]]):
	for i in _iter:
		try:
			yield _func(i)
		except Exception as e:
			if type(e) in excepts:
				yield e

class JSONRPC:
	def __init__(self, dispatcher: Dispatcher[Callable[[str, dict, str | int], JSONRPCResult | None]]):

		self._queue = Queue()
		self._dispatcher = dispatcher

		@self.endpoint(path='shutdown')
		def _shutdown(self, name, msg, id) -> JSONRPCResult: return Shutdown()
		@self.endpoint(path='exit')
		def _exit(self, name, msg, id) -> JSONRPCResult: return Exit()

	def dispatch(self, obj):
		match obj:
			case {"jsonrpc": "2.0", "method": method, "params": params, "id": id}:
				if not isinstance(method, (str,)):
					raise Error(-32600, "Invalid Request")
				self._dispatcher(method)(method, params, id)
			case _:
				raise Error(-32600, "Invalid Request")

	def parse_header(self, header: str):
		content_length = -1
		content_type = "application/vscode-jsonrpc; charset=utf-8"

		fields = header.split('\r\n')
		it = iter(fields)
		for field in it:
			if not field:
				break
			key, value = field.split(':')
			if key == "Content-Length":
				content_length = int(value.strip('\r\n'))
			if key == "Content-Type":
				content_type = value.strip('\r\n')
		return content_length, content_type, next(it)

	def parse(self, msg: str):
		try:
			obj = json.loads(msg)
		except:
			raise Error(-32700, "Parse error")
		if isinstance(obj, (dict,)):
			self.dispatch(obj)
		if isinstance(obj, (list,)):
			raise JSONRPCBatch([i.args[0] for i in emap(self.dispatch, obj, [JSONRPCSuccess, JSONRPCError])])

	def handler(self, msg: str, writer: Callable[[bytes], None]):
		try:
			self.parse(msg)
		except (JSONRPCSuccess, JSONRPCError, JSONRPCBatch) as e:
			writer(json.dumps(e.args[0]).encode('utf8'))
		except (JSONRPCExit, JSONRPCShutdown) as e:
			raise e
		except Exception as e:
			raise Error(-1, f"{e.args[0]}")

	def default(self, f: Callable[['JSONRPC', str, dict, str | int], JSONRPCResult | None] | None):
		if f is None:
			self._dispatcher.default(None)
			return None
		def wrapper(name, params, id) -> JSONRPCResult | None:
			return f(self, name, params, id)
		self._dispatcher.default(wrapper)
		return wrapper

	def endpoint(self, path: str):
		def decorator(_f: Callable[[JSONRPC, str, dict, str | int], JSONRPCResult | None]):
			def wrapper(name, params, id) -> JSONRPCResult | None:
				r = _f(self, name, params, id)
				if r is not None:
					raise r
			self._dispatcher[path] = wrapper
			return wrapper
		return decorator
