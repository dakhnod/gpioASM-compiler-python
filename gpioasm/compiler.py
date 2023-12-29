import struct
import sys
import math
import itertools

class Compiler:
    class CommandParameters:
        def __init__(self, command_byte, *argument_parers, command_parser=None) -> None:
            self.command_byte = command_byte
            self.argument_parsers = argument_parers
            self.command_parser = command_parser

    class CommandData:
        def __init__(self, command, data, offset, label=None):
            self.command = command
            self.data = data
            self.offset = offset
            self.label = label

    def __init__(self) -> None:
        self._commands = {
            'write_digital': self.CommandParameters(0b00000000, self._encode_pin_bits, command_parser=self._pin_bits_count_encoder_index(1)),
            'write_analog_channel_0': self.CommandParameters(0b00010000, self._encode_uint_16),
            'write_analog_channel_1': self.CommandParameters(0b00010001, self._encode_uint_16),
            'write_analog_channel_2': self.CommandParameters(0b00010010, self._encode_uint_16),
            'write_analog_channel_3': self.CommandParameters(0b00010011, self._encode_uint_16),
            'write_analog_channel_4': self.CommandParameters(0b00010100, self._encode_uint_16),
            'write_analog_channel_5': self.CommandParameters(0b00010101, self._encode_uint_16),
            'write_analog_channel_6': self.CommandParameters(0b00010110, self._encode_uint_16),
            'write_analog_channel_7': self.CommandParameters(0b00010111, self._encode_uint_16),
            'write_analog_channel_8': self.CommandParameters(0b00011000, self._encode_uint_16),
            'write_analog_channel_9': self.CommandParameters(0b00011001, self._encode_uint_16),
            'write_analog_channel_10': self.CommandParameters(0b00011010, self._encode_uint_16),
            'write_analog_channel_11': self.CommandParameters(0b00011011, self._encode_uint_16),
            'sleep_ms': self.CommandParameters(0b00100000, self._encode_varint),
            'sleep_match_all': self.CommandParameters(0b00110000, self._encode_pin_bits, command_parser=self._pin_bits_count_encoder_index(1)),
            'sleep_match_any': self.CommandParameters(0b01000000, self._encode_pin_bits, command_parser=self._pin_bits_count_encoder_index(1)),
            'sleep_match_all_timeout': self.CommandParameters(0b01010000, self._encode_pin_bits, self._encode_varint, command_parser=self._pin_bits_count_encoder_index(2)),
            'sleep_match_any_timeout': self.CommandParameters(0b01100000, self._encode_pin_bits, self._encode_varint, command_parser=self._pin_bits_count_encoder_index(2)),
            'jump': self.CommandParameters(0b01110000, self._encode_jump_label),
            'jump_match_all': self.CommandParameters(0b10010000, self._encode_jump_label, self._encode_pin_bits, command_parser=self._pin_bits_count_encoder_index(2)),
            'jump_match_any': self.CommandParameters(0b10100000, self._encode_jump_label, self._encode_pin_bits, command_parser=self._pin_bits_count_encoder_index(2)),
            'jump_count': self.CommandParameters(0b10110000, self._encode_jump_label, self._encode_varint),
            'exit': self.CommandParameters(0b11000000)
        }
        self.labels = None

    def _encode_jump_label(self, arg):
        return [arg]

    def _pin_bits_count_encoder_index(self, index):
        def encode_pin_bits_count(args):
            return math.ceil(len(args[index]) / 4)
        return encode_pin_bits_count

    def _encode_pin_bits(self, arg):
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
    
    def _encode_varint(self, arg):
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
    
    def _encode_uint_16(self, arg):
        return struct.pack('<H', int(arg))

    def _command_compile(self, parts):
        command = parts[0]

        if command == 'label':
            # ignore for now
            self.labels[parts[1]] = self.offset
            return []

        command_data = self._commands[command]

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

    def _line_compile(self, line: str):
        line = line.strip()
        if not line:
            return None
        
        parts = line.split(' ')
        parts = filter(bool, parts)
        parts = map(str.lower, parts)
        parts = list(parts)

        return self.CommandData(
            parts[0],
            self._command_compile(parts),
            None
        )
    
    def str_compile(self, content: str):
        self.labels = {}

        assembled = [128, 0] # code for version check
        self.offset = len(assembled)

        commands = []

        for line in content.splitlines():
            command_data = self._line_compile(line)
            if command_data is None:
                continue
            command_data.offset = self.offset
            self.offset += len(command_data.data)
            commands.append(command_data)

        for command in commands:
            if command.command.startswith('jump'):
                try:
                    command.data[1] = self.labels[command.data[1]]
                except KeyError:
                    raise KeyError(f'label {command.data[1]} undeclared')
            assembled.extend(command.data)

        if len(assembled) > 127:
            raise RuntimeError('python compiler can only compile files up to 127 bytes at the moment.')
        return assembled
    
    def file_compile(self, filename: str):
        with open(filename, 'r') as file:
            return self.str_compile(file.read())

if __name__ == '__main__':
    compiler = Compiler()
    result = compiler.file_compile(sys.argv[1])
    print(result)
