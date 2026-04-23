from __future__ import annotations

from dataclasses import dataclass
from mods_base import build_mod, keybind, BoolOption, hook
from unrealsdk import make_struct, find_all
from unrealsdk.unreal import UObject, BoundFunction, IGNORE_STRUCT
from unrealsdk.logging import info, warning
from unrealsdk.hooks import Type

Z_OFFSET = 90
CANISTER_SCRIPT_CLASS = 'Script_PearlGearGenerator_Carryable_C'

auto_deposit = BoolOption(
    identifier="Auto Deposit Canisters",
    description="Automatically deposit Ordonite Canisters when they spawn",
    value=True
)

def _locate_ordonite_processor():
    for container in find_all("CarryableObjectContainer"):
        if (
            # For the one in the Stone Demon Bounty Pack
            "PearlGearGenerator" in container.Name
            # For the ones in the base game
            or (
                container.FactsConduit is not None
                and container.FactsConduit.SubmapName is not None
                and 'PearlGenerator' in container.FactsConduit.SubmapName.Name
            )
        ):
            if (
                container.RootComponent is not None
                and container.RootComponent.RelativeLocation is not None
            ):
                location = container.RootComponent.RelativeLocation
                return make_struct("Vector", X=location.X, Y=location.Y, Z=location.Z + Z_OFFSET)
            warning("Ordonite Processor lacks location information.")
    warning("Could not locate Ordonite Processor.")
    return None

def _deposit_ordonite_canisters():
    processor_location = _locate_ordonite_processor()
    if processor_location is None:
        warning("Cannot deposit Ordonite Canisters without processor location.")
        return

    for carryable in find_all("CarryableObject"):
        if (
            carryable.Name is not None
            and "PearlGearGenerator" in carryable.Name
        ):
            info(f"Depositing {carryable.Name} at processor...")
            if carryable.K2_TeleportTo(processor_location, IGNORE_STRUCT):
                info(f"Successfully deposited {carryable.Name}.")
                return
            else:
                warning(f"Failed to deposit {carryable.Name}.")

@keybind("Manually Deposit Canisters")
def manually_deposit_ordonite_canisters():
    """Keybind to manually deposit canisters"""
    info("Manually depositing Ordonite Canisters...")
    _deposit_ordonite_canisters()

@hook('/Script/GbxGame.GbxActorScript:OnInit', Type.POST)
def on_ordonite_canister_init(obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction):
    """Automatically deposit canisters when they are initialized"""
    if (
        not auto_deposit.value
        or obj is None
        or obj.Class is None
        or obj.Class.Name != CANISTER_SCRIPT_CLASS
    ):
        return
    info("Detected Ordonite Canister initialization, attempting to deposit...")
    _deposit_ordonite_canisters()

build_mod(
    keybinds=[manually_deposit_ordonite_canisters],
    options=[auto_deposit]
)
