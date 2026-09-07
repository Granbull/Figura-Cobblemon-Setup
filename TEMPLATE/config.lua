local config = {
--user customization
	--name to appear in nametag, defaults to pokemon name if nil
	nickname = nil,

	--whether you want the chance to be shiny
	shinylocked = false,

--pokemon setup
	--REQUIRED
		--name of the model/pokemon
		modelname = "NAME_HERE",

		--Head setup, if unsure leave all but the "head" as their default
		pokehead = {--arg labels are notes for grabbing values from official posers
			{--copy this entire code block to add another head (line 16 to 28)
			["head"] = models["NAME_HERE"].PATH.TO.HEAD, --MODELPART GOES HERE, just put "NONE" after the = if you have no head
			["invertX"] = false, 		--whether or not the X axis rotation should be inverted
			["invertY"] = false, 		--where or not the Y axis rotation should be inverted
			["disableX"] = false,		--whether or not X rotation should apply to this head
			["disableY"] = false,		--whether or not Y rotation should apply to this head
			["pitchMultiplier"] = 1, 	--multiplier to apply to the X rotation		-arg1-
			["yawMultiplier"] = 1, 		--multiplier to apply to the Y rotation		-arg2-
			["maxPitch"] = 70,			--maximum rotation for the X rotation		-arg3-
			["minPitch"] = -45,			--minimum rotation for the X rotation		-arg4-
			["maxYaw"] = 45,			--maximum rotation for the Y rotation		-arg5-
			["minYaw"] = -45,			--minimum rotation for the Y rotation		-arg6-
			},
		},
	
	--OPTIONAL

		--find this value in common/src/main/resources/data/cobblemon/species/generationX/[pokemon].json
		pokescale = 1,

		--relative height of the camera, 1 is the default player, .5 would be half height
		camheight = 1,

		--crosshair adjustment can be flagged as cheating by servers, set to false if nessecary
		crosshairAdjust = true,

		--relative height that the nameplate should appear at, 1 is the default player, .5 would be half height
		nameplatepivot = 1,

		--set to true to remove the custom nameplate text to either just have your vanilla name or allow you more control over the nameplate in separate scripts
		vanillaplate = false,

		--whether you want to adjust the move animation speed of the walk to better match the animation, default off as the calculation is.. suspect
		speedscale = false,

		--find this value in common/src/main/resources/data/cobblemon/species/generationX/[pokemon].json. default is .35 if not present in the file, only does anything with speedscale on
		movespeed = 0.35,

		--scale adjustment for the paperdoll/inventory preview
		pdollscale = 1,

		--whether to use the cobblemon/resource pack sound or [pokemonname]_cry.ogg in the avatar's folder for the cry (pokemonname is the model's name with anything after an _ removed
		customcry = false,

		--animations to scale the speed of based on sprinting/crouching
		movement_anims = {
			"ground_walk",
		},

		--parts to be used to make the model look like its sitting while riding something
		legs = {
			--modelpart for the Left Leg
			left = nil,

			--modelpart for the Right Leg
			right = nil,
		},

		--animated part info can be found in common/src/main/resources/assets/cobblemon/textures/pokemon/[natdexnum]_[pokemon]/[subfolder (ex. flame)]

		--list of animated parts for models with animated textures (e.g. Ponyta mane and tail, Golurk fire hands)
		animatedParts = nil
}

	local addquirk = require("Pokemon.quirks")[1]
	--quirk info can be found at common/src/main/kotlin/com/cobblemon/mod/common/client/render/models/blockbench/pokemon/genX/[Pokemon]Model.kt
	--how to translate that info into what addquirk wants can be found in quirk.png
	--addquirk(name, animation, min, max, pose)
	addquirk("blink", animations[config.modelname].blink)

return config