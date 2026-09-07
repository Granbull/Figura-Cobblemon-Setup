local keys = {}
keys.sleepKey = keybinds:newKeybind("Toggle Sleep", nil)
keys.battleKey = keybinds:newKeybind("Toggle Battle", nil)
keys.faintKey = keybinds:newKeybind("Toggle Faint", nil)
keys.rideToggle = keybinds:newKeybind("Toggle Ride Overlay", nil)
keys.cryKey = keybinds:newKeybind("Make Cry", nil)

local pokedata = require("config")
local mainPage = action_wheel:newPage()
action_wheel:setPage(mainPage)

local _underscorePos = pokedata.modelname:find("_", 1, true)
local onlyname = _underscorePos and pokedata.modelname:sub(1, _underscorePos - 1) or pokedata.modelname

local states = {
battling = false,
sleeping = false,
fainted = false,
ridden = false
}

local nomove = {}

local function untoggleOtherActions(currentAction)
	for _, action in pairs(nomove) do 
		if action ~= currentAction and action:isToggled() then
			action.toggle(false)
			action:toggled(false)
		end
	end
end

--actions that just happen once
function pings.cry(pitch)
	if states.battling then
		if animations[pokedata.modelname].battle_cry then animations[pokedata.modelname].battle_cry:play() 
		elseif animations[pokedata.modelname].cry then animations[pokedata.modelname].cry:play() end
	else
		if animations[pokedata.modelname].cry then animations[pokedata.modelname].cry:play() end
	end

	if not player:isLoaded() then return end
	local soundname = pokedata.customcry and onlyname.."_cry" or "cobblemon:pokemon."..onlyname..".cry"
	--sounds:playSound(soundname ,player:getPos(), 1, pitch)

end

local cryAct = mainPage:newAction() 
	:title("cry out")
	:item("minecraft:note_block")
	:onLeftClick(function() pings.cry(1) end)

--actions that toggle and cancel with movement
function pings.rest(state)
	states.sleeping = state
end

nomove.sleepAct = mainPage:newAction()
	:title("go to sleep")
	:toggleTitle("get up")
	:item("minecraft:red_bed")
	:onToggle(function(state, action)
		if state then untoggleOtherActions(action) end
		pings.rest(state)
	end)
	
function pings.battle(state)
	states.battling = state
end

nomove.battleAct = mainPage:newAction()
	:title("start battling")
	:toggleTitle("end battle")
	:item("minecraft:iron_sword")
	:onToggle(function(state, action)
		if state then untoggleOtherActions(action) end
		pings.battle(state)
	end)


function pings.faint(state)
	states.fainted = state
end

nomove.faintAct = mainPage:newAction()
	:title("Faint")
	:toggleTitle("Cancel Faint")
	:item("minecraft:skeleton_skull")
	:onToggle(function(state, action)
		if state then untoggleOtherActions(action) end
		pings.faint(state)
	end)

function pings.ride(state)
	states.ridden = state
end

local rideAct = mainPage:newAction()
	:title("Toggle whether to use Ride Overlay anims")
	:item("minecraft:saddle")
	:onToggle(function(state )
		pings.ride(state)
	end)
--keybinds
keys.sleepKey.press = function()
	local keystate = not nomove.sleepAct:isToggled()
	nomove.sleepAct.toggle(keystate)
	nomove.sleepAct:toggled(keystate)
end

keys.battleKey.press = function()
	local keystate = not nomove.battleAct:isToggled()
	nomove.battleAct.toggle(keystate)
	nomove.battleAct:toggled(keystate)
end

keys.faintKey.press = function()
	local keystate = not nomove.faintAct:isToggled()
	nomove.faintAct.toggle(keystate)
	nomove.faintAct:toggled(keystate)
end

keys.rideToggle.press = function()
	local keystate = not rideAct:isToggled()
	rideAct.toggle(keystate)
	rideAct:toggled(keystate)
end

keys.cryKey.press = function()
	cryAct:leftClick()
end

return mainPage, states, nomove, cryAct, keys