"""Control-partition wire format for the experimental single installer.

These helpers only operate on explicitly supplied file objects; they do not
open or write physical devices. The Windows host implementation is pending.
"""
import re

CONTROL_START = 1024 * 1024
CONTROL_SIZE = 128 * 1024 * 1024
HEADER_SIZE = 4096
BOOT_SIZE = 96 * 1024 * 1024
NONCE = re.compile(r'^[0-9a-f]{32}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')


def request(nonce, digest):
    if not NONCE.fullmatch(nonce) or not DIGEST.fullmatch(digest):
        raise ValueError('invalid nonce or boot digest')
    data = f'TB710FU-REQUEST:{nonce}:{digest}:{BOOT_SIZE}\n'.encode('ascii')
    return data.ljust(HEADER_SIZE, b'\0')


def acknowledgement(nonce):
    if not NONCE.fullmatch(nonce):
        raise ValueError('invalid nonce')
    return f'TB710FU-OK:{nonce}\n'.encode('ascii').ljust(512, b'\0')


def is_acknowledgement(block, nonce):
    return block == acknowledgement(nonce)
