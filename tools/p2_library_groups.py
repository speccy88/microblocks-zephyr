"""Present the compatible P2 API in focused libraries without changing code."""
# SPDX-License-Identifier: MPL-2.0
import re

GROUPS = [('P2 Core', 'Control'), ('P2 Signals', 'Pins'), ('P2 Serial', 'Comm'),
          ('P2 Analog', 'Pins'), ('P2 Capture', 'Input')]


def group_for(selector):
    name = selector.removeprefix('[p2:').removesuffix(']')
    if any(word in name for word in ['UART', 'Serial', 'Sync', 'Async']):
        return 'P2 Serial'
    if name in {'p2ADCCapture', 'p2ADCSetup', 'p2ADCScope', 'p2ScopeInput'}:
        return 'P2 Analog'
    if any(word in name for word in ['Capture', 'Scope', 'SINC', 'Stream', 'Record', 'SamplingPower', 'DMA', 'BitDensity']):
        return 'P2 Capture'
    if any(word in name for word in ['ADC', 'DAC', 'LevelInput', 'ScaleSample']):
        return 'P2 Analog'
    if any(word in name for word in ['Frequency', 'PWM', 'Duty', 'Pulse', 'Transition', 'Servo', 'TimedSquare',
                                     'Quadrature', 'Register', 'Count', 'Ticks', 'Event', 'Period', 'Window',
                                     'Measure', 'Timeout', 'EdgeCode', 'Difference', 'Filter', 'Debounce', 'LogicInput']):
        # Pin count is an inventory reporter, rather than a counter.
        if name != 'p2PinCount':
            return 'P2 Signals'
    return 'P2 Core'


def split_library(raw):
    """The canonical file is also retained for old projects and hardware tests.

    Top-level GP declarations begin in column zero; function bodies are retained
    verbatim, including all primitive names and argument validation.
    """
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
            specs[group].append((advanced, command))
        elif kind == 'to':
            name = re.match(r'to\s+(\w+)', command)[1]
            group = group_for(name)
            owners[name] = group
            functions[group].append(command)
    if len(owners) < 100 or sum(len(v) for v in functions.values()) != 79:
        raise ValueError('Review changed P2 public API before grouping')
    result = {}
    for name, category in GROUPS:
        lines = [f"module '{name}' {category}", *metadata, 'version 0 11']
        if name == 'P2 Core':
            lines += choices
        else:
            lines += ["depends 'P2 Core'"]
        is_advanced = False
        for hidden, command in specs[name]:
            if hidden and not is_advanced:
                lines.append('advanced')
                is_advanced = True
            lines.append(command)
        lines += ['', *functions[name]]
        result[f'Libraries/P2/{name}.ubl'] = ('\n\n'.join(lines) + '\n').encode()
    return result, owners
