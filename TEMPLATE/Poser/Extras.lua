--extra anims that cobblemon does not ever have, but you may want/need, can use this file by adding "Poser/Extras" into the auto scripts of avatar.json

RegisterPose(
    "sitting",
    {"STAND", "WALK"},
    "isRiding",
    nil,
    "riding", --this is the animation name
    10,
    "blink",
    nil,
    nil
)
--remember the default settings will have ground_walk play at 50% speed when crouching, what anims are slowed down with crouching can be configured in the config
RegisterPose(
    "crouching",
    "STAND",
    "isSneaking",
    nil,
    "ground_idle_sneak", --this is the animation name, could also do {"sneak", "ground_idle"}
    10,
    "blink",
    nil,
    nil
)

RegisterPose(
    "sneaking",
    "WALK",
    "isSneaking",
    nil,
    "ground_walk_sneak", --this is the animation name, could also do {"sneak", "ground_walk"}
    10,
    "blink",
    nil,
    nil
)