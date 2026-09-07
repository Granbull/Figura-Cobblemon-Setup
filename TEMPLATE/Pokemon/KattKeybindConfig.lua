--╔══════════════════════════════════════════════════════════════════════════╗--
--║                                                                          ║--
--║  ██  ██  ██████  ██████   █████    ██    ██████   ████    ████    ████   ║--
--║  ██ ██     ██      ██    ██       ████     ██    ██  ██  ██          ██  ║--
--║  ████      ██      ██    ██       █  █     ██     █████  █████    ████   ║--
--║  ██ ██     ██      ██    ██      ██████    ██        ██  ██  ██  ██      ║--
--║  ██  ██  ██████    ██     █████  ██  ██    ██     ████    ████    ████   ║--
--║                                                                          ║--
--╚══════════════════════════════════════════════════════════════════════════╝--

--v1.1

--This script does the tedious task of keeping keybinds synced if the user changes them in the Keybinds Menu.
--Changes are kept in the ConfigAPI and persist between reload and between avatars.
--Keybinds are tracked via their display name. If multiple avatars use the same keybind name, 
--  this script ensures they will share the same key.
--If this behavior is unwanted, you can change which config file keybinds are saved and loaded from.
--This script returns a table. Inside that table is the `setKeybindConfigFile` function.
--You can either give a string value or nil. nil will use the config file with the same name as the currently equipped avatar,
--  so that keybinds can be local to this avatar, rather than global to all avatars.
--
--This script uses the ConfigAPI. If you also use the ConfigAPI, make sure to call config:name before any save/load operations.
--
--This script needs to be loaded before any keybinds are created, else they wont be tracked.
--The best way to do so is to is by `require`ing this script before making any keybinds.

---@type Keybind[]
local syncedKeybinds = {}
---@type string?
local configFileName = "KattKeybindConfig"

---@param k Keybind
local function setKeyIfPresent(k)
  local _name=config:getName()
  config:setName(configFileName)
  local configValue = config:load(k:getName())
  if configValue then k:key(configValue) end
  config:setName(_name)
end

---@type table
local __index = figuraMetatables.KeybindAPI.__index
local track = {newKeybind = 1, of = 1, fromVanilla = 1}
for name, func in pairs(__index) do
  if track[name] then
    __index[name] = function(...)
      local success, keybind = pcall(func, ...)
      if not success then error(keybind, 2) end
      table.insert(syncedKeybinds, keybind)
      setKeyIfPresent(keybind)
      return keybind
    end
  end
end

if host:isHost() then
  function events.TICK()
    local _name=config:getName()
    config:setName(configFileName)
    for _, keybind in ipairs(syncedKeybinds) do
      if keybind:getKey() ~= config:load(keybind:getName()) then
        config:save(keybind:getName(), keybind:getKey())
      end
    end
    config:setName(_name)
  end
end

local API = {}
---
---@param filename string|nil
function API.setKeybindConfigFile(filename)
  configFileName = filename
  for _, k in ipairs(syncedKeybinds) do
    setKeyIfPresent(k)
  end
end

return API
