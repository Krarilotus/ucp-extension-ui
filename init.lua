-- Keep the existing native transition owner available to module observers.
local transitionPattern='55 8B 6C 24 08 83 FD 17 56 8B F1 75 05 BD 29 00 00 00 8B 44 24 10 53 57 89 6E 18 89 46 04 FF 15 ? ? ? ? 89 46 08 8B C5 83 E8 0C 0F 84 2D 02 00 00 83 E8 02 74 2D 83 E8 02 74 1D'
local ok,transitionEntry=pcall(core.AOBScan,transitionPattern)
assert(ok and type(transitionEntry)=='number' and transitionEntry>=0x10000
  and transitionEntry<0x7fffffff-60,'UI cannot resolve the native menu transition')
local duplicate=core.scanForAOB(transitionPattern,transitionEntry+1)
assert(duplicate==nil or duplicate==0,'UI native menu transition is ambiguous')
local transitionBytes=core.readBytes(transitionEntry,60)
local position=0
for token in transitionPattern:gmatch('%S+') do
  position=position+1
  assert(token=='?' or transitionBytes[position]==tonumber(token,16),
    'UI native menu transition has modified instructions')
end
-- Immutable strings retain length through the framework's readonly table proxy.
local transitionGuard=string.char((table.unpack or unpack)(transitionBytes))
local _, pThis = utils.AOBExtract("A3 I( ? ? ? ? ) 89 5C 24 1C")
assert(type(pThis)=='number' and pThis>=0x10000 and pThis<0x7fffffff-0x2400,
  'UI native menu receiver is invalid')
local pSwitchToMenuView = core.exposeCode(transitionEntry, 3, 1)

---@type luajit
local luajit = modules.luajit

---@type LuaJITState
local state

local manager = require("manager")
manager.initialize()

local patches = require("patches")

---@class Module_UI
local ui = {}

local function initialize(options)
  local options = options or {
    headers = 'latest',
  }
  local state = luajit:createState({
    name = "ui",
    requireHandler = function(self, path)
      local handle, err = io.open(string.format("ucp/modules/ui/%s.lua", path))
      if not handle then
        handle, err = io.open(string.format("ucp/modules/ui/%s/init.lua", path))
      end
    
      if not handle then
        error( err)
      end
    
      local contents = handle:read("*all")
      handle:close()

      return contents
    end,
    globals = {},
    interface = {
      env = _ENV,
      extra = {
        manager = manager,
      }
    }
  })

  state:importHeaderFile(string.format("ucp/modules/ui/ui/headers/%s/ui.h", options.headers))
  state:executeString([[ui = require("ui")]])

  state:registerRequireHandler(function(self, path)
    local err2
    local handle, err1 = io.open(string.format("%s.lua", path))
    if not handle then
      handle, err2 = io.open(string.format("%s/init.lua", path))
    end
  
    if not handle then
      error( string.format("%s\n%s", err1, err2))
    end
  
    local contents = handle:read("*all")
    handle:close()

    return contents
  end)

  return state
end

function ui:enable()

  state = initialize()

  patches.setButtonPropertiesPatch()
end

function ui:disable()

end


function ui:registerMenu(menuAddress, preferredID)
  return manager.registerMenu(menuAddress, preferredID)
end

function ui:switchToMenu(menuID, delay)
  pSwitchToMenuView(pThis, menuID or 41, delay or 0)
end

-- Available after module initialization, like switchToMenu. Consumers preserve
-- the owner's bridge and verify this captured guard before adding observers.
function ui:getNativeMenuInterface()
  return {version=1,entry=transitionEntry,gameCore=pThis,bytes=transitionGuard}
end

local _, mmc1 = utils.AOBExtract("B9 I( ? ? ? ? ) E8 ? ? ? ? 5E 5B E9 ? ? ? ?")
local _, mmc2 = utils.AOBExtract("B9 I(? ? ? ?) E8 ? ? ? ? B9 ? ? ? ? 89 ? ? ? ? ? 89 ? ? ? ? ? 89 ? ? ? ? ?")
local _, mmc3 = utils.AOBExtract("B9 I( ? ? ? ? ) E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? 8B ? ? ? ? ? 8B ? ? ? ? ? A1 ? ? ? ?")
local mmcNonpersistent = mmc1
local mmcPersistent = mmc2
local _activateModalDialog = core.exposeCode(core.AOBScan("53 55 33 ED 39 6C 24 10"), 3, 1)

function ui:activateModalMenu(menuID, slot, delay)
  if slot == 1 then
    _activateModalDialog(mmcNonpersistent, menuID or -1, delay or 0)
  else
    _activateModalDialog(mmcPersistent, menuID or -1, delay or 0)
  end
end

function ui:createMenuFromFile(path, convert, cleanup)
  return state:executeFile(path, convert, cleanup)
end

function ui:registerEventHandler(key, func)
  state:registerEventHandler(key, func)
end

function ui:sendEvent(key, obj)
  state:sendEvent(key, obj)
end

function ui:registerRequireHandler(func)
  state:registerRequireHandler(func)
end

---@return LuaJITState
function ui:getState()
  return state
end

function ui:access()
  return {
    game = require("ui.game"),
    api = require("ui.menu"),
    manager = manager,
  }
end

--- Bad idea for now:
-- ---Creates a basic UI state from scratch
-- ---Only useful if you don't want to use the global UI state of this module
-- ---@return LuaJITState
-- function ui:createState()
--   return initialize()
-- end


return ui, {
  proxy = {
    ignored = {
      "getState",
      "createState",
      "createMenuFromFile",
      "registerMenu",
      "access",
    }
  }
}
