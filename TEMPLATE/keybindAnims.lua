--Change the names in quotes to match the anim names that your model has, put "none" if you want to make sure it isnt available
--if a different pose like water or air uses the same anim as normal, just put the same anim name in the quotes

local quirk1 =			"quirk"
local water_quirk1 =	"water_quirk"
local air_quirk1 =		"air_quirk"

local quirk2 =			"quirk2"
local water_quirk2 =	"water_quirk2"
local air_quirk2 =		"air_quirk2"

local quirk3 =			"quirk3"
local water_quirk3 =	"water_quirk3"
local air_quirk3 =		"air_quirk3"

local physical =		"physical"
local water_physical =	"water_physical"
local air_physical =	"air_physical"

local special =			"special"
local water_special = 	"water_special"
local air_special =		"air_special"

local status = 			"status"
local water_status = 	"water_status"
local air_status = 		"air_status"

local recoil = 			"recoil"
local water_recoil = 	"water_recoil"
local air_recoil = 		"air_recoil"

local toggleAnim = 		"render"

--the keys each keybind will be set to, if changing the num row keys to numpad then change the .keyboard to .keypad 
--for list of keyboard key ids check this site https://applejuiceyy.github.io/figs/latest/Keybinds/

local keyCry = 		"key.keyboard.1"
local keyQuirk1 = 	"key.keyboard.2"
local keyQuirk2 = 	"key.keyboard.3"
local keyFaint = 	"key.keyboard.4"
local keyBattle = 	"key.keyboard.5"
local keySleep = 	"key.keyboard.6"
local keyQuirk3 = 	"key.keyboard.7"
local keyPhys = 	"key.keyboard.c"
local keySpec = 	"key.keyboard.v"
local keyStatus = 	"key.keyboard.y"
local keyRecoil = 	"key.keyboard.g"
local keyToggle =	"key.keyboard.equal"

--if an anim needs to override then set its value to true
local overriders = {
	["quirk1"] = false,
	["water_quirk1"] = false,
	["air_quirk1"] = false,
	["quirk2"] = false,
	["water_quirk2"] = false,
	["air_quirk2"] = false,
	["quirk3"] = false,
	["water_quirk3"] = false,
	["air_quirk3"] = false,
	["physical"] = true,
	["water_physical"] = true,
	["air_physical"] = true,
	["special"] = true,
	["water_special"] = true,
	["air_special"] = true,
	["status"] = true,
	["water_status"] = true,
	["air_status"] = true,
	["recoil"] = false,
	["water_recoil"] = false,
	["air_recoil"] = false,
	}

--ignore this


local getCurrentPose, modelname, setOverride = require("Pokemon.pokemon")
local _, _, _, _, keys = require("Pokemon.actions")
local anims = animations[modelname]

function pings.playAnim(ground, water, air)
	local currentPose = getCurrentPose()
	local a = nil
	if currentPose == "float-surface" or currentPose == "float" then
		a = anims[water]
		if a then
			a:play()
			if overriders[water] then setOverride(true) end
		end
	elseif currentPose == "hover" then
		a = anims[air]
		if a then
			a:play()
			if overriders[air] then setOverride(true) end
		end
	elseif currentPose == "standing" then
		a = anims[ground]
		if a then
			a:play()
			if overriders[ground] then setOverride(true) end
		end
	end
end

function pings.toggleAnim(anim, state)
	if anims[anim] then anims[anim]:setPlaying(state) end
	setOverride(state)
end

keys.cryKey:setKey(keyCry)
keybinds:newKeybind("Quirk1", keyQuirk1):onPress(function() pings.playAnim(quirk1, water_quirk1, air_quirk1) end)
keybinds:newKeybind("Quirk2", keyQuirk2):onPress(function() pings.playAnim(quirk2, water_quirk2, air_quirk2) end)
keys.faintKey:setKey(keyFaint)
keys.battleKey:setKey(keyBattle)
keys.sleepKey:setKey(keySleep)
keybinds:newKeybind("Quirk3", keyQuirk3):onPress(function() pings.playAnim(quirk3, water_quirk3, air_quirk3) end)
keybinds:newKeybind("Physical Attack", keyPhys):onPress(function() pings.playAnim(physical, water_physical, air_physical) end)
keybinds:newKeybind("Special Attack", keySpec):onPress(function() pings.playAnim(special, water_special, air_special) end)
keybinds:newKeybind("Status Move", keyStatus):onPress(function() pings.playAnim(status, water_status, air_status) end)
keybinds:newKeybind("Recoil", keyRecoil):onPress(function() pings.playAnim(recoil, water_recoil, air_recoil) end)
local togglestate = false
keybinds:newKeybind("ToggleAnim", keyToggle):onPress(function() togglestate = not togglestate pings.toggleAnim(toggleAnim, togglestate) end)

for key, value in pairs(overriders) do
	local anim = anims[key]
	if anim and value then
		anim:newCode(anim:getLength() - (1/24), "local _, _, setOverride = require('Pokemon.pokemon') setOverride(false)")
	end
end