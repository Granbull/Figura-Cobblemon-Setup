--Complete
--Includes ground_idle, ground_walk, ground_run (will automatically check if actually present), sleep, battle_idle, faint
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
    "battle-standing",
    "STATIONARY_POSES",
    "isBattling",
    nil,
    "battle_idle",
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