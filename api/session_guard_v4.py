"""Serialize operations on the same session, avoiding read/write revision races."""
import re,weakref
import anyio

def install(app):
    locks=weakref.WeakValueDictionary()
    @app.middleware('http')
    async def session_guard(request,call_next):
        match=re.match(r'^/api/(?:v4/)?sessions/([0-9a-f]{32})(?:/|$)',request.url.path)
        if not match:return await call_next(request)
        sid=match.group(1);lock=locks.get(sid)
        if lock is None:lock=anyio.Lock();locks[sid]=lock
        async with lock:return await call_next(request)
