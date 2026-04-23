from __future__ import annotations

from typing import Any
from threading import Event, Thread
from time import sleep
from mods_base import build_mod, keybind, BoolOption, hook
from unrealsdk import make_struct, find_all
from unrealsdk.unreal import UObject, BoundFunction, IGNORE_STRUCT, WeakPointer
from unrealsdk.logging import warning
from unrealsdk.hooks import Type

# Used to clear out the deposit spot if anything gets stuck.
HIGH_Z_OFFSET = 3000
CLEAR_SPACING = 200
# A distance that works to get canisters into the deposit spot relative to the processor.
Z_OFFSET = 90
# Used to avoid deposit collisions
DEPOSIT_DELAY = 1.5
# Used to identify the script run on canister creation.
CANISTER_SCRIPT_CLASS = 'Script_PearlGearGenerator_Carryable_C'

auto_deposit = BoolOption(
    identifier="Auto Deposit Canisters",
    description="Automatically deposit Ordonite Canisters when they spawn",
    value=True
)

# Keep track of canisters that need to be deposited
# to avoid depositing canisters twice before the object is destroyed.
undeposited_canisters = {}

def _locate_ordonite_processor() -> Vector | None:
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
                return container.RootComponent.RelativeLocation
            warning("Ordonite Processor lacks location information.")
    warning("Could not locate Ordonite Processor.")
    return None

class OrdoniteDepositerThread(Thread):
    """Thread to handle depositing canisters with a delay to avoid collisions"""
    def __init__(self, deposit_location: Vector | None = None):
        super().__init__()
        self.enabled = Event()
        self.canisters = set()
        self.deposit_location = deposit_location
        self.running = True
        self.daemon = True

    def run(self):
        while self.running:
            self.enabled.wait()
            if len(self.canisters) == 0:
                self.enabled.clear()
                continue
            self.deposit()
            # Wait a bit before the next deposit to avoid collisions.
            sleep(DEPOSIT_DELAY)

    def enqueue(self, canister: str):
        """Trigger a deposit outside of the regular interval"""
        self.canisters.add(canister)

    def deposit(self):
        """Deposit one enqueued canister"""
        if len(self.canisters) == 0:
            return
        canister_name = self.canisters.pop()
        if canister_name is not None and canister_name in undeposited_canisters:
            canister = undeposited_canisters[canister_name]()
            if canister is None:
                undeposited_canisters.pop(canister_name, None)
                return
            if self.deposit_location is not None:
                canister.K2_TeleportTo(self.deposit_location, IGNORE_STRUCT)
            else:
                warning("Cannot deposit canister without deposit location.")

class OrdoniteDepositer:
    """Wrapper that manages depositer thread lifecycle and allows recreating threads"""
    def __init__(self):
        self._thread: OrdoniteDepositerThread | None = None
        self._start_thread()

    def _start_thread(self):
        """Create and start a new depositer thread"""
        self._thread = OrdoniteDepositerThread(None)
        self._thread.start()

    def start(self):
        """Create a fresh thread if the current one has stopped"""
        if not self._thread or not self._thread.is_alive():
            self._start_thread()

    def enqueue(self, canister: str):
        """Trigger a deposit outside of the regular interval"""
        if self._thread and self._thread.is_alive():
            self._thread.enqueue(canister)

    def deposit(self):
        """Deposit one enqueued canister"""
        if self._thread and self._thread.is_alive():
            self._thread.deposit()

    def set_deposit_location(self, deposit_location: Vector):
        """Set the deposit location for canisters"""
        if self._thread and self._thread.is_alive():
            self._thread.deposit_location = deposit_location

    def stop(self):
        """Stop the depositer thread"""
        if self._thread and self._thread.is_alive():
            self._thread.running = False

    def pause(self):
        """Pause the depositer"""
        if self._thread and self._thread.is_alive():
            self._thread.enabled.clear()

    def resume(self):
        """Resume the depositer"""
        if self._thread and self._thread.is_alive():
            self._thread.enabled.set()

depositer = OrdoniteDepositer()

def deposit_ordonite_canisters():
    """Deposit all canisters into the processor"""
    processor_location = _locate_ordonite_processor()
    if processor_location is None:
        warning("Cannot deposit Ordonite Canisters without processor location.")
        return
    deposit_location = make_struct(
        "Vector", X=processor_location.X, Y=processor_location.Y, Z=processor_location.Z + Z_OFFSET)
    depositer.set_deposit_location(deposit_location)

    if len(undeposited_canisters) > 0:
        clear_distance = 0
        # Clear out the space by teleporting the canisters into the sky
        # then teleport them down with a delay to avoid collisions that cause failed teleports.
        for name in list(undeposited_canisters.keys()):
            canister = undeposited_canisters[name]()
            # If it's already been garbage collected, remove it from tracking and skip it.
            if canister is None:
                undeposited_canisters.pop(name, None)
                continue
            canister.K2_TeleportTo(make_struct("Vector",
                X=deposit_location.X,
                Y=deposit_location.Y + clear_distance,
                Z=deposit_location.Z + HIGH_Z_OFFSET
            ), IGNORE_STRUCT)
            clear_distance += CLEAR_SPACING
            depositer.enqueue(name)
        depositer.resume()

@keybind("Manually Deposit Canisters")
def manually_deposit_ordonite_canisters():
    """Keybind to manually deposit canisters"""
    deposit_ordonite_canisters()

def on_ordonite_canister_init(obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction):
    """Track canister creation and auto deposit if enabled"""
    if (
        obj is None
        or obj.Class is None
        or obj.Class.Name != CANISTER_SCRIPT_CLASS
        or obj.Outer is None
    ):
        return
    undeposited_canisters[obj.Outer.Name] = WeakPointer(obj.Outer)
    if auto_deposit.value:
        deposit_ordonite_canisters()

# The processor event flow is as follows:
# 1. Activating (on lever pull)
# 2. Active (accepting canisters)
# 3. Active disabled then Releasing (after wave is complete)
# 4a. [If not the final wave] Active (accepting canisters for next wave)
# 4b. [If final wave] Complete (after final canister is deposited)
# 5. CooldownIsActive then ResetMission then Idle (after killing last ordonite enemy)
# There is also an Inactive state that I haven't seen trigger.
# The GbxActorScriptEvt__OnCarryablePlacedInContainerBP event isn't stored in the scripts
# and fires on depositing a canister. However, there's no obvious event for when the deposit ends.

# This event fires all the time but is the only way to track canister creation.
# Disabling the hook outside of processor events helps with performance.
canister_hook = hook('/Script/GbxGame.GbxActorScript:OnInit', Type.POST)(on_ordonite_canister_init)

# Happens when the processor is ready to receive canisters
@hook('/Game/DLC/Cello/InteractiveObjects/PearlGearGenerator/Script_PearlGearGenerator.Script_PearlGearGenerator_C:Active__OnStateEnabled', Type.POST)
def enable_canister_hook(obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction):
    """Enable the canister hook to track canisters
    for auto depositing when the processor is active"""
    canister_hook.enable()
    depositer.start()
    # Also trigger a deposit in case of extra canisters from the previous wave.
    if auto_deposit.value:
        deposit_ordonite_canisters()

# Happens when a wave is complete and the processor cannot accept canisters
@hook('/Game/DLC/Cello/InteractiveObjects/PearlGearGenerator/Script_PearlGearGenerator.Script_PearlGearGenerator_C:Active__OnStateDisabled', Type.POST)
# Happens as the lever becomes usable again after a run
@hook('/Game/DLC/Cello/InteractiveObjects/PearlGearGenerator/Script_PearlGearGenerator.Script_PearlGearGenerator_C:CooldownIsActive__OnStateEnabled', Type.POST)
def disable_canister_hook(obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction):
    """Disable the canister hook to stop tracking canisters
    for auto depositing when the processor is inactive"""
    canister_hook.disable()
    depositer.stop()

# Untrack canisters when they are deposited
@hook('/Game/DLC/Cello/InteractiveObjects/PearlGearGenerator/Script_PearlGearGenerator_Carryable.Script_PearlGearGenerator_Carryable_C:GbxActorScriptEvt__OnPlacedInContainer', Type.POST)
def on_canister_deposit(obj: UObject, _args: WrappedStruct, _ret: Any, _func: BoundFunction):
    """Remove canister from tracking when it's deposited"""
    if (
        obj is None
        or obj.Outer is None
        or obj.Outer.Name is None
    ):
        return
    undeposited_canisters.pop(obj.Outer.Name, None)

build_mod(
    keybinds=[manually_deposit_ordonite_canisters],
    options=[auto_deposit],
    on_disable=canister_hook.disable
)
