# Dawarich Home Assistant Integration

<!--toc:start-->
- [Dawarich Home Assistant Integration](#dawarich-home-assistant-integration)
  - [Install](#install)
    - [Install with HACS](#install-with-hacs)
    - [Manual Installation](#manual-installation)
<!--toc:end-->
> [!WARNING]
> As of Dawarich 0.8.0 support for home assistant version < 2025.1 has been removed.

> [!NOTE]
> This is an experimental integration for Dawarich, expect possibly breaking changes. This is a community integration, not affiliated with Dawarich.


[Dawarich](https://dawarich.app/) is a self-hosted Google Timeline alternative ([see](https://support.google.com/maps/answer/14169818?hl=en&co=GENIE.Platform%3DAndroid) why you would want to consider it).

This integration does two things, of which one is optional.
1. It provides statistics for your account, this includes total distance in kilometers, number of cities visited etc, and your current Dawarich version.
2. (optional) You can set a device tracker (mobile phone for example) to send it's data through home assistant to Dawarich. That way you won't need another app, and can simply use the, probably already existing, location in HA.

## Install
There are two ways to install this. The easiest is with [HACS](https://hacs.xyz/).

### Install with HACS

Altough the below instructions might look complicated, they are rather simple.
1. Make sure you have HACS installed using [these instructions](https://hacs.xyz/docs/use/).
2. Click the button below to add the custom repository to HACS directly:\
   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=AlbinLind&repository=dawarich-home-assistant&category=integration)
3. Press the download button in the bottom right corner.
4. Restart Home Assistant.
5. Click the button below to configure the Dawarich integration:\
   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=dawarich)

### Manual Installation
Take the items under `custom_components/dawarich` and place them in the folder `homeassistant/custom_components/dawarich`.
