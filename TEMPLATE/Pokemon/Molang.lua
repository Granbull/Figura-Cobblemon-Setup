-- Implementing math.mod for molang compatibility
-- Modified by ynrie to use native C functions
-- This is the alternative version (cached pcall)
function math.mod(x, y)
	return x % y
end

math.random_integer = math.random

-- Upvalue-cached trig: one multiply + one C call per invocation instead of
-- the old math.rad function-call overhead, while correctly treating the
-- entire argument as degrees (so additive constants like -90 convert too).
local _sin = math.sin
local _cos = math.cos
local DEG_TO_RAD = math.pi / 180

Math = Math or {}
Math.sin = function(a) return _sin(a * DEG_TO_RAD) end
Math.cos = function(a) return _cos(a * DEG_TO_RAD) end

-- Resolve q.anim_time to the calling animation's actual playback time via
-- traceback inspection (Auria's technique). All helpers are upvalue-cached
-- and a per-call-site cache eliminates string parsing after the first access
-- from each keyframe location.
local animlist = {}
for _, v in pairs(animations:getAnimations()) do
	animlist[v:getName()] = v
end

local _pcall = pcall
local _find = string.find
local _sub = string.sub
local anim_by_src = {}
local function err() error('', 4) end

q = setmetatable({}, {
	__index = function(_, i)
		if i == 'anim_time' then
			local _, tb = _pcall(err)
			local anim = anim_by_src[tb]
			if anim == nil then
				local pos = _find(tb, ' keyframe', 1, true)
				if pos then
					anim = animlist[_sub(tb, 1, pos - 1)]
				end
				anim_by_src[tb] = anim or false
			end
			return anim and anim:getTime()
		end
	end
})

local rot = vec(0, 0, 0)
local last_rot = rot
local rot_change = vec(0, 0, 0)
local last_rot_change = vec(0, 0, 0)
local friction = 0.6

function events.tick()
	last_rot = rot
	rot = (player:getRot().xy_ + 180) % 360 - 180
	last_rot_change = rot_change
	rot_acc = math.shortAngle(rot, last_rot) * -20
	rot_change = rot_change + rot_acc
	rot_change = rot_change * friction
end

function events.render(delta)
	rot_delta = math.lerp(last_rot_change, rot_change, delta)
end

q.r = {
	velocity_x = function()
		return 0
	end,
	velocity_y = function()
		return 0
	end,
	velocity_z = function()
		return 0
	end,
	yaw_change = function()
		return math.clamp(rot_delta.y / 140, -1, 1)
	end,
	pitch_change = function()
		return math.clamp(rot_delta.x / 90, -1, 1) * -1
	end,
	roll_change = function()
		return 0
	end,
	speed = function()
		return 0
	end,
	velocity_right = function()
		return 0
	end,
	velocity_left = function()
		return 0
	end,
	velocity_forward = function()
		return 0
	end,
	velocity_up = function()
		return 0
	end,
	yaw = function()
		return 0
	end,
	pitch = function()
		return 0
	end,
	roll = function()
		return 0
	end,
	input_right = function()
		return 0
	end,
	input_forward = function()
		return 0
	end,
	input_up = function()
		return 0
	end
}
query = q
