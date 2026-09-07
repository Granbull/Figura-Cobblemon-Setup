--Complete
--Includes Standard Animations as well as air_idle, air_fly, air_battle_idle

--valid poses are STAND, WALK, FLOAT, SWIM, HOVER, FLY, SLEEP FAINT
--MOVING_POSES, STATIONARY_POSES, STANDING_POSES, SWIMMING_POSES, FLYING_POSES

RegisterPose(
    "standing",
    "STATIONARY_POSES",
    nil,
    "isBattling",
    {"ground_idle","closed_wings"},
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
    {"ground_walk","closed_wings"},
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
    {"ground_run","closed_wings"},
    10,
    "blink",
    nil,
    nil
)
end

RegisterPose(
    "hover",
    "HOVER",
    nil,
    nil,
    {"air_idle","wings"},
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "fly",
    "FLY",
    nil,
    nil,
    {"air_fly","wings"},
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
    {"sleep","closed_wings"},
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
    {"battle_idle","closed_wings"},
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "battle-hover",
    "HOVER",
    "isBattling",
    nil,
    {"air_battle_idle","wings"},
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

Unblend("wings", "closed_wings")