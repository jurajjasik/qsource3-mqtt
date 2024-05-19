# qsource3-mqtt

MQTT client for JanasCard QSource3 - an RF generator for quadrupole mass filter.

## Depends on

- https://github.com/jurajjasik/janascard-qsource3

## MQTT Messages

The topis structure is `<topic_base>/<action>/<device_name>/<command>`.

The value of `<topic_base>` is given in the configuration file (see ...).

The default value of `<device_name>` is `QSource3`. It can be changed in the configuration file (see ...). Useful when multiple QSource3 devices are used.

### Status messages:

Messages send by the client.

#### `<topic_base>/connected/<device_name>` 
Identify connected QSource3 device by simply subscribing to this topic.
A retained message (value=1) is published on this topic when the device is connected.

### Error messages:

Messages send by the client.

#### `<topic_base>/error/disconnected/<device_name>`

### Command messages:

Messages subscribed by the client to set the internal state of the device. 

The command emits either a corresponding response message containing the new value or an error message, the both with the payload containing a copy of the command's message payload in the field `"sender_payload":[<command's message payload>]` - useful to keep the track of the message with the command's sender. 

The new value to set is in the field `"value"` of the payload. 

Should no `"value"` field given in the payload, the response message contains the last value successuly set - a getter function.

#### `<topic_base>/cmnd/<device_name>/mz` 
Set RF amplitude and DC difference according to given *m/z* 
and internal state (`is_dc_on`, `is_rod_polarity_positive`, `calib_pnts_dc`, `calib_pnts_rf`).

> Payload: `["value":<float mz>]`
>
> Response message: `<topic_base>/response/<device_name>/mz`
>
> Error message: `<topic_base>/error/disconnected/<device_name>`

### Response messages:

Messages send by the client as a response to the command messages.

#### `<topic_base>/response/<device_name>/mz`
Get the last value of *m/z*

> Payload: `["value":<float mz>, "sender_payload":[<corresponding command's message payload>]]`
