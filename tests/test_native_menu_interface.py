"""Actual UI public API/readonly proxy with relocated native metadata."""
from pathlib import Path
import os
import re
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class NativeMenuInterfaceTests(unittest.TestCase):
    def prepare(self,runtime):
        lua=runtime(unpack_returned_tuples=True)
        self.lua=lua;g=lua.globals();g.root=ROOT.as_posix()
        pattern=re.search(r"local transitionPattern='([^']+)'",(ROOT/'init.lua').read_text(encoding='utf-8'))[1]
        self.memory=[0x19 if t=='?' else int(t,16) for t in pattern.split()]
        self.scans=[]
        def scan(p,start=None):
            self.scans.append((p,start))
            return 0 if start else 0x10000000 if p==pattern else 0x11000000
        g.scan=scan;g.read_bytes=lambda a,n:lua.table_from(self.memory[:n])
        lua.execute('''
package.path=root..'/?.lua;'..package.path
modules={luajit={}};package.loaded.manager={initialize=function() end}
package.loaded.patches={};receiver=0x20000000
utils={AOBExtract=function() return 0x12000000,receiver end}
calls={};exposed=0
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,
 exposeCode=function(address,n,abi)
  exposed=exposed+1;assert(n==3 and abi==1)
  return function(...) calls[#calls+1]={address,...} end
 end}
''')

    def test_actual_public_api_proxy_and_switch_reuse_the_same_entry(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                proxy=os.environ.get('UCP_FRAMEWORK_PROXIES')
                self.assertTrue(proxy,'Set UCP_FRAMEWORK_PROXIES to the actual framework source')
                self.lua.globals().proxies=self.lua.execute(Path(proxy).read_text(encoding='utf-8'))
                self.lua.execute('''
local owner=dofile(root..'/init.lua');local public=proxies.ExtensionProxy(owner)
local api=public:getNativeMenuInterface()
assert(api.version==1 and api.entry==0x10000000 and api.gameCore==0x20000000)
assert(#api.bytes==60 and api.bytes:byte(1)==0x55 and exposed==2)
assert(not pcall(function() api.entry=123 end))
assert(not pcall(function() api.bytes='' end))
local copy=owner:getNativeMenuInterface();copy.entry=123
assert(owner:getNativeMenuInterface().entry==0x10000000)
public:switchToMenu(58,7);public:switchToMenu()
assert(#calls[1]==4 and calls[1][1]==api.entry and calls[1][2]==api.gameCore)
assert(calls[1][3]==58 and calls[1][4]==7 and calls[2][3]==41 and calls[2][4]==0)
for i=1,100 do assert(public:getNativeMenuInterface().entry==api.entry) end
''')
                self.assertEqual(len(self.scans),3) # transition/uniqueness + existing modal lookup

    def test_invalid_discovery_context_or_receiver_never_exposes_a_bridge(self):
        for runtime in (Lua54,LuaJIT):
            for case in ('missing','ambiguous','modified','receiver'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare(runtime)
                    if case=='missing':self.lua.execute('core.AOBScan=function() return 0 end')
                    elif case=='ambiguous':self.lua.execute('core.scanForAOB=function() return 123 end')
                    elif case=='modified':self.memory[29]=0xcc
                    else:self.lua.execute('receiver=0')
                    self.lua.execute("assert(not pcall(dofile,root..'/init.lua'));assert(exposed==0)")
