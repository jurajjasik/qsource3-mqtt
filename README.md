
# QSource3-MQTT

MQTT client for the JanasCard QSource3 RF generator, designed for controlling a quadrupole mass filter.

## Overview

This MQTT client facilitates communication with the JanasCard QSource3 RF generator using MQTT (Message Queuing Telemetry Transport) protocol. It allows users to control the RF generator, monitor its status, and respond to commands remotely. The client leverages the [janascard-qsource3 library](https://github.com/jurajjasik/janascard-qsource3) for direct interaction with the RF generator.

## Dependencies

- **janascard-qsource3**: A Python library to interface with the JanasCard QSource3 RF generator.
  - Repository: [jurajjasik/janascard-qsource3](https://github.com/jurajjasik/janascard-qsource3)
- **paho-mqtt**: A Python library for implementing MQTT clients.
- **other dependencies**: List any additional libraries or tools your client depends on.

## Configuration

The MQTT client requires a configuration file where you can specify various settings, including the base topic and device name.

### Configuration Options

- **topic_base**: The base topic used for all MQTT messages. This should be defined in the configuration file.
- **device_name**: The name of the QSource3 device. Default is `QSource3`, but this can be customized, especially useful when managing multiple devices.

> Example configuration:
> ```yaml
> topic_base: "qsource3"
> device_name: "QSource3"
> mqtt_broker: "mqtt.example.com"
> mqtt_port: 1883
> ```

## MQTT Message Structure

The client communicates using MQTT messages structured as `<topic_base>/<action>/<device_name>/<command>`.

### Status Messages

These messages are sent by the client to provide information about the connection status of the QSource3 device.

#### `<topic_base>/connected/<device_name>` 

- **Description**: This topic identifies the connected QSource3 device. Subscribing to this topic allows you to check if the device is connected.
- **Message**: A retained message (value = 1) is published on this topic when the device is connected.

### Error Messages

These messages are sent by the client when there are issues such as disconnection.

#### `<topic_base>/error/disconnected/<device_name>`

- **Description**: This topic is used to notify when the QSource3 device is disconnected.

### Command Messages

These are the commands subscribed by the client to control the internal state of the QSource3 device.

- **Structure**: `<topic_base>/cmnd/<device_name>/<command>`
- **Payload**: The payload typically includes a `"value"` field that sets the new value or retrieves the current value.
- **Response**: A corresponding response message or an error message is published based on the outcome of the command.

#### `<topic_base>/cmnd/<device_name>/mz`

- **Description**: Sets the RF amplitude and DC difference according to the provided *m/z* value and internal state parameters (`is_dc_on`, `is_rod_polarity_positive`, `calib_pnts_dc`, `calib_pnts_rf`).
- **Payload**: 
  - `"value": <float mz>` - The *m/z* ratio to set.
- **Response Message**: 
  - `<topic_base>/response/<device_name>/mz`
- **Error Message**: 
  - `<topic_base>/error/disconnected/<device_name>`

> Example Payload:
> ```json
> {
>   "value": 50.5
> }
> ```

#### `<topic_base>/cmnd/<device_name>/is_dc_on`

- **Description**: Sets the flag to apply or remove the DC difference on the rods, which toggles between mass filter mode and ion guide mode. The DC offset and RF amplitude are preserved when this flag is toggled.
- **Payload**: 
  - `"value": <bool>` - Set to `True` to apply the DC difference (mass filter mode) or `False` to remove it (ion guide mode).
- **Response Message**: 
  - `<topic_base>/response/<device_name>/is_dc_on`
- **Error Message**: 
  - `<topic_base>/error/disconnected/<device_name>`

> Example Payload:
> ```json
> {
>   "value": true
> }
> ```

#### `<topic_base>/cmnd/<device_name>/is_rod_polarity_positive`

- **Description**: Sets the polarity of the DC difference applied to the rods. The DC offset, RF amplitude, and the absolute value of the DC difference are preserved when this polarity is toggled.
- **Payload**: 
  - `"value": <bool>` - Set to `True` to apply a positive polarity to the rods or `False` to apply a negative polarity.
- **Response Message**: 
  - `<topic_base>/response/<device_name>/is_rod_polarity_positive`
- **Error Message**: 
  - `<topic_base>/error/disconnected/<device_name>`

> Example Payload:
> ```json
> {
>   "value": true
> }
> ```

### Response Messages

These messages are sent by the client in response to command messages.

#### `<topic_base>/response/<device_name>/mz`

- **Description**: Returns the last value of the *m/z* ratio.
- **Payload**: 
  - `"value": <float mz>` - The current *m/z* value.
  - `"sender_payload": [<corresponding command's message payload>]` - The original command's payload for tracking.

> Example Payload:
> ```json
> {
>   "value": 50.5,
>   "sender_payload": {"value": 50.5}
> }
> ```

#### `<topic_base>/response/<device_name>/is_dc_on`

- **Description**: Returns the current status of the DC difference flag (`is_dc_on`), indicating whether the DC difference is applied to the rods.
- **Payload**: 
  - `"value": <bool>` - `True` if the DC difference is applied, `False` if it is not.
  - `"sender_payload": [<corresponding command's message payload>]` - The original command's payload for tracking.

> Example Payload:
> ```json
> {
>   "value": true,
>   "sender_payload": {"value": true}
> }
> ```

#### `<topic_base>/response/<device_name>/is_rod_polarity_positive`

- **Description**: Returns the current polarity of the DC difference applied to the rods (`is_rod_polarity_positive`).
- **Payload**: 
  - `"value": <bool>` - `True` if the polarity is positive, `False` if it is negative.
  - `"sender_payload": [<corresponding command's message payload>]` - The original command's payload for tracking.

> Example Payload:
> ```json
> {
>   "value": true,
>   "sender_payload": {"value": true}
> }
> ```

## Usage
TODO ...
