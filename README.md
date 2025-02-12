# python-jsonrpc

A simple (??) implementation of the json remote procedure call protocol as defined in the spec (https://www.jsonrpc.org/)


### Example


The Client:

```python

from jsonrpc import SocketClientSession, request, JSONRPCSuccess, JSONRPCError

client = SocketClientSession()

def then(self, response: JSONRPCSuccess):
	print("Success:", response['result'])

def error(self, response: JSONRPCError):
	print("Error:", response['error'])

client.send(request("ping", []), then, error)
client.send([
		request("ping", []),
		request("ping", []),
		request("ping", []),
		request("ping", []),
	], then, error)

while client.loop():
	pass
```

And the server:

```python
from jsonrpc import SocketServer, Success, Error, Shutdown, Exit


server = SocketServer()

@server.jrpc.endpoint("ping")
def test(self, name, params, id):
	return Error(code=id, message="pong", id=id)

@server.cleanup
def cleanup(self):
	print("Done")

while server.loop():
	pass
```
