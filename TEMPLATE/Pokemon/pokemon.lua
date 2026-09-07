--main variables
local pokedata = require("config")

vanilla_model.ALL:setVisible(false)
vanilla_model.ALL:setScale(0)
vanilla_model.HELD_ITEMS:setVisible(true)

local onlyname = pokedata.modelname:find("_",1,true) ~= nil and pokedata.modelname:sub(1, pokedata.modelname:find("_",1,true) - 1) or pokedata.modelname
local defaultname = onlyname:sub(1,1):upper()..onlyname:sub(2)
models[pokedata.modelname]:setPrimaryRenderType("TRANSLUCENT_CULL")
local camera = require("Pokemon.camera")
camera.setCamera(pokedata.camheight)
camera.cheating = pokedata.crosshairAdjust or true
local currentPose = "none"
local lastPose = "none"
local Override = false

local GSBlend = require("Pokemon.GSAnimBlend")

--model control variables
local posePos = vectors.vec3()
local worldPos = vectors.vec3()

local poseRot = vectors.vec3()
local worldRot = vectors.vec3()

--add the Molang Compat Script
require("Pokemon.Molang")

--sound keyframe replacement
local crypitch = 1
function KeySound(id)
	if not player:isLoaded() then return end

	local soundname = id
	if id:find(".cry") then
		soundname = pokedata.customcry and onlyname.."_cry" or "cobblemon:"..id
	end
	
	sounds:playSound(soundname, player:getPos(), nil, crypitch)
end

if client:compareVersions("0.1.4", client:getFiguraVersion()) > 0 then
	error("this Avatar only works on versions 0.1.4 and above")
end

--[[animation control states
local riding = false
local wasmoving = false
local moving = false
local running = false
local sleeping = false
local battling = false
local inwater = false
local onsurface = false
local inair = false
local onground = false
local idle = false
local fainted = false
]]--
--animation presence states
Animpossible = {}

--pokemon walk speed can be approximated to be a multiplier applied to a .5 blocks per tick movement speed the default multiplier is .35
local walkanimspeed = (pokedata.speedscale or false) and (pokedata.pokescale * (pokedata.movespeed or 0.35))/0.2 or 1

nameplate.ENTITY:setPivot(0,(2.2*pokedata.nameplatepivot),0)
--nameplate.ENTITY:setText((nickname or defaultname).." \nLevel: 0")
if not pokedata.vanillaplate then
nameplate.ENTITY:setText('[{text:"'..(pokedata.nickname or defaultname)..'"},{text:"${badges}"},{text:"\n"},{text:"Level: 0"}]')
end



local function setHeadRot(rot)
	for key, value in ipairs(pokedata.pokehead) do
		local thisRot = rot:copy()
		if value.head == "NONE" then
			return
		elseif value.head == nil then
			error('Your pokehead '.. (key) ..' path is improper, check the path for typos or if there is not a separate head then replace the head with "NONE"')
		end

		if value.disableX then
			thisRot.x = 0
		else
			thisRot.x = math.clamp(thisRot.x * (value.invertX and -1 or 1), value.minPitch, value.maxPitch) * value.pitchMultiplier
		end

		if value.disableY then 
			thisRot.y = 0
		else
			thisRot.y = math.clamp(thisRot.y * (value.invertY and -1 or 1), value.minYaw, value.maxYaw) * value.yawMultiplier
		end
		value.head:offsetRot(thisRot)
	end

end

function events.render(delta, ctx, matrix)
	--Head rotation control
	local headrot = (vanilla_model.HEAD:getOriginRot() + 180) %360 - 180
	local scalefactor = 1
	
	if animations[pokedata.modelname].sleep and animations[pokedata.modelname].sleep:isPlaying() then
		headrot = vectors.vec3(0, 0, 0)
	end
	setHeadRot(headrot)
	
	--if the pokemon is a world part make sure its scaling right and doesnt show in first person
	if models[pokedata.modelname]:getParentType() == "World" then
		scalefactor = 1
		models[pokedata.modelname]:setVisible(ctx == "RENDER" )
	else
		scalefactor = math.worldScale
		models[pokedata.modelname]:setVisible(true)
	end

	--make paperdoll have a unique scale so it can be not too big or small
	if ctx == "PAPERDOLL" or ctx == "MINECRAFT_GUI" then
		models[pokedata.modelname]:setScale(pokedata.pdollscale)
	else
		models[pokedata.modelname]:setScale(scalefactor*pokedata.pokescale)
	end
end

if not pokedata.vanillaplate then
	function events.tick()
		--set nameplate to the pokemon name and player level
		if player:getGamemode() ~= "CREATIVE" then
			nameplate.ENTITY:setText('[{text:"'..(pokedata.nickname or defaultname)..' "},{text:"${badges}"},{text:"\n"},{text:"Level: '..player:getExperienceLevel()..'"}]')
		else
			nameplate.ENTITY:setText('[{text:"'..(pokedata.nickname or defaultname)..' "},{text:"${badges}"},{text:"\n"},{text:"Level: §k999"}]')
		end
	end
end
--action wheel variables
local page, states, nomove, cryAction  = require("Pokemon.actions")

--syncing creative flight
local creativeFlying=false
function pings.setFlying(flying)
  creativeFlying=flying
end
if host:isHost() then
  function events.tick()
    local _flying = host:isFlying()
    if creativeFlying~=_flying then
      pings.setFlying(_flying)
    end
  end
end

--set up what animations we can use and their blend times
local function animcheck()

	if animations[pokedata.modelname].air_fly then Animpossible.canfly = true end
	if animations[pokedata.modelname].water_idle then Animpossible.canswim = true end
	if animations[pokedata.modelname].faint then Animpossible.canfaint = true end
	if animations[pokedata.modelname].surfacewater_idle then Animpossible.canswim = true end
	if animations[pokedata.modelname].battle_idle then Animpossible.canbattle = true end
	if animations[pokedata.modelname].ground_run then Animpossible.runanim = true end
	if animations[pokedata.modelname].sleep then Animpossible.cansleep = true end
	if animations[pokedata.modelname].water_sleep then Animpossible.watercansleep = true end

	for key, value in pairs(animations:getAnimations()) do
		if not (value:getName() == "blink" or value:getName() == "cry" or value:getName():find("quirk") ~= nil) then
			value:setBlendTime(10)
			value:onBlend(function(state, data)
			  if state.starting then GSBlend.oldF.play(state.anim) end
			  GSBlend.defaultCallback(state, data)
			end)
		end
	end
	
end

--quirk animation control
local addPose = require("Pokemon.quirks")[2]
local idlestop = require("Pokemon.quirks")[3]


--the function that controls what animation we are in at any given time


--animation variables
local poseCategory = {
	["FLYING_POSES"] = {["FLY"]=true, ["HOVER"]=true},
	["SWIMMING_POSES"] = {["SWIM"]=true, ["FLOAT"]=true},
	["STANDING_POSES"] = {["STAND"]=true, ["WALK"]=true},
	["MOVING_POSES"] = {["WALK"]=true, ["SWIM"]=true, ["FLY"]=true},
	["STATIONARY_POSES"] = {["STAND"]=true, ["FLOAT"]=true, ["HOVER"]=true}
}
local poseType = "STAND"
local otherstates = {}
otherstates.isBattling = false
otherstates.isSubmergedInWater = false
otherstates.isTouchingWater = false
otherstates.isRunning = false
otherstates.isRiding = false
otherstates.isMount = false

local registered_anims = {}
function RegisterPose(Name, Poses, Included_states, Excluded_states, Animations, transformTicks, quirk, HiddenPart, ShownPart, Transition)

	registered_anims[Name] = {}
	
	if Animations == nil or (type(Animations) == "table" and #Animations == 0) then
		error("No Valid Animation present in " .. Name .. " make sure you are using the right preset or typed the animation in correctly if not using or editing a preset")
	end
	
	Animations = type(Animations) == "table" and Animations or {Animations}
	for key, value in ipairs(Animations) do
		if type(value) == "string" then
			Animations[key] = animations[pokedata.modelname][value]
		end
	end

	registered_anims[Name].Poses = type(Poses) == "table" and Poses or {Poses}
	registered_anims[Name].Inclu = type(Included_states) == "table" and Included_states or {Included_states}
	registered_anims[Name].Exclu = type(Excluded_states) == "table" and Excluded_states or {Excluded_states}
	registered_anims[Name].Anims = Animations
	registered_anims[Name].HidePart = type(HiddenPart) == "table" and HiddenPart or {HiddenPart}
	registered_anims[Name].ShowPart = type(ShownPart) == "table" and ShownPart or {ShownPart}
	registered_anims[Name].Transition = Transition

	quirk = type(quirk) == "table" and quirk or {quirk}
	for key, value in ipairs(Animations) do
		value:blendTime(transformTicks or 10)
		
		for int, val in ipairs(quirk) do
			addPose(val, table.unpack(registered_anims[Name].Anims))
		end
	end
end

RegisterPose("none", nil, nil, nil, "none")

function Unblend(...)
for key, value in ipairs({...}) do
	if animations[pokedata.modelname][value] then
	animations[pokedata.modelname][value]:setBlendTime(0)
	end
end

end

local function poseActive(Poses)
	for key, value in pairs(Poses) do
		
		if poseType == value or (poseCategory[value] and poseCategory[value][poseType]) then 
			return true
		end
	end
	return false
end

local function stateCheck(Inclu, Exclu)
	local inclustate = true
	
	if Inclu[1] then
		for key, value in pairs(Inclu) do 
			if not otherstates[value] then inclustate = false break end
		end
	end

	local exclustate = false
	if Exclu[1] then
		for key, value in pairs(Exclu) do 
			if otherstates[value] then exclustate = true break end
		end
	end

	return inclustate and not exclustate
end

local function ParseAnimations()

	--local animfound = false
	lastPose = currentPose
	currentPose = "NONE"
	if Override then currentPose = "ALTERNATE" end
	for _, value in ipairs(require("Poser/priority")) do

		local pose = registered_anims[value]

		if pose and pose.Anims[1] then
		
			local state = (poseActive(pose.Poses) and stateCheck(pose.Inclu, pose.Exclu)) and not animfound
			if state == true and currentPose == "NONE" then currentPose = value end
			
		end
	end
	
	if currentPose ~= lastPose then
		--cancel outgoing anims
		local outPose = registered_anims[lastPose]
		local inPose = registered_anims[currentPose]
		
		if outPose then
			for key, animation in ipairs(outPose.Anims) do
				animation:pause()
				if animations[pokedata.modelname]["ride_"..animation:getName()] then
				animations[pokedata.modelname]["ride_"..animation:getName()]:pause()
				end
			end
		
			for key, modelpart in ipairs(outPose.HidePart) do
				modelpart:setVisible(true)
			end
		
			for key, modelpart in ipairs(outPose.ShowPart) do
				modelpart:setVisible(false)
			end
			

			if outPose.Transition then
				for pose, anim in pairs(outPose.Transition) do
					if currentPose == pose then
						animations[pokedata.modelname][anim]:play()
					end
				end
			end
		end

		--play incoming anims
		if currentPose ~= "ALTERNATE"  and  currentPose ~= "NONE" then

			for key, animation in ipairs(inPose.Anims) do
				animation:play()
				if otherstates.isMount and animations[pokedata.modelname]["ride_"..animation:getName()] then
				animations[pokedata.modelname]["ride_"..animation:getName()]:play()
				end
			end

			for key, modelpart in ipairs(inPose.HidePart) do
				modelpart:setVisible(false)
			end

			for key, modelpart in ipairs(inPose.ShowPart) do
				modelpart:setVisible(true)
			end
		
		end

		if outPose then
			for key, animation in ipairs(outPose.Anims) do
				if animation:getPlayState() == "PAUSED" then
					animation:stop()
					if animations[pokedata.modelname]["ride_"..animation:getName()] then
						animations[pokedata.modelname]["ride_"..animation:getName()]:stop()
					end
				end
			end
		end

	end

end

local function setOverride(state)

	Override = state
end

local function getCurrentPose()
	return currentPose
end

local function newmovementcontroller()
	
	local isSleeping = (player:getPose() == "SLEEPING" or states["sleeping"])
	local isMoving = creativeFlying and player:getVelocity().xz:length() > 0.10 or player:getVelocity().xz:length() > 0.01
	local isPassenger = player:getVehicle() ~= nil
	local isUnderwater = player:isUnderwater()
	local isFlying = (creativeFlying or player:getPose() == "FALL_FLYING") and not player:isInWater()
	local isFainting = player:getHealth() <= 0 or states["fainted"]
--	local isGrounded = world.getBlockState(player:getPos():sub(0, -0.1, 0))

	if isFainting then 						poseType = "FAINT"
	elseif isPassenger then 				poseType = "STAND"
	elseif isSleeping then 					poseType = Animpossible.cansleep and "SLEEP" or "STAND"
	elseif isMoving and isUnderwater then 	poseType = "SWIM"
	elseif isUnderwater then 				poseType = "FLOAT"
	elseif isMoving and isFlying then		poseType = "FLY"
	elseif isFlying then					poseType = "HOVER"
	elseif isMoving then 					poseType = "WALK"
	else 									poseType = "STAND" end

	otherstates.isBattling = states["battling"]
	otherstates.isSubmergedInWater = player:isUnderwater()
	otherstates.isTouchingWater = player:isInWater()
	otherstates.isRunning = player:isSprinting()
	otherstates.isSneaking = player:getPose() == "CROUCHING"
	otherstates.isRiding = player:getVehicle() ~= nil 
	otherstates.isMount = states["ridden"]

	ParseAnimations()
end

events.TICK:register(newmovementcontroller)

--[[
local function movementcontroller()
	
	riding = player:getVehicle() ~= nil
	wasmoving = moving
	moving = player:getVelocity().xz:length() > 0.01 and not riding
	running = player:isSprinting() and runanim
	sleeping = (player:getPose() == "SLEEPING" or states["sleeping"])
	battling = states["battling"] and canbattle
	inwater = player:isInWater()
	onsurface = player:isInWater() and not player:isUnderwater() and surfaceswim
	inair = (creativeFlying or player:getPose() == "FALL_FLYING") and not inwater
	onground = not ((inair and canfly) or (inwater and (canswim or surfaceswim)))
	idle = not moving and not (sleeping or battling or idlestop())
	fainted = (player:getHealth() <= 0 or states["fainted"]) and canfaint

	--standard movement
	--ground
	animations[pokedata.modelname].ground_idle:setPlaying((idle or riding) and onground)
	animations[pokedata.modelname].ground_walk:setPlaying(moving and not running and onground)
	
	if runanim then
	animations[pokedata.modelname].ground_run:setPlaying(moving and running and onground)
	end
	
	--water
	if canswim and not surfaceswim then
	animations[pokedata.modelname].water_idle:setPlaying(idle and inwater)
	animations[pokedata.modelname].water_swim:setPlaying(moving and inwater)
	elseif canswim then
	animations[pokedata.modelname].water_idle:setPlaying(idle and inwater and not onsurface)
	animations[pokedata.modelname].water_swim:setPlaying(moving and inwater and not onsurface)
	end

	if surfaceswim and not canswim then
	animations[pokedata.modelname].surfacewater_idle:setPlaying(idle and inwater)
	animations[pokedata.modelname].surfacewater_swim:setPlaying(moving and inwater)
	elseif surfaceswim then
	animations[pokedata.modelname].surfacewater_idle:setPlaying(idle and onsurface)
	animations[pokedata.modelname].surfacewater_swim:setPlaying(moving and onsurface)
	end
	--air
	
	if canfly then
	animations[pokedata.modelname].air_idle:setPlaying(idle and inair)
	animations[pokedata.modelname].air_fly:setPlaying(moving and inair)
	end
	
	--basic anims
	if cansleep then
	animations[pokedata.modelname].sleep:setPlaying(sleeping and onground)
	end
	
	if watercansleep then
	animations[pokedata.modelname].water_sleep:setPlaying(sleeping and inwater)
	end

	if canbattle then
	animations[pokedata.modelname].battle_idle:setPlaying(battling)
	end
	
	if canfaint then
	animations[pokedata.modelname].faint:setPlaying(fainted)
	end
end
]]--

local wasmoving = false
local moving = false

function events.tick()

	wasmoving = moving
	moving = player:getVelocity().xz:length() > 0.01

	if not wasmoving and moving then 
		--[[
		for key, value in pairs(nomove) do
			if value:isToggled() then
				value.toggle(false)
				value:toggled(false)
			end
		end
		]]	
		if nomove.sleepAct:isToggled() then
			nomove.sleepAct:toggled(false).toggle(false)
		end
	end

	--forward/backwards velocity check
	local pv = player:getVelocity():mul(1, 0, 1):normalize()
	local pl = models[pokedata.modelname]:partToWorldMatrix():applyDir(0,0,-1):mul(1, 0, 1):normalize()
	local fwd = pv:dot(pl)
	local backwards = fwd < -.8 and -1 or 1

	local moveAnimSpeed = 1 * walkanimspeed * backwards
	if player:getPose() == "CROUCHING" then 
		moveAnimSpeed = .5 * walkanimspeed * backwards
	elseif player:isSprinting() then
		moveAnimSpeed = 1.5 * walkanimspeed * backwards
	end

	--speed alterations based on movement
	for key,value in ipairs(pokedata.movement_anims) do 
		if animations[pokedata.modelname][value] then
			animations[pokedata.modelname][value]:setSpeed(moveAnimSpeed)
		end
	end

	--special poses
	if otherstates.isRiding then
		if pokedata.legs.left and pokedata.legs.right then 	
			pokedata.legs.left:setOffsetRot(vec(80,-20,0):sub(pokedata.legs.left:getAnimRot()))
			pokedata.legs.right:setOffsetRot(vec(80,20,0):sub(pokedata.legs.right:getAnimRot()))
			posePos = vectors.vec3(0,-2,0)
		else
		
			posePos = vectors.vec3(0,12,0)
	
		end	
	elseif player:getPose() == "SLEEPING" and Animpossible.cansleep then
		poseRot = vectors.vec3(-90,0,90)
		posePos = vectors.vec3(0,22,0)
	elseif player:getPose() == "CROUCHING" then
		posePos = vectors.vec3(0,2,0)
		poseRot = vectors.vec3()
	else
		if pokedata.legs.left and pokedata.legs.right then 
			pokedata.legs.left:setOffsetRot()
			pokedata.legs.right:setOffsetRot()
		else
			nameplate.ENTITY:setPivot(0,2.2*pokedata.nameplatepivot+(12/16),0)
		end

		posePos = vectors.vec3()
		poseRot = vectors.vec3()
			
	end

end

--swimming and gliding mechanics
--[[
function events.world_render(delta)
	if player:isLoaded() then
		if (player:getPose() == "SWIMMING" and Animpossible.canswim) or (player:getPose() == "FALL_FLYING" and Animpossible.canfly) or (player:getHealth() <= 0 and Animpossible.canfaint) then
			local pos = player:getPos(delta)
			local blocklight = world.getBlockLightLevel(pos:add(0,.4,0))
			local skylight = world.getSkyLightLevel(pos:add(0,.4,0))
			
			models[pokedata.modelname]:setParentType("World")
			worldPos = player:getPos(delta)*16
			
			models[pokedata.modelname]:setLight(blocklight,skylight)
			
			if not (player:getHealth() <= 0) then
				pokedata.pokehead:setRot(-45 + -player:getRot().x*.25, 0, 0)
				worldRot = vectors.vec3(-player:getRot().x*.75,-player:getBodyYaw(delta)+180,0)
			else
				pokedata.pokehead:setRot()
				worldRot = vectors.vec3(0,-player:getBodyYaw(delta)+180,0)
			end
		else
			models[pokedata.modelname]:setParentType()
			worldPos = vectors.vec3()
			worldRot = vectors.vec3()
			models[pokedata.modelname]:setLight()
			pokedata.pokehead:setRot()
		end
	end
end
]]--

local unswimtimer = 0
local wasSwim = false
function events.tick()
	local swim = player:getPose() == "SWIMMING" and Animpossible.canswim

	if not swim and wasSwim then 
		unswimtimer = 15
	end

	if unswimtimer >= 0 then
		unswimtimer = unswimtimer - 1
	end
	wasSwim = swim
end
local rootoverride = false
function events.render(delta,context,matrix)

	local swim = player:getPose() == "SWIMMING" and Animpossible.canswim
	local fly = player:getPose() == "FALL_FLYING" and Animpossible.canfly
	local faint = player:getHealth() <= 0 and Animpossible.canfaint
	local swimout = unswimtimer > 0



	if rootoverride then
		local playerRot = (player:getRot(delta) + 180) %360 - 180
		local bodyYaw = (player:getBodyYaw(delta) + 180) %360 - 180
		if not faint then
			setHeadRot(vec(-45 + -playerRot.x*.25, 0, 0))
			worldRot = vectors.vec3(-playerRot.x*.75,-bodyYaw+180,0)
		else
			--pokedata.pokehead:setRot()
			worldRot = vectors.vec3(0,-bodyYaw+180,0)
		end

		if unswimtimer >= 0 then
			
			worldRot.x = math.lerp(worldRot.x,0, (30-unswimtimer+delta)/30)
			local vanillahead = (vanilla_model.HEAD:getOriginRot() + 180) %360 - 180
			local headrot = math.lerp(-45, 0, (30-unswimtimer+delta)/30)
			setHeadRot(vec(headrot+ -vanillahead.x*.25, 0, 0))
		end
	else
		worldRot = vectors.vec3()
		--pokedata.pokehead:setRot()
	end
	rootoverride = swim or fly or faint or swimout
	wasSwim = swim

	--print(string.format('rootoverride: %s: %d', tostring(rootoverride), worldRot.y))
	renderer:setRootRotationAllowed(not rootoverride)
	
	models[pokedata.modelname]:setPos(posePos + worldPos)
	models[pokedata.modelname]:setRot(poseRot + worldRot)
end

--our movement stuff actually being called
animcheck()
--events.TICK:register(movementcontroller)

--texture animation
local animEntries = {}
local function initAnimatedTextures()
	local raw_parts = pokedata.animatedParts
	if not raw_parts and pokedata.animatedPart then
		raw_parts = {{
			part = pokedata.animatedPart,
			animtexname = pokedata.animtexname,
			framenumber = pokedata.framenumber,
			animfps = pokedata.animfps,
			animemissive = pokedata.animemissive
		}}
	end

	if raw_parts then
		for _, item in ipairs(raw_parts) do
			if item.part and item.framenumber and item.framenumber > 0 then
				local base_name = item.animtexname or ""
				local is_zero = textures[base_name.."0"] or textures[pokedata.modelname.."."..base_name.."0"]
				local frames = {}
				for f = 0, item.framenumber - 1 do
					local frame_num = is_zero and f or (f + 1)
					local tex_name = base_name..frame_num
					frames[f] = textures[tex_name] or textures[pokedata.modelname.."."..tex_name]
				end
				table.insert(animEntries, {
					part = item.part,
					frames = frames,
					framenumber = item.framenumber,
					fps = item.animfps or 10,
					emissive = item.animemissive
				})
			end
		end
	end
end
initAnimatedTextures()

local function textureanimator(delta)
	local animseconds = (world.getTime() + delta) / 20
	for _, entry in ipairs(animEntries) do
		local idx = math.floor(animseconds * entry.fps) % entry.framenumber
		local tex = entry.frames[idx]
		if tex then
			entry.part:setPrimaryTexture("CUSTOM", tex)
			if entry.emissive then
				entry.part:setSecondaryTexture("CUSTOM", tex)
			end
		end
	end
end

if #animEntries > 0 then
	events.RENDER:register(textureanimator)
end

--set pos and rot of the model based on calculated values

--check if we can even be shiny
if not pokedata.shinylocked and (textures[onlyname.."_shiny"] or textures[pokedata.modelname.."."..onlyname.."_shiny"]) then --shiny stuff
	--calculate if we're shiny and then change to the shiny texture and then remind other clients that we're shiny
	local shiny = false
	function pings.shiny()
		models[pokedata.modelname]:setPrimaryTexture("CUSTOM", textures[onlyname.."_shiny"] or textures[pokedata.modelname.."."..onlyname.."_shiny"])
	end

	if host:isHost() then
		if math.random(1,500) == 1 then
			shiny = true
			pings.shiny() 
		end
	end

	function events.tick()
		if world.getTime()%2400 == 0 and shiny then
			pings.shiny()
		end
	end
	
end


return getCurrentPose, pokedata.modelname, setOverride