"""Generate small P2 mode palettes without changing existing executable code."""
# SPDX-License-Identifier: MPL-2.0
import re

# Explicit ownership avoids accidentally exposing a new API in an unrelated mode.
MODE_FUNCTIONS = {
    'P2 Simple IO': 'p2DigitalWrite p2DigitalInput p2DigitalRead setUserLED',
    'P2 Frequency': 'p2FrequencyHz p2Frequency p2TimedSquare',
    'P2 NCO Duty': 'p2Duty p2NCODuty',
    'P2 PWM Sawtooth': 'p2PWMPercent p2SawPWM p2PWM',
    'P2 PWM Triangle': 'p2TrianglePWM',
    'P2 PWM Feedback': 'p2FeedbackPWM p2PWMSMPS',
    'P2 Servo': 'p2ServoPulseUS p2ServoAngle',
    'P2 Pulse': 'p2Pulse',
    'P2 Transition': 'p2Transition',
    'P2 Quadrature': 'p2Quadrature',
    'P2 Gated Count Up': 'p2RegisterUp',
    'P2 Count Up Down': 'p2RegisterUpDown',
    'P2 Count Rises': 'p2CountRises p2CountWindowMS',
    'P2 Count Highs': 'p2CountHighs',
    'P2 Difference Counter': 'p2DifferenceCounter',
    'P2 State Timing': 'p2StateTicks',
    'P2 High Timing': 'p2HighTicks',
    'P2 Event Timing': 'p2EventTicks p2EventCode p2MeasureEvents p2Timeout',
    'P2 Period Timing': 'p2PeriodTicks p2PeriodHighs p2MeasurePeriods',
    'P2 Window Timing': 'p2WindowTicks p2WindowHighs p2WindowPeriods p2MeasureWindow',
    'P2 Measurements': 'p2MeasurePulseTicks p2MeasureHighUS p2MeasurePeriodUS p2MeasureFrequency p2MeasureDutyPermille p2MeasureDutyPercent',
    'P2 UART': 'p2UART p2UARTWrite p2UARTRead p2AsyncTransmit p2AsyncReceive p2AsyncTransmitWords p2AsyncReceiveWords p2SerialBusy',
    'P2 Sync Serial': 'p2SyncTransmit p2SyncReceive p2SyncTransmitWords p2SyncReceiveWords',
    'P2 Serial Data': 'p2SerialSendHex p2SerialReadHex',
    'P2 ADC': 'p2ADCSampleInput p2ADCSample p2ADCSetup p2ScaleSample',
    'P2 External ADC': 'p2ADCExternalInput p2ADCExternal',
    'P2 ADC Snapshot': 'p2ADCCapture',
    'P2 ADC Scope': 'p2ScopeInput p2ADCScope',
    'P2 DAC': 'p2DAC8',
    'P2 DAC Noise': 'p2DACNoise',
    'P2 DAC Dither': 'p2DAC16',
    'P2 DAC Random Dither': 'p2DACRandomDither',
    'P2 DAC PWM Dither': 'p2DACPWMDither',
    'P2 Level Input': 'p2LevelInput',
    'P2 Logic Input': 'p2LogicInput',
    'P2 Input Filter': 'p2FilterConfigure p2FilterInfo p2FilteredInput p2DebounceInput p2FilteredRises p2FilterInput p2FilteredSmartPin',
    'P2 SINC Stream': 'p2StartSINC p2StartExternalSINC p2StartSINCWithCircuit p2StreamRead',
    'P2 Scope Capture': 'p2StartScopeBurst p2StartTriggeredScope p2ScopeCapture',
    'P2 Bit Capture': 'p2StartBitCapture p2StartExternalBitStream',
    'P2 Internal Record': 'p2SamplingPower p2StartInternalStream p2RecordInternalBits p2RecordRecentBits p2DMARecord p2DMACapture',
    'P2 Capture Control': 'p2BitDensity p2CaptureStop p2CaptureState p2CaptureInfo p2CaptureRead p2CaptureRunning p2CaptureComplete p2CaptureHasData p2CaptureAvailable p2CaptureSampleRate p2CaptureStart',
    'P2 Repository': 'p2Repository',
    'P2 Advanced': 'p2ConfigureSmartPin p2StartSmartPinRaw p2SmartPin p2SmartPinRaw p2PadNamed p2PadRaw p2Configure p2ConfigureInputs p2LocalPinDIR p2PinWriteX p2PinWriteY p2PinModeHex p2PinPeekHex p2PinAck',
    'P2 Board': 'p2Board p2FlashID p2ClockHz p2RuntimeRevision p2PinCount',
    'P2 Cogs': 'p2Cog p2CogStart p2CogStop p2CogRunning p2CogError p2CogStackOK p2CogStackUsed',
    'P2 Shared Values': 'p2ListAtomicAdd p2SharedRead p2SharedAdd p2SharedWrite',
    'P2 Core': 'p2PinUsable p2PinRelease p2PinReady p2PinReadHex p2PinSample p2PinRead p2WaitPinReady p2ReadReady p2EdgeCode p2TicksToUS',
}
GROUPS = [('P2 Core', 'Control')] + [(name, 'Comm' if name in {'P2 UART', 'P2 Sync Serial', 'P2 Serial Data'} else 'Pins')
                                        for name in MODE_FUNCTIONS if name != 'P2 Core']
OWNERS = {name: group for group, names in MODE_FUNCTIONS.items() for name in names.split()}


def group_for(selector):
    name = selector.removeprefix('[p2:').removesuffix(']')
    if name not in OWNERS:
        raise ValueError('Assign new P2 API to a mode library: ' + name)
    return OWNERS[name]


def library_dependencies(files):
    """Read the generated manifest for packaging and saved-project organization."""
    return {name: re.findall(r"^depends '([^']+)'", files[f'Libraries/P2/{name}.ubl'].decode(), re.M)
            for name, _ in GROUPS}


def split_library(raw):
    """Retain declarations verbatim; compute complete function dependencies."""
    text = raw.decode('utf-8')
    starts = list(re.finditer(r'^(module|author|version|description|choices|spec|advanced|space|to)\b', text, re.M))
    commands = [text[m.start():starts[i+1].start() if i+1 < len(starts) else len(text)].strip() for i,m in enumerate(starts)]
    specs = {name: [] for name, _ in GROUPS}
    functions = {name: [] for name, _ in GROUPS}
    metadata, choices, owners = [], [], {}
    advanced = False
    for command in commands:
        kind = command.split(maxsplit=1)[0]
        if kind in {'author', 'description'}:
            metadata.append(command)
        elif kind == 'choices':
            choices.append(command)
        elif kind == 'advanced':
            advanced = True
        elif kind == 'spec':
            match = re.match(r"spec\s+'[^']*'\s+'([^']+)'", command)
            if not match:
                raise ValueError('Review changed P2 block declaration')
            selector = match[1]
            group = group_for(selector)
            owners[selector] = group
            # Generic register editors are always opt-in advanced blocks.
            specs[group].append((advanced or group == 'P2 Advanced', command))
        elif kind == 'to':
            name = re.match(r'to\s+(\w+)', command)[1]
            group = group_for(name)
            owners[name] = group
            functions[group].append(command)
    if len(owners) < 100 or sum(len(v) for v in functions.values()) != 82:
        raise ValueError('Review changed P2 public API before grouping')
    deps = {name: set() if name == 'P2 Core' else {'P2 Core'} for name, _ in GROUPS}
    for name, bodies in functions.items():
        for body in bodies:
            for referenced in re.findall(r'\b(?:p2\w+|setUserLED)\b', body):
                if referenced in owners and owners[referenced] != name:
                    deps[name].add(owners[referenced])
    # Shared mode-specific read/stop controls should arrive with their producer.
    for name in ['P2 UART', 'P2 Sync Serial']:
        deps[name].add('P2 Serial Data')
    for name in ['P2 SINC Stream', 'P2 Scope Capture', 'P2 Bit Capture', 'P2 Internal Record']:
        deps[name].add('P2 Capture Control')
    result = {}
    for name, category in GROUPS:
        lines = [f"module '{name}' {category}", *metadata, 'version 0 12']
        if name == 'P2 Core':
            lines += choices
        lines += [f"depends '{dep}'" for dep, _ in GROUPS if dep in deps[name]]
        is_advanced = False
        for hidden, command in specs[name]:
            if hidden and not is_advanced:
                lines.append('advanced')
                is_advanced = True
            lines.append(command)
        lines += ['', *functions[name]]
        result[f'Libraries/P2/{name}.ubl'] = ('\n\n'.join(lines) + '\n').encode()
    return result, owners
