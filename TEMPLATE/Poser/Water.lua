--Complete
--Includes standard animations as well as water_idle, water_swim, surfacewater_idle, surfacewater_swim,
--water_battle_idle, surfacewater_Battle_idle, water_sleep, surfacewater_sleep
--valid poses are STAND, WALK, FLOAT, SWIM, HOVER, FLY, SLEEP FAINT
--MOVING_POSES, STATIONARY_POSES, STANDING_POSES, SWIMMING_POSES, FLYING_POSES

RegisterPose(
    "standing",
    "STATIONARY_POSES",
    nil,
    "isBattling",
    "ground_idle",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "walking",
    "MOVING_POSES",
    nil,
    Animpossible.runanim and "isRunning" or nil,
    "ground_walk",
    10,
    "blink",
    nil,
    nil
)

if Animpossible.runanim then
RegisterPose(
    "running",
    "MOVING_POSES",
    "isRunning",
    nil,
    "ground_run",
    10,
    "blink",
    nil,
    nil
)
end

RegisterPose(
    "float",
    "FLOAT",
    {"isTouchingWater", "isSubmergedInWater"},
    "isBattling",
    "water_idle",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "float-surface",
    "STAND",
    "isTouchingWater",
    {"isSubmergedInWater", "isBattling"},
    "surfacewater_idle",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "swim",
    "SWIM",
    {"isTouchingWater", "isSubmergedInWater"},
    nil,
    "water_swim",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "swim-surface",
    "WALK",
    "isTouchingWater",
    "isSubmergedInWater",
    "surfacewater_swim",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "battle-sleep",
    "SLEEP",
    "isBattling",
    nil,
    "battle_sleep",
    10,
    nil,
    nil,
    nil
)

RegisterPose(
    "sleep",
    "SLEEP",
    nil,
    nil,
    "sleep",
    10,
    nil,
    nil,
    nil
)

RegisterPose(
    "sleep-water",
    "SLEEP",
    {"isTouchingWater", "isSubmergedInWater"},
    nil,
    "water_sleep",
    10,
    nil,
    nil,
    nil
)

RegisterPose(
    "sleep-surface",
    "SLEEP",
    "isTouchingWater",
    "isSubmergedInWater",
    "surfacewater_sleep",
    10,
    nil,
    nil,
    nil
)

RegisterPose(
    "battle-standing",
    "STAND",
    "isBattling",
    nil,
    "battle_idle",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "battle-water",
    "FLOAT",
    "isBattling",
    nil,
    "water_battle_idle",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "battle-surface",
    "STAND",
    {"isTouchingWater", "isBattling"},
    "isSubmergedInWater",
    "surfacewater_battle_idle",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "faint",
    "FAINT",
    nil,
    nil,
    "faint",
    10,
    nil,
    nil,
    nil
)