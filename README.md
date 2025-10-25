# Dawarich Home Assistant Integration

<!--toc:start-->
- [Dawarich Home Assistant Integration](#dawarich-home-assistant-integration)
  - [Install](#install)
    - [Install with HACS](#install-with-hacs)
    - [Manual Installation](#manual-installation)
  - [Configuration](#configuration)
<!--toc:end-->
---
> [!NOTE]
> This is an experimental integration for Dawarich, expect possibly breaking changes. This is a community integration, not affiliated with Dawarich.


[Dawarich](https://dawarich.app/) is a self-hosted Google Timeline alternative ([see](https://support.google.com/maps/answer/14169818?hl=en&co=GENIE.Platform%3DAndroid) why you would want to consider it).

This integration does two things, one of which is optional.
1. It provides statistics for your account. This includes total distance, number of cities visited, current Dawarich version, and more.
2. (optional) You can set a device tracker (such as a mobile phone) to send its data through Home Assistant to Dawarich. This way, you don't need another app and can instead use any existing location entities in Home Assistant.

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

## Configuration
Below are the configuration options for the Dawarich Home Assistant integration. After configuration, input your Dawarich API key when prompted, which is available on the Dawarich account page.

- **Host:** hostname, IP address, or URL that resolves to the running Dawarich instance
- **Port:** port number for host
- **Name:** integration entry category to contain devices
- **Device Tracker:** device tracker to send data to Dawarich
- **Use SSL:** check to use HTTPS (i.e. prepends url with `https`)
- **Verify SSL:** make sure secure connection is made through SSL

# Known Issues
Below are some known issues that are being looked at, but with workarounds for the moment.
