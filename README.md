
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

#### `<topic_base>/state/<device_name>`

- **Description**: Publishes the current state of the quadrupole, including various operational parameters and statuses. This message is generated every `<milliseconds>` milliseconds, where the interval is predefined in the configuration YAML file.
- **Payload**: 
  - `"range": <int>` - The current mass measurement range of the quadrupole. 
    - `0`: Highest range, typically around 1050 kHz.
    - `1`: Mid-range, typically around 480 kHz.
    - `2`: Lowest range, typically around 240 kHz.
  - `"frequency": <float>` - The frequency of the generator at the actual range in Hz.
  - `"rf_amp": <float>` - The RF amplitude with zero to peak value in Volts.
  - `"dc1": <float>` - The DC voltage \( U_1 \) in Volts.
  - `"dc2": <float>` - The DC voltage \( U_2 \) in Volts.
  - `"current": <float>` - The RF generator current in mA.
  - `"mz": <float>` - The last value of the *m/z* ratio.
  - `"is_dc_on": <bool>` - The current status of the DC difference flag.
  - `"is_rod_polarity_positive": <bool>` - The current polarity of the DC difference applied to the rods.
  - `"max_mz": <float>` - The maximum *m/z* value of the quadrupole.

> Example Payload:
> ```json
> {
>   "range": 1,
>   "frequency": 480000.0,
>   "rf_amp": 500.0,
>   "dc1": 10.0,
>   "dc2": -10.0,
>   "current": 150.0,
>   "mz": 50.5,
>   "is_dc_on": true,
>   "is_rod_polarity_positive": true,
>   "max_mz": 1000.0
> }
> ```

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

#### `<topic_base>/cmnd/<device_name>/max_mz`

- **Description**: Retrieves the maximum *m/z* value of the quadrupole. The values of \(\delta(m/z)\) and \(\rho(m/z)\) are not accounted for in this calculation.
- **Payload**: 
  - No payload is required for this command. It acts as a getter to retrieve the maximum *m/z* value.
- **Response Message**: 
  - `<topic_base>/response/<device_name>/max_mz`
- **Error Message**: 
  - `<topic_base>/error/disconnected/<device_name>`

> Example Payload:
> ```json
> {}
> ```

#### `<topic_base>/cmnd/<device_name>/calib_pnts_dc`

- **Description**: Gets or sets the calibration points for the DC difference (resolution) used to construct \(\rho(m/z)\). The points are represented as a 2D array, where each entry is a pair of *m/z* and \(\rho\) values. When setting these points, a new interpolation function (`interp_fnc_calib_pnts_dc`) is created based on the provided calibration points.
- **Payload**: 
  - To **set** calibration points: 
    - `"value": [[<float (m/z)_0>, <float \(\rho\)_0>], [<float (m/z)_1>, <float \(\rho\)_1>], ...]`
  - To **get** the current calibration points, no specific payload is required.
- **Response Message**: 
  - `<topic_base>/response/<device_name>/calib_pnts_dc`
- **Error Message**: 
  - `<topic_base>/error/disconnected/<device_name>`

> Example Payload (for setting calibration points):
> ```json
> {
>   "value": [[50.0, -0.001], [100.0, -0.002], [150.0, -0.003]]
> }
> ```

#### `<topic_base>/cmnd/<device_name>/calib_pnts_rf`

- **Description**: Gets or sets the calibration points for the RF amplitude (*m/z* calibration) used to construct \(\delta(m/z)\). The points are represented as a 2D array, where each entry is a pair of *m/z* and \(\delta\) values. When setting these points, a new interpolation function (`interp_fnc_calib_pnts_rf`) is created based on the provided calibration points.
- **Payload**: 
  - To **set** calibration points: 
    - `"value": [[<float (m/z)_0>, <float \(\delta\)_0>], [<float (m/z)_1>, <float \(\delta\)_1>], ...]`
  - To **get** the current calibration points, no specific payload is required.
- **Response Message**: 
  - `<topic_base>/response/<device_name>/calib_pnts_rf`
- **Error Message**: 
  - `<topic_base>/error/disconnected/<device_name>`

> Example Payload (for setting calibration points):
> ```json
> {
>   "value": [[50.0, -0.001], [100.0, -0.0015], [150.0, -0.0005]]
> }
> ```

#### `<topic_base>/cmnd/<device_name>/dc_offst`

- **Description**: Gets or sets the DC offset \( U_{\text{ofst}} \) (in Volts) for the system. The DC offset is calculated as \( U_{\text{ofst}} = \frac{U_1 + U_2}{2} \), where \( U_1 \) and \( U_2 \) are the voltages applied to the rods. When setting the DC offset, \( U_1 \) and \( U_2 \) are adjusted based on the provided offset and the current DC difference \( U_{\text{diff}} \).
- **Payload**: 
  - To **set** the DC offset:
    - `"value": <float>` - The desired DC offset value in volts.
  - To **get** the current DC offset, no specific payload is required.
- **Response Message**: 
  - `<topic_base>/response/<device_name>/dc_offst`
- **Error Message**: 
  - `<topic_base>/error/disconnected/<device_name>`

> Example Payload (for setting the DC offset):
> ```json
> {
>   "value": -5.0
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

#### `<topic_base>/response/<device_name>/max_mz`

- **Description**: Returns the maximum *m/z* value of the quadrupole (`max_mz`).
- **Payload**: 
  - `"value": <float>` - The maximum *m/z* value.
  - `"sender_payload": [<corresponding command's message payload>]` - The original command's payload for tracking.

> Example Payload:
> ```json
> {
>   "value": 1000.0,
>   "sender_payload": {}
> }
> ```

#### `<topic_base>/response/<device_name>/calib_pnts_dc`

- **Description**: Returns the current calibration points for the DC difference (`calib_pnts_dc`) as a 2D array.
- **Payload**: 
  - `"value": [[<float (m/z)_0>, <float \(\rho\)_0>], [<float (m/z)_1>, <float \(\rho\)_1>], ...]` - The current or newly set calibration points.
  - `"sender_payload": [<corresponding command's message payload>]` - The original command's payload for tracking.

> Example Payload (for getting calibration points):
> ```json
> {
>   "value": [[50.0, -0.001], [100.0, -0.002], [150.0, -0.003]],
>   "sender_payload": {}
> }
> ```

#### `<topic_base>/response/<device_name>/calib_pnts_rf`

- **Description**: Returns the current calibration points for the RF amplitude (`calib_pnts_rf`) as a 2D array.
- **Payload**: 
  - `"value": [[<float (m/z)_0>, <float \(\delta\)_0>], [<float (m/z)_1>, <float \(\delta\)_1>], ...]` - The current or newly set calibration points.
  - `"sender_payload": [<corresponding command's message payload>]` - The original command's payload for tracking.

> Example Payload (for getting calibration points):
> ```json
> {
>   "value": [[50.0, -0.001], [100.0, -0.0015], [150.0, -0.0005]],
>   "sender_payload": {}
> }
> ```

#### `<topic_base>/response/<device_name>/dc_offst`

- **Description**: Returns the current DC offset \( U_{\text{ofst}} \) in volts.
- **Payload**: 
  - `"value": <float>` - The current or newly set DC offset value.
  - `"sender_payload": [<corresponding command's message payload>]` - The original command's payload for tracking.

> Example Payload (for getting the DC offset):
> ```json
> {
>   "value": -5.0,
>   "sender_payload": {}
> }
> ```

## Usage
TODO ...
