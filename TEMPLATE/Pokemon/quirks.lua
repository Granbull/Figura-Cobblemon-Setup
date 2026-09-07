local quirks = {}
local random = math.random
local getTime = world.getTime

--set up all the quirk info and the sane defaults
local function addquirk(name, anim, minsec, maxsec, pose, stopidle)
	if name and anim then
		local anims = type(anim) == "table" and anim or {anim}
		local minVal = minsec or 8
		local maxVal = maxsec or 30
		local poseList = type(pose) == "table" and pose or {pose}
		quirks[name] = {
			animation = anims,
			min = minVal,
			max = maxVal,
			pose = poseList,
			stopidle = stopidle or false,
			next = getTime() + (random(minVal, maxVal) * 20),
			nopose = pose == nil
		}
	end
end

local function addPose(name, ...)
	local quirk = quirks[name]
	if quirk then
		local poseTable = quirk.pose
		for _, value in ipairs{...} do
			if type(value) == "Animation" then
				poseTable[#poseTable + 1] = value
				quirk.nopose = false
			end
		end
	end
end

--returns true if one of our animations is supposed to override the idle
local function stoppedidle()
	for _, value in pairs(quirks) do 
		if value.stopidle then
			for _, anim in ipairs(value.animation) do
				if anim:isPlaying() then return true end
			end
		end
	end
	return false
end

--schedules and plays quirk animations
function events.tick()
	local currentTime = getTime()
	for _, value in pairs(quirks) do
		local playable = value.nopose
		if not playable then
			for _, anim in ipairs(value.pose) do
				if anim:isPlaying() then
					playable = true
					break
				end
			end
		end

		if playable and currentTime >= value.next then
			local animList = value.animation
			animList[random(#animList)]:play()
			value.next = currentTime + (random(value.min, value.max) * 20)
		end
	end
end

return {addquirk, addPose, stoppedidle}