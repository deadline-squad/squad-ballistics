"""Snapshot of every Squad Ballistics weapon view as the game files define it.

Reads the SquadExtract JSON dumps of the Squad paks and writes, for each entry of
``weapons.json`` (one entry per weapon *view*), the launch, flight and view values the
game gives, so a test oracle can check ``weapons.json`` against the game instead of
against itself.

Usage::

    python3 -I tools/game_weapons.py --build 26005357 --date 2026-10-30 \\
        --out tests/data/game_weapons.json \\
        [--root DIR ...] [--resolved resolved.json] [--compare weapons.json]

``--root`` (repeatable, searched in the order given) are SquadExtract ``dumpall``
output directories: ``<root>/SquadGame/Content/<path>.uasset.json`` with every export
of the asset. Without ``--root`` the roots in ``DEFAULT_ROOTS`` are used. They must
together hold the weapon, projectile, turret and tripod Blueprints, the weapons'
skeletal meshes and skeletons, the turrets' yaw-to-pitch curves and, for the RMB
divisor, the weapon Blueprints dumped with Kismet bytecode (the extractor built with
``provider.ReadScriptData = true``). ``--resolved`` is the output of
``tools/game_ballistics/collect.py``: when given, every weapon class it holds must give
the same muzzle velocity and projectile movement as this reader, or the run fails.
``--compare`` prints, after writing, a Markdown table of every value of the snapshot
that differs from that ``weapons.json`` (velocity, gravity, acceleration and its
time, max_speed, lifespan, rotation_follows_velocity, bore, zoom, elevation limits). The output depends only on the dumps and the
arguments; ``--date`` and ``--build`` are recorded in ``_source``.

Sources and rules (Squad build 26005357; units in the files are cm, the snapshot is
in m, m/s and degrees):

* Blueprint values are the deepest override along the class chain (a CDO and its
  components store only what differs from the parent), merged struct by struct.
  Components come from the CDO's default subobjects and the construction script
  templates (``*_GEN_VARIABLE``); a component's parent is its ``AttachParent`` or its
  construction-script parent node.
* Launch: ``WeaponConfig.MuzzleVelocity`` of the weapon, along its barrel socket
  ``WeaponConfig.BarrelSocketName``. Flight: the projectile's ``SQProjectileMovement``
  component: ``ProjectileGravityScale`` (x 9.80 m/s^2), ``MaxSpeed`` (clamped every
  substep, 0 = none), ``ConstantAcceleration.X`` for ``ConstantAccelerationTimeout``
  seconds (0 = the whole flight), ``bRotationFollowsVelocity`` and
  ``bIgnoreGravityDuringConstantAcceleration``. A field no Blueprint sets keeps the
  native default in ``NATIVE_DEFAULTS`` and is listed under ``sources.defaults``.
* bore (degrees the shot leaves above the centre of the view): the barrel socket's
  pitch minus the pitch of the camera the player looks through, both relative to the
  component the weapon is mounted on (``GunAttachPoint`` of a closed turret,
  ``GunMountComponent`` of an open turret or a tripod). The socket's pitch is the
  socket rotation composed with its bone's reference pose in the skeleton and the
  weapon mesh component's own rotation; the camera's is the rotations from the camera
  component up to the mount. Closed turrets: ``FirstPersonCamera``; open turrets:
  ``Camera1pPositionComponent`` (normal view) and ``AdsCamera1pPositionComponent``
  (RMB); tripods: ``FirstPersonVehicleCam`` (normal view) and
  ``AdsCamera1pPositionComponent`` (RMB). Weapons aimed by elevation or mils
  (mortars, UB-32, BM-21, Hell Cannon, the technical's mortar and UB-32, M1064) get
  ``bore`` and ``zoom`` null.
* zoom (FOV divisor, 1 = the game's FOV): a closed turret's gunner sight is its first
  ``ZoomLevels`` entry; an RMB sight is the divisor of the ``SetFieldOfView(FOV / k)``
  call in the weapon's ``BlueprintOnZoom`` graph (the most derived class that defines
  ``BlueprintOnZoom``; none = 1); the ZiS-3's RMB sight is its ``ZoomLevels[1]``.
* elevation_limits ([min, max] degrees of the shot): the mount's pitch limits
  (``RotationConstraints.PitchInterval``, or, when the turret has
  ``ParentYawToMinPitch`` / ``ParentYawToMaxPitch`` curves, their widest values over
  the turret's yaw; that the curves replace the interval is inferred from the M1A2,
  Leopard and Challenger 2, whose curves go to -10 under an inherited interval of -1
  or -0.5) plus the barrel socket's pitch on the mount; null for
  handheld weapons and for the weapons aimed by elevation, whose tube or launcher is
  laid by its own sight readout (the raw mount limits are in ``sources``).
* launch (the weapons of a vehicle that are aimed by elevation: Technical mortar and UB-32,
  M1064 M121, BM-21, and the direct-fire weapons whose view names a ``seat``: the MK19, AGS-17 and
  SPG-9 on vehicles): where the shell starts, in metres, for ``launch_height`` (the barrel's
  pivot above the ground), ``muzzle_forward`` (the barrel socket along the barrel from the
  pivot) and ``muzzle_up`` (above the barrel's axis). The pivot is the origin of the turret's
  mount component (``GunMountComponent``), which the pitch rotates; its place in the vehicle
  is the vehicle mesh's seat socket (or bone) composed with the turret mesh's attach socket
  (a socket the mesh lacks attaches at the component's origin, as UE does) and the mount's
  relative transform. The socket is the weapon's ``BarrelSocketName`` on the weapon mesh,
  which sits at the mount's origin. The ground is where the vehicle's wheels touch it in the
  reference pose: the lowest ``wheel_<side><n>`` bone minus the ``WheelRadius`` of that wheel in
  the vehicle config (the vehicle's suspension at rest and a track's thickness are not in the files).
  A turret whose mesh has its root bone away from its origin (the Kozak-2M1's AGS-17) and a boat
  (no wheels, floats on pontoons) are refused: their launch point is not in the files
  (deadline-squad/squad-ballistics#12). A muzzle up to 35 cm beside the barrel's vertical plane
  and a mount leaning up to 2 degrees in the vehicle's reference pose (the M113's) are accepted and
  noted in ``sources.launch``; the pitch limits stay the mount's. ``elevation_limits`` of
  these weapons are the mount's pitch limits plus the socket's pitch (the barrel's pitch), or,
  for the Technical mortar, the range of its HUD's degrees table (``hud``), whose readout is
  the mount's world pitch + 40.
* lifespan (s): the projectile Blueprint's ``InitialLifeSpan`` of the entry's first class: the
  projectile actor is destroyed that long after it spawns (0: never). A shot that takes longer
  cannot hit. Where the classes of an entry disagree (M72A7 LAW 20 s, RPG-26 5 s) the first
  class is the reference, like for the velocity and the movement.
* burst_radius (m): the widest ``ExplosiveDamageOuterRadius`` that deals damage among the
  entry's projectiles (``ExplosiveBaseDamage`` above 0, or the native 115 when the Blueprint
  sets no base damage; ``SecondaryExplosionOuterRadius`` when ``bUseSecondaryExplosion``);
  0 for a projectile whose Blueprints override no explosion field (the AP and APFSDS rounds:
  they hit with their impact damage and do not explode) and for smoke. ``warhead`` is
  "splash" when it is above ``SPLASH_RADIUS`` and "direct" otherwise: the shaped charges of
  the launchers and the SPG-9 burst within 8-10 m, the HE, FRAG, HESH, thermobaric and tank
  HEAT rounds within 16-35 m. A mixed entry (a tank's HEAT/HE) is "splash" when any of its
  rounds is.
* Handheld weapons: the game fires them along the barrel socket too (native
  ``ASQWeapon::GetAimDirection``, vtable slot 0xa78 of ``ASQWeapon`` in build 26005357),
  but the socket's angle to the ADS camera is set by the first-person animation and the
  sight, not by components this reads: ``bore`` 0 and ``zoom`` 1 are assumptions
  (``bore_assumed`` / ``zoom_assumed``), see ``HANDHELD``.

Each entry of ``ENTRIES`` names the weapon classes it covers (the first is the one
of the view the entry is for), the mount and camera of that view, the zoom source,
and other mounts that show the same view (checked; a mount that differs is listed
under ``view_variants``). Classes that differ from the first on a ballistic field are
listed under ``variants``. See tests/test_vehicle_sights.py and
tests/test_mark_end_to_end.py for how the views are used.
"""

import argparse
import json
import math
import os
import re
import sys

DEFAULT_ROOTS = (
    # SquadExtract dumpall with provider.ReadScriptData = true: every Blueprint
    # '^SquadGame/Content/(Vehicles/.*/BP_[^/]*|Vehicles/BP_[^/]*|Blueprints/Items/
    # (GrenadeLaunchers|RocketLaunchers)/.*BP_[^/]*|Blueprints/Items/BP_[^/]*)\.uasset$'
    # (bytecode for the RMB divisors), then the weapon meshes, skeletons and
    # yaw-to-pitch curves the other roots lack.
    "/tmp/sb-flight-data/sdump",
    "/tmp/sb-flight-data/mdump",
    # Every Blueprint under Blueprints/ and Vehicles/ (tools/game_ballistics/README.md).
    "~/data/squad-weapons/dump",
    # Vehicle and turret Blueprints, meshes and skeletons.
    "/tmp/mech/vdump2",
    "/tmp/mech/dump",
    "/tmp/mech/vdump",
    "/tmp/mech/dump2",
    "/tmp/mech/dump3",
    "/tmp/mech/dump4",
)

GENERATOR = "tools/game_weapons.py"

# Projectile movement fields a Blueprint may leave at the native (C++) value:
# UProjectileMovementComponent defaults, bRotationFollowsVelocity true for every
# ASQProjectile subclass, the Squad-only fields 0 / false.
NATIVE_DEFAULTS = {
    "MaxSpeed": 0.0,
    "ProjectileGravityScale": 1.0,
    "ConstantAcceleration": {"X": 0.0, "Y": 0.0, "Z": 0.0},
    "ConstantAccelerationTimeout": 0.0,
    "bRotationFollowsVelocity": True,
    "bIgnoreGravityDuringConstantAcceleration": False,
}

# Fields of a projectile Blueprint that make up its explosion, and the native (C++)
# values of the ones it may leave out (the same table as tools/game_ballistics/gamecheck.py).
EXPLOSION_FIELDS = ("ExplosiveBaseDamage", "ExplosiveDamageInnerRadius", "ExplosiveDamageOuterRadius",
                    "ExplosiveDamageFalloff", "ExplosiveDamageDistanceFromImpactNormal")
NATIVE_EXPLOSION = {"ExplosiveBaseDamage": 115.0, "ExplosiveDamageOuterRadius": 1500.0, "bUseSecondaryExplosion": False}

# A round whose damaging explosion reaches further than this (m) is a splash round: its hit is
# judged by the ground around the impact, not by the height at the target.
SPLASH_RADIUS = 10.0

BALLISTIC_FIELDS = ("velocity", "gravity_scale", "max_speed", "acceleration", "acceleration_timeout")

# Camera components (see the module docstring).
CLOSED_SIGHT = "FirstPersonCamera"
OPEN_PLAIN = "Camera1pPositionComponent"
TRIPOD_PLAIN = "FirstPersonVehicleCam"
ADS = "AdsCamera1pPositionComponent"

HANDHELD = (
    "handheld: the shot leaves along the barrel socket (native ASQWeapon::GetAimDirection and "
    "GetProjectileSpawnTransform read WeaponConfig.BarrelSocketName on the weapon mesh and add the "
    "soldier's sway), but the socket's angle to the ADS camera comes from the 1P animation pose and "
    "the sight, which the Blueprints do not hold; bore 0 and zoom 1 are assumed"
)


def view(mount, camera, zoom, also=(), seat=None):
    """One entry's view: the mount Blueprint (turret, tripod) the weapon sits on, the
    camera component on it the player looks through, the zoom source and other
    mounts that must show the same view.

    `zoom` is ("levels", i): the mount's ZoomLevels[i]; ("rmb",): the weapon's RMB
    divisor from its bytecode; ("plain",): 1. `also` holds (mount, weapon) pairs, or
    (mount, weapon, seat) triples when the other vehicle's launch point is compared too.
    `seat` (see `seat()`) is the vehicle the entry's turret is on: with it the entry gets
    a `launch` (pivot height, muzzle reach and rise), as the weapons aimed by elevation do.
    """
    return {"mount": mount, "camera": camera, "zoom": zoom, "also": tuple(also), "seat": seat}


INDIRECT = "indirect"


def seat(vehicle, socket, hud=None):
    """Where a vehicle's turret hangs: the vehicle Blueprint, the socket (or bone) of its mesh
    the seat attaches the turret to (SeatAttachSocket) and, for a readout the files show, the
    HUD widget that lists its degrees."""
    return {"vehicle": vehicle, "seat": socket, "hud": hud}

# weapons.json entry -> (weapon classes, view). Paths are relative to /Game/. The first
# class is the one of the view the entry is for; view None = handheld; INDIRECT = aimed
# by elevation (bore and zoom null). Mounts and cameras were read off the Blueprints:
# closed turrets put the camera and the gun on GunAttachPoint, open turrets and tripods
# on GunMountComponent.
GL = "Blueprints/Items/GrenadeLaunchers/"
RL = "Blueprints/Items/RocketLaunchers/"
V = "Vehicles/"
AGS17 = V + "Kozak_2M1_AFU/"  # the vehicle AGS-17 weapon Blueprints live in the Kozak-2M1 folder
MK19_TRIPOD = view(V + "Emplaced_Mk19/BP_EmplacedMk19_Tripod", ADS, ("rmb",), also=(
    (V + "Emplaced_Mk19/BP_EmplacedC16_Tripod", V + "Emplaced_Mk19/BP_Weapon_C16"),
    (V + "Emplaced_Mk19/BP_EmplacedL134A1_Tripod", V + "Emplaced_Mk19/BP_Weapon_L134A1"),
))
QLZ_TURRETS = (
    (V + "CSK131/Weapons/BP_QLZ87_CSK_OpenTop_Turret", V + "CSK131/Weapons/BP_QLZ87_OpenTurret_Weapon"),
    (V + "WZ551/Turrets/QLZ87/BP_QLZ87_WZ551_OpenTop_Turret", V + "WZ551/Turrets/QLZ87/BP_QLZ87_Weapon_WZ551"),
    (V + "ZBL08/Turrets/Cupola_QLZ87/BP_QLZ87_ZBL08_OpenTop_Turret", V + "ZBL08/Turrets/Cupola_QLZ87/BP_QLZ87_Weapon_ZBL08"),
)
QLZ_CLASSES = [V + "Lynx_8x8/Weapons/BP_QLZ87_Weapon_Lynx8x8"] + [w for _, w in QLZ_TURRETS]
T72_FAMILY = (  # (turret, AP, HEAT, Frag): the T-72A / T-72S / T-90A / Sprut beside the T-72B3
    (V + "T72A/Turrets/BP_T72A_IMF_Turret", V + "T72A/Weapons/BP_2A46_T72A_AP", V + "T72A/Weapons/BP_2A46_T72A_HEAT", V + "T72A/Weapons/BP_2A46_T72A_Frag"),
    (V + "T72AV/Turrets/BP_T72S_GFI_Turret", V + "T72AV/Weapons/BP_2A46_T72S_AP", V + "T72AV/Weapons/BP_2A46_T72S_HEAT", V + "T72AV/Weapons/BP_2A46_T72S_Frag"),
    (V + "T90A/Turrets/BP_T90A_Turret", V + "T90A/Weapons/BP_2A46M_AP", V + "T90A/Weapons/BP_2A46M_HEAT", V + "T90A/Weapons/BP_2A46M_Frag"),
    (V + "Sprut-SDM1/Turrets/BP_Sprut_Turret", V + "Sprut-SDM1/Weapons/BP_2A45_AP", V + "Sprut-SDM1/Weapons/BP_2A45_HEAT", V + "Sprut-SDM1/Weapons/BP_2A45_Frag"),
)
T72B3 = V + "T72B3/Turrets/BP_T72B3_Turret"
M1A2 = V + "M1A2/Turrets/BP_M1A2_Turret"
AUS_M1A1 = V + "AUS_M1A1/Turrets/BP_AUS_M1A1_Turret"
LEOPARD = V + "Leopard2/Turrets/BP_2A6_Turret_Woodland"
M60T = V + "M60T/Turrets/BP_M60T_Turret"
M60T_WPMC = V + "M60T_WPMC/Turrets/BP_M60T_Turret_WPMC"
FV4034 = V + "FV4034/Turrets/BP_FV4034_Turret"
M1128 = V + "M1128_MGS/Turrets/BP_M1128_Turret"
ZTZ99 = V + "ZTZ99/Turrets/BP_ZTZ99_Turret"
ZTZ99_CAGE = V + "ZTZ99/Turrets/BP_ZTZ99_Turret_Cage"
T62 = V + "T62/Turrets/BP_T62_Turret"
T64 = V + "T64_BM2/Turrets/BP_T64BM2_Turret"
ZTD05 = V + "ZTD05/Turrets/BP_ZTD05_Turret"
ZTD05_WOODLAND = V + "ZTD05/Turrets/BP_ZTD05_Turret_WoodLand"
SPG9_TRIPOD = V + "Emplaced_SPG9/BP_EmplacedSPG9_Tripod"
SPG9_SCOPE_TRIPOD = V + "Emplaced_SPG9/BP_EmplacedSPG9_TripodScope"
SPG9_TECHNICAL = V + "Technical/Turrets/BP_Technical_Turret_SPG9"
AGS17_TRIPOD = V + "Emplaced_AGS-17/BP_Emplaced_AGS-17_Tripod"
AGS17_OPTIC_TRIPOD = V + "Emplaced_AGS-17/BP_Emplaced_AGS-17_Optic_Tripod"
QLZ_TRIPOD = V + "Emplaced_QLZ87/BP_EmplacedQLZ87_Tripod"
ZIS3 = V + "Emplaced_ZiS3_Cannon/BP_ZiS3_Base"


def tank(turret, also=(), seat=None):
    """The gunner's sight of a closed turret at its first zoom level."""
    return view(turret, CLOSED_SIGHT, ("levels", 0), also, seat)


MK19_OPEN = V + "Emplaced_Mk19/BP_Mk19_OpenTurret_Weapon"
M113_SEAT = "bone_manned_turretSocket"


def M113_MK19_VIEW(camera, zoom):
    """The MK19 open turret of the M113A3 and M113A2T (TLF), also its desert and cage variants."""
    return view(V + "M113A3/Turrets/BP_M113A3_OpenTurret_Mk19_Turret", camera, zoom, also=(
        (V + "M113A3/Turrets/BP_M113A3_OpenTurret_Mk19_Turret_Desert", MK19_OPEN, seat(V + "M113A3/BP_M113A3_MK19_Desert", M113_SEAT)),
        (V + "M113A3/Turrets/BP_M113A3_OpenTurret_Mk19_Turret_Desert", MK19_OPEN, seat(V + "M113A3/BP_M113A3_MK19_Desert_Cage", M113_SEAT)),
        (V + "M113A2T_TLF/Turrets/BP_M113A2T_TLF_OpenTurret_Mk19_Turret", MK19_OPEN, seat(V + "M113A2T_TLF/BP_M113A2T_MK19_TLF", M113_SEAT)),
        (V + "M113A2T_TLF/Turrets/BP_M113A2T_TLF_Desert_OpenTurret_Mk19_Turret", MK19_OPEN, seat(V + "M113A2T_TLF/BP_M113A2T_MK19_TLF_Desert", M113_SEAT))),
        seat=seat(V + "M113A3/BP_M113A3_MK19", M113_SEAT))


def M1151_MK19_VIEW(camera, zoom):
    """The MK19 open turret of the M1151 (all four Blueprints: plain, Woodland, Light, Light Woodland)."""
    turret, woodland = V + "M1151/Turrets/BP_M1151_Mk19_Turret", V + "M1151/Turrets/BP_M1151_Mk19_Turret_Woodland"
    return view(turret, camera, zoom, also=(
        (woodland, MK19_OPEN, seat(V + "M1151/BP_M1151_Mk19_Woodland", "socket_turret")),
        (turret, MK19_OPEN, seat(V + "M1151/BP_M1151_Light_Mk19", "socket_turret")),
        (woodland, MK19_OPEN, seat(V + "M1151/BP_M1151_Light_Mk19_Woodland", "socket_turret"))),
        seat=seat(V + "M1151/BP_M1151_Mk19", "socket_turret"))


def MATV_MK19_VIEW(camera, zoom):
    """The MK19 open turret of the MATV (the M1151's turret on the MATV's turret socket), also USMC and Woodland."""
    turret, woodland = V + "M1151/Turrets/BP_M1151_Mk19_Turret", V + "M1151/Turrets/BP_M1151_Mk19_Turret_Woodland"
    return view(turret, camera, zoom, also=(
        (V + "M1151/Turrets/BP_M1151_Mk19_Turret_Green", MK19_OPEN, seat(V + "MATV/BP_MATV_Mk19_Woodland", "bone_turretSocket")),
        (turret, MK19_OPEN, seat(V + "MATV_USMC/BP_MATV_Mk19_USMC", "bone_turretSocket")),
        (woodland, MK19_OPEN, seat(V + "MATV_USMC/BP_MATV_Mk19_USMC_Woodland", "bone_turretSocket"))),
        seat=seat(V + "MATV/BP_MATV_Mk19", "bone_turretSocket"))


def AGS17_VIEW(turret, vehicle, socket, also=()):
    """An AGS-17 on a vehicle's open turret: the open-sight gun (barrel socket 4.5 degrees up), the same
    camera pitch in the normal view and on RMB, no zoom."""
    return view(turret, OPEN_PLAIN, ("plain",), also, seat=seat(vehicle, socket))


def SPG9_2SEATER_ALSO(weapon):
    """The other Technical2Seater Blueprints that carry the SPG-9 (camo, armoured camo): same seat."""
    return tuple((SPG9_TECHNICAL, V + "Technical/Weapons/" + weapon, seat(V + "Technical2Seater/" + vehicle, "socket_turret"))
                 for vehicle in ("BP_Technical2Seater_Camo_SPG9", "BP_Armored_Technical2Seater_Camo_SPG9"))


def SPG9_VIEW(camera, zoom, vehicle, also=()):
    """The SPG-9 on a technical's open turret: the scope gun's barrel socket, RMB divisor 4."""
    return view(SPG9_TECHNICAL, camera, zoom, also, seat=seat(vehicle, "socket_turret"))


ENTRIES = {
    # Under-barrel and handheld grenade launchers and rockets: no mount.
    "M203 / M320 / GP-25 / HK79 / SL40": ([GL + "M4M203_UGL/BP_M4M203_UGL_Parent", GL + "M320/BP_M320_Parent", GL + "AK74GP25_UGL/BP_AK74GP25_UGL_Parent", GL + "G3A3HK79_UGL/BP_G3A3HK79_UGL_HE", GL + "EF88SL40_UGL/BP_EF88_SL40_UGL_Parent"], None),
    "MGL / M32": ([GL + "MGL_GL/BP_MGL_Parent", GL + "M32/BP_M32_Parent"], None),
    "AK-40GL (MPT-76)": ([GL + "MPT76AK40_UGL/BP_MPT76_AK40GL_UGL_Parent"], None),
    "QLG10": ([GL + "QBZ-95-1_QLG-10_UGL/BP_QBZ95-1_QLG-10_UGL_Parent"], None),
    "Rifle grenade": ([GL + "FNFAL_GL/BP_FNFAL_GL_Frag", GL + "FNFAL_GL/BP_FNFAL_GL_HEAT"], None),
    # MK19 of the M1117's gunner sight (ZoomLevels [1, 4.5]); no launch point: the files hang its
    # turret on a socket 1.2 m below the hull's turret bone, the CROWS mesh is at 2.6 m (#NN).
    "MK19": ([V + "M1117/Weapons/BP_M1117_MK19", V + "RHIB/Weapons/BP_Mk19_RHIB_Weapon", V + "Emplaced_Mk19/BP_Mk19_OpenTurret_Weapon"],
             tank(V + "M1117/Turrets/BP_M1117_Turret")),
    "MK19 · AAVP-7A1": ([V + "AAVP7A1/Weapons/BP_AAVP7A1_MK19", V + "AAVP7A1/Weapons/BP_AAVP7A1_MK19_Woodland"],
                        tank(V + "AAVP7A1/Turrets/BP_AAVP7A1_Turret", also=((V + "AAVP7A1/Turrets/BP_AAVP7A1_Turret_Woodland", V + "AAVP7A1/Weapons/BP_AAVP7A1_MK19_Woodland",
                                                                          seat(V + "AAVP7A1/BP_AAVP7A1_Woodland", "bone_turret")),),
                             seat=seat(V + "AAVP7A1/BP_AAVP7A1", "bone_turret"))),
    "MK19 · PARS III RWS": ([V + "PARS_III/Sancak_RWS/Weapons/BP_SancakRWS_MK19"],
                            tank(V + "PARS_III/Sancak_RWS/BP_SancakRWS_MK19_Turret", also=((V + "PARS_III/Sancak_RWS/BP_SancakRWS_MK19_Turret_Desert", V + "PARS_III/Sancak_RWS/Weapons/BP_SancakRWS_MK19_Desert",
                                                                                           seat(V + "PARS_III/BP_PARS3_MK19_Desert", "bone_RWSSocket")),),
                                 seat=seat(V + "PARS_III/BP_PARS3_MK19", "bone_RWSSocket"))),
    "MK19 · TAPV C16 RWS": ([V + "TAPV/Protector_C16/BP_C16_MK19"],
                            tank(V + "TAPV/Protector_C16/BP_C16_Turret", also=((V + "TAPV/Protector_C16/BP_C16_Turret_Desert", V + "TAPV/Protector_C16/BP_C16_MK19_Desert",
                                                                               seat(V + "TAPV/BP_TAPV_C16_Desert", "bone_turretSocket")),),
                                 seat=seat(V + "TAPV/BP_TAPV_C16", "bone_turretSocket"))),
    # Open turrets aimed through the sights (RMB moves the camera to the ADS position, no zoom) or
    # from the normal view (the camera is on the barrel's axis).
    "MK19 · M113 open turret": ([MK19_OPEN], M113_MK19_VIEW(ADS, ("rmb",))),
    "MK19 · M113 open turret · no sights": ([MK19_OPEN], M113_MK19_VIEW(OPEN_PLAIN, ("plain",))),
    "MK19 · M1151 open turret": ([MK19_OPEN], M1151_MK19_VIEW(ADS, ("rmb",))),
    "MK19 · M1151 open turret · no sights": ([MK19_OPEN], M1151_MK19_VIEW(OPEN_PLAIN, ("plain",))),
    "MK19 · MATV open turret": ([MK19_OPEN], MATV_MK19_VIEW(ADS, ("rmb",))),
    "MK19 · MATV open turret · no sights": ([MK19_OPEN], MATV_MK19_VIEW(OPEN_PLAIN, ("plain",))),
    "MK19 · RHIB open turret": ([V + "RHIB/Weapons/BP_Mk19_RHIB_Weapon"], view(V + "RHIB/Turrets/BP_RHIB_Turret_Mk19", ADS, ("rmb",))),
    "MK19 · emplacement / C16 / L134A1": ([V + "Emplaced_Mk19/BP_Mk19_Weapon", V + "Emplaced_Mk19/BP_Weapon_C16", V + "Emplaced_Mk19/BP_Weapon_L134A1"], MK19_TRIPOD),
    "MK19 · emplacement / C16 / L134A1 · no sights": ([V + "Emplaced_Mk19/BP_Mk19_Weapon", V + "Emplaced_Mk19/BP_Weapon_C16", V + "Emplaced_Mk19/BP_Weapon_L134A1"],
                                                      dict(MK19_TRIPOD, camera=TRIPOD_PLAIN, zoom=("plain",))),
    # AGS-17 tripods: the optic gun (Attach_Muzzle_Scoped) and the open-sight gun (Attach_Muzzle).
    "AGS-17 · emplacement · optic (RMB ×2.5)": ([V + "Emplaced_AGS-17/BP_AGS-17_Weapon_Optic", V + "Emplaced_AGS-17/BP_AGS-17_Weapon"], view(AGS17_OPTIC_TRIPOD, ADS, ("rmb",))),
    "AGS-17 · emplacement · no optic": ([V + "Emplaced_AGS-17/BP_AGS-17_Weapon_Optic"], view(AGS17_OPTIC_TRIPOD, TRIPOD_PLAIN, ("plain",))),
    "AGS-17 · iron sights emplacement": ([V + "Emplaced_AGS-17/BP_AGS-17_Weapon"], view(AGS17_TRIPOD, TRIPOD_PLAIN, ("plain",))),
    # AGS-17 on vehicles: the open-sight gun (socket 4.5 degrees up), the mount's pitch limits -13..85.
    # The Kozak-2M1's and the RHIB's launch points are not in the files (#NN), so they have no entry.
    "AGS-17 · Technical": ([AGS17 + "Weapons/AGS-17/BP_AGS-17_Technical_Weapon"],
                           AGS17_VIEW(V + "Technical/Turrets/BP_Technical_Turret_AGS17", V + "Technical2Seater/BP_Technical2Seater_White_AGS17", "socket_turret", also=(
                               (V + "Technical/Turrets/BP_Technical_Turret_AGS17", AGS17 + "Weapons/AGS-17/BP_AGS-17_Technical_Weapon", seat(V + "Technical2Seater/BP_Technical2Seater_Camo_AGS17", "socket_turret")),
                               (V + "Technical/Turrets/BP_Technical_Turret_AGS17", AGS17 + "Weapons/AGS-17/BP_AGS-17_Technical_Weapon", seat(V + "Technical_Armoured/BP_Armored_Technical2Seater_White_AGS17", "socket_turret")),
                               (V + "Technical/Turrets/BP_Technical_Turret_AGS17", AGS17 + "Weapons/AGS-17/BP_AGS-17_Technical_Weapon", seat(V + "Technical_Armoured/BP_Armored_Technical2Seater_Camo_AGS17", "socket_turret"))))),
    "AGS-17 · Tigr": ([AGS17 + "Turrets/BP_AGS-17_OpenTurret_Weapon"],
                      AGS17_VIEW(V + "Tigr/Turrets/BP_Tigr_AGS17_Turret", V + "Tigr/BP_Tigr_AGS17", "bone_turretSocket_AGS17", also=(
                          (V + "Tigr/Turrets/BP_Tigr_AGS17_Turret_Desert", AGS17 + "Turrets/BP_AGS-17_OpenTurret_Weapon", seat(V + "Tigr/BP_Tigr_AGS17_Desert", "bone_turretSocket_AGS17")),))),
    "AGS-17 · Safir": ([AGS17 + "Weapons/AGS-17/BP_AGS-17_Safir_Weapon"],
                       AGS17_VIEW(V + "Safir/Turrets/BP_Safir_Turret_AGS-17", V + "Safir/BP_Safir_AGS-17", "socket_turret_ags17")),
    "AGS-17 · M1151": ([AGS17 + "Turrets/BP_AGS-17_OpenTurret_Weapon"],
                       AGS17_VIEW(V + "M1151/Turrets/BP_M1151_AGS17_Turret", V + "M1151_MEI/BP_M1151_Technical_AGS17", "socket_turret")),
    "AGS-17 · BTR-D": ([AGS17 + "Turrets/BP_AGS-17_OpenTurret_Weapon"],
                       AGS17_VIEW(V + "BTR-D/Turrets/BP_BTR-D_AGS17_Turret", V + "BTR-D/BP_BTR-D_AGS17", "bone_turret_Kord", also=(
                           (V + "BTR-D/Turrets/BP_BTR-D_AGS17_Turret", AGS17 + "Turrets/BP_AGS-17_OpenTurret_Weapon", seat(V + "BTR-D/BP_BTR-D_AGS17_Desert", "bone_turret_Kord")),))),
    # QLZ87 tripod and the open turrets of the Lynx, CSK131, WZ551 and ZBL-08.
    "QLZ87 · optic (RMB ×3)": ([V + "Emplaced_QLZ87/BP_QLZ87_Weapon", GL + "QLZ-87/BP_QLZ-87_AGL_Parent", V + "CSK131/Weapons/BP_QLZ87_OpenTurret_Weapon"], view(QLZ_TRIPOD, ADS, ("rmb",))),
    "QLZ87 · no optic": ([V + "Emplaced_QLZ87/BP_QLZ87_Weapon"], view(QLZ_TRIPOD, TRIPOD_PLAIN, ("plain",))),
    "QLZ87 · Lynx / CSK131 · optic (RMB ×3)": (QLZ_CLASSES, view(V + "Lynx_8x8/Weapons/BP_QLZ87_Lynx8x8_OpenTop_Turret", ADS, ("rmb",), also=QLZ_TURRETS)),
    "QLZ87 · Lynx / CSK131 · no optic": (QLZ_CLASSES, view(V + "Lynx_8x8/Weapons/BP_QLZ87_Lynx8x8_OpenTop_Turret", OPEN_PLAIN, ("plain",), also=QLZ_TURRETS)),
    # AGS-30 / KBA-117 gunner's sights (socket BarrelStart_AGS).
    "AGS-30 / BTR-4 AGS": ([V + "BTR4/Weapons/BP_BTR4_KBA117"], tank(V + "BTR4/Turrets/BP_BTR4_Turret")),
    "AGS-30 (BMP-1TS)": ([V + "BMP1TS_AFU/Weapons/BP_BMP1TS_KBA117"], tank(V + "BMP1TS_AFU/Turrets/BP_BMP1TS_Turret")),
    "AGS-30 (BMP-2M)": ([V + "BMP-2M/Weapons/Woodland/BP_BMP2M_AGS30"],
                        tank(V + "BMP-2M/Turrets/BP_BMP2M_Turret", also=((V + "BMP-2M/Turrets/BP_BMP2M_Turret_Desert", V + "BMP-2M/Weapons/Desert/BP_BMP2M_AGS30_Desert"),))),
    "M72A7 LAW / RPG-26": ([RL + "BP_M72A7_M72A5_2mags", RL + "BP_RPG26_2mags", RL + "BP_HAR66_2mags"], None),
    "AT-4": ([RL + "BP_M136AT4"], None),
    "MK153 SMAW": ([RL + "SMAW/BP_SMAW_HEAT_2mags", RL + "SMAW/BP_SMAW_Tandem_2mags"], None),
    "PF98 · Tandem": ([RL + "PF-98/BP_PF-98_Tandem_2mags"], None),
    "PF98 · HE-I": ([RL + "PF-98/BP_PF-98_HE_2mags"], None),
    "RPG-29": ([RL + "BP_RPG29"], None),
    "C90-CR": ([RL + "C90/BP_C90CR"], None),
    "DZJ-08": ([RL + "DZJ-08/BP_DZJ-08"], None),
    "RPG-28": ([RL + "RPG28/BP_RPG28"], None),
    "RPG-7 · PG-7V HEAT / OG-7V": ([RL + "RPG7/RPG7/BP_RPG7_Heat", RL + "RPG7/RPG7/BP_RPG7_Frag"], None),
    "RPG-7 · PG-7VR Tandem": ([RL + "RPG7/RPG7/BP_RPG7_Tandem"], None),
    "RPG-7V1 · PG-7VR Tandem": ([RL + "RPG7/RPG7V1/BP_RPG7V1_Tandem"], None),
    "RPG-7V2 · PG-7VR Tandem": ([RL + "RPG7/RPG7V2/BP_RPG7V2_Tandem_2mag"], None),
    "RPG-7 · TBG-7V Thermobaric": ([RL + "RPG7/RPG7/BP_RPG7_Thermo"], None),
    "RPG-7V1 · HEAT": ([RL + "RPG7/RPG7V1/BP_RPG7V1_Heat", RL + "RPG7/RPG7V1/BP_RPG7V1_Frag"], None),
    "M3 MAAWS · HEAT / Smoke": ([RL + "M3MAAWS/BP_M3MAAWS_Heat", RL + "M3MAAWS/BP_M3MAAWS_Smoke"], None),
    "M3 MAAWS · Tandem": ([RL + "M3MAAWS/BP_M3MAAWS_Tandem"], None),
    "Carl Gustav M2 · FFV551 HEAT": ([RL + "BP_CarlGustavM2_Parent"], None),
    "Carl Gustav M2 · FFV441D HE": ([RL + "BP_CarlGustavM2_FFV441D_No78Mk1"], None),
    "Carl Gustav M2 · FFV751 Tandem": ([RL + "BP_CarlGustavM2_FFV751_No78Mk1"], None),
    "NLAW": ([RL + "NLAW/BP_NLAW"], None),
    # SPG-9: open-sight tripod (no RMB zoom), scope tripod (RMB x4); the technical's SPG-9
    # has the scope gun's socket and RMB divisor.
    "SPG-9 · HEAT": ([V + "Emplaced_SPG9/BP_EmplacedSPG9", V + "Technical/Weapons/BP_SPG9"], view(SPG9_TRIPOD, TRIPOD_PLAIN, ("plain",))),
    "SPG-9 · HEAT · scope · optic (RMB ×4)": ([V + "Emplaced_SPG9/BP_EmplacedSPG9Scope", V + "Technical/Weapons/BP_SPG9"],
                             view(SPG9_SCOPE_TRIPOD, ADS, ("rmb",), also=((SPG9_TECHNICAL, V + "Technical/Weapons/BP_SPG9"),))),
    "SPG-9 · HEAT · scope · no optic": ([V + "Emplaced_SPG9/BP_EmplacedSPG9Scope"], view(SPG9_SCOPE_TRIPOD, TRIPOD_PLAIN, ("plain",))),
    "SPG-9 · FRAG": ([V + "Emplaced_SPG9/BP_EmplacedSPG9_Frag", V + "Technical/Weapons/BP_SPG9_Frag"], view(SPG9_TRIPOD, TRIPOD_PLAIN, ("plain",))),
    "SPG-9 · FRAG · scope · optic (RMB ×4)": ([V + "Emplaced_SPG9/BP_EmplacedSPG9_FragScope", V + "Technical/Weapons/BP_SPG9_Frag"],
                             view(SPG9_SCOPE_TRIPOD, ADS, ("rmb",), also=((SPG9_TECHNICAL, V + "Technical/Weapons/BP_SPG9_Frag"),))),
    "SPG-9 · FRAG · scope · no optic": ([V + "Emplaced_SPG9/BP_EmplacedSPG9_FragScope"], view(SPG9_SCOPE_TRIPOD, TRIPOD_PLAIN, ("plain",))),
    # SPG-9 on the technicals: the scope gun (socket 2.34 degrees up, RMB divisor 4); the Technical2Seater
    # (white, camo, armoured camo) and the INS armoured technical stand at different heights.
    "SPG-9 · HEAT · technical · optic (RMB ×4)": ([V + "Technical/Weapons/BP_SPG9"], SPG9_VIEW(ADS, ("rmb",), V + "Technical2Seater/BP_Technical2Seater_White_SPG9", also=SPG9_2SEATER_ALSO("BP_SPG9"))),
    "SPG-9 · HEAT · technical · no optic": ([V + "Technical/Weapons/BP_SPG9"], SPG9_VIEW(OPEN_PLAIN, ("plain",), V + "Technical2Seater/BP_Technical2Seater_White_SPG9", also=SPG9_2SEATER_ALSO("BP_SPG9"))),
    "SPG-9 · FRAG · technical · optic (RMB ×4)": ([V + "Technical/Weapons/BP_SPG9_Frag"], SPG9_VIEW(ADS, ("rmb",), V + "Technical2Seater/BP_Technical2Seater_White_SPG9", also=SPG9_2SEATER_ALSO("BP_SPG9_Frag"))),
    "SPG-9 · FRAG · technical · no optic": ([V + "Technical/Weapons/BP_SPG9_Frag"], SPG9_VIEW(OPEN_PLAIN, ("plain",), V + "Technical2Seater/BP_Technical2Seater_White_SPG9", also=SPG9_2SEATER_ALSO("BP_SPG9_Frag"))),
    "SPG-9 · HEAT · INS armoured technical · optic (RMB ×4)": ([V + "Technical/Weapons/BP_SPG9"], SPG9_VIEW(ADS, ("rmb",), V + "Technical_Armoured/BP_Technical_SPG9_INS_Armoured")),
    "SPG-9 · HEAT · INS armoured technical · no optic": ([V + "Technical/Weapons/BP_SPG9"], SPG9_VIEW(OPEN_PLAIN, ("plain",), V + "Technical_Armoured/BP_Technical_SPG9_INS_Armoured")),
    "SPG-9 · FRAG · INS armoured technical · optic (RMB ×4)": ([V + "Technical/Weapons/BP_SPG9_Frag"], SPG9_VIEW(ADS, ("rmb",), V + "Technical_Armoured/BP_Technical_SPG9_INS_Armoured")),
    "SPG-9 · FRAG · INS armoured technical · no optic": ([V + "Technical/Weapons/BP_SPG9_Frag"], SPG9_VIEW(OPEN_PLAIN, ("plain",), V + "Technical_Armoured/BP_Technical_SPG9_INS_Armoured")),
    # 2A28 Grom: BMP-1 (and the BMP-1 technical), BMD-1M.
    "2A28 Grom (BMP-1 / BMD-1) · HEAT": ([V + "BMP-1/Weapons/BP_BMP1_2A28_HEAT", V + "BMD-1M/Weapons/BP_BMD1M_2A28_HEAT", V + "Technical2Seater/Weapons/BP_Technical_BMP1_2A28_HEAT"],
                                         tank(V + "BMP-1/Turrets/BP_BMP1_Turret_MEI", also=((V + "Technical2Seater/Turrets/BP_BMP1_Turret_Technical", V + "Technical2Seater/Weapons/BP_Technical_BMP1_2A28_HEAT"),))),
    "2A28 Grom (BMD-1M) · HEAT": ([V + "BMD-1M/Weapons/BP_BMD1M_2A28_HEAT"], tank(V + "BMD-1M/Turrets/BP_BMD1M_Turret")),
    "2A28 Grom (BMP-1 / BMD-1) · FRAG": ([V + "BMP-1/Weapons/BP_BMP1_2A28_Frag", V + "BMD-1M/Weapons/BP_BMD1M_2A28_Frag", V + "Technical2Seater/Weapons/BP_Technical_BMP1_2A28_Frag"],
                                         tank(V + "BMP-1/Turrets/BP_BMP1_Turret_MEI", also=((V + "Technical2Seater/Turrets/BP_BMP1_Turret_Technical", V + "Technical2Seater/Weapons/BP_Technical_BMP1_2A28_Frag"),))),
    "2A28 Grom (BMD-1M) · FRAG": ([V + "BMD-1M/Weapons/BP_BMD1M_2A28_Frag"], tank(V + "BMD-1M/Turrets/BP_BMD1M_Turret")),
    # 2A70 100mm: BMP-3M, ZBD-04A, BMD-4M.
    "2A70 100mm (BMP-3 / BMD-4 / ZBD04A) · FRAG": ([V + "BMP-3M/Weapons/BP_BMP3M_2A70_HEFrag", V + "BMD-4M/Weapons/BP_BMD4M_2A70_HEFrag", V + "ZBD04A/Weapons/BP_ZBD04A_2A70_HEFrag"], tank(V + "BMP-3M/Turrets/BP_BMP3M_Turret")),
    "2A70 100mm (ZBD-04A) · FRAG": ([V + "ZBD04A/Weapons/BP_ZBD04A_2A70_HEFrag"], tank(V + "ZBD04A/Turrets/BP_ZBD04A_Turret")),
    "2A70 100mm (BMD-4M) · FRAG": ([V + "BMD-4M/Weapons/BP_BMD4M_2A70_HEFrag"], tank(V + "BMD-4M/Turrets/BP_BMD4M_Turret")),
    # ZiS-3: RMB sight = ZoomLevels[1] (x4), normal view = ZoomLevels[0] (x1).
    "ZiS-3 · optic (RMB ×4)": ([V + "Emplaced_ZiS3_Cannon/Weapons/BP_ZiS3_Weapon_HEAT", V + "Emplaced_ZiS3_Cannon/Weapons/BP_ZiS3_Weapon_Frag"], view(ZIS3, ADS, ("levels", 1))),
    "ZiS-3 · no optic": ([V + "Emplaced_ZiS3_Cannon/Weapons/BP_ZiS3_Weapon_HEAT", V + "Emplaced_ZiS3_Cannon/Weapons/BP_ZiS3_Weapon_Frag"], view(ZIS3, TRIPOD_PLAIN, ("levels", 0))),
    # Tanks, AP: the T-72B3 view also covers the T-72A, T-72S, T-90A and Sprut-SDM1.
    "Tank AP · 2A46 / ZPT98 / 2A20 / 2A45 / KBA3": ([V + "T72B3/Weapons/BP_2A46_AP"] + [f[1] for f in T72_FAMILY] + [V + "ZTZ99/Weapons/BP_ZPT-98_AP", V + "T62/Weapons/BP_2A20_AP", V + "T64_BM2/Weapons/BP_KBA3_AP"],
                                                    tank(T72B3, also=tuple((f[0], f[1]) for f in T72_FAMILY))),
    "Tank AP · T-62 (2A20)": ([V + "T62/Weapons/BP_2A20_AP"], tank(T62)),
    "Tank AP · T-64BM2 (KBA3)": ([V + "T64_BM2/Weapons/BP_KBA3_AP"], tank(T64)),
    "Tank AP · ZTZ-99 (ZPT-98)": ([V + "ZTZ99/Weapons/BP_ZPT-98_AP"], tank(ZTZ99, also=((ZTZ99_CAGE, V + "ZTZ99/Weapons/BP_ZPT-98_AP"),))),
    "Tank AP · M256 / Rh120": ([V + "M1A2/Weapons/BP_M256A1_AP", V + "AUS_M1A1/Weapons/BP_M256A1_AP_ADF", V + "Leopard2/Weapons/BP_L55_AP", V + "M60T/Weapons/BP_MG253_AP"],
                               tank(M1A2, also=((AUS_M1A1, V + "AUS_M1A1/Weapons/BP_M256A1_AP_ADF"),))),
    "Tank AP · Leopard 2A6 (Rh120)": ([V + "Leopard2/Weapons/BP_L55_AP"], tank(LEOPARD)),
    "Tank AP · M60T (MG253)": ([V + "M60T/Weapons/BP_MG253_AP", V + "M60T_WPMC/Weapons/BP_MG253_AP_WPMC"], tank(M60T, also=((M60T_WPMC, V + "M60T_WPMC/Weapons/BP_MG253_AP_WPMC"),))),
    "Tank AP · L30A1 (Challenger 2) / M68A2": ([V + "FV4034/Weapons/BP_L30A1_AP", V + "M1128_MGS/Weapons/BP_M68A2_AP"], tank(FV4034)),
    "Tank AP · M1128 MGS (M68A2)": ([V + "M1128_MGS/Weapons/BP_M68A2_AP"], tank(M1128)),
    # Tanks, HEAT and HE/Frag: the classes each view fires (the turret's inventory).
    "Tank HEAT/HE · M256 / Rh120 / 2A46 / ZPT98 / 2A20 / M68A2": (
        [V + "T72B3/Weapons/BP_2A46_HEAT", V + "T72B3/Weapons/BP_2A46_Frag"] + [c for f in T72_FAMILY for c in f[2:]]
        + [V + "M1A2/Weapons/BP_M256A1_HEAT", V + "Leopard2/Weapons/BP_L55_HEAT", V + "ZTZ99/Weapons/BP_ZPT-98_HEAT", V + "ZTZ99/Weapons/BP_ZPT-98_HE",
           V + "T62/Weapons/BP_2A20_HEAT", V + "T62/Weapons/BP_2A20_Frag", V + "M1128_MGS/Weapons/BP_M68A2_HEAT", V + "M60T/Weapons/BP_MG253_Frag"],
        tank(T72B3, also=tuple((f[0], f[2]) for f in T72_FAMILY))),
    "Tank HEAT/HE · M1A1 / M1A2 (M256)": ([V + "M1A2/Weapons/BP_M256A1_HEAT"], tank(M1A2, also=((AUS_M1A1, V + "M1A2/Weapons/BP_M256A1_HEAT"),))),
    "Tank HEAT/HE · Leopard 2A6 (Rh120)": ([V + "Leopard2/Weapons/BP_L55_HEAT"], tank(LEOPARD)),
    "Tank HEAT/HE · M1128 MGS (M68A2)": ([V + "M1128_MGS/Weapons/BP_M68A2_HEAT"], tank(M1128)),
    "Tank HEAT/HE · M60T (MG253)": ([V + "M60T/Weapons/BP_MG253_Frag", V + "M60T_WPMC/Weapons/BP_MG253_Frag_WPMC"], tank(M60T, also=((M60T_WPMC, V + "M60T_WPMC/Weapons/BP_MG253_Frag_WPMC"),))),
    "Tank HEAT/HE · ZTZ-99 (ZPT-98)": ([V + "ZTZ99/Weapons/BP_ZPT-98_HEAT", V + "ZTZ99/Weapons/BP_ZPT-98_HE"], tank(ZTZ99, also=((ZTZ99_CAGE, V + "ZTZ99/Weapons/BP_ZPT-98_HEAT"),))),
    "Tank HEAT/HE · T-62 (2A20)": ([V + "T62/Weapons/BP_2A20_HEAT", V + "T62/Weapons/BP_2A20_Frag"], tank(T62)),
    "Tank HEAT/HE · T-64BM2 (KBA3)": ([V + "T64_BM2/Weapons/BP_KBA3_HEAT", V + "T64_BM2/Weapons/BP_KBA3_Frag"], tank(T64)),
    "Tank HESH · L30A1 (Challenger 2)": ([V + "FV4034/Weapons/BP_L30A1_HESH", V + "FV4034/Weapons/BP_L30A1_Smoke"], tank(FV4034)),
    "ZPL-98A 105mm (ZTD-05) · AP": ([V + "ZTD05/Weapons/BP_ZTD05_ZPL-98A_AP"], tank(ZTD05, also=((ZTD05_WOODLAND, V + "ZTD05/Weapons/BP_ZTD05_ZPL-98A_AP"),))),
    "ZPL-98A 105mm (ZTD-05) · HEAT / HE": ([V + "ZTD05/Weapons/BP_ZTD05_ZPL-98A_HEAT", V + "ZTD05/Weapons/BP_ZTD05_ZPL-98A_Frag"], tank(ZTD05, also=((ZTD05_WOODLAND, V + "ZTD05/Weapons/BP_ZTD05_ZPL-98A_HEAT"),))),
    # Aimed by elevation or mils: (weapon classes, INDIRECT, mount for the raw pitch limits).
    "Mortar (M252 / 2B14 / L16 / Type 63)": ([V + "BP_GenericMortarWeapon", V + "Emplaced_M252mortar/BP_M252mortar", V + "Emplaced_2b14podnosmortar/BP_2b14podnosmortar", V + "Emplaced_M252mortar/BP_L16mortar",
                                              V + "Emplaced_PP87Mortar/BP_PP87Mortar", V + "Emplaced_M1937mortar/BP_M1937mortar", V + "Emplaced_81mmMortar_CAF/BP_81mmMortar"],
                                             (INDIRECT, V + "BP_GenericDeployableMortarVehicle")),
    "Technical Mortar": ([V + "Technical2Seater/Weapons/BP_Technical_M1937mortar", V + "Technical2Seater_WPMC/Weapons/BP_Technical_M252mortar"], (INDIRECT, V + "Technical2Seater/Turrets/BP_Technical_MortarTurret",
                         seat(V + "Technical2Seater/BP_Technical2Seater_White_Mortar", "socket_turret_rear_mortar", hud=V + "Technical2Seater/Weapons/UMG_MortarHUD_Technical"))),
    "M1064 M121 (120mm)": ([V + "M1064A3/Weapons/BP_M1064A3_M121mortar", V + "M1064A3/Weapons/BP_M1064A3_M121mortar_Airburst"], (INDIRECT, V + "M1064A3/Turrets/BP_M1064A3_MortarTurret",
                         seat(V + "M1064A3/BP_M1064A3_M121", "1064_turretSocket"))),
    "Hell Cannon": ([V + "Emplaced_HellCannon/BP_Emplaced_HellCannon"], (INDIRECT, V + "Emplaced_HellCannon/BP_Emplaced_HellCannon_Base")),
    "UB-32 (S-5 rockets)": ([V + "Emplaced_UB32_RocketArtillery/BP_EmplacedUB32", V + "BRDM-2/Weapons/BP_BRDM2_GFI_UB32"], (INDIRECT, V + "Emplaced_UB32_RocketArtillery/BP_EmplacedUB32_Tripod")),
    "Technical UB-32": ([V + "Technical/Weapons/BP_UB32"], (INDIRECT, V + "Technical/Turrets/BP_Technical_Turret_UB32",
                         seat(V + "Technical2Seater/BP_Technical2Seater_White_UB32", "socket_turret"))),
    "BM-21 Grad": ([V + "Ural375_BM21Grad/Weapons/BP_BM21Grad_Weapon_MEI"], (INDIRECT, V + "Ural375_BM21Grad/Turrets/BP_BM21Grad_Turret_INS",
                seat(V + "Ural375_BM21Grad/BP_BM21Grad_MEI", "bone_turret"))),
}


class GameDataError(Exception):
    """A class, component, socket or value the snapshot needs is missing or ambiguous."""


class Assets:
    """The exports of every dumped asset, looked up by package path.

    Package paths are matched case-insensitively (FName comparison: Blueprints refer
    to `.../mesh/X` when the pak holds `.../Mesh/X`). The first root that holds a
    package wins; roots are read once and cached.
    """

    def __init__(self, roots):
        self.index = {}
        for root in roots:
            content = os.path.join(root, "SquadGame", "Content")
            for directory, _, files in sorted(os.walk(content)):
                for name in sorted(files):
                    if name.endswith(".uasset.json"):
                        path = os.path.join(directory, name)
                        key = os.path.relpath(path, content)[:-len(".uasset.json")].replace(os.sep, "/").lower()
                        self.index.setdefault(key, path)
        self.cache = {}

    def exports(self, package):
        """All exports of `package` ('/Game/X/Y' or 'X/Y'), or None when no root has it."""
        key = package[len("/Game/"):] if package.startswith("/Game/") else package
        key = key.lower()
        if key not in self.cache:
            path = self.index.get(key)
            if path is None:
                self.cache[key] = None
            else:
                with open(path, encoding="utf-8") as stream:
                    self.cache[key] = json.load(stream)
        return self.cache[key]

    def require(self, package):
        """`exports(package)`, raising GameDataError when it is not dumped."""
        found = self.exports(package)
        if found is None:
            raise GameDataError(f"{package}: not in any dump root")
        return found


def package_of(reference):
    """'/Game/A/B.C' or {'ObjectPath': '/Game/A/B.0'} -> '/Game/A/B'; None for none."""
    if isinstance(reference, dict):
        reference = reference.get("ObjectPath") or reference.get("AssetPathName")
    if not reference:
        return None
    head, _, _ = reference.partition(".")
    return head


def short(path):
    """The class or asset name at the end of a path."""
    return path.rsplit("/", 1)[-1] if path else path


def merge(base, override):
    """Struct-by-struct override of Blueprint properties."""
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for key, value in override.items():
            out[key] = merge(base[key], value) if key in base else value
        return out
    return override


def component_name(reference):
    """Component name from an AttachParent reference ('T'Default__X_C:Name_GEN_VARIABLE'')."""
    name = (reference or {}).get("ObjectName", "").split(":")[-1].rstrip("'")
    return name[:-len("_GEN_VARIABLE")] if name.endswith("_GEN_VARIABLE") else name


class Blueprint:
    """A Blueprint class resolved along its parent chain.

    Attributes: `chain` (package paths, root first), `cdo` (merged CDO properties),
    `components` ({name: merged properties}), `types` ({name: export type}),
    `parents` ({name: parent component name}), `exports` ({package: its exports}),
    `native_parent` (the /Script/ class the chain starts from).
    """

    def __init__(self, assets, path):
        package = "/Game/" + path if not path.startswith("/Game/") else path
        chain, native_parent = [], None
        while package:
            if package.startswith("/Script/"):
                native_parent = package
                break
            exports = assets.require(package)
            generated = next((e for e in exports if e.get("Type") == "BlueprintGeneratedClass"), None)
            if generated is None:
                raise GameDataError(f"{package}: no BlueprintGeneratedClass")
            chain.append((package, exports, generated))
            package = package_of(generated.get("Super")) or (generated.get("Super") or {}).get("ObjectPath")
        chain.reverse()
        self.chain = [package for package, _, _ in chain]
        self.exports = {package: exports for package, exports, _ in chain}
        self.native_parent = native_parent
        self.cdo, self.components, self.types, self.parents = {}, {}, {}, {}
        for _, exports, generated in chain:
            self._apply(exports, generated)

    def _apply(self, exports, generated):
        """Merge one class's CDO and components over its parents'. A component's
        AttachParent property sets its parent; a construction-script node sets it only
        where no AttachParent has."""
        cdo_name = "Default__" + generated["Name"]
        nodes = {}
        for export in exports:
            name = export.get("Name", "")
            outer = (export.get("Outer") or {}).get("ObjectName", "")
            if name == cdo_name:
                self.cdo = merge(self.cdo, export.get("Properties") or {})
            elif name.endswith("_GEN_VARIABLE") or (cdo_name in outer and export.get("Type") != "Function"):
                component = name[:-len("_GEN_VARIABLE")] if name.endswith("_GEN_VARIABLE") else name
                properties = export.get("Properties") or {}
                self.components[component] = merge(self.components.get(component, {}), properties)
                self.types.setdefault(component, export.get("Type"))
                if properties.get("AttachParent"):
                    self.parents[component] = component_name(properties["AttachParent"])
            if export.get("Type") == "SCS_Node":
                nodes[name] = export.get("Properties") or {}
        for node in nodes.values():
            variable = node.get("InternalVariableName")
            if node.get("ParentComponentOrVariableName") and variable not in self.parents:
                self.parents[variable] = node["ParentComponentOrVariableName"]
            for child in node.get("ChildNodes") or []:
                child_node = nodes.get(child.get("ObjectName", "").split(".")[-1].split(":")[-1].rstrip("'"))
                if child_node and child_node.get("InternalVariableName") not in self.parents:
                    self.parents[child_node["InternalVariableName"]] = variable

    def functions(self, package):
        """{function name: bytecode statements} of one class in the chain."""
        return {e["Name"]: e.get("ScriptBytecode") for e in self.exports[package] if e.get("Type") == "Function"}


# Rotations (UE: X forward, Y right, Z up; FRotator in degrees).

def quaternion(rotator):
    """FRotator {'Pitch', 'Yaw', 'Roll'} -> quaternion (x, y, z, w), as FRotator::Quaternion."""
    rotator = rotator or {}
    half = math.pi / 360
    sp, cp = math.sin(rotator.get("Pitch", 0.0) * half), math.cos(rotator.get("Pitch", 0.0) * half)
    sy, cy = math.sin(rotator.get("Yaw", 0.0) * half), math.cos(rotator.get("Yaw", 0.0) * half)
    sr, cr = math.sin(rotator.get("Roll", 0.0) * half), math.cos(rotator.get("Roll", 0.0) * half)
    return (cr * sp * sy - sr * cp * cy, -cr * sp * cy - sr * cp * sy, cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


def compose(a, b):
    """Quaternion product a * b (b applied first, then a)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def pitch(q):
    """Pitch (degrees) of the forward axis X rotated by q."""
    x, y, z, w = q
    forward = (1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y))
    return math.degrees(math.atan2(forward[2], math.hypot(forward[0], forward[1])))


IDENTITY = (0.0, 0.0, 0.0, 1.0)


def socket_rotation(assets, mesh_path, socket):
    """Rotation of `socket` in the reference pose of skeletal mesh `mesh_path`.

    The mesh's sockets are searched first, then its skeleton's (USkeletalMesh::FindSocket);
    names compare case-insensitively. The bone's rotation is composed from the skeleton's
    reference pose down from the root.
    """
    mesh_exports = assets.require(mesh_path)
    mesh = next((e for e in mesh_exports if e.get("Type") == "SkeletalMesh"), None)
    if mesh is None:
        raise GameDataError(f"{mesh_path}: not a skeletal mesh")
    skeleton_path = package_of(mesh["Properties"].get("Skeleton"))
    skeleton_exports = assets.require(skeleton_path)
    sockets = [e.get("Properties") or {} for e in mesh_exports + skeleton_exports if e.get("Type") == "SkeletalMeshSocket"]
    found = next((s for s in sockets if (s.get("SocketName") or "").lower() == socket.lower()), None)
    if found is None:
        raise GameDataError(f"{short(mesh_path)}: no socket {socket}")
    skeleton = next(e for e in skeleton_exports if e.get("Type") == "Skeleton")
    reference = skeleton["ReferenceSkeleton"]
    bones = [(info["Name"], info["ParentIndex"], pose["Rotation"]) for info, pose in zip(reference["FinalRefBoneInfo"], reference["FinalRefBonePose"])]
    index = {name.lower(): i for i, (name, _, _) in enumerate(bones)}
    bone = index.get((found.get("BoneName") or "").lower())
    if bone is None:
        raise GameDataError(f"{short(skeleton_path)}: no bone {found.get('BoneName')}")
    path = []
    while bone >= 0:
        path.append(bones[bone])
        bone = bones[bone][1]
    rotation = IDENTITY
    for _, _, r in reversed(path):
        rotation = compose(rotation, (r["X"], r["Y"], r["Z"], r["W"]))
    return compose(rotation, quaternion(found.get("RelativeRotation")))


def chain_rotation(blueprint, start, stop):
    """Rotation of component `start` relative to component `stop` of `blueprint`
    (its RelativeRotations composed up the attachment chain); None when `stop` is
    not an ancestor (the chain ends first)."""
    rotation, name, seen = IDENTITY, start, set()
    while name and name != stop:
        if name in seen:
            raise GameDataError(f"{short(blueprint.chain[-1])}: attachment loop at {name}")
        seen.add(name)
        rotation = compose(quaternion(blueprint.components.get(name, {}).get("RelativeRotation")), rotation)
        name = blueprint.parents.get(name)
    return rotation if name == stop else None


class Transform:
    """A rigid transform: rotation quaternion (x, y, z, w) and translation in cm."""

    def __init__(self, rotation=IDENTITY, translation=(0.0, 0.0, 0.0)):
        self.rotation = rotation
        self.translation = translation

    def __mul__(self, other):
        """self * other: `other` first, then self."""
        moved = rotate(self.rotation, other.translation)
        return Transform(compose(self.rotation, other.rotation),
                         tuple(a + b for a, b in zip(moved, self.translation)))


def rotate(q, v):
    """The vector v rotated by the quaternion q."""
    x, y, z, w = q
    t = (2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0]))
    return (v[0] + w * t[0] + (y * t[2] - z * t[1]),
            v[1] + w * t[1] + (z * t[0] - x * t[2]),
            v[2] + w * t[2] + (x * t[1] - y * t[0]))


def relative_transform(properties):
    """The RelativeLocation / RelativeRotation of a component's properties; a scale other
    than 1 is refused (the offsets below are not scaled)."""
    properties = properties or {}
    scale = properties.get("RelativeScale3D")
    if scale and any(abs(scale[axis] - 1.0) > 1e-6 for axis in "XYZ"):
        raise GameDataError(f"a component is scaled {scale}: its offsets would need scaling")
    location = properties.get("RelativeLocation") or {}
    return Transform(quaternion(properties.get("RelativeRotation")),
                     (location.get("X", 0.0), location.get("Y", 0.0), location.get("Z", 0.0)))


def skeleton_of(assets, mesh_path):
    """(mesh exports, skeleton exports, bones) of a skeletal mesh; bones are
    (name, parent index, reference-pose Transform)."""
    mesh_exports = assets.require(mesh_path)
    mesh = next((e for e in mesh_exports if e.get("Type") == "SkeletalMesh"), None)
    if mesh is None:
        raise GameDataError(f"{mesh_path}: not a skeletal mesh")
    skeleton_exports = assets.require(package_of(mesh["Properties"].get("Skeleton")))
    reference = next(e for e in skeleton_exports if e.get("Type") == "Skeleton")["ReferenceSkeleton"]
    bones = []
    for info, pose in zip(reference["FinalRefBoneInfo"], reference["FinalRefBonePose"]):
        r, t = pose["Rotation"], pose["Translation"]
        bones.append((info["Name"], info["ParentIndex"], Transform((r["X"], r["Y"], r["Z"], r["W"]), (t["X"], t["Y"], t["Z"]))))
    return mesh_exports, skeleton_exports, bones


def bone_transform(bones, name):
    """The reference-pose transform of bone `name` in mesh space, or None for an unknown bone."""
    index = {bone[0].lower(): i for i, bone in enumerate(bones)}
    i = index.get(name.lower())
    if i is None:
        return None
    path = []
    while i >= 0:
        path.append(bones[i][2])
        i = bones[i][1]
    result = Transform()
    for local in reversed(path):
        result = result * local
    return result


def attach_transform(assets, mesh_path, name):
    """Where a component attached to `name` of a skeletal mesh sits, in mesh space: the
    socket (mesh sockets first, then the skeleton's), else the bone, else, as UE does for
    a name the mesh lacks, the mesh component's origin."""
    mesh_exports, skeleton_exports, bones = skeleton_of(assets, mesh_path)
    sockets = [e.get("Properties") or {} for e in mesh_exports + skeleton_exports if e.get("Type") == "SkeletalMeshSocket"]
    socket = next((s for s in sockets if (s.get("SocketName") or "").lower() == name.lower()), None)
    if socket is not None:
        bone = bone_transform(bones, socket.get("BoneName") or "")
        if bone is None:
            raise GameDataError(f"{short(mesh_path)}: socket {name} is on the unknown bone {socket.get('BoneName')}")
        return bone * relative_transform(socket)
    return bone_transform(bones, name) or Transform()


def attach_sockets(blueprint):
    """{component: AttachToName} from the construction-script nodes of the class chain (the
    most derived wins)."""
    names = {}
    for package in blueprint.chain:
        for export in blueprint.exports[package]:
            node = export.get("Properties") or {}
            if export.get("Type") == "SCS_Node" and node.get("AttachToName"):
                names[node["InternalVariableName"]] = node["AttachToName"]
    return names


def component_transform(assets, blueprint, name):
    """Transform of component `name` in the Blueprint actor's space: its relative transform and
    the attach sockets of the skeletal meshes it hangs on, up to the root."""
    sockets = attach_sockets(blueprint)
    result, seen = Transform(), set()
    while name:
        if name in seen:
            raise GameDataError(f"{short(blueprint.chain[-1])}: attachment loop at {name}")
        seen.add(name)
        result = relative_transform(blueprint.components.get(name)) * result
        parent = blueprint.parents.get(name)
        if parent and name in sockets and blueprint.types.get(parent) == "SkeletalMeshComponent":
            mesh = package_of(blueprint.components[parent].get("SkeletalMesh"))
            result = attach_transform(assets, mesh, sockets[name]) * result
        name = parent
    return result


def wheel_radii(config):
    """{wheel bone: WheelRadius in cm} of a vehicle config asset's exports. A tracked config lists
    each wheel's ``BoneName`` with its own ``WheelRadius``; a wheeled config states one radius
    for all wheels (the bone is not next to it), returned under the key None."""
    found, radii = {}, set()

    def walk(node):
        if isinstance(node, dict):
            if "BoneName" in node and "WheelRadius" in node:
                found[node["BoneName"].lower()] = float(node["WheelRadius"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(config)
    if found:
        return found
    radii = set(re.findall(r'"WheelRadius": ([\d.]+)', json.dumps(config)))
    if len(radii) != 1:
        raise GameDataError(f"WheelRadius {sorted(radii)}")
    return {None: float(radii.pop())}


def wheel_contact(assets, vehicle):
    """(height of the wheels' lowest contact above the vehicle mesh's origin in cm, description):
    the lowest ``wheel_<side><n>`` bone of the vehicle mesh in the reference pose minus that
    wheel's ``WheelRadius`` in the vehicle's config asset (a tracked vehicle's wheels differ in
    radius; the track's own thickness is not in the files and not counted)."""
    movement = next((props for name, props in vehicle.components.items() if "VehicleConfigAsset" in props), None)
    if movement is None:
        raise GameDataError(f"{short(vehicle.chain[-1])}: no VehicleConfigAsset")
    config = package_of(movement["VehicleConfigAsset"])
    try:
        radii = wheel_radii(assets.require(config))
    except GameDataError as error:
        raise GameDataError(f"{short(config)}: {error}") from error
    _, _, bones = skeleton_of(assets, package_of(vehicle.components["Vehicle Mesh"].get("SkeletalMesh")))
    bottoms = []
    for name, _, _ in bones:
        if not re.fullmatch(r"wheel_[LR]\d+", name):
            continue
        radius = radii.get(name.lower(), radii.get(None))
        if radius is None:
            raise GameDataError(f"{short(config)}: no WheelRadius for {name}")
        bottoms.append((bone_transform(bones, name).translation[2] - radius, name, radius))
    if not bottoms:
        raise GameDataError(f"{short(vehicle.chain[-1])}: no wheel bones")
    lowest, name, radius = min(bottoms)
    return lowest, f"lowest wheel bone {round_to(lowest + radius, 1)} cm - WheelRadius {radius:g} cm ({short(config)})"


# The Technical mortar's HUD shows the mount's world pitch plus this many degrees
# (UMG_MortarHUD_Technical.AngleRotationDisplay: K2_GetComponentRotation of GunMountComponent,
# BreakRotator, Add_DoubleDouble(Pitch, 40.0)).
HUD_PITCH_OFFSET = 40.0


def hud_table(assets, widget_path):
    """(degrees ascending, ranges in metres descending) of the table a HUD widget prints: its
    text blocks written 'NN.N°' (the one named Angle is the live readout's placeholder) and
    'NNNm'. The two lists pair up in this order, the longest range on the lowest readout."""
    degrees, ranges = [], []
    for export in assets.require(widget_path):
        if export.get("Type") != "TextBlock" or export.get("Name") == "Angle":
            continue
        text = (export.get("Properties") or {}).get("Text") or {}
        invariant = re.fullmatch(r"([\d.]+)\u00b0", text.get("CultureInvariantString") or "")
        metres = re.fullmatch(r"(\d+)m", text.get("SourceString") or "")
        if invariant:
            degrees.append(float(invariant.group(1)))
        elif metres:
            ranges.append(float(metres.group(1)))
    if not degrees or len(degrees) != len(ranges):
        raise GameDataError(f"{short(widget_path)}: {len(degrees)} degrees and {len(ranges)} ranges")
    return sorted(degrees), sorted(ranges, reverse=True)


def mount_component(turret):
    """The component a turret's weapons are mounted on: GunAttachPoint (closed turret)
    or GunMountComponent (open turret, tripod)."""
    for name in ("GunAttachPoint", "GunMountComponent"):
        if name in turret.components:
            return name
    raise GameDataError(f"{short(turret.chain[-1])}: no GunAttachPoint or GunMountComponent")


# A muzzle may sit this far (cm) beside the vertical plane of the barrel's pivot, and a
# turret mount may lean this many degrees against the vehicle's reference pose: the flat shot
# is computed in that plane and with the mount's pitch limits, so both are reported in
# `sources` when they are not zero. A turret mesh whose root bone is more than MAX_ROOT_OFFSET
# cm from its origin is refused (see `turret_root_offset`).
MAX_MUZZLE_LATERAL = 35.0
MAX_MOUNT_TILT = 2.0
MAX_ROOT_OFFSET = 50.0


def turret_root_offset(assets, turret, mount):
    """Refuse a turret whose skeletal mesh has its root bone away from the mesh origin: such a
    mesh (the Kozak-2M1's AGS-17 turret, root bone at the vehicle's seat socket) is authored in
    vehicle space, and hanging it on the seat socket would count the seat height twice."""
    name = mount
    while name:
        if turret.types.get(name) == "SkeletalMeshComponent" and turret.components[name].get("SkeletalMesh"):
            _, _, bones = skeleton_of(assets, package_of(turret.components[name]["SkeletalMesh"]))
            root = bones[0][2].translation
            if max(abs(v) for v in root) > MAX_ROOT_OFFSET:
                raise GameDataError(f"{short(turret.chain[-1])}: the root bone of {name} is at {[round_to(v, 1) for v in root]} cm, "
                                    "the mesh is authored in vehicle space and its attachment is not in the files")
        name = turret.parents.get(name)


def round_to(value, digits=4):
    """`value` rounded for the snapshot, with -0.0 written as 0.0."""
    return round(value, digits) + 0.0


class Weapon:
    """A weapon class: its launch and flight values and its barrel socket."""

    def __init__(self, assets, path):
        self.path = path
        self.blueprint = Blueprint(assets, path)
        config = self.blueprint.cdo.get("WeaponConfig") or {}
        if "MuzzleVelocity" not in config or not config.get("ProjectileClass"):
            raise GameDataError(f"{path}: no WeaponConfig.MuzzleVelocity or ProjectileClass")
        self.config = config
        self.projectile_path = package_of(config["ProjectileClass"])[len("/Game/"):]
        self.projectile = Blueprint(assets, self.projectile_path)
        movement = [name for name, kind in self.projectile.types.items() if kind and "ProjectileMovement" in kind]
        if len(movement) != 1:
            raise GameDataError(f"{self.projectile_path}: {len(movement)} projectile movement components")
        self.movement_raw = self.projectile.components[movement[0]]
        self.defaults = sorted(k for k in NATIVE_DEFAULTS if k not in self.movement_raw)
        self.movement = merge(NATIVE_DEFAULTS, self.movement_raw)
        self.assets = assets

    def ballistics(self):
        """The launch and flight values in m, m/s and s (see the module docstring)."""
        move = self.movement
        return {
            "velocity": round_to(self.config["MuzzleVelocity"] / 100),
            "gravity_scale": round_to(move["ProjectileGravityScale"]),
            "max_speed": round_to(move["MaxSpeed"] / 100),
            "acceleration": round_to((move["ConstantAcceleration"] or {}).get("X", 0.0) / 100),
            "acceleration_timeout": round_to(move["ConstantAccelerationTimeout"]),
            "rotation_follows_velocity": bool(move["bRotationFollowsVelocity"]),
            "ignore_gravity_while_boosting": bool(move["bIgnoreGravityDuringConstantAcceleration"]),
            "lifespan": self.lifespan(),
        }

    def lifespan(self):
        """The projectile's ``InitialLifeSpan`` in s (the deepest override along its class chain);
        0 when no Blueprint sets one: the actor then lives until it hits something."""
        return round_to(self.projectile.cdo.get("InitialLifeSpan") or 0.0)

    def burst_radius(self):
        """Outer radius in m of the widest explosion of the projectile that deals damage; 0 when
        the Blueprints set no explosion field or the explosion deals none (see the module docstring)."""
        cdo = self.projectile.cdo
        if not any(field in cdo for field in EXPLOSION_FIELDS):
            return 0.0
        values = merge(NATIVE_EXPLOSION, cdo)
        radii = [values["ExplosiveDamageOuterRadius"]] if values["ExplosiveBaseDamage"] > 0 else []
        if values["bUseSecondaryExplosion"] and values.get("SecondaryExplosionBaseDmg", 0) > 0:
            radii.append(values["SecondaryExplosionOuterRadius"])
        return round_to(max(radii, default=0.0) / 100)

    def barrel(self):
        """(mesh path, socket name, pitch of the socket on the weapon's root in degrees).

        The socket is WeaponConfig.BarrelSocketName on the mesh of WeaponMesh1P; the
        mesh component's own rotation (relative to the weapon's root) is included.
        """
        socket = self.config.get("BarrelSocketName") or self.blueprint.cdo.get("BarrelSocketName")
        mesh_component = self.blueprint.components.get("WeaponMesh1P") or {}
        mesh = package_of(mesh_component.get("SkeletalMesh"))
        if not socket or not mesh:
            raise GameDataError(f"{self.path}: no barrel socket or weapon mesh")
        root = chain_rotation(self.blueprint, "WeaponMesh1P", None) or IDENTITY
        rotation = compose(root, socket_rotation(self.assets, mesh, socket))
        return mesh, socket, pitch(rotation)

    def rmb_divisor(self):
        """(k, class) of the weapon's RMB FOV divisor: SetFieldOfView(FOV / k) in the
        graph of the most derived class that defines BlueprintOnZoom; (1.0, None) when
        no class does or that graph sets no divided FOV. Needs a dump with bytecode."""
        for package in reversed(self.blueprint.chain):
            functions = self.blueprint.functions(package)
            if "BlueprintOnZoom" not in functions:
                continue
            divisors = set()
            for statements in functions.values():
                if statements is None:
                    raise GameDataError(f"{package}: dumped without bytecode; add a root dumped with ReadScriptData")
                if "SetFieldOfView" in json.dumps(statements):
                    divisors.update(fov_divisors(statements))
            if len(divisors) > 1:
                raise GameDataError(f"{package}: several FOV divisors {sorted(divisors)}")
            return (divisors.pop() if divisors else 1.0), package
        return 1.0, None


def fov_divisors(node):
    """Constant divisors of every Divide_* call in a bytecode tree."""
    found = []
    if isinstance(node, dict):
        if node.get("Token") == "EX_CallMath" and "Divide" in json.dumps(node.get("Function")):
            parameters = node.get("Parameters") or []
            if len(parameters) == 2 and parameters[1].get("Token") in ("EX_DoubleConst", "EX_FloatConst"):
                found.append(float(parameters[1]["Value"]))
        for value in node.values():
            found += fov_divisors(value)
    elif isinstance(node, list):
        for value in node:
            found += fov_divisors(value)
    return found


def curve_values(assets, reference):
    """Key values of a CurveFloat asset (linear or constant between keys, so its
    extremes are among them) and its value at time 0."""
    curve = next(e for e in assets.require(package_of(reference)) if e.get("Type") == "CurveFloat")
    keys = sorted(curve["Properties"]["FloatCurve"]["Keys"], key=lambda k: k["Time"])
    at_zero = keys[0]["Value"] if 0 <= keys[0]["Time"] else keys[-1]["Value"]
    for a, b in zip(keys, keys[1:]):
        if a["Time"] <= 0 <= b["Time"]:
            at_zero = a["Value"] if a.get("InterpMode") == "RCIM_Constant" else a["Value"] + (b["Value"] - a["Value"]) * (0 - a["Time"]) / (b["Time"] - a["Time"])
    return [k["Value"] for k in keys], at_zero


def mount_limits(assets, turret):
    """(min, max, description) of the mount's pitch limits; None when it has none."""
    holders = [(name, props) for name, props in sorted(turret.components.items())
               if "PitchInterval" in (props.get("RotationConstraints") or {}) or "ParentYawToMinPitch" in props]
    if not holders:
        return None
    if len(holders) > 1:
        raise GameDataError(f"{short(turret.chain[-1])}: several turret movements {[n for n, _ in holders]}")
    name, props = holders[0]
    interval = (props.get("RotationConstraints") or {}).get("PitchInterval")
    low_curve, high_curve = props.get("ParentYawToMinPitch"), props.get("ParentYawToMaxPitch")
    if low_curve and high_curve:
        lows, low_zero = curve_values(assets, low_curve)
        highs, high_zero = curve_values(assets, high_curve)
        return (min(lows), max(highs), f"{name} curves {short(package_of(low_curve))} / {short(package_of(high_curve))}: "
                f"{round_to(min(lows))}..{round_to(max(highs))} (yaw 0: {round_to(low_zero)}..{round_to(high_zero)})")
    if interval is None:
        return None
    return interval["X"], interval["Y"], f"{name}.RotationConstraints.PitchInterval {interval['X']}..{interval['Y']}"


class Snapshot:
    """Builds the snapshot entries from the dumps."""

    def __init__(self, assets):
        self.assets = assets
        self.weapons, self.blueprints = {}, {}

    def weapon(self, path):
        """The Weapon of class `path`, read once."""
        if path not in self.weapons:
            self.weapons[path] = Weapon(self.assets, path)
        return self.weapons[path]

    def blueprint(self, path):
        """The Blueprint of class `path`, read once."""
        if path not in self.blueprints:
            self.blueprints[path] = Blueprint(self.assets, path)
        return self.blueprints[path]

    def view_of(self, weapon, mount_path, camera, zoom):
        """(bore, zoom, socket pitch on the mount, sources) of one weapon on one mount."""
        turret = self.blueprint(mount_path)
        mount = mount_component(turret)
        rotation = chain_rotation(turret, camera, mount)
        if rotation is None:
            raise GameDataError(f"{short(mount_path)}: camera {camera} is not on {mount}")
        camera_pitch = pitch(rotation)
        mesh, socket, socket_pitch = weapon.barrel()
        levels = turret.cdo.get("ZoomLevels")
        if zoom[0] == "levels":
            if not levels or len(levels) <= zoom[1]:
                raise GameDataError(f"{short(mount_path)}: no ZoomLevels[{zoom[1]}]")
            divisor, zoom_source = levels[zoom[1]], f"{short(mount_path)}.ZoomLevels[{zoom[1]}] of {levels}"
        elif zoom[0] == "rmb":
            divisor, defined_in = weapon.rmb_divisor()
            zoom_source = (f"{short(defined_in)} BlueprintOnZoom: SetFieldOfView(FOV / {divisor:g})" if divisor != 1
                           else f"RMB keeps the FOV ({short(defined_in) or short(weapon.path)}: no SetFieldOfView(FOV / k))")
        else:
            divisor, zoom_source = 1.0, "normal view, the game's FOV"
        sources = {
            "barrel": f"{short(mesh)}:{socket} {round_to(socket_pitch)}",
            "mount": mount_path,
            "camera": f"{camera} {round_to(camera_pitch)} on {mount}",
            "zoom": zoom_source,
        }
        return round_to(socket_pitch - camera_pitch), round_to(float(divisor)), socket_pitch, sources

    def launch(self, weapon, turret_path, seat_spec, limits):
        """(launch, elevation_limits, sources) of an elevation weapon on a vehicle's turret.

        launch: `launch_height`, `muzzle_forward`, `muzzle_up` in metres and `barrel_pitch`, the
        barrel socket's pitch in the reference pose, in degrees (see the module docstring).
        """
        vehicle, turret = self.blueprint(seat_spec["vehicle"]), self.blueprint(turret_path)
        mesh_component_name = "Vehicle Mesh"
        vehicle_mesh = package_of(vehicle.components[mesh_component_name].get("SkeletalMesh"))
        if vehicle.components[mesh_component_name].get("RelativeLocation") or vehicle.components[mesh_component_name].get("RelativeRotation"):
            raise GameDataError(f"{short(seat_spec['vehicle'])}: the vehicle mesh is not at the actor's origin")
        mount = mount_component(turret)
        turret_root_offset(self.assets, turret, mount)
        pivot = attach_transform(self.assets, vehicle_mesh, seat_spec["seat"]) * component_transform(self.assets, turret, mount)
        upright = rotate(pivot.rotation, (0.0, 0.0, 1.0))
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, upright[2]))))
        if tilt > MAX_MOUNT_TILT:
            raise GameDataError(f"{short(turret_path)}: the mount is tilted {round_to(tilt, 2)} degrees in the vehicle")
        mesh, socket, _ = weapon.barrel()
        muzzle = component_transform(self.assets, weapon.blueprint, "WeaponMesh1P") * attach_transform(self.assets, mesh, socket)
        direction = rotate(muzzle.rotation, (1.0, 0.0, 0.0))
        horizontal = math.hypot(direction[0], direction[1])
        elevation = math.atan2(direction[2], horizontal)
        along, lateral = (direction[0] / horizontal, direction[1] / horizontal), (-direction[1] / horizontal, direction[0] / horizontal)
        reach = muzzle.translation[0] * along[0] + muzzle.translation[1] * along[1]
        sideways = muzzle.translation[0] * lateral[0] + muzzle.translation[1] * lateral[1]
        if abs(sideways) > MAX_MUZZLE_LATERAL:
            raise GameDataError(f"{short(mesh)}:{socket} is {round_to(abs(sideways), 1)} cm off the pitch plane")
        forward = reach * math.cos(elevation) + muzzle.translation[2] * math.sin(elevation)
        up = -reach * math.sin(elevation) + muzzle.translation[2] * math.cos(elevation)
        contact, contact_text = wheel_contact(self.assets, vehicle)
        barrel_pitch = math.degrees(elevation)
        launch = {
            "launch_height": round_to((pivot.translation[2] - contact) / 100, 4),
            "muzzle_forward": round_to(forward / 100, 4),
            "muzzle_up": round_to(up / 100, 4),
            "barrel_pitch": round_to(barrel_pitch, 3),
        }
        sources = {
            "launch": (f"{short(seat_spec['vehicle'])}: {seat_spec['seat']} of {short(vehicle_mesh)} -> "
                       f"{mount} of {short(turret_path)} = pivot {round_to(pivot.translation[2], 2)} cm above the mesh origin; "
                       f"ground {round_to(contact, 2)} cm ({contact_text}); socket {socket} of {short(mesh)} at "
                       f"{[round_to(v, 2) for v in muzzle.translation]} cm on the mount, pitch {round_to(barrel_pitch, 3)}"
                       + (f"; the muzzle is {round_to(abs(sideways), 1)} cm beside the pitch plane (not modelled)" if abs(sideways) > 1.0 else "")
                       + (f"; the mount is tilted {round_to(tilt, 2)} degrees in the vehicle (pitch limits are the mount's)" if tilt > 1e-3 else "")),
        }
        if seat_spec["hud"]:
            degrees, ranges = hud_table(self.assets, seat_spec["hud"])
            if not limits or abs(degrees[0] - HUD_PITCH_OFFSET - limits[0]) > 0.05 or abs(degrees[-1] - HUD_PITCH_OFFSET - limits[1]) > 0.05:
                raise GameDataError(f"{short(seat_spec['hud'])}: degrees {degrees[0]}..{degrees[-1]} are not the mount's limits + {HUD_PITCH_OFFSET:g}")
            launch["hud"] = {"degrees": degrees, "ranges": ranges}
            sources["elevation"] = (f"the readout of {short(seat_spec['hud'])}: the mount's world pitch + {HUD_PITCH_OFFSET:g} "
                                    f"(AngleRotationDisplay), table {degrees[0]:g}..{degrees[-1]:g} degrees = {limits[2]} + {HUD_PITCH_OFFSET:g}")
            return launch, [degrees[0], degrees[-1]], sources
        if not limits:
            raise GameDataError(f"{short(turret_path)}: no pitch limits")
        sources["elevation"] = limits[2] + " + barrel socket pitch"
        return launch, [round_to(limits[0] + barrel_pitch), round_to(limits[1] + barrel_pitch)], sources

    def entry(self, classes, spec):
        """The snapshot object of one weapons.json entry."""
        reference = self.weapon(classes[0])
        result = reference.ballistics()
        result["burst_radius"] = max(self.weapon(path).burst_radius() for path in classes)
        result["warhead"] = "splash" if result["burst_radius"] > SPLASH_RADIUS else "direct"
        sources = {"weapon": classes[0], "projectile": reference.projectile_path}
        if reference.defaults:
            sources["defaults"] = "native default: " + ", ".join(reference.defaults)
        if spec is None:
            result.update(bore=0.0, zoom=1.0, elevation_limits=None, bore_assumed=True, zoom_assumed=True)
            sources["view"] = HANDHELD
        elif isinstance(spec, tuple) and spec[0] == INDIRECT:
            result.update(bore=None, zoom=None, elevation_limits=None)
            turret = self.blueprint(spec[1])
            limits = mount_limits(self.assets, turret)
            mesh, socket, socket_pitch = reference.barrel()
            sources["view"] = ("aimed by elevation: no bore or zoom; the tube is laid by its own readout, "
                               "so the shot's limits are not derived" if len(spec) < 3 else
                               "aimed by elevation: no bore or zoom; the launch point and the limits of the barrel's pitch are derived")
            sources["mount"] = spec[1]
            sources["mount_limits"] = limits[2] if limits else "none"
            sources["barrel"] = f"{short(mesh)}:{socket} {round_to(socket_pitch)} (mesh reference pose)"
            if len(spec) > 2:
                result["launch"], result["elevation_limits"], launch_sources = self.launch(reference, spec[1], spec[2], limits)
                sources.update(launch_sources)
        else:
            bore, zoom, socket_pitch, view_sources = self.view_of(reference, spec["mount"], spec["camera"], spec["zoom"])
            limits = mount_limits(self.assets, self.blueprint(spec["mount"]))
            result.update(bore=bore, zoom=zoom,
                          elevation_limits=[round_to(limits[0] + socket_pitch), round_to(limits[1] + socket_pitch)] if limits else None)
            sources.update(view_sources)
            sources["elevation"] = (limits[2] + " + socket pitch") if limits else "no mount limit"
            if spec["seat"]:
                result["launch"], launch_limits, launch_sources = self.launch(reference, spec["mount"], spec["seat"], limits)
                if launch_limits != result["elevation_limits"]:
                    raise GameDataError(f"{classes[0]}: the launch's limits {launch_limits} are not the view's {result['elevation_limits']}")
                sources["launch"] = launch_sources["launch"]
            agree, differ = [], {}
            for mount, weapon_path, *other_seat in spec["also"]:
                other = self.view_of(self.weapon(weapon_path), mount, spec["camera"], spec["zoom"])
                other_limits = mount_limits(self.assets, self.blueprint(mount))
                other_elevation = [round_to(other_limits[0] + other[2]), round_to(other_limits[1] + other[2])] if other_limits else None
                found = {"bore": other[0], "zoom": other[1], "elevation_limits": other_elevation}
                if spec["seat"] and other_seat:
                    other_launch = self.launch(self.weapon(weapon_path), mount, other_seat[0], other_limits)[0]
                    found.update({k: other_launch[k] for k in ("launch_height", "muzzle_forward", "muzzle_up")})
                changed = {k: v for k, v in found.items() if k in ("bore", "zoom", "elevation_limits") and v != result[k]}
                changed.update({k: v for k, v in found.items() if k in ("launch_height", "muzzle_forward", "muzzle_up") and v != result["launch"][k]})
                label = f"{mount} on {other_seat[0]['vehicle']}" if other_seat else mount
                if changed:
                    differ[label] = dict(changed, barrel=other[3]["barrel"], camera=other[3]["camera"])
                else:
                    agree.append(label)
            if agree:
                sources["same_view"] = agree
            if differ:
                result["view_variants"] = differ
        sources["classes"] = [f"{short(c)} -> {short(self.weapon(c).projectile_path)} ({max_speed_text(self.weapon(c))})" for c in classes]
        variants = {}
        for path in classes[1:]:
            values = self.weapon(path).ballistics()
            changed = {k: values[k] for k in BALLISTIC_FIELDS if values[k] != result[k]}
            if changed:
                variants[path] = dict(changed, projectile=self.weapon(path).projectile_path)
        if variants:
            result["variants"] = variants
        result["sources"] = sources
        return result


def max_speed_text(weapon):
    """'MaxSpeed 850 m/s' or 'no MaxSpeed' for a weapon's projectile."""
    cap = weapon.ballistics()["max_speed"]
    return f"MaxSpeed {cap:g} m/s" if cap else "no MaxSpeed"


def check_resolved(snapshot, resolved_path):
    """Fail when collect.py's resolved.json disagrees with this reader on any weapon class used."""
    with open(resolved_path, encoding="utf-8") as stream:
        resolved = {k.replace("/Game/", "", 1): v for k, v in json.load(stream).items()}
    checked = 0
    for path, weapon in sorted(snapshot.weapons.items()):
        other = resolved.get(path)
        if other is None:
            continue
        move = merge(NATIVE_DEFAULTS, (other.get("projectile") or {}).get("movement") or {})
        theirs = {
            "velocity": round_to(other["config"]["MuzzleVelocity"] / 100), "gravity_scale": round_to(move["ProjectileGravityScale"]),
            "max_speed": round_to(move["MaxSpeed"] / 100), "acceleration": round_to(move["ConstantAcceleration"]["X"] / 100),
            "acceleration_timeout": round_to(move["ConstantAccelerationTimeout"]),
            "lifespan": round_to((other.get("projectile") or {}).get("life") or 0.0),
        }
        mine = {k: weapon.ballistics()[k] for k in theirs}
        if mine != theirs:
            raise GameDataError(f"{path}: resolved.json {theirs} != dumps {mine}")
        checked += 1
    return checked


def same_boost_time(game, app_time):
    """Whether weapons.json's acceleration_time gives the game's boost: the timeout when
    the game sets one, or, for a boost over the whole flight (timeout 0), any time from
    where MaxSpeed stops a speeding-up boost on (the cap holds the speed after it)."""
    if not game["acceleration"]:
        return True
    if game["acceleration_timeout"] > 0:
        return abs(game["acceleration_timeout"] - app_time) <= 0.005
    if game["acceleration"] > 0 and game["max_speed"] > game["velocity"]:
        return app_time >= (game["max_speed"] - game["velocity"]) / game["acceleration"] - 0.005
    return False


def compare(snapshot, weapons_path):
    """Markdown rows: entry | field | game | weapons.json, for every differing value.

    weapons.json leaves out fields at their defaults: gravity 1, acceleration 0,
    max_speed 0 (none), rotation_follows_velocity true, bore 0 and zoom 1 (for a
    weapon with a view), elevation_limits none.
    """
    with open(weapons_path, encoding="utf-8") as stream:
        current = json.load(stream)
    rows = []
    for name, game in snapshot.items():
        if name.startswith("_"):
            continue
        app = current.get(name)
        if app is None:
            rows.append(f"| {name} | (new entry) | {game['velocity']:g} m/s, bore {game['bore']}, zoom {game['zoom']} | — |")
            continue
        boost = app.get("acceleration_time", 0)
        pairs = [
            ("velocity", game["velocity"], app.get("velocity")),
            ("gravity", game["gravity_scale"], app.get("gravity", 1)),
            ("acceleration", game["acceleration"], app.get("acceleration", 0)),
            ("acceleration_time", game["acceleration_timeout"] if not same_boost_time(game, boost) else boost, boost),
            ("max_speed", game["max_speed"], app.get("max_speed", 0)),
            ("lifespan", game["lifespan"], app.get("lifespan", 0)),
            ("rotation_follows_velocity", game["rotation_follows_velocity"], app.get("rotation_follows_velocity", True)),
            ("bore", game["bore"], app.get("bore", 0.0) if game["bore"] is not None else app.get("bore")),
            ("zoom", game["zoom"], app.get("zoom", 1.0) if game["zoom"] is not None else app.get("zoom")),
            ("elevation_limits", game["elevation_limits"], app.get("elevation_limits")),
        ]
        for field, ours, theirs in pairs:
            if isinstance(ours, bool) or isinstance(theirs, bool):
                same = ours == theirs
            elif isinstance(ours, list) and isinstance(theirs, list):
                same = all(abs(a - b) <= 0.005 for a, b in zip(ours, theirs))
            elif isinstance(ours, (int, float)) and isinstance(theirs, (int, float)):
                same = abs(ours - theirs) <= 0.005 + 1e-9
            else:
                same = ours == theirs
            if not same:
                rows.append(f"| {name} | {field} | {ours} | {theirs} |")
    return rows


def main(argv=None):
    """Command line entry point: write the snapshot, optionally check and compare it."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", action="append", help="SquadExtract dumpall root (repeatable, searched in order)")
    parser.add_argument("--resolved", help="collect.py's resolved.json to cross-check the ballistics against")
    parser.add_argument("--compare", help="weapons.json to print the differences against")
    parser.add_argument("--build", required=True, help="Squad build id of the dumped paks")
    parser.add_argument("--date", required=True, help="date recorded in _source (YYYY-MM-DD)")
    parser.add_argument("--out", required=True, help="snapshot JSON to write")
    args = parser.parse_args(argv)
    roots = [os.path.expanduser(r) for r in (args.root or DEFAULT_ROOTS)]
    snapshot = Snapshot(Assets(roots))
    out = {"_source": {
        "build": args.build,
        "generator": GENERATOR,
        "date": args.date,
        "units": "m, m/s, s, degrees; bore and zoom null = aimed by elevation; elevation_limits null = no mount or not derived",
    }}
    for name, (classes, spec) in ENTRIES.items():
        try:
            out[name] = snapshot.entry(classes, spec)
        except GameDataError as error:
            raise SystemExit(f"{name}: {error}") from error
    if args.resolved:
        try:
            checked = check_resolved(snapshot, os.path.expanduser(args.resolved))
        except GameDataError as error:
            raise SystemExit(f"resolved.json: {error}") from error
        print(f"resolved.json agrees on {checked} weapon classes", file=sys.stderr)
    with open(args.out, "w", encoding="utf-8") as stream:
        json.dump(out, stream, indent=1, ensure_ascii=False)
        stream.write("\n")
    print(f"{len(out) - 1} entries -> {args.out}", file=sys.stderr)
    if args.compare:
        with open(args.compare, encoding="utf-8") as stream:
            missing = sorted(k for k in json.load(stream) if not k.startswith("_") and k not in out)
        if missing:
            raise SystemExit(f"weapons.json entries with no row in ENTRIES: {missing}")
        print("| Entry | Field | Game | weapons.json |\n|---|---|---|---|")
        print("\n".join(compare(out, args.compare)))


if __name__ == "__main__":
    main()
