import struct
import sys
import math
import itertools

class CommandParameters:
    def __init__(self, command_byte, *argument_parsers, command_parser=None) -> None:
        self.command_byte = command_byte
        self.argument_parsers = argument_parsers
        self.command_parser = command_parser

class CommandData:
    def __init__(self, command, data, offset, label=None):
        self.command = command
        self.data = data
        self.label = label


def _encode_pin_bits(arg):
    payload = [0xFF] * math.ceil(len(arg) / 4)
    for i in range(len(arg)):
        bit_index = (i * 2) % 8
        byte_index = len(payload) - math.floor(i / 4) - 1
        state = arg[i]
        if state == '0':
            payload[byte_index] &= ~(0b11 << bit_index)
        elif state == '1':
            payload[byte_index] &= ~(0b10 << bit_index)
        elif state == 'i':
            payload[byte_index] &= ~(0b01 << bit_index)
    return payload

def _encode_uint_16(arg):
    return struct.pack('<H', int(arg))

def _encode_varint(arg):
    varint = int(arg)
    if varint < 0:
        raise RuntimeError('can only encode positive integers to varint')
    if varint == 0:
        return [0x00]
    payload = []
    while varint != 0:
        payload.append((varint & 0b1111111) | 0b10000000) # append only least significant 7 bits
        varint >>= 7
    payload[len(payload) - 1] &= 0b01111111 # unset MSB, since it indicates that a byte is following
    return payload

def _pin_bits_count_encoder_index(index):
    def encode_pin_bits_count(args):
        return math.ceil(len(args[index]) / 4)
    return encode_pin_bits_count

def _encode_jump_label(arg):
    return [arg]

_commands = {
    'write_digital': CommandParameters(0b00000000, _encode_pin_bits, command_parser=_pin_bits_count_encoder_index(1)),
    'write_analog_channel_0': CommandParameters(0b00010000, _encode_uint_16),
    'write_analog_channel_1': CommandParameters(0b00010001, _encode_uint_16),
    'write_analog_channel_2': CommandParameters(0b00010010, _encode_uint_16),
    'write_analog_channel_3': CommandParameters(0b00010011, _encode_uint_16),
    'write_analog_channel_4': CommandParameters(0b00010100, _encode_uint_16),
    'write_analog_channel_5': CommandParameters(0b00010101, _encode_uint_16),
    'write_analog_channel_6': CommandParameters(0b00010110, _encode_uint_16),
    'write_analog_channel_7': CommandParameters(0b00010111, _encode_uint_16),
    'write_analog_channel_8': CommandParameters(0b00011000, _encode_uint_16),
    'write_analog_channel_9': CommandParameters(0b00011001, _encode_uint_16),
    'write_analog_channel_10': CommandParameters(0b00011010, _encode_uint_16),
    'write_analog_channel_11': CommandParameters(0b00011011, _encode_uint_16),
    'sleep_ms': CommandParameters(0b00100000, _encode_varint),
    'sleep_match_all': CommandParameters(0b00110000, _encode_pin_bits, command_parser=_pin_bits_count_encoder_index(1)),
    'sleep_match_any': CommandParameters(0b01000000, _encode_pin_bits, command_parser=_pin_bits_count_encoder_index(1)),
    'sleep_match_all_timeout': CommandParameters(0b01010000, _encode_pin_bits, _encode_varint, command_parser=_pin_bits_count_encoder_index(2)),
    'sleep_match_any_timeout': CommandParameters(0b01100000, _encode_pin_bits, _encode_varint, command_parser=_pin_bits_count_encoder_index(2)),
    'jump': CommandParameters(0b01110000, _encode_jump_label),
    'jump_match_all': CommandParameters(0b10010000, _encode_jump_label, _encode_pin_bits, command_parser=_pin_bits_count_encoder_index(2)),
    'jump_match_any': CommandParameters(0b10100000, _encode_jump_label, _encode_pin_bits, command_parser=_pin_bits_count_encoder_index(2)),
    'jump_count': CommandParameters(0b10110000, _encode_jump_label, _encode_varint),
    'exit': CommandParameters(0b11000000)
}

def _command_compile(parts):
    command = parts[0]

    command_data = _commands[command]

    if (len(parts) - 1) != len(command_data.argument_parsers):
        raise RuntimeWarning(f'command {command} requires {len(command_data) - 1} arguments')
    
    arguments = parts[1:]
    argument_parsers = command_data.argument_parsers
    argument_bytes = []

    for i in range(len(arguments)):
        argument_bytes.extend(argument_parsers[i](arguments[i]))

    command_byte = command_data.command_byte

    if command_byte is None:
        return []

    if command_data.command_parser is not None:
        command_byte |= command_data.command_parser(parts)

    return [command_byte] + argument_bytes

def _line_split(line):
    line = line.strip()
    if not line:
        return None
    
    parts = line.split(' ')
    parts = filter(bool, parts)
    parts = map(str.lower, parts)
    return list(parts)

def _line_compile(parts):
    return CommandData(
        parts[0],
        _command_compile(parts),
        None
    )

def str_compile(content: str):
    assembled = [128, 0] # code for version check

    offset = len(assembled)
    labels = {}

    commands = []

    for line in content.splitlines():
        parts = _line_split(line)

        if not parts:
            continue

        if parts[0] == 'label':
            if len(parts) != 2:
                raise RuntimeError(f'could not compile line {line}')
            labels[parts[1]] = offset
            continue

        command_data = _line_compile(parts)

        if command_data is None:
            continue

        command_data.offset = offset
        offset += len(command_data.data)
        commands.append(command_data)

    for command in commands:
        if command.command.startswith('jump'):
            try:
                command.data[1] = labels[command.data[1]]
            except KeyError:
                raise KeyError(f'label {command.data[1]} undeclared')
        assembled.extend(command.data)

    if len(assembled) > 127:
        raise RuntimeError('python compiler can only compile files up to 127 bytes at the moment.')
    return assembled

def file_compile(filename: str):
    with open(filename, 'r') as file:
        return str_compile(file.read())

if __name__ == '__main__':
    result = file_compile(sys.argv[1])
    print(result)
