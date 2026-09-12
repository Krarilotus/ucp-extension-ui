# ucp-extension-ui
Extension for the game Stronghold Crusader to provide UI features using the Unofficial Crusader Patch

Module consumers can call `getNativeMenuInterface()` after UI initialization.
Version 1 returns the existing transition `entry`, `gameCore` receiver and an
immutable `bytes` string containing its 60-byte identifying context. Consumers
must verify that context before installing native observers. Ordinary menu
changes should continue to use `switchToMenu(menuID, delay)`.
