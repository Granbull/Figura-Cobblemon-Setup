--Complete
--Includes standard animations as well as surfacewater_idle, surfacewater_swim, surfacewater_Battle_idle, surfacewater_sleep
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
    "float-surface",
    {"STAND","FLOAT"},
    "isTouchingWater",
    "isBattling",
    "surfacewater_idle",
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "swim-surface",
    {"WALK","SWIM"},
    "isTouchingWater",
    nil,
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
    "sleep-surface",
    "SLEEP",
    "isTouchingWater",
    nil,
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
    "battle-surface",
    {"STAND","FLOAT"},
    {"isTouchingWater", "isBattling"},
    nil,
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