# BL4 Autordonite
Borderlands 4 Mod for automatically depositing canisters in ordonite processor events

## Features

- Automatically deposite ordonite canisters in the ordonite processor.
- Bind a key to manually deposite ordonite canisters instead if preferred or for cases where automatic depositing fails.

## Installation

1. Install the BL4 SDK following the instructions at https://bl-sdk.github.io/oak2-mod-db/
2. Download the sdkmod from the [releases page](https://github.com/jlangowells/bl4_ordonite_helper/releases/latest/download/Autordonite.sdkmod) and place it in your `sdk_mods` folder

## Configuration

You can use the SDK mod console to toggle automatic depositing or change the manual deposit hotkey.

## Future Goals

Currently there are some issues with depositing multiple canisters at a time which will cause canisters to get stuck in a state in which
you need to grapple and throw them to deposit. I'd like to add a queueing system to handle that and other edge cases in which a deposit fails.

## License

GPL-3.0 - See LICENSE file for details

## Author

Lango

## Feedback & Issues

Please report any issues at https://github.com/jlangowells/bl4_ordonite_helper/issues,
or feel free to send me a pull request.

You can also reach me on the [Borderlands Modding Discord](https://discord.com/invite/bXeqV8Ef9R) as @Lango.