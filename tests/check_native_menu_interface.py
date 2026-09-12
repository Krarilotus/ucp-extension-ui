"""Actual UI initialization/framework extraction on a private PE; no game."""
import hashlib
from pathlib import Path
import re
import struct
import pefile
from lupa.lua54 import LuaRuntime


def check(path,variant,framework):
    root=Path(__file__).resolve().parents[1]
    raw=path.read_bytes();pe=pefile.PE(data=raw)
    base=pe.OPTIONAL_HEADER.ImageBase;image=bytearray(pe.get_memory_mapped_image())
    lua=LuaRuntime(unpack_returned_tuples=True)
    scans=[];bridges=[]
    def scan(pattern,start=None,stop=None):
        scans.append((pattern,start))
        regex=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=(start or base)-base
        found=re.search(regex,image[offset:(stop-base) if stop else None],re.DOTALL)
        return base+offset+found.start() if found else 0
    def read(a,n):
        assert base<=a and a+n<=base+len(image)
        return bytes(image[a-base:a-base+n])
    g=lua.globals();g.root=root.as_posix();g.framework=framework.as_posix();g.scan=scan
    g.read_bytes=lambda a,n:lua.table_from(read(a,n))
    g.read_int=lambda a:struct.unpack('<i',read(a,4))[0]
    g.expose=lambda a,n,abi:bridges.append((a,n,abi))
    lua.execute('''
package.path=root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int,
 exposeCode=function(a,n,abi) expose(a,n,abi);return function(...) lastCall={a,...} end end}
package.loaded.core=core;modules={luajit={}};log=function() end
package.loaded.manager={initialize=function() end};package.loaded.patches={}
utils=dofile(framework..'/utils.lua')
owner=dofile(root..'/init.lua')
local proxies=dofile(framework..'/extensions/proxies.lua')
public=proxies.ExtensionProxy(owner);api=public:getNativeMenuInterface()
''')
    entry,receiver=(0x46b340,0x1fe7d10) if variant=='SHC' else (0x46b560,0x2a7b210)
    api=g.api
    assert (api.version,api.entry,api.gameCore)==(1,entry,receiver)
    assert lua.eval('function(api) return api.bytes:byte(1,#api.bytes) end')(api)==tuple(read(entry,60))
    assert bridges[0]==(entry,3,1) and len(bridges)==2
    before=len(scans)
    lua.execute('''
public:switchToMenu(58,7)
assert(#lastCall==4 and lastCall[1]==api.entry and lastCall[2]==api.gameCore
 and lastCall[3]==58 and lastCall[4]==7)
for i=1,100 do assert(public:getNativeMenuInterface().entry==api.entry) end
assert(not pcall(function() api.bytes='' end))
''')
    assert len(scans)==before
    pattern=scans[0][0];negative=0
    for case in ('missing','stale','ambiguous','receiver'):
        saved=read(entry,1);count=len(bridges)
        if case=='ambiguous':g.core.scanForAOB=lambda p,start: entry+100 if p==pattern else scan(p,start)
        elif case=='receiver':lua.execute('utils.AOBExtract=function() return 1,0 end')
        else:
            image[entry-base]=0xcc
            if case=='stale':g.core.AOBScan=lambda p: entry if p==pattern else scan(p)
        lua.execute("assert(not pcall(dofile,root..'/init.lua'))")
        assert len(bridges)==count;negative+=1
        image[entry-base:entry-base+1]=saved;g.core.AOBScan=scan;g.core.scanForAOB=scan
    return dict(variant=variant,sha256=hashlib.sha256(raw).hexdigest(),bindings=2,
                negativeCases=negative,discoveryCalls=before,liveGame=False)
